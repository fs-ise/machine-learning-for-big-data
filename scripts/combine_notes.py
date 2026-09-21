"""Combine session teaching notes into a single, printable Quarto document."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

DOCUMENT_TITLE = "Machine Learning for Big Data – Teaching Notes"
SESSION_ID_PATTERN = re.compile(r"session-(\d+)(?:-[a-z0-9]+)*")


@dataclass(frozen=True)
class Section:
    """A source document and the labels used for its rendered pages."""

    title: str
    body: str
    page_prefix: str


def split_front_matter(source: str, path: Path) -> tuple[dict[str, Any], str]:
    """Return parsed YAML front matter and the Markdown body."""
    lines = source.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path}: missing YAML front matter")

    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as error:
        raise ValueError(f"{path}: unterminated YAML front matter") from error

    metadata = yaml.safe_load("".join(lines[1:end]))
    if not isinstance(metadata, dict):
        raise ValueError(f"{path}: YAML front matter must be a mapping")
    return metadata, "".join(lines[end + 1 :])


def latex_escape(value: str) -> str:
    """Escape text for a LaTeX command argument."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def session_page_prefix(metadata: dict[str, Any], path: Path) -> str:
    """Return a display prefix such as ``Session-3`` from YAML metadata."""
    session_id = metadata.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(
            f"{path}: YAML front matter requires a session_id such as 'session-03'"
        )
    match = SESSION_ID_PATTERN.fullmatch(session_id)
    if match is None:
        raise ValueError(
            f"{path}: invalid session_id {session_id!r}; expected 'session-<number>'"
        )
    return f"Session-{int(match.group(1))}"


def read_checklist(path: Path) -> tuple[str, str]:
    """Return the title and body of a heading-led checklist fragment."""
    source = path.read_text(encoding="utf-8")
    first_content = next((line for line in source.splitlines() if line.strip()), "")
    heading = re.fullmatch(r"#\s+(.+?)\s*", first_content)
    if heading is None or not heading.group(1).strip():
        raise ValueError(f"{path}: checklist requires a non-empty level-1 heading")

    title = heading.group(1).strip()
    body = source.splitlines(keepends=True)
    heading_index = next(i for i, line in enumerate(body) if line.strip())
    return title, "".join(body[heading_index + 1 :]).strip()


def combine_notes(paths: Sequence[Path], checklist: Path | None = None) -> str:
    """Build a combined QMD string from session files in deterministic order."""
    if not paths:
        raise ValueError("no session note files supplied")

    sections: list[Section] = []
    if checklist is not None:
        title, body = read_checklist(checklist)
        sections.append(Section(title, body, "Checklist"))
    for path in sorted(paths, key=lambda item: item.as_posix()):
        metadata, body = split_front_matter(path.read_text(encoding="utf-8"), path)
        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{path}: YAML front matter requires a non-empty title")
        sections.append(
            Section(title.strip(), body.rstrip(), session_page_prefix(metadata, path))
        )

    header = f"""---
title: "{DOCUMENT_TITLE}"
execute:
  enabled: true
format:
  pdf:
    papersize: a4
    toc: true
    toc-depth: 1
    number-sections: false
    geometry:
      - left=1.5cm
      - right=1.5cm
      - top=1.5cm
      - bottom=2.2cm
      - includefoot
      - footskip=0.9cm
    filters:
      - ../scripts/html_br_to_linebreak.lua
    include-in-header:
      text: |
        \\usepackage{{scrlayer-scrpage}}
        \\DeclareTOCStyleEntry[
          pagenumberwidth=8em,
          rightindent=9em
        ]{{tocline}}{{section}}
        \\AfterTOCHead[toc]{{%
          \\noindent\\textbf{{Section}}\\hfill\\textbf{{Pages start with}}\\par
          \\smallskip
        }}
        \\newcommand{{\\teachingnotesfooterlabel}}{{{DOCUMENT_TITLE}}}
        \\clearpairofpagestyles
        \\ifoot[\\teachingnotesfooterlabel]{{\\teachingnotesfooterlabel}}
        \\ofoot[\\pagemark]{{\\pagemark}}
        \\pagestyle{{scrheadings}}
---
"""
    rendered_sections: list[str] = []
    for section in sections:
        rendered_sections.append(
            "```{=latex}\n"
            "\\clearpage\n"
            f"\\renewcommand{{\\thepage}}{{{section.page_prefix}/p\\arabic{{page}}}}\n"
            "\\setcounter{page}{1}\n"
            f"\\renewcommand{{\\teachingnotesfooterlabel}}"
            f"{{MLBD -- {latex_escape(section.title)}}}\n"
            "```\n\n"
            f"# {section.title}\n\n{section.body}\n"
        )
    return header + "\n" + "\n".join(rendered_sections)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--checklist", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        combine_notes(args.inputs, checklist=args.checklist), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
