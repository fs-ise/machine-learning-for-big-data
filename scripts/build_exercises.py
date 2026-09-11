"""Build student-facing exercise sources from canonical Quarto documents."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

Variant = Literal["assign", "solution"]
VARIANTS: tuple[Variant, ...] = ("assign", "solution")
SEMANTIC_CLASSES = frozenset({"direction", "sol"})
PROJECT_CONFIG = """project:
  type: default
  output-dir: _rendered
  render:
    - "session_*_assign.qmd"
    - "session_*_solution.qmd"
  resources:
    - "data/**"

format:
  html: default
  pdf:
    documentclass: article
    papersize: a4
    geometry:
      - margin=25mm
    template-partials:
      - solution-pdf/in-header.tex
      - solution-pdf/before-body.tex
"""
COURSE_TITLE = "Machine Learning for Big Data"
SOLUTION_TEMPLATES = (
    Path("scripts/templates/exercise-solution-in-header.tex"),
    Path("scripts/templates/exercise-solution-before-body.tex"),
)
FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(?P<body>.*?)^---[ \t]*$", re.MULTILINE | re.DOTALL)
TITLE = re.compile(r'^title:[ \t]*(?P<title>.+?)[ \t]*$', re.MULTILINE)
SESSION_FILENAME = re.compile(r"^session_(?P<number>\d+)(?:_(?P<suffix>[a-z]+))?$")
DIV_OPEN = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>:{3,})[ \t]*(?P<attrs>(?!:)\S.*?)[ \t]*(?:\r?\n)?$")
DIV_CLOSE = re.compile(r"^[ \t]*:{3,}[ \t]*(?:\r?\n)?$")
CODE_FENCE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})")
CLASS = re.compile(r"\.([A-Za-z_][\w-]*)")


class ExerciseSyntaxError(ValueError):
    """Raised when a semantic fenced Div cannot be parsed safely."""


@dataclass(frozen=True)
class Div:
    line: int
    semantic: str | None


def _wanted(semantic: str, variant: Variant) -> bool:
    return {
        "direction": variant == "assign",
        "sol": variant == "solution",
    }[semantic]


def _strip_html_comments(source: str) -> str:
    """Remove HTML comments outside fenced code blocks.

    This deliberately uses a small state machine rather than a document-wide
    regular expression: comments may span lines, several comments may occur in
    one document, and HTML-looking examples inside code fences are source text.
    """
    output: list[str] = []
    code_fence: tuple[str, int] | None = None
    in_comment = False

    for line in source.splitlines(keepends=True):
        code_match = CODE_FENCE.match(line)
        if code_fence is not None:
            output.append(line)
            if (
                code_match
                and code_match.group("fence")[0] == code_fence[0]
                and len(code_match.group("fence")) >= code_fence[1]
            ):
                code_fence = None
            continue
        if not in_comment and code_match:
            code_fence = (code_match.group("fence")[0], len(code_match.group("fence")))
            output.append(line)
            continue

        position = 0
        visible: list[str] = []
        while position < len(line):
            if in_comment:
                end = line.find("-->", position)
                if end < 0:
                    position = len(line)
                else:
                    in_comment = False
                    position = end + 3
            else:
                start = line.find("<!--", position)
                if start < 0:
                    visible.append(line[position:])
                    position = len(line)
                else:
                    visible.append(line[position:start])
                    in_comment = True
                    position = start + 4
        output.extend(visible)

    return "".join(output)


def sanitize(source: str, variant: Variant, *, filename: str = "<input>") -> str:
    """Return one variant while retaining source text exactly where possible."""
    source = _strip_html_comments(source)
    output: list[str] = []
    divs: list[Div] = []
    code_fence: tuple[str, int] | None = None

    for line_number, line in enumerate(source.splitlines(keepends=True), 1):
        code_match = CODE_FENCE.match(line)
        if code_fence is not None:
            output.append(line) if all(
                frame.semantic is None or _wanted(frame.semantic, variant) for frame in divs
            ) else None
            if code_match and code_match.group("fence")[0] == code_fence[0] and len(code_match.group("fence")) >= code_fence[1]:
                code_fence = None
            continue
        if code_match:
            code_fence = (code_match.group("fence")[0], len(code_match.group("fence")))
            if all(frame.semantic is None or _wanted(frame.semantic, variant) for frame in divs):
                output.append(line)
            continue

        opening = DIV_OPEN.match(line)
        if opening:
            classes = SEMANTIC_CLASSES.intersection(CLASS.findall(opening.group("attrs")))
            if len(classes) > 1:
                raise ExerciseSyntaxError(
                    f"{filename}:{line_number}: fenced Div has multiple exercise classes: "
                    f"{', '.join(sorted(classes))}"
                )
            semantic = next(iter(classes), None)
            divs.append(Div(line_number, semantic))
            if semantic is None and all(
                frame.semantic is None or _wanted(frame.semantic, variant) for frame in divs
            ):
                output.append(line)
            continue

        if DIV_CLOSE.match(line):
            if not divs:
                output.append(line)
                continue
            frame = divs.pop()
            if frame.semantic is None and all(
                ancestor.semantic is None or _wanted(ancestor.semantic, variant) for ancestor in divs
            ):
                output.append(line)
            continue

        if all(frame.semantic is None or _wanted(frame.semantic, variant) for frame in divs):
            output.append(line)

    semantic_frames = [frame for frame in divs if frame.semantic is not None]
    if semantic_frames:
        frame = semantic_frames[-1]
        raise ExerciseSyntaxError(
            f"{filename}:{frame.line}: unclosed .{frame.semantic} fenced Div"
        )
    return "".join(output)


def _yaml_scalar(value: str) -> str:
    """Read the simple quoted or plain scalar used by canonical exercise titles."""
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return json.loads(value)
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def solution_metadata(source: str, stem: str) -> dict[str, str]:
    """Derive PDF-only semantic metadata from canonical filename and title."""
    session = SESSION_FILENAME.fullmatch(stem)
    front_matter = FRONT_MATTER.match(source)
    title = TITLE.search(front_matter.group("body")) if front_matter else None
    if session is None or title is None:
        raise ExerciseSyntaxError(
            f"{stem}: solution PDF metadata requires a session_XX filename and YAML title"
        )

    number = session.group("number")
    suffix = session.group("suffix")
    if suffix:
        number += suffix.upper()
    canonical_title = _yaml_scalar(title.group("title"))
    topic = re.sub(
        r"^(?:Session\s+\d+[A-Za-z]?(?:\s+Supplement)?|Exercise)\s*:\s*",
        "",
        canonical_title,
        flags=re.IGNORECASE,
    )
    return {
        "course-title": COURSE_TITLE,
        "exercise-number": number,
        "exercise-variant": "Solution",
        "exercise-topic": topic,
    }


def add_solution_metadata(source: str, stem: str) -> str:
    """Add metadata consumed only by the shared PDF title partial."""
    metadata = solution_metadata(source, stem)
    front_matter = FRONT_MATTER.match(source)
    assert front_matter is not None  # validated by solution_metadata
    fields = "".join(f"{key}: {json.dumps(value)}\n" for key, value in metadata.items())
    insert_at = front_matter.end("body")
    return source[:insert_at] + fields + source[insert_at:]


def build(root: Path) -> list[Path]:
    exercises = root / "exercises"
    destination = root / "_generated" / "exercises"
    destination.mkdir(parents=True, exist_ok=True)
    generated_data = destination / "data"
    shutil.rmtree(generated_data, ignore_errors=True)
    source_data = exercises / "data"
    if source_data.is_dir():
        shutil.copytree(source_data, generated_data)
    template_destination = destination / "solution-pdf"
    template_destination.mkdir(exist_ok=True)
    for template_source in SOLUTION_TEMPLATES:
        destination_name = template_source.name.removeprefix("exercise-solution-")
        shutil.copy2(root / template_source, template_destination / destination_name)
    (destination / "_quarto.yml").write_text(PROJECT_CONFIG, encoding="utf-8", newline="")
    sources = sorted(exercises.glob("session_*.qmd"))
    expected: set[Path] = set()
    written: list[Path] = []
    for source in sources:
        with source.open(encoding="utf-8", newline="") as source_file:
            original = source_file.read()
        for variant in VARIANTS:
            target = destination / f"{source.stem}_{variant}.qmd"
            expected.add(target)
            rendered = sanitize(original, variant, filename=str(source))
            if variant == "solution":
                rendered = add_solution_metadata(rendered, source.stem)
            target.write_text(rendered, encoding="utf-8", newline="")
            written.append(target)
    for stale in destination.glob("session_*_*.qmd"):
        if stale not in expected:
            stale.unlink()
    return written


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        written = build(args.root)
    except ExerciseSyntaxError as error:
        parser.exit(1, f"error: {error}\n")
    print(f"Generated {len(written)} exercise variants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
