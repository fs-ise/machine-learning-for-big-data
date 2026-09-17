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


def write_checklist(path: Path, title: str = "Teaching checklist") -> None:
    path.write_text(f"# {title}\n\n- [ ] Check everything.\n", encoding="utf-8")


def test_orders_sessions_and_extracts_yaml_titles(tmp_path: Path) -> None:
    later = tmp_path / "session_10.qmd"
    earlier = tmp_path / "session_02.qmd"
    write_note(later, "Session Ten")
    write_note(earlier, "Session Two")

    result = combine_notes([later, earlier])

    assert result.index("# Session Two") < result.index("# Session Ten")


def test_checklist_precedes_sorted_sessions_and_appears_once(tmp_path: Path) -> None:
    checklist = tmp_path / "z_checklist.qmd"
    later = tmp_path / "session_10.qmd"
    earlier = tmp_path / "session_02.qmd"
    write_checklist(checklist)
    write_note(later, "Session Ten")
    write_note(earlier, "Session Two")

    result = combine_notes([later, earlier], checklist=checklist)

    assert result.count("# Teaching checklist") == 1
    assert result.index("# Teaching checklist") < result.index("# Session Two")
    assert result.index("# Session Two") < result.index("# Session Ten")


def test_checklist_has_own_footer_and_page_break(tmp_path: Path) -> None:
    checklist = tmp_path / "checklist.qmd"
    note = tmp_path / "session_01.qmd"
    write_checklist(checklist, "Before class & support")
    write_note(note, "First session")

    result = combine_notes([note], checklist=checklist)

    assert (
        r"\renewcommand{\teachingnotesfooterlabel}"
        r"{MLBD -- Before class \& support}" in result
    )
    assert result.count("```{=latex}\n\\clearpage") == 2


def test_combines_without_optional_checklist(tmp_path: Path) -> None:
    note = tmp_path / "session_01.qmd"
    write_note(note, "Only session")

    result = combine_notes([note])

    assert "# Only session" in result
    assert "Teaching checklist" not in result


@pytest.mark.parametrize(
    "contents",
    ["", "Checklist without a heading\n", "## Level two\n", "#   \n"],
)
def test_rejects_checklist_without_nonempty_level_one_heading(
    tmp_path: Path, contents: str
) -> None:
    checklist = tmp_path / "checklist.qmd"
    note = tmp_path / "session_01.qmd"
    checklist.write_text(contents, encoding="utf-8")
    write_note(note, "Session")

    with pytest.raises(ValueError, match="non-empty level-1 heading"):
        combine_notes([note], checklist=checklist)


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
    assert "execute:\n  enabled: true" in result
    assert "execute: false" not in result
    assert r"\usepackage{scrlayer-scrpage}" in result
    assert "fancyhdr" not in result
    assert r"\clearpairofpagestyles" in result
    assert r"\ifoot[\teachingnotesfooterlabel]{\teachingnotesfooterlabel}" in result
    assert r"\ofoot[\pagemark]{\pagemark}" in result
    assert r"\pagestyle{scrheadings}" in result
    assert r"\usepackage{etoolbox}" not in result
    assert r"\pretocmd{\subsection}{\clearpage}" not in result
    assert rf"\newcommand{{\teachingnotesfooterlabel}}{{{DOCUMENT_TITLE}}}" in result
    assert "mlbdfooterlabel" not in result.lower()

    front_matter = result.split("---", 2)[1]
    metadata = yaml.safe_load(front_matter)
    assert metadata["execute"] == {"enabled": True}


def test_preserves_project_root_solution_include(tmp_path: Path) -> None:
    note = tmp_path / "session_05.qmd"
    include = "{{< include /_generated/exercises/includes/_session_05_solution.qmd >}}"
    write_note(note, "Session Five", f"## Exercise solution\n\n{include}")

    assert include in combine_notes([note])


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
    checklist = tmp_path / "checklist.qmd"
    write_note(note, "Unchanged", "Original <br> body")
    write_checklist(checklist)
    before = note.read_bytes()
    checklist_before = checklist.read_bytes()

    combine_notes([note], checklist=checklist)

    assert note.read_bytes() == before
    assert checklist.read_bytes() == checklist_before


def test_canonical_notes_and_exercises_have_no_layout_only_page_breaks() -> None:
    canonical = [
        *REPOSITORY_ROOT.glob("notes/session_*.qmd"),
        *REPOSITORY_ROOT.glob("exercises/session_*.qmd"),
    ]

    for path in canonical:
        source = path.read_text(encoding="utf-8")
        assert "{{< pagebreak" not in source, path
        assert r"\clearpage" not in source, path
        assert r"\newpage" not in source, path


def test_requested_teaching_note_headings_have_selective_needspace() -> None:
    expected = {
        "session_01.qmd": {"Output": 8},
        "session_09_b.qmd": {
            "Organizational value creation": 12,
            "NIST AI RMF and regulatory context": 12,
        },
    }

    for filename, headings in expected.items():
        source = (REPOSITORY_ROOT / "notes" / filename).read_text(encoding="utf-8")
        for heading, lines in headings.items():
            assert f"{{{{< needspace {lines} >}}}}\n\n## {heading}\n" in source


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
    shutil.copy(
        REPOSITORY_ROOT / "scripts/build_exercises.py",
        tmp_path / "scripts/build_exercises.py",
    )
    shutil.copytree(
        REPOSITORY_ROOT / "scripts/templates",
        tmp_path / "scripts/templates",
    )
    shutil.copytree(
        REPOSITORY_ROOT / "_extensions/needspace",
        tmp_path / "_extensions/needspace",
    )
    (tmp_path / "exercises").mkdir()
    write_note(tmp_path / "notes/session_01.qmd", "Session One")
    write_checklist(tmp_path / "notes/teaching_checklist.qmd")

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
assert combined.count("# Teaching checklist") == 1
assert combined.index("# Teaching checklist") < combined.index("# Session One")
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
