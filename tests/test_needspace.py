import re
import shutil
import subprocess
from pathlib import Path

import pytest


QUARTO = shutil.which("quarto")
PDFTOTEXT = shutil.which("pdftotext")


@pytest.mark.skipif(QUARTO is None, reason="Quarto is not installed")
def test_needspace_shortcode_is_format_aware(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "_extensions/needspace", tmp_path / "_extensions/needspace")
    (tmp_path / "index.qmd").write_text(
        "---\nformat:\n  pdf:\n    keep-tex: true\n---\n\n"
        "{{< needspace >}}\n\n## First\n\n{{< needspace 12 >}}\n\n## Second\n",
        encoding="utf-8",
    )

    subprocess.run(
        [QUARTO, "render", "index.qmd", "--to", "pdf"], cwd=tmp_path, check=True
    )
    assert (tmp_path / "index.pdf").is_file()
    latex = (tmp_path / "index.tex").read_text(encoding="utf-8")
    assert r"\usepackage{needspace}" in latex
    assert r"\Needspace{5\baselineskip}" in latex
    assert r"\Needspace{12\baselineskip}" in latex

    subprocess.run(
        [QUARTO, "render", "index.qmd", "--to", "html"], cwd=tmp_path, check=True
    )
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "First" in html and "Second" in html
    assert "Needspace" not in html
    assert not re.search(r"\{\{\s*&lt;\s*needspace", html)


@pytest.mark.skipif(
    QUARTO is None or PDFTOTEXT is None,
    reason="Quarto and pdftotext are required",
)
def test_combined_notes_render_without_visible_shortcode(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    render_dir = tmp_path / "_pdf-tmp"
    shutil.copytree(root / "_extensions/needspace", render_dir / "_extensions/needspace")
    (tmp_path / "scripts").mkdir()
    shutil.copy(
        root / "scripts/html_br_to_linebreak.lua",
        tmp_path / "scripts/html_br_to_linebreak.lua",
    )
    note = tmp_path / "session_01.qmd"
    note.write_text(
        "---\ntitle: Test session\n---\n\n"
        "{{< needspace 12 >}}\n\n## Kept heading\n\nRendered body.\n",
        encoding="utf-8",
    )

    from scripts.combine_notes import combine_notes

    combined = render_dir / "teaching-notes.qmd"
    combined.write_text(combine_notes([note]), encoding="utf-8")
    result = subprocess.run(
        [QUARTO, "render", str(combined), "--to", "pdf", "--output", "notes.pdf"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [PDFTOTEXT, str(tmp_path / "notes.pdf"), str(tmp_path / "notes.txt")],
        check=True,
    )

    assert "unknown shortcode" not in (result.stdout + result.stderr).lower()
    pdf_text = (tmp_path / "notes.txt").read_text(encoding="utf-8")
    assert "Kept heading" in pdf_text
    assert "needspace" not in pdf_text.lower()
