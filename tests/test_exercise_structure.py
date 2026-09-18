from pathlib import Path
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.check_exercise_structure import validate_lines


def validate(source: str):
    return validate_lines(source.splitlines(), Path("example.qmd"))


def test_missing_blank_line_before_heading():
    problems = validate("Paragraph\n## Heading\n")
    assert [problem.line for problem in problems] == [2]
    assert "heading" in problems[0].explanation


def test_missing_blank_line_after_closing_div():
    problems = validate("::: {.sol}\nAnswer\n:::\nParagraph\n")
    assert [problem.line for problem in problems] == [3]
    assert "closing fenced Div" in problems[0].explanation


def test_missing_blank_line_between_code_fence_and_heading():
    problems = validate("```python\nprint('hi')\n```\n## Next\n")
    assert [problem.line for problem in problems] == [4]


def test_correctly_formatted_document():
    assert not validate("---\ntitle: Test\n---\n# Exercise\n\n::: {.sol}\nAnswer\n:::\n\nDone.\n")


def test_nested_divs_are_tracked():
    source = ":::: {.outer}\n\n::: {.inner}\nText\n:::\n\n::::\n\n# Next\n"
    assert not validate(source)


def test_headings_in_r_and_python_chunks_are_ignored():
    source = "```{r}\nx <- 1\n# R comment\n```\n\n~~~{python}\nx = 1\n## Python comment\n~~~\n"
    assert not validate(source)


def test_yaml_and_html_comments_are_ignored():
    source = "---\ntitle: '# Not a heading'\n---\n# Heading\n\n<!--\n## Hidden\n::: {.hidden}\n-->\n"
    assert not validate(source)


def test_longer_code_fences_and_divs():
    source = "````markdown\n```\n# Hidden\n```\n````\n\n::::: {.box}\nText\n:::::\n"
    assert not validate(source)


def test_cli_reports_filename_line_and_failure_status(tmp_path):
    qmd = tmp_path / "bad.qmd"
    qmd.write_text("Text\n# Too close\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/check_exercise_structure.py", str(qmd)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert f"{qmd}:2:" in result.stdout
    assert "heading must be preceded" in result.stdout


def test_repository_exercises_pass():
    paths = sorted(Path("exercises").glob("session_*.qmd"))
    assert paths
    problems = [problem for path in paths for problem in validate_lines(path.read_text().splitlines(), path)]
    assert not problems
