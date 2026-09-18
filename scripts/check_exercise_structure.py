#!/usr/bin/env python3
"""Check blank-line conventions in canonical exercise QMD documents."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


HEADING = re.compile(r"^[ \t]{0,3}#{1,6}(?:[ \t]+|$)")
DIV_FENCE = re.compile(r"^[ \t]*(?P<fence>:{3,})(?P<label>[ \t]*(?!:)\S.*?)?[ \t]*$")
CODE_FENCE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})")
CODE_CLOSE = re.compile(r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[ \t]*$")


@dataclass(frozen=True)
class Violation:
    """A single formatting problem at a source location."""

    path: Path
    line: int
    explanation: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.explanation}"


def _yaml_end(lines: Sequence[str]) -> int:
    """Return the zero-based YAML closing line, or -1 when none exists."""
    if not lines or lines[0].strip() != "---":
        return -1
    for index in range(1, len(lines)):
        if lines[index].strip() in {"---", "..."}:
            return index
    return -1


def _without_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    """Mask HTML comments, retaining any Markdown outside them."""
    visible: list[str] = []
    position = 0
    while position < len(line):
        if in_comment:
            end = line.find("-->", position)
            if end == -1:
                return "".join(visible), True
            in_comment = False
            position = end + 3
        else:
            start = line.find("<!--", position)
            if start == -1:
                visible.append(line[position:])
                break
            visible.append(line[position:start])
            in_comment = True
            position = start + 4
    return "".join(visible), in_comment


def validate_lines(lines: Sequence[str], path: Path | str = "<input>") -> list[Violation]:
    """Validate *lines* and return all blank-line violations."""
    source = Path(path)
    violations: list[Violation] = []
    yaml_end = _yaml_end(lines)
    code_fence: tuple[str, int] | None = None
    div_stack: list[int] = []
    in_comment = False

    for index, raw_line in enumerate(lines):
        if index <= yaml_end:
            continue

        line, in_comment = _without_comments(raw_line.rstrip("\r\n"), in_comment)

        if code_fence is not None:
            closing = CODE_CLOSE.match(line)
            if closing:
                marker = closing.group("fence")
                if marker[0] == code_fence[0] and len(marker) >= code_fence[1]:
                    code_fence = None
            continue

        code = CODE_FENCE.match(line)
        if code:
            marker = code.group("fence")
            code_fence = (marker[0], len(marker))
            continue

        div = DIV_FENCE.fullmatch(line)
        if div:
            marker_length = len(div.group("fence"))
            if div.group("label") is not None:
                if index > 0 and lines[index - 1].strip():
                    violations.append(
                        Violation(source, index + 1, "opening fenced Div must be preceded by a blank line")
                    )
                div_stack.append(marker_length)
            elif div_stack and marker_length >= div_stack[-1]:
                div_stack.pop()
                if index + 1 < len(lines) and lines[index + 1].strip():
                    violations.append(
                        Violation(source, index + 1, "closing fenced Div must be followed by a blank line")
                    )
            continue

        if HEADING.match(line):
            follows_yaml = yaml_end >= 0 and index == yaml_end + 1
            if index > 0 and not follows_yaml and lines[index - 1].strip():
                violations.append(
                    Violation(source, index + 1, "heading must be preceded by a blank line")
                )

    return violations


def check_file(path: Path) -> list[Violation]:
    """Read and validate one UTF-8 QMD file."""
    return validate_lines(path.read_text(encoding="utf-8").splitlines(), path)


def default_paths() -> list[Path]:
    """Return canonical exercise files relative to the current directory."""
    return sorted(Path("exercises").glob("session_*.qmd"))


def run(paths: Iterable[Path]) -> list[Violation]:
    """Validate each path in iteration order."""
    return [problem for path in paths for problem in check_file(path)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="QMD files (default: exercises/session_*.qmd)")
    args = parser.parse_args(argv)
    problems = run(args.paths or default_paths())
    for problem in problems:
        print(problem)
    if problems:
        print(f"Found {len(problems)} exercise structure violation(s).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
