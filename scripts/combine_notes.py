"""Combine session teaching notes into a single, printable Quarto document."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

import yaml


DOCUMENT_TITLE = "Machine Learning for Big Data – Teaching Notes"


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


def combine_notes(paths: Sequence[Path]) -> str:
    """Build a combined QMD string from session files in deterministic order."""
    if not paths:
        raise ValueError("no session note files supplied")

    sections: list[tuple[str, str]] = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        metadata, body = split_front_matter(path.read_text(encoding="utf-8"), path)
        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{path}: YAML front matter requires a non-empty title")
        sections.append((title.strip(), body.rstrip()))

    header = f'''---
title: "{DOCUMENT_TITLE}"
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
        \\usepackage{{etoolbox}}
        \\newcommand{{\\teachingnotesfooterlabel}}{{{DOCUMENT_TITLE}}}
        \\clearpairofpagestyles
        \\ifoot[\\teachingnotesfooterlabel]{{\\teachingnotesfooterlabel}}
        \\ofoot[\\pagemark]{{\\pagemark}}
        \\pagestyle{{scrheadings}}
        \\pretocmd{{\\subsection}}{{\\clearpage}}{{}}{{}}
execute:
  enabled: false
---
'''
    rendered_sections: list[str] = []
    for title, body in sections:
        rendered_sections.append(
            "```{=latex}\n"
            "\\clearpage\n"
            f"\\renewcommand{{\\teachingnotesfooterlabel}}"
            f"{{MLBD -- {latex_escape(title)}}}\n"
            "```\n\n"
            f"# {title}\n\n{body}\n"
        )
    return header + "\n" + "\n".join(rendered_sections)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(combine_notes(args.inputs), encoding="utf-8")


if __name__ == "__main__":
    main()
