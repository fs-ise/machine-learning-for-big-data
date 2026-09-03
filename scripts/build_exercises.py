"""Build student-facing exercise sources from canonical Quarto documents."""

from __future__ import annotations

import argparse
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
"""
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


def build(root: Path) -> list[Path]:
    exercises = root / "exercises"
    destination = root / "_generated" / "exercises"
    destination.mkdir(parents=True, exist_ok=True)
    generated_data = destination / "data"
    shutil.rmtree(generated_data, ignore_errors=True)
    source_data = exercises / "data"
    if source_data.is_dir():
        shutil.copytree(source_data, generated_data)
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
