import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.build_exercises import ExerciseSyntaxError, PROJECT_CONFIG, VARIANTS, build, sanitize


SOURCE = """---
title: Test
---
Common
:::{.direction}
Directions
```{r}
#| eval: false
x <- c(1, 2)  # unchanged
mean(x)
```
:::
::: {.sol}
Solution
:::: {.callout-note}
nested ordinary
::::
:::
::: {.ordinary}
ordinary div
:::
"""


def test_variant_semantics_and_clean_wrappers() -> None:
    variants = {variant: sanitize(SOURCE, variant) for variant in VARIANTS}
    assert all("Common" in text for text in variants.values())
    assert "Directions" in variants["assign"]
    assert "Directions" not in variants["solution"]
    assert "Solution" not in variants["assign"]
    assert "Solution" in variants["solution"]
    assert all(class_name not in text for text in variants.values() for class_name in (".direction", ".sol"))


def test_canonical_shared_setup_survives_in_both_variants() -> None:
    """Guard representative setup that solution chunks consume after filtering."""
    root = Path(__file__).resolve().parents[1]
    cases = {
        "session_02.qmd": (
            'customer_df <- read_csv(',
            "summary(customer_df)",
        ),
        "session_04.qmd": (
            'df <- read_csv(',
            "model <- lm(",
        ),
    }

    for filename, (setup, use) in cases.items():
        source = (root / "exercises" / filename).read_text(encoding="utf-8")
        for variant in VARIANTS:
            generated = sanitize(source, variant, filename=filename)
            assert setup in generated
            if variant == "solution":
                assert use in generated
                assert generated.index(setup) < generated.index(use)


def test_chunks_and_unrelated_nested_divs_are_preserved() -> None:
    chunk = "```{r}\n#| eval: false\nx <- c(1, 2)  # unchanged\nmean(x)\n```\n"
    assert chunk in sanitize(SOURCE, "assign")
    expected = ":::: {.callout-note}\nnested ordinary\n::::\n"
    assert expected in sanitize(SOURCE, "solution")
    ordinary = "::: {.ordinary}\nordinary div\n:::\n"
    assert all(ordinary in sanitize(SOURCE, variant) for variant in VARIANTS)


@pytest.mark.parametrize("variant", VARIANTS)
def test_html_comments_are_removed_from_both_variants(variant: str) -> None:
    source = "before<!-- single -->middle<!--\nmultiple\nlines\n-->after\n"
    assert sanitize(source, variant) == "beforemiddleafter\n"


def test_multiple_comments_do_not_remove_intervening_text() -> None:
    source = "start<!-- first -->kept<!-- second -->end\n"
    assert sanitize(source, "assign") == "startkeptend\n"


@pytest.mark.parametrize("fence", ("```", "~~~~"))
def test_html_comment_syntax_inside_code_fences_is_preserved(fence: str) -> None:
    source = f"{fence}text\n<!-- literal example -->\n{fence}\n"
    assert sanitize(source, "solution") == source


def test_comment_removal_preserves_semantic_div_filtering() -> None:
    source = """<!-- hidden -->
::: {.direction}
assignment
:::
::: {.sol}
solution
:::
"""
    assert "assignment" in sanitize(source, "assign")
    assert "solution" not in sanitize(source, "assign")
    assert "assignment" not in sanitize(source, "solution")
    assert "solution" in sanitize(source, "solution")


def test_commented_survey_is_absent_from_canonical_variants() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "exercises/session_02.qmd").read_text(encoding="utf-8")
    assert "{{< survey session_02 exercise >}}" in source
    for variant in VARIANTS:
        generated = sanitize(source, variant, filename="session_02.qmd")
        assert "Session 2 survey" not in generated
        assert "{{< survey" not in generated
        assert "<!--" not in generated
        assert "-->" not in generated


@pytest.mark.parametrize(
    "source",
    ["::: {.sol}\nmissing close\n", "::: {.sol.direction}\nambiguous\n:::\n"],
)
def test_malformed_semantic_div_fails_clearly(source: str) -> None:
    with pytest.raises(ExerciseSyntaxError, match=r"<test>:\d+:"):
        sanitize(source, "solution", filename="<test>")


def test_build_is_deterministic_removes_stale_and_never_changes_source(tmp_path: Path) -> None:
    exercises = tmp_path / "exercises"
    exercises.mkdir()
    data = exercises / "data"
    data.mkdir()
    fixture = data / "market_data_log.csv"
    fixture.write_text("price\n42\n", encoding="utf-8")
    canonical = exercises / "session_01.qmd"
    canonical.write_text(SOURCE, encoding="utf-8")
    original = canonical.read_bytes()
    build(tmp_path)
    generated = tmp_path / "_generated/exercises"
    assert (generated / "_quarto.yml").read_text(encoding="utf-8") == PROJECT_CONFIG
    assert "output-dir: _rendered" in PROJECT_CONFIG
    assert (generated / "data/market_data_log.csv").read_bytes() == fixture.read_bytes()
    first = {
        path.relative_to(generated): path.read_bytes()
        for path in generated.rglob("*")
        if path.is_file()
    }
    stale = generated / "session_99_assign.qmd"
    stale.write_text("stale")
    old_variant = generated / "session_01_old.qmd"
    old_variant.write_text("legacy")
    (generated / "data/stale.csv").write_text("stale", encoding="utf-8")
    build(tmp_path)
    second = {
        path.relative_to(generated): path.read_bytes()
        for path in generated.rglob("*")
        if path.is_file()
    }
    assert first == second
    assert canonical.read_bytes() == original
    assert not stale.exists()
    assert not old_variant.exists()


def test_make_build_publishes_rendered_variants_and_data(tmp_path: Path) -> None:
    """Exercise the real Make targets with a minimal Quarto stand-in."""
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "exercises").mkdir()
    (tmp_path / "exercises/data").mkdir()
    shutil.copy(root / "Makefile", tmp_path / "Makefile")
    shutil.copy(root / "_quarto.yml", tmp_path / "_quarto.yml")
    shutil.copy(root / "scripts/build_exercises.py", tmp_path / "scripts/build_exercises.py")
    (tmp_path / "exercises/session_01.qmd").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "exercises/data/market_data_log.csv").write_text("price\n42\n", encoding="utf-8")

    quarto = tmp_path / "fake_quarto.py"
    quarto.write_text(
        """#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path

args = sys.argv[1:]
assert args[0] == "render"
if len(args) > 1 and args[1] == "_generated/exercises":
    assert "--output" not in args
    assert "--output-dir" not in args
    assert args[args.index("--to") + 1] == "html"
    project = Path(args[1])
    assert (project / "_quarto.yml").exists()
    assert "output-dir: _rendered" in (project / "_quarto.yml").read_text(encoding="utf-8")
    assert (project / "data/market_data_log.csv").exists()
    output_dir = project / "_rendered"
    output_dir.mkdir(parents=True, exist_ok=True)
    for source in project.glob("session_*_*.qmd"):
        (output_dir / source.with_suffix(".html").name).write_text("rendered", encoding="utf-8")
    shutil.copytree(project / "data", output_dir / "data")
else:
    config = Path("_quarto.yml").read_text(encoding="utf-8")
    site = Path("_site")
    site.mkdir(exist_ok=True)
    (site / "index.html").write_text("website", encoding="utf-8")
    if '!exercises/**' not in config and '"!exercises/**"' not in config:
        canonical = site / "exercises/session_01.html"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text("unexpected", encoding="utf-8")
""",
        encoding="utf-8",
    )
    quarto.chmod(0o755)

    subprocess.run(
        [
            "make",
            "site",
            f"PYTHON={sys.executable}",
            f"QUARTO={quarto}",
        ],
        cwd=tmp_path,
        check=True,
    )

    assert sorted(path.name for path in (tmp_path / "_generated/exercises").glob("*.qmd")) == [
        "session_01_assign.qmd",
        "session_01_solution.qmd",
    ]
    published = tmp_path / "_site/exercises"
    assert sorted(path.name for path in published.iterdir()) == [
        "data",
        "session_01_assign.html",
        "session_01_assign.qmd",
        "session_01_solution.html",
        "session_01_solution.qmd",
    ]
    assert (published / "data/market_data_log.csv").read_text(encoding="utf-8") == "price\n42\n"
    assert (tmp_path / "_generated/exercises/_rendered/session_01_assign.html").exists()
    assert not (tmp_path / "_site/exercises/generated").exists()
    assert not (tmp_path / "_site/exercises/_quarto.yml").exists()
    assert not (tmp_path / "_site/exercises/session_01.html").exists()
    assert not (tmp_path / "_site/session_01_assign.html").exists()
    assert not (tmp_path / "_site/session_01_solution.html").exists()
    assert not list(tmp_path.rglob("*.ipynb"))

    subprocess.run(["make", "clean"], cwd=tmp_path, check=True)
    assert not (tmp_path / "_generated").exists()
    assert not (tmp_path / "_site").exists()


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_real_quarto_project_render_smoke(tmp_path: Path) -> None:
    """Catch invalid Quarto CLI combinations when Quarto is available."""
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "exercises").mkdir()
    (tmp_path / "exercises/data").mkdir()
    shutil.copy(root / "Makefile", tmp_path / "Makefile")
    shutil.copy(root / "scripts/build_exercises.py", tmp_path / "scripts/build_exercises.py")
    (tmp_path / "exercises/session_01.qmd").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "exercises/data/market_data_log.csv").write_text("price\n42\n", encoding="utf-8")

    subprocess.run(
        ["make", "exercises", f"PYTHON={sys.executable}"],
        cwd=tmp_path,
        check=True,
    )
    assert sorted(path.name for path in (tmp_path / "_site/exercises").iterdir()) == [
        "data",
        "session_01_assign.html",
        "session_01_assign.qmd",
        "session_01_solution.html",
        "session_01_solution.qmd",
    ]
    assert (tmp_path / "_generated/exercises/_rendered/session_01_assign.html").exists()
    assert (tmp_path / "_site/exercises/data/market_data_log.csv").exists()
