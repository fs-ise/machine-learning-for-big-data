import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.build_exercises import (
    ExerciseSyntaxError,
    PROJECT_CONFIG,
    VARIANTS,
    add_solution_metadata,
    build,
    sanitize,
    solution_include,
    solution_metadata,
)


SOURCE = """---
session: Session 1
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


def test_solution_pdf_metadata_only_adds_pdf_fields() -> None:
    source = '---\nsession: "Session 3"\ntitle: "EDA"\n---\nBody\n'
    assert solution_metadata(source) == {
        "course-title": "Machine Learning for Big Data",
        "exercise-variant": "Solution",
    }


def test_pdf_metadata_is_added_only_when_explicitly_building_solution() -> None:
    source = '---\nsession: "Session 3"\ntitle: "EDA"\nformat:\n  html: default\n---\nBody\n'
    generated = add_solution_metadata(source)
    assert 'session: "Session 3"' in generated
    assert 'title: "EDA"' in generated
    assert 'exercise-number:' not in generated
    assert 'exercise-topic:' not in generated
    assert generated.endswith("Body\n")


def test_pdf_config_and_templates_use_static_preamble_and_dynamic_body() -> None:
    root = Path(__file__).resolve().parents[1]
    templates = root / "scripts/templates"
    preamble = templates.joinpath("exercise-solution-preamble.tex").read_text()
    body = templates.joinpath("exercise-solution-before-body.tex").read_text()

    assert "include-in-header:\n      - solution-pdf/preamble.tex" in PROJECT_CONFIG
    assert "template-partials:\n      - solution-pdf/before-body.tex" in PROJECT_CONFIG
    assert "solution-pdf/in-header.tex" not in PROJECT_CONFIG
    assert r"\usepackage{scrlayer-scrpage}" in preamble
    assert r"\usepackage{fvextra}" in preamble
    assert r"\usepackage{needspace}" in preamble
    assert r"\AtBeginDocument" in preamble
    assert r"\DefineVerbatimEnvironment{Highlighting}{Verbatim}" in preamble
    assert r"\RecustomVerbatimEnvironment{Highlighting}{Verbatim}" not in preamble
    assert "breaklines=true" in preamble
    assert "breaknonspaceingroup=true" in preamble
    assert "breakanywhere=true" in preamble
    assert "breaksymbolleft={}" in preamble
    assert r"\KOMAoptions{headsepline=0.3pt}" in preamble
    assert r"\setkomafont{section}{\sffamily\bfseries\Large}" in preamble
    assert r"\setkomafont{subsection}{\sffamily\bfseries\normalsize}" in preamble
    assert r"\setkomafont{subsubsection}{\sffamily\bfseries\small}" in preamble
    assert r"\setkomafont{paragraph}{\sffamily\bfseries\small}" in preamble
    assert r"\setkomafont{subparagraph}{\sffamily\bfseries\footnotesize}" in preamble
    assert "$course-title$" not in preamble
    assert "$exercise-number$" not in preamble
    assert r"\ihead[" in body  # optional argument also configures the plain style
    assert r"\ohead[" in body
    assert r"\ofoot[\pagemark]{\pagemark}" in body
    assert r"\thispagestyle{scrheadings}" in body
    assert r"\renewcommand*{\raggedsection}{\centering}" in body
    assert r"\setkomafont{section}{\sffamily\bfseries\LARGE}" in body
    for field in ("$course-title$", "$session$", "$title$", "$exercise-variant$"):
        assert field in body
    assert r"\section*{$title$}" in body
    assert "$exercise-number$" not in body
    assert "$exercise-topic$" not in body


def test_canonical_exercises_use_separate_session_and_topic_titles() -> None:
    exercises = REPOSITORY_ROOT / "exercises"
    sources = sorted(exercises.glob("session_*.qmd"))

    assert sources
    for source in sources:
        front_matter = source.read_text(encoding="utf-8").split("---", 2)[1]
        assert re.search(r'^session:\s*["\']?Session\s+\d+[A-Za-z]?["\']?\s*$', front_matter, re.MULTILINE)
        title = re.search(r'^title:\s*["\']?(?P<title>.+?)["\']?\s*$', front_matter, re.MULTILINE)
        assert title is not None
        assert not re.match(r"Session\s+\d+[A-Za-z]?\s*:", title.group("title"))


def test_pdf_wrapping_covers_a_long_quoted_highlighted_url() -> None:
    """Keep a single-token string that requires breaking inside a Pandoc group."""
    root = Path(__file__).resolve().parents[1]
    source = root.joinpath("exercises/session_03.qmd").read_text(encoding="utf-8")
    url = (
        "https://raw.githubusercontent.com/fs-ise/machine-learning-for-big-data/"
        "main/exercises/data/employee_work_profiles.csv"
    )

    assert len(url) > 100
    assert f'  "{url}",' in sanitize(source, "solution", filename="session_03.qmd")


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


def test_solution_setup_marker_suppresses_only_generated_solution_output() -> None:
    source = """```{r}
#| label: setup
#| solution-setup: true
#| warning: true
library(tidyverse)
df <- read_csv("data.csv")
glimpse(df)
```
"""
    assignment = sanitize(source, "assign")
    solution = sanitize(source, "solution")

    assert "solution-setup" not in assignment + solution
    assert "#| warning: true" in assignment
    assert "#| output: false" not in assignment
    for code in ("library(tidyverse)", 'df <- read_csv("data.csv")', "glimpse(df)"):
        assert code in assignment
        assert code in solution
    for option in ("echo", "output", "message", "warning"):
        value = "true" if option == "echo" else "false"
        assert solution.count(f"#| {option}: {value}") == 1
    assert "#| warning: true" not in solution

    include = solution_include(source)
    assert "library(tidyverse)" in include
    assert "glimpse(df)" in include
    assert "#| output: false" in include


def test_assignment_removes_labels_only_from_executable_chunks() -> None:
    source = """````{r load-data, echo=FALSE}
#| label: yaml-r-label
#| warning: false
x <- 1 # unchanged
````
~~~{python fit_model}
  #| label: yaml-python-label
#| echo: true
print("unchanged")
~~~
````qmd
```{r example-label}
#| label: literal-example
```
````
```text
#| label: ordinary-code
```
"""

    assignment = sanitize(source, "assign")
    solution = sanitize(source, "solution")

    assert "````{r, echo=FALSE}" in assignment
    assert "~~~{python}" in assignment
    assert "yaml-r-label" not in assignment
    assert "yaml-python-label" not in assignment
    for unchanged in (
        "#| warning: false",
        "#| echo: true",
        "x <- 1 # unchanged",
        'print("unchanged")',
        "```{r example-label}",
        "#| label: literal-example",
        "#| label: ordinary-code",
    ):
        assert unchanged in assignment

    for original_label in (
        "````{r load-data, echo=FALSE}",
        "#| label: yaml-r-label",
        "~~~{python fit_model}",
        "#| label: yaml-python-label",
    ):
        assert original_label in solution

    assert sanitize(assignment, "assign") == assignment


def test_canonical_setup_suppression_preserves_task_results() -> None:
    root = Path(__file__).resolve().parents[1]
    session_5 = (root / "exercises/session_05.qmd").read_text(encoding="utf-8")
    assignment = sanitize(session_5, "assign", filename="session_05.qmd")
    solution = sanitize(session_5, "solution", filename="session_05.qmd")

    setup_label = "#| label: package-setup-load-packages"
    assert setup_label not in assignment
    start = assignment.index("library(tidyverse)")
    assignment_setup = assignment[start : assignment.index("```", start)]
    assert "#| output: false" not in assignment_setup
    start = solution.index(setup_label)
    solution_setup = solution[start : solution.index("```", start)]
    for content in ("library(tidyverse)", "df <- read_csv(", "glimpse(df)", "#| output: false"):
        assert content in solution_setup

    # Analytical results remain unsuppressed rather than inheriting a global option.
    model_chunk = solution[solution.index("#| label: solution-model") :]
    model_chunk = model_chunk[: model_chunk.index("```")]
    assert "summary(model)" in model_chunk
    assert "#| output: false" not in model_chunk

    session_6 = (root / "exercises/session_06.qmd").read_text(encoding="utf-8")
    session_6_solution = sanitize(session_6, "solution", filename="session_06.qmd")
    inspection = session_6_solution[
        session_6_solution.index("#| label: task-1-1-load-and-inspect-the-data-df") :
    ]
    inspection = inspection[: inspection.index("```")]
    assert "glimpse(df)" in inspection
    assert "count(df, default)" in inspection
    assert "#| output: false" not in inspection


def test_chunks_and_unrelated_nested_divs_are_preserved() -> None:
    chunk = "```{r}\n#| eval: false\nx <- c(1, 2)  # unchanged\nmean(x)\n```\n"
    assert chunk in sanitize(SOURCE, "assign")
    expected = ":::: {.callout-note}\nnested ordinary\n::::\n"
    assert expected in sanitize(SOURCE, "solution")
    ordinary = "::: {.ordinary}\nordinary div\n:::\n"
    assert all(ordinary in sanitize(SOURCE, variant) for variant in VARIANTS)


def test_solution_include_has_filtered_body_executable_chunks_and_nested_headings() -> None:
    source = SOURCE + "# Part\n## Detail\n```{python}\nprint('executed')\n```\n{{< needspace 8 >}}\n"
    fragment = solution_include(source)
    assert not fragment.startswith("---")
    assert "title: Test" not in fragment
    assert "Directions" not in fragment
    assert "Solution" in fragment
    assert "```{python}\nprint('executed')\n```" in fragment
    assert "### Part\n#### Detail" in fragment
    assert "{{< needspace 8 >}}" not in fragment


def test_solution_include_nests_semantic_part_and_task_headings() -> None:
    source = "---\ntitle: Test\n---\n# Part 1\n## Task 1.1\n### Detail\n"

    fragment = solution_include(source)

    assert "### Part 1\n#### Task 1.1\n##### Detail\n" in fragment
    assert not any(line.startswith("# ") for line in fragment.splitlines())


@pytest.mark.parametrize("variant", VARIANTS)
def test_needspace_directives_are_removed_but_code_examples_are_preserved(variant: str) -> None:
    source = "\n".join(
        (
            "before",
            "",
            "  {{<   needspace   12   >}}  ",
            "",
            "{{< needspace >}}",
            "after",
            "`{{< needspace 4 >}}`",
            "```qmd",
            "{{< needspace 8 >}}",
            "```",
            "",
        )
    )
    rendered = sanitize(source, variant)

    assert "\n\n\nafter" not in rendered
    assert "{{<   needspace   12   >}}" not in rendered
    assert "\n{{< needspace >}}\n" not in rendered
    assert "`{{< needspace 4 >}}`" in rendered
    assert "```qmd\n{{< needspace 8 >}}\n```" in rendered


def test_needspace_can_be_preserved_for_pdf_render_sources() -> None:
    source = "before\n\n{{< needspace 12 >}}\n\n## Heading\n"

    assert "{{< needspace 12 >}}" in sanitize(
        source, "solution", preserve_needspace=True
    )


def test_requested_exercise_pagination_is_selective_and_headings_are_separate() -> None:
    root = Path(__file__).resolve().parents[1]
    expected = {
        "session_01.qmd": {"Edit a Quarto document": 10},
        "session_02.qmd": {"Part 2: Data structuring 2": 8},
        "session_03.qmd": {"Exploratory check": 8, "Standardization": 10},
        "session_04.qmd": {
            "Task D2: Compare the subgroup models": 8,
            "Part E — Deployment": 10,
            "Task E3: Reflect on practical and organizational considerations": 8,
        },
        "session_05.qmd": {
            "Task 1.2 — Estimate the model": 20,
            "Task 1.4 — From coefficients to classification": 10,
        },
        "session_06.qmd": {
            "Part 6 — Evaluate the logistic baseline": 10,
            "Part 10 — Reflect on generalization": 8,
        },
        "session_07.qmd": {"Part 6 — RBF support vector machine": 10},
    }
    for filename, headings in expected.items():
        source = (root / "exercises" / filename).read_text(encoding="utf-8")
        for heading, lines in headings.items():
            assert re.search(
                rf"\{{\{{< needspace {lines} >\}}\}}\n\n#+ {re.escape(heading)}(?: |\n)",
                source,
            )

    for filename, heading in (
        ("session_06.qmd", "# Part 2 — Specify preprocessing without leakage {#recipe}"),
    ):
        source = (root / "exercises" / filename).read_text(encoding="utf-8")
        assert f":::\n\n{heading}\n" in source


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
    template = tmp_path / "scripts/templates"
    template.mkdir(parents=True)
    template.joinpath("exercise-solution-before-body.tex").write_text("shared template")
    template.joinpath("exercise-solution-preamble.tex").write_text("shared preamble")
    extension = tmp_path / "_extensions/needspace"
    extension.mkdir(parents=True)
    extension.joinpath("_extension.yml").write_text("title: needspace\n")
    data = exercises / "data"
    data.mkdir()
    fixture = data / "market_data_log.csv"
    fixture.write_text("price\n42\n", encoding="utf-8")
    canonical = exercises / "session_01.qmd"
    canonical.write_text(
        SOURCE
        + "\n```{r generated-r-label}\n#| label: generated-yaml-label\n"
        + "#| echo: false\nvalue <- 42\n```\n"
        + "~~~{python generated-python-label}\nprint(42)\n~~~\n"
        + "\n{{< needspace 8 >}}\n"
        + "`{{< needspace 3 >}}`\n"
        + "```qmd\n{{< needspace >}}\n```\n",
        encoding="utf-8",
    )
    original = canonical.read_bytes()
    build(tmp_path)
    generated = tmp_path / "_generated/exercises"
    assert (generated / "_quarto.yml").read_text(encoding="utf-8") == PROJECT_CONFIG
    assert (generated / "solution-pdf/before-body.tex").read_text() == "shared template"
    assert (generated / "solution-pdf/preamble.tex").read_text() == "shared preamble"
    assert (generated / "_extensions/needspace/_extension.yml").exists()
    assert "output-dir: _rendered" in PROJECT_CONFIG
    assert '    - "pdf_session_*_solution.qmd"' in PROJECT_CONFIG
    assert "html:" not in PROJECT_CONFIG
    assignment = (generated / "session_01_assign.qmd").read_text(encoding="utf-8")
    solution = (generated / "session_01_solution.qmd").read_text(encoding="utf-8")
    include = (generated / "includes/_session_01_solution.qmd").read_text(encoding="utf-8")
    pdf_source = (generated / "pdf_session_01_solution.qmd").read_text(encoding="utf-8")
    assert "title: Test" in assignment
    for field in ("course-title", "exercise-variant"):
        assert f"{field}:" not in assignment
    assert "session: Session 1" in assignment
    assert "title: Test" in solution
    assert "session: Session 1" in solution
    assert 'course-title: "Machine Learning for Big Data"' in solution
    assert 'exercise-variant: "Solution"' in solution
    assert "exercise-number:" not in solution
    assert "exercise-topic:" not in solution
    assert "generated-r-label" not in assignment
    assert "generated-yaml-label" not in assignment
    assert "generated-python-label" not in assignment
    assert "```{r}\n#| echo: false\nvalue <- 42\n```" in assignment
    for label in (
        "```{r generated-r-label}",
        "#| label: generated-yaml-label",
        "~~~{python generated-python-label}",
    ):
        assert label in solution
    assert not include.startswith("---")
    assert "Directions" not in include
    assert "Solution" in include
    for artifact in (assignment, solution, include):
        assert "\n{{< needspace 8 >}}\n" not in artifact
        assert "`{{< needspace 3 >}}`" in artifact
        assert "```qmd\n{{< needspace >}}\n```" in artifact
    assert "\n{{< needspace 8 >}}\n" in pdf_source
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
    stale_include = generated / "includes/_session_99_solution.qmd"
    stale_include.write_text("stale")
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
    assert not stale_include.exists()


def test_every_canonical_exercise_gets_an_include(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    # The repository build itself is cheap and proves the complete canonical set.
    build(root)
    canonical_stems = {path.stem for path in (root / "exercises").glob("session_*.qmd")}
    include_stems = {
        path.name.removeprefix("_").removesuffix("_solution.qmd")
        for path in (root / "_generated/exercises/includes").glob("_session_*_solution.qmd")
    }
    assert include_stems == canonical_stems
    session_5_include = (root / "_generated/exercises/includes/_session_05_solution.qmd").read_text()
    for prerequisite in ("library(tidyverse)", "library(pROC)", "df <- read_csv("):
        assert prerequisite in session_5_include


def test_make_build_publishes_rendered_variants_and_data(tmp_path: Path) -> None:
    """Exercise the real Make targets with a minimal Quarto stand-in."""
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/templates").mkdir()
    (tmp_path / "exercises").mkdir()
    (tmp_path / "exercises/data").mkdir()
    shutil.copy(root / "Makefile", tmp_path / "Makefile")
    shutil.copy(root / "_quarto.yml", tmp_path / "_quarto.yml")
    shutil.copytree(root / "_extensions/needspace", tmp_path / "_extensions/needspace")
    shutil.copy(root / "scripts/build_exercises.py", tmp_path / "scripts/build_exercises.py")
    shutil.copy(
        root / "scripts/templates/exercise-solution-before-body.tex",
        tmp_path / "scripts/templates/exercise-solution-before-body.tex",
    )
    shutil.copy(
        root / "scripts/templates/exercise-solution-preamble.tex",
        tmp_path / "scripts/templates/exercise-solution-preamble.tex",
    )
    (tmp_path / "exercises/session_01.qmd").write_text(
        SOURCE + "\n{{< needspace 8 >}}\n\n## Kept together\nBody\n", encoding="utf-8"
    )
    (tmp_path / "exercises/data/market_data_log.csv").write_text("price\n42\n", encoding="utf-8")

    quarto = tmp_path / "fake_quarto.py"
    quarto.write_text(
        """#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path
import os

args = sys.argv[1:]
assert args[0] == "render"
if Path.cwd().name == "exercises" and Path.cwd().parent.name == "_generated":
    assert "--output-dir" not in args
    output_format = args[args.index("--to") + 1]
    output_name = args[args.index("--output") + 1]
    source = Path(args[1])
    assert source.name.startswith("pdf_session_") and source.name.endswith("_solution.qmd")
    assert "{{< needspace 8 >}}" in source.read_text(encoding="utf-8")
    assert output_name == source.name.removeprefix("pdf_").removesuffix(".qmd") + ".pdf"
    assert output_format == "pdf"
    assert "--no-execute" not in args
    assert Path("_quarto.yml").exists()
    assert "output-dir: _rendered" in Path("_quarto.yml").read_text(encoding="utf-8")
    assert Path("data/market_data_log.csv").exists()
    output_dir = Path("_rendered")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("FAKE_QUARTO_SKIP_OUTPUT"):
        (output_dir / output_name).write_text("rendered", encoding="utf-8")
    if not (output_dir / "data").exists():
        shutil.copytree("data", output_dir / "data")
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

    # A no-clean rebuild must remove exercise HTML left by an older build.
    old_rendered = tmp_path / "_generated/exercises/_rendered"
    old_rendered.mkdir(parents=True)
    (old_rendered / "pdf_session_01_solution.pdf").write_text("stale", encoding="utf-8")
    (old_rendered / "session_01_solution.pdf").write_text("stale", encoding="utf-8")
    (old_rendered / "session_01_assign.html").write_text("old", encoding="utf-8")
    (old_rendered / "session_01_solution.html").write_text("old", encoding="utf-8")
    old_published = tmp_path / "_site/exercises"
    old_published.mkdir(parents=True)
    (old_published / "session_01_assign.html").write_text("old", encoding="utf-8")
    (old_published / "session_01_solution.html").write_text("old", encoding="utf-8")
    (old_published / "session_01.html").write_text("old", encoding="utf-8")

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
        "pdf_session_01_solution.qmd",
        "session_01_assign.qmd",
        "session_01_solution.qmd",
    ]
    published = tmp_path / "_site/exercises"
    assert sorted(path.name for path in published.iterdir()) == [
        "data",
        "session_01_assign.qmd",
        "session_01_solution.pdf",
        "session_01_solution.qmd",
    ]
    assert (published / "data/market_data_log.csv").read_text(encoding="utf-8") == "price\n42\n"
    assert not list((tmp_path / "_generated/exercises/_rendered").glob("*.html"))
    assert not (tmp_path / "_generated/exercises/_rendered/session_01_assign.pdf").exists()
    assert (tmp_path / "_generated/exercises/_rendered/session_01_solution.pdf").exists()
    assert (tmp_path / "_generated/exercises/_rendered/session_01_solution.pdf").read_text() == "rendered"
    assert not list(tmp_path.glob("_generated/exercises/_rendered/pdf_session_*.pdf"))
    assert not list(published.glob("pdf_session_*"))
    assert not (tmp_path / "_site/exercises/generated").exists()
    assert not (tmp_path / "_site/exercises/_quarto.yml").exists()
    assert not (tmp_path / "_site/exercises/session_01.html").exists()
    assert not (tmp_path / "_site/session_01_assign.html").exists()
    assert not (tmp_path / "_site/session_01_solution.html").exists()
    assert not list(tmp_path.rglob("*.ipynb"))

    # The phony render target must remain repeatable with --no-clean.
    subprocess.run(
        ["make", "exercises", f"PYTHON={sys.executable}", f"QUARTO={quarto}"],
        cwd=tmp_path,
        check=True,
    )

    checked = subprocess.run(
        ["make", "exercises-check", f"PYTHON={sys.executable}", f"QUARTO={quarto}"],
        cwd=tmp_path,
        env={**os.environ, "FAKE_QUARTO_SKIP_OUTPUT": "1"},
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0

    (published / "session_01_solution.pdf").unlink()
    failed = subprocess.run(
        ["make", "exercises-check", f"PYTHON={sys.executable}", f"QUARTO={quarto}"],
        cwd=tmp_path,
        env={**os.environ, "FAKE_QUARTO_SKIP_OUTPUT": "1"},
        capture_output=True,
        text=True,
    )
    assert failed.returncode != 0
    assert "Quarto did not create expected PDF" in failed.stderr
    assert not (published / "session_01_solution.pdf").exists()

    subprocess.run(["make", "clean"], cwd=tmp_path, check=True)
    assert not (tmp_path / "_generated").exists()
    assert not (tmp_path / "_site").exists()


def test_make_exercises_is_incremental(tmp_path: Path) -> None:
    """Cover discovery, invalidation, restoration, and stale cleanup end to end."""
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "scripts/templates").mkdir(parents=True)
    (tmp_path / "exercises/data").mkdir(parents=True)
    shutil.copy(root / "Makefile", tmp_path / "Makefile")
    shutil.copy(root / "scripts/build_exercises.py", tmp_path / "scripts/build_exercises.py")
    shutil.copytree(root / "_extensions", tmp_path / "_extensions")
    for template in (root / "scripts/templates").glob("exercise-solution-*.tex"):
        shutil.copy(template, tmp_path / "scripts/templates" / template.name)
    (tmp_path / "exercises/data/input.csv").write_text("x\n1\n", encoding="utf-8")

    def source(number: int, body: str = "Common") -> str:
        return SOURCE.replace("title: Test", f"title: Session {number}: Test") + body + "\n"

    for number in (1, 2):
        (tmp_path / f"exercises/session_{number:02}.qmd").write_text(
            source(number), encoding="utf-8"
        )

    quarto = tmp_path / "quarto"
    quarto.write_text(
        """#!/usr/bin/env python3
import sys
from pathlib import Path
args = sys.argv[1:]
assert args[0] == "render" and args[2:4] == ["--to", "pdf"]
source = Path(args[1])
output = args[args.index("--output") + 1]
with (Path.cwd().parents[1] / "render.log").open("a") as log:
    log.write(source.name + "\\n")
destination = Path("_rendered") / output
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text("rendered " + source.name)
""",
        encoding="utf-8",
    )
    quarto.chmod(0o755)

    def run(target: str = "exercises") -> list[str]:
        subprocess.run(
            ["make", target, f"PYTHON={sys.executable}", f"QUARTO={quarto}"],
            cwd=tmp_path,
            check=True,
        )
        log = tmp_path / "render.log"
        calls = log.read_text().splitlines() if log.exists() else []
        log.write_text("")
        return calls

    # A/B: clean build renders both; a repeat preserves every published mtime.
    assert sorted(run()) == ["pdf_session_01_solution.qmd", "pdf_session_02_solution.qmd"]
    outputs = sorted((tmp_path / "_site/exercises").glob("session_*"))
    mtimes = {path.name: path.stat().st_mtime_ns for path in outputs}
    assert run() == []
    assert {path.name: path.stat().st_mtime_ns for path in outputs} == mtimes

    # C: a canonical edit changes and renders only its own artifacts.
    pdf_two = tmp_path / "_site/exercises/session_02_solution.pdf"
    pdf_two_mtime = pdf_two.stat().st_mtime_ns
    one = tmp_path / "exercises/session_01.qmd"
    one.write_text(source(1, "changed"), encoding="utf-8")
    assert run() == ["pdf_session_01_solution.qmd"]
    assert pdf_two.stat().st_mtime_ns == pdf_two_mtime

    # D/E: a shared template invalidates all PDFs; a missing PDF only itself.
    template = tmp_path / "scripts/templates/exercise-solution-preamble.tex"
    template.write_text(template.read_text() + "\n% changed\n")
    assert sorted(run()) == ["pdf_session_01_solution.qmd", "pdf_session_02_solution.qmd"]
    (tmp_path / "_site/exercises/session_01_solution.pdf").unlink()
    assert run() == ["pdf_session_01_solution.qmd"]

    # F: generator code changes run generation, but stable output prevents renders.
    generator = tmp_path / "scripts/build_exercises.py"
    generator.write_text(generator.read_text() + "\n# harmless test edit\n")
    assert run() == []

    # G/H: wildcard discovery adds a new exercise and removal cleans stale outputs.
    (tmp_path / "exercises/session_03.qmd").write_text(source(3), encoding="utf-8")
    assert run() == ["pdf_session_03_solution.qmd"]
    (tmp_path / "exercises/session_02.qmd").unlink()
    assert run() == []
    assert not list((tmp_path / "_generated/exercises").glob("*session_02*"))
    assert not list((tmp_path / "_site/exercises").glob("session_02*"))

    # I/J: a missing public QMD is restored without rendering; checks are incremental.
    public_qmd = tmp_path / "_site/exercises/session_01_assign.qmd"
    public_qmd.unlink()
    assert run() == []
    assert public_qmd.exists()
    assert run("exercises-check") == []
    assert run("exercises-check") == []


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_real_quarto_project_render_smoke(tmp_path: Path) -> None:
    """Catch invalid Quarto CLI combinations when Quarto is available."""
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/templates").mkdir()
    (tmp_path / "exercises").mkdir()
    (tmp_path / "exercises/data").mkdir()
    shutil.copy(root / "Makefile", tmp_path / "Makefile")
    shutil.copytree(root / "_extensions/needspace", tmp_path / "_extensions/needspace")
    shutil.copy(root / "scripts/build_exercises.py", tmp_path / "scripts/build_exercises.py")
    shutil.copy(
        root / "scripts/templates/exercise-solution-before-body.tex",
        tmp_path / "scripts/templates/exercise-solution-before-body.tex",
    )
    shutil.copy(
        root / "scripts/templates/exercise-solution-preamble.tex",
        tmp_path / "scripts/templates/exercise-solution-preamble.tex",
    )
    (tmp_path / "exercises/session_01.qmd").write_text(
        SOURCE + "\n{{< needspace 8 >}}\n\n## Kept together\nBody\n", encoding="utf-8"
    )
    (tmp_path / "exercises/data/market_data_log.csv").write_text("price\n42\n", encoding="utf-8")

    subprocess.run(
        ["make", "exercises", f"PYTHON={sys.executable}"],
        cwd=tmp_path,
        check=True,
    )
    assert sorted(path.name for path in (tmp_path / "_site/exercises").iterdir()) == [
        "data",
        "session_01_assign.qmd",
        "session_01_solution.pdf",
        "session_01_solution.qmd",
    ]
    assert not list((tmp_path / "_generated/exercises/_rendered").glob("*.html"))
    pdf = tmp_path / "_site/exercises/session_01_solution.pdf"
    assert pdf.stat().st_size > 0
    assert "{{< needspace 8 >}}" in (
        tmp_path / "_generated/exercises/pdf_session_01_solution.qmd"
    ).read_text(encoding="utf-8")
    assert r"\Needspace{8\baselineskip}" in (
        tmp_path / "_generated/exercises/_rendered/session_01_solution.tex"
    ).read_text(encoding="utf-8")
    assert not list((tmp_path / "_site/exercises").glob("pdf_session_*"))
    assert (tmp_path / "_site/exercises/data/market_data_log.csv").exists()
