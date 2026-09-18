"""Build exercise variants and include fragments from canonical Quarto documents."""

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
    - "pdf_session_*_solution.qmd"
  resources:
    - "data/**"

format:
  pdf:
    pdf-engine: lualatex
    documentclass: scrartcl
    classoption:
      - 11pt
      - headings=small
      - parskip=half
    papersize: a4
    geometry:
      - top=27mm
      - bottom=25mm
      - left=28mm
      - right=28mm
      - headheight=15pt
      - headsep=8mm
      - footskip=12mm
    keep-tex: true
    include-in-header:
      - solution-pdf/preamble.tex
    template-partials:
      - solution-pdf/before-body.tex
"""
COURSE_TITLE = "Machine Learning for Big Data"
SOLUTION_TEMPLATES = (
    Path("scripts/templates/exercise-solution-preamble.tex"),
    Path("scripts/templates/exercise-solution-before-body.tex"),
)
FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(?P<body>.*?)^---[ \t]*$", re.MULTILINE | re.DOTALL)
TITLE = re.compile(r'^title:[ \t]*(?P<title>.+?)[ \t]*$', re.MULTILINE)
HEADING = re.compile(
    r"^(?P<indent>[ \t]*)(?P<marks>#{1,6})(?P<rest>[ \t]+[^\r\n]*)(?P<ending>\r?\n)?$"
)
SESSION_FILENAME = re.compile(r"^session_(?P<number>\d+)(?:_(?P<suffix>[a-z]+))?$")
DIV_OPEN = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>:{3,})[ \t]*(?P<attrs>(?!:)\S.*?)[ \t]*(?:\r?\n)?$")
DIV_CLOSE = re.compile(r"^[ \t]*:{3,}[ \t]*(?:\r?\n)?$")
CODE_FENCE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})")
EXECUTABLE_CODE_FENCE = re.compile(
    r"^(?P<prefix>[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*\{(?P<engine>r|python))"
    r"(?P<body>[^}\r\n]*)(?P<suffix>\}[^\r\n]*(?:\r?\n)?)$",
    re.IGNORECASE,
)
CHUNK_LABEL = re.compile(r"^[ \t]*#\|[ \t]*label:[^\r\n]*(?:\r?\n)?$")
FENCE_IDENTIFIER = re.compile(
    r"^[ \t]+[A-Za-z][\w.-]*(?P<rest>[ \t]*,.*|[ \t]*)$"
)
CLASS = re.compile(r"\.([A-Za-z_][\w-]*)")
NEEDSPACE = re.compile(
    r"^[ \t]*\{\{<[ \t]*needspace(?:[ \t]+\d+)?[ \t]*>\}\}[ \t]*(?:\r?\n)?$"
)
SOLUTION_SETUP = re.compile(r"^[ \t]*#\|[ \t]*solution-setup:[ \t]*true[ \t]*(?:\r?\n)?$")
CHUNK_OPTION = re.compile(
    r"^[ \t]*#\|[ \t]*(?:echo|output|message|warning):[ \t]*.*(?:\r?\n)?$"
)
SOLUTION_SETUP_OPTIONS = (
    "#| echo: true\n"
    "#| output: false\n"
    "#| message: false\n"
    "#| warning: false\n"
)


class ExerciseSyntaxError(ValueError):
    """Raised when a semantic fenced Div cannot be parsed safely."""


def write_if_changed(path: Path, content: str | bytes) -> bool:
    """Write *content* only when its bytes differ, preserving stable mtimes."""
    data = content.encode("utf-8") if isinstance(content, str) else content
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def copy_if_changed(source: Path, destination: Path) -> bool:
    """Copy one file without touching an identical destination."""
    return write_if_changed(destination, source.read_bytes())


def sync_tree(source: Path, destination: Path) -> None:
    """Synchronize a generated resource tree without rewriting equal files."""
    expected: set[Path] = set()
    if source.is_dir():
        for source_file in sorted(path for path in source.rglob("*") if path.is_file()):
            relative = source_file.relative_to(source)
            expected.add(relative)
            copy_if_changed(source_file, destination / relative)
    if destination.is_dir():
        for old_file in sorted(path for path in destination.rglob("*") if path.is_file()):
            if old_file.relative_to(destination) not in expected:
                old_file.unlink()
        for directory in sorted(
            (path for path in destination.rglob("*") if path.is_dir()), reverse=True
        ):
            if not any(directory.iterdir()):
                directory.rmdir()


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


def _apply_solution_setup_convention(source: str, variant: Variant) -> str:
    """Expand canonical solution-only setup markers into Quarto options."""
    lines = source.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    while index < len(lines):
        opening = CODE_FENCE.match(lines[index])
        if not opening:
            output.append(lines[index])
            index += 1
            continue

        fence_char = opening.group("fence")[0]
        fence_length = len(opening.group("fence"))
        end = index + 1
        while end < len(lines):
            closing = CODE_FENCE.match(lines[end])
            if (
                closing
                and closing.group("fence")[0] == fence_char
                and len(closing.group("fence")) >= fence_length
            ):
                break
            end += 1

        chunk = lines[index : min(end + 1, len(lines))]
        markers = [position for position, line in enumerate(chunk) if SOLUTION_SETUP.match(line)]
        if len(markers) > 1:
            raise ExerciseSyntaxError("a code chunk contains multiple solution-setup markers")
        if not markers:
            output.extend(chunk)
        else:
            marker = markers[0]
            for position, line in enumerate(chunk):
                if position == marker:
                    if variant == "solution":
                        output.append(SOLUTION_SETUP_OPTIONS)
                elif variant != "solution" or not CHUNK_OPTION.match(line):
                    output.append(line)
        index = end + 1
    return "".join(output)


def _strip_assignment_chunk_labels(source: str) -> str:
    """Remove explicit labels from executable R and Python chunks only."""
    output: list[str] = []
    code_fence: tuple[str, int, bool] | None = None

    for line in source.splitlines(keepends=True):
        if code_fence is not None:
            closing = CODE_FENCE.match(line)
            if (
                closing
                and closing.group("fence")[0] == code_fence[0]
                and len(closing.group("fence")) >= code_fence[1]
            ):
                code_fence = None
                output.append(line)
            elif not code_fence[2] or not CHUNK_LABEL.match(line):
                output.append(line)
            continue

        opening = EXECUTABLE_CODE_FENCE.match(line)
        if not opening:
            fence = CODE_FENCE.match(line)
            if fence:
                marker = fence.group("fence")
                code_fence = (marker[0], len(marker), False)
            output.append(line)
            continue

        fence = opening.group("fence")
        code_fence = (fence[0], len(fence), True)
        body = opening.group("body")
        identifier = FENCE_IDENTIFIER.fullmatch(body)
        if identifier:
            rest = identifier.group("rest")
            body = rest if "," in rest else ""
        output.append(opening.group("prefix") + body + opening.group("suffix"))

    return "".join(output)


def sanitize(
    source: str,
    variant: Variant,
    *,
    filename: str = "<input>",
    preserve_needspace: bool = False,
) -> str:
    """Return one variant while retaining source text exactly where possible."""
    source = _strip_html_comments(source)
    output: list[str] = []
    divs: list[Div] = []
    code_fence: tuple[str, int] | None = None
    removed_needspace = False

    for line_number, line in enumerate(source.splitlines(keepends=True), 1):
        code_match = CODE_FENCE.match(line)
        if code_fence is not None:
            output.append(line) if all(
                frame.semantic is None or _wanted(frame.semantic, variant) for frame in divs
            ) else None
            if (
                code_match
                and code_match.group("fence")[0] == code_fence[0]
                and len(code_match.group("fence")) >= code_fence[1]
            ):
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
            if NEEDSPACE.match(line) and not preserve_needspace:
                removed_needspace = True
                continue
            if removed_needspace:
                removed_needspace = False
                if not line.strip() and output and not output[-1].strip():
                    continue
            output.append(line)

    semantic_frames = [frame for frame in divs if frame.semantic is not None]
    if semantic_frames:
        frame = semantic_frames[-1]
        raise ExerciseSyntaxError(
            f"{filename}:{frame.line}: unclosed .{frame.semantic} fenced Div"
        )
    rendered = _apply_solution_setup_convention("".join(output), variant)
    if variant == "assign":
        rendered = _strip_assignment_chunk_labels(rendered)
    return rendered


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


def solution_include(source: str, *, filename: str = "<input>", heading_offset: int = 2) -> str:
    """Return a metadata-free solution body suitable for a Quarto include.

    The normal solution filtering is deliberately applied first, so includes and
    standalone solutions have exactly the same executable content.  Headings are
    lowered to nest underneath the teaching note's ``## Exercise solution``.
    """
    rendered = sanitize(source, "solution", filename=filename)
    front_matter = FRONT_MATTER.match(rendered)
    if front_matter:
        rendered = rendered[front_matter.end() :].lstrip("\r\n")

    output: list[str] = []
    code_fence: tuple[str, int] | None = None
    for line in rendered.splitlines(keepends=True):
        code_match = CODE_FENCE.match(line)
        if code_fence is not None:
            output.append(line)
            if code_match and code_match.group("fence")[0] == code_fence[0] and len(code_match.group("fence")) >= code_fence[1]:
                code_fence = None
            continue
        if code_match:
            code_fence = (code_match.group("fence")[0], len(code_match.group("fence")))
            output.append(line)
            continue
        heading = HEADING.match(line)
        if heading:
            marks = "#" * min(6, len(heading.group("marks")) + heading_offset)
            line = (
                f'{heading.group("indent")}{marks}{heading.group("rest")}'
                f'{heading.group("ending") or ""}'
            )
        output.append(line)
    return "".join(output)


def build(root: Path) -> list[Path]:
    exercises = root / "exercises"
    destination = root / "_generated" / "exercises"
    destination.mkdir(parents=True, exist_ok=True)
    generated_data = destination / "data"
    source_data = exercises / "data"
    sync_tree(source_data, generated_data)
    template_destination = destination / "solution-pdf"
    template_destination.mkdir(exist_ok=True)
    for template_source in SOLUTION_TEMPLATES:
        destination_name = template_source.name.removeprefix("exercise-solution-")
        copy_if_changed(root / template_source, template_destination / destination_name)
    extensions = destination / "_extensions"
    sync_tree(root / "_extensions" / "needspace", extensions / "needspace")
    write_if_changed(destination / "_quarto.yml", PROJECT_CONFIG)
    sources = sorted(exercises.glob("session_*.qmd"))
    includes = destination / "includes"
    includes.mkdir(exist_ok=True)
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
            write_if_changed(target, rendered)
            written.append(target)
        # Keep pagination markup in a render-only source.  The public variants
        # above deliberately remain free of layout instructions.
        pdf_target = destination / f"pdf_{source.stem}_solution.qmd"
        expected.add(pdf_target)
        pdf_rendered = sanitize(
            original,
            "solution",
            filename=str(source),
            preserve_needspace=True,
        )
        write_if_changed(pdf_target, add_solution_metadata(pdf_rendered, source.stem))
        written.append(pdf_target)
        include = includes / f"_{source.stem}_solution.qmd"
        expected.add(include)
        write_if_changed(include, solution_include(original, filename=str(source)))
        written.append(include)
    for stale in destination.glob("session_*_*.qmd"):
        if stale not in expected:
            stale.unlink()
    for stale in destination.glob("pdf_session_*_solution.qmd"):
        if stale not in expected:
            stale.unlink()
    for stale in includes.glob("_session_*_solution.qmd"):
        if stale not in expected:
            stale.unlink()
    # Generated render products and published files for removed exercises must
    # not survive merely because the corresponding Make target disappeared.
    stems = {source.stem for source in sources}
    for directory in (destination / "_rendered", root / "_site" / "exercises"):
        if not directory.is_dir():
            continue
        for artifact in directory.glob("session_*"):
            match = re.match(r"^(session_\d+(?:_[a-z]+)?)_(?:assign|solution)", artifact.name)
            if match and match.group(1) not in stems:
                if artifact.is_dir():
                    shutil.rmtree(artifact)
                else:
                    artifact.unlink()
        for html in directory.glob("session_*.html"):
            html.unlink()
        for internal_pdf in directory.glob("pdf_session_*_solution.pdf"):
            internal_pdf.unlink()
    sync_tree(source_data, root / "_site" / "exercises" / "data")
    return written


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        written = build(args.root)
    except ExerciseSyntaxError as error:
        parser.exit(1, f"error: {error}\n")
    print(f"Generated {len(written)} exercise artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
