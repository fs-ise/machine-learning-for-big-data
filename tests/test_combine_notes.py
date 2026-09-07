from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.combine_notes import DOCUMENT_TITLE, combine_notes, latex_escape


def write_note(path: Path, title: str, body: str = "Body") -> None:
    metadata = yaml.safe_dump({"title": title, "session_id": "test"}, sort_keys=False)
    path.write_text(f"---\n{metadata}---\n\n{body}\n", encoding="utf-8")


def test_orders_sessions_and_extracts_yaml_titles(tmp_path: Path) -> None:
    later = tmp_path / "session_10.qmd"
    earlier = tmp_path / "session_02.qmd"
    write_note(later, "Session Ten")
    write_note(earlier, "Session Two")

    result = combine_notes([later, earlier])

    assert result.index("# Session Two") < result.index("# Session Ten")


def test_document_configuration_and_course_specific_footer(tmp_path: Path) -> None:
    note = tmp_path / "session_01.qmd"
    write_note(note, "First session")

    result = combine_notes([note])

    assert f'title: "{DOCUMENT_TITLE}"' in result
    assert "toc: true" in result
    assert "toc-depth: 1" in result
    assert "number-sections: false" in result
    assert "papersize: a4" in result
    assert "left=1.5cm" in result
    assert "right=1.5cm" in result
    assert "top=1.5cm" in result
    assert "bottom=2.2cm" in result
    assert "includefoot" in result
    assert "footskip=0.9cm" in result
    assert "execute:\n  enabled: false" in result
    assert "execute: false" not in result
    assert r"\usepackage{scrlayer-scrpage}" in result
    assert "fancyhdr" not in result
    assert r"\clearpairofpagestyles" in result
    assert r"\ifoot[\teachingnotesfooterlabel]{\teachingnotesfooterlabel}" in result
    assert r"\ofoot[\pagemark]{\pagemark}" in result
    assert r"\pagestyle{scrheadings}" in result
    assert r"\pretocmd{\subsection}{\clearpage}" in result
    assert rf"\newcommand{{\teachingnotesfooterlabel}}{{{DOCUMENT_TITLE}}}" in result
    assert "mlbdfooterlabel" not in result.lower()

    front_matter = result.split("---", 2)[1]
    metadata = yaml.safe_load(front_matter)
    assert metadata["execute"] == {"enabled": False}


def test_escapes_title_for_latex_footer(tmp_path: Path) -> None:
    note = tmp_path / "session_01.qmd"
    title = r"Data & 100% of x_1 # {cases} ~ ^ \\"
    write_note(note, title)

    result = combine_notes([note])

    footer_command = (
        r"\renewcommand{\teachingnotesfooterlabel}"
        f"{{MLBD -- {latex_escape(title)}}}"
    )
    session_opening = (
        "```{=latex}\n"
        "\\clearpage\n"
        f"{footer_command}\n"
        "```\n\n"
        f"# {title}"
    )
    assert session_opening in result
    assert r"Data \& 100\% of x\_1 \# \{cases\}" in result


def test_starts_every_session_on_a_new_page(tmp_path: Path) -> None:
    notes = [tmp_path / f"session_0{i}.qmd" for i in (1, 2, 3)]
    for index, note in enumerate(notes, 1):
        write_note(note, f"Session {index}")

    result = combine_notes(notes)

    assert result.count("```{=latex}\n\\clearpage") == 3
    assert result.index("```{=latex}\n\\clearpage") < result.index("# Session 1")


def test_preserves_html_break_and_configures_lua_filter(tmp_path: Path) -> None:
    note = tmp_path / "session_01.qmd"
    body = "| Item | Detail |\n|---|---|\n| A | one<br>two<br/>three<br />four |"
    write_note(note, "Tables", body)

    result = combine_notes([note])

    assert "one<br>two<br/>three<br />four" in result
    assert "../scripts/html_br_to_linebreak.lua" in result


def test_source_files_remain_unchanged(tmp_path: Path) -> None:
    note = tmp_path / "session_01.qmd"
    write_note(note, "Unchanged", "Original <br> body")
    before = note.read_bytes()

    combine_notes([note])

    assert note.read_bytes() == before


@pytest.mark.parametrize(
    "contents, message",
    [("No front matter", "missing YAML"), ("---\nsession_id: one\n---\n", "title")],
)
def test_validates_front_matter(tmp_path: Path, contents: str, message: str) -> None:
    note = tmp_path / "session_01.qmd"
    note.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        combine_notes([note])


def test_make_notes_moves_standalone_render_output(tmp_path: Path) -> None:
    """The standalone render must not use Quarto's project-only --output-dir."""
    (tmp_path / "notes").mkdir()
    (tmp_path / "scripts").mkdir()
    shutil.copy(REPOSITORY_ROOT / "Makefile", tmp_path / "Makefile")
    shutil.copy(
        REPOSITORY_ROOT / "scripts/combine_notes.py",
        tmp_path / "scripts/combine_notes.py",
    )
    shutil.copy(
        REPOSITORY_ROOT / "scripts/html_br_to_linebreak.lua",
        tmp_path / "scripts/html_br_to_linebreak.lua",
    )
    write_note(tmp_path / "notes/session_01.qmd", "Session One")

    quarto = tmp_path / "fake_quarto.py"
    quarto.write_text(
        """#!/usr/bin/env python3
import sys
from pathlib import Path

args = sys.argv[1:]
assert args[:2] == ["render", "_pdf-tmp/teaching-notes.qmd"]
assert "--output-dir" not in args
assert args[args.index("--output") + 1] == "notes.pdf"
source = Path(args[1])
combined = source.read_text(encoding="utf-8")
assert "../scripts/html_br_to_linebreak.lua" in combined
Path("notes.pdf").write_bytes(b"%PDF-fake")
""",
        encoding="utf-8",
    )
    quarto.chmod(0o755)

    subprocess.run(
        [
            "make",
            "notes",
            f"PYTHON={sys.executable}",
            f"QUARTO={quarto}",
        ],
        cwd=tmp_path,
        check=True,
    )

    assert (tmp_path / "_site/notes.pdf").read_bytes() == b"%PDF-fake"
    assert not (tmp_path / "_pdf-tmp/notes.pdf").exists()
    assert not (tmp_path / "_pdf-tmp/teaching-notes.qmd").exists()
