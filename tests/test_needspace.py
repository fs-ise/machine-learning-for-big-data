import re
import shutil
import subprocess
from pathlib import Path

import pytest


QUARTO = shutil.which("quarto")


@pytest.mark.skipif(QUARTO is None, reason="Quarto is not installed")
def test_needspace_shortcode_is_format_aware(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "_extensions/needspace", tmp_path / "_extensions/needspace")
    (tmp_path / "index.qmd").write_text(
        "---\nformat:\n  pdf:\n    keep-tex: true\n---\n\n"
        "{{< needspace >}}\n\n## First\n\n{{< needspace 8 >}}\n\n## Second\n",
        encoding="utf-8",
    )

    subprocess.run(
        [QUARTO, "render", "index.qmd", "--to", "pdf"], cwd=tmp_path, check=True
    )
    assert (tmp_path / "index.pdf").is_file()
    latex = (tmp_path / "index.tex").read_text(encoding="utf-8")
    assert r"\usepackage{needspace}" in latex
    assert r"\Needspace{5\baselineskip}" in latex
    assert r"\Needspace{8\baselineskip}" in latex

    subprocess.run(
        [QUARTO, "render", "index.qmd", "--to", "html"], cwd=tmp_path, check=True
    )
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "First" in html and "Second" in html
    assert "Needspace" not in html
    assert not re.search(r"\{\{\s*&lt;\s*needspace", html)
