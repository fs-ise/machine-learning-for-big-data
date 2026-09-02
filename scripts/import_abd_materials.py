#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path
from urllib.parse import unquote, urlsplit

import colrev.loader.load_utils
import colrev.writer.write_utils


SOURCE = Path("/home/gerit/repos/analytics-and-big-data")
TARGET = Path("/home/gerit/repos/machine-learning-for-big-data")

CONTENT_DIRS = ("slides", "exercises", "notes")

DEPENDENCY_EXTENSIONS = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".json",
    ".parquet",
    ".rds",
    ".rda",
    ".rdata",
    ".txt",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
    ".mp4",
    ".webm",
    ".mp3",
    ".wav",
    ".html",
    ".htm",
    ".tex",
    ".md",
    ".qmd",
    ".css",
    ".js",
    ".r",
    ".R",
    ".py",
    ".sql",
}

TEXT_EXTENSIONS = {
    ".qmd",
    ".md",
    ".html",
    ".htm",
    ".tex",
    ".css",
    ".js",
    ".r",
    ".R",
    ".py",
    ".sql",
}

EXTENSION_PATTERN = "|".join(
    re.escape(extension)
    for extension in sorted(DEPENDENCY_EXTENSIONS, key=len, reverse=True)
)

REFERENCE_PATTERNS = [
    # Markdown links and images:
    # [text](path/file.csv)
    # ![](images/figure.png)
    re.compile(r"!?\[[^\]]*]\(([^)]+)\)"),

    # Quarto includes:
    # {{< include file.qmd >}}
    re.compile(r"\{\{<\s*include\s+([^\s>]+)"),

    # CSS:
    # url(images/foo.png)
    re.compile(r"url\(([^)]+)\)"),

    # Quoted paths in code or markup:
    # read_csv("data/file.csv")
    re.compile(
        rf"""["']([^"'<>]+(?:{EXTENSION_PATTERN}))["']"""
    ),
]

# Pandoc/Quarto citations such as:
#
#   @Wickham2014
#   [@Wickham2014]
#   [@Wickham2014; @ChenChan2024]
#
# Citation keys are deliberately restricted to letters, digits,
# underscores, and hyphens. In particular, trailing punctuation such
# as "." or ":" is not included in the extracted key.
CITATION_RE = re.compile(
    r"(?<![\w@])@([A-Za-z0-9][A-Za-z0-9_-]*)"
)


def run_git(repo: Path, *args: str) -> str:
    """Run git in a repository and return stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def check_repositories() -> str:
    """Validate repositories and return the source HEAD SHA."""
    for repo in (SOURCE, TARGET):
        if not repo.is_dir():
            raise FileNotFoundError(
                f"Repository not found: {repo}"
            )

        run_git(
            repo,
            "rev-parse",
            "--show-toplevel",
        )

    source_status = run_git(
        SOURCE,
        "status",
        "--porcelain",
    )

    if source_status:
        raise RuntimeError(
            "Source repository has uncommitted changes.\n"
            "Commit or discard them before creating the migration baseline."
        )

    target_status = run_git(
        TARGET,
        "status",
        "--porcelain",
    )

    if target_status:
        print(
            "WARNING: target repository has uncommitted changes.",
            file=sys.stderr,
        )

    return run_git(
        SOURCE,
        "rev-parse",
        "HEAD",
    )


def sha256(path: Path) -> str:
    """Calculate the SHA-256 digest of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def same_file(
    source: Path,
    target: Path,
) -> bool:
    """Return whether two files are byte-for-byte identical."""
    if not target.is_file():
        return False

    if source.stat().st_size != target.stat().st_size:
        return False

    return sha256(source) == sha256(target)


def copy_file(
    source: Path,
    target: Path,
    *,
    dry_run: bool,
) -> None:
    """Copy a file without overwriting different target content."""
    relative_target = target.relative_to(TARGET)

    if target.exists():
        if same_file(source, target):
            print(f"UNCHANGED {relative_target}")
            return

        raise RuntimeError(
            "Refusing to overwrite a different target file:\n"
            f"  source: {source}\n"
            f"  target: {target}"
        )

    print(f"COPY      {relative_target}")

    if dry_run:
        return

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        source,
        target,
    )


def collect_content_files() -> list[Path]:
    """Collect source QMD files from slides, exercises, and notes."""
    files: list[Path] = []

    for dirname in CONTENT_DIRS:
        root = SOURCE / dirname

        if not root.exists():
            continue

        files.extend(
            path
            for path in root.rglob("*.qmd")
            if path.is_file()
        )

    return sorted(files)


def clean_reference(
    raw_reference: str,
) -> str | None:
    """Normalize a local file reference extracted from source text."""
    reference = raw_reference.strip()

    if not reference:
        return None

    # Markdown links can contain an optional title:
    #
    # [text](file.csv "title")
    #
    # Paths containing spaces may be enclosed in angle brackets:
    #
    # [text](<file with spaces.csv>)
    if reference.startswith("<") and ">" in reference:
        reference = reference[
            1 : reference.index(">")
        ]
    else:
        reference = reference.split()[0]

    reference = reference.strip(
        "\"'<>"
    )

    if not reference:
        return None

    parts = urlsplit(reference)

    # Ignore external URLs.
    if parts.scheme or parts.netloc:
        return None

    path = unquote(parts.path)

    if not path or path.startswith("#"):
        return None

    return path


def is_inside_source(
    path: Path,
) -> bool:
    """Return whether a resolved path belongs to the source repository."""
    try:
        path.relative_to(SOURCE.resolve())
    except ValueError:
        return False

    return True


def resolve_reference(
    reference: str,
    referring_file: Path,
) -> Path | None:
    """Resolve a local reference against its file and repository root."""
    candidates: list[Path] = []

    if reference.startswith("/"):
        candidates.append(
            SOURCE / reference.lstrip("/")
        )
    else:
        candidates.extend(
            [
                referring_file.parent / reference,
                SOURCE / reference,
            ]
        )

    for candidate in candidates:
        candidate = candidate.resolve()

        if not is_inside_source(candidate):
            continue

        if candidate.is_file():
            return candidate

    return None


def extract_dependencies(
    path: Path,
) -> set[Path]:
    """Extract existing local file dependencies from a text file."""
    try:
        text = path.read_text(
            encoding="utf-8",
        )
    except UnicodeDecodeError:
        return set()

    dependencies: set[Path] = set()

    for pattern in REFERENCE_PATTERNS:
        for match in pattern.finditer(text):
            reference = clean_reference(
                match.group(1)
            )

            if reference is None:
                continue

            dependency = resolve_reference(
                reference,
                path,
            )

            if dependency is None:
                continue

            # Bibliography records are handled separately.
            if dependency.name == "references.bib":
                continue

            dependencies.add(
                dependency
            )

    return dependencies


def collect_dependencies(
    content_files: list[Path],
) -> set[Path]:
    """Recursively collect local dependencies.

    Text dependencies are scanned recursively. For example, an included
    QMD file may itself reference additional datasets or images.
    """
    dependencies: set[Path] = set()
    scanned: set[Path] = set()

    queue: deque[Path] = deque(
        content_files
    )

    while queue:
        path = queue.popleft()

        if path in scanned:
            continue

        scanned.add(path)

        for dependency in extract_dependencies(path):
            if dependency in dependencies:
                continue

            dependencies.add(
                dependency
            )

            if dependency.suffix in TEXT_EXTENSIONS:
                queue.append(
                    dependency
                )

    return dependencies


def extract_citation_keys(
    files: set[Path] | list[Path],
) -> set[str]:
    """Extract Pandoc/Quarto citation keys from imported text files."""
    keys: set[str] = set()

    for path in files:
        if path.suffix not in TEXT_EXTENSIONS:
            continue

        try:
            text = path.read_text(
                encoding="utf-8",
            )
        except UnicodeDecodeError:
            continue

        keys.update(
            CITATION_RE.findall(text)
        )

    return keys


def merge_references(
    files: set[Path] | list[Path],
    *,
    dry_run: bool,
) -> tuple[int, set[str]]:
    """Merge required bibliography records using CoLRev."""
    source_bib = SOURCE / "references.bib"
    target_bib = TARGET / "references.bib"

    if not source_bib.is_file():
        print(
            "No source references.bib found; skipping bibliography."
        )
        return 0, set()

    source_records = (
        colrev.loader.load_utils.load(
            filename=source_bib
        )
    )

    if target_bib.exists():
        target_records = (
            colrev.loader.load_utils.load(
                filename=target_bib
            )
        )
    else:
        target_records = {}

    citation_keys = extract_citation_keys(
        files
    )

    # Intersecting with the bibliography automatically removes Quarto
    # cross-references such as @fig-example and @tbl-results.
    required_keys = (
        citation_keys
        & set(source_records)
    )

    added = 0

    for record_id in sorted(required_keys):
        if record_id in target_records:
            print(
                f"BIB KEEP  {record_id}"
            )
            continue

        print(
            f"BIB ADD   {record_id}"
        )

        target_records[record_id] = (
            source_records[record_id]
        )

        added += 1

    if added and not dry_run:
        colrev.writer.write_utils.write_file(
            target_records,
            filename=target_bib,
        )

    missing_keys = (
        citation_keys
        - set(source_records)
    )

    if missing_keys:
        print(
            "\nCitation-like identifiers not found "
            "in source references.bib:"
        )

        for key in sorted(missing_keys):
            print(
                f"  - {key}"
            )

    return added, required_keys


def verify_files(
    files: set[Path] | list[Path],
) -> None:
    """Verify all copied source files byte-for-byte."""
    failures: list[Path] = []

    for source_file in sorted(files):
        relative_path = (
            source_file.relative_to(SOURCE)
        )

        target_file = (
            TARGET / relative_path
        )

        if not same_file(
            source_file,
            target_file,
        ):
            failures.append(
                relative_path
            )

    if failures:
        formatted = "\n".join(
            f"  - {path}"
            for path in failures
        )

        raise RuntimeError(
            "Verification failed for imported files:\n"
            f"{formatted}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import unchanged Analytics & Big Data teaching "
            "materials into Machine Learning for Big Data."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show what would be copied without "
            "changing target files."
        ),
    )

    args = parser.parse_args()

    source_sha = check_repositories()

    content_files = collect_content_files()

    if not content_files:
        raise RuntimeError(
            "No source QMD files found in "
            "slides/, exercises/, or notes/."
        )

    dependencies = collect_dependencies(
        content_files
    )

    print()
    print("=== Source ===")
    print(
        f"Repository:    {SOURCE}"
    )
    print(
        f"Commit:        {source_sha}"
    )
    print(
        f"QMD files:     {len(content_files)}"
    )
    print(
        f"Dependencies:  {len(dependencies)}"
    )

    imported_files: set[Path] = set()

    print()
    print("=== Teaching materials ===")

    for source_file in content_files:
        relative_path = (
            source_file.relative_to(SOURCE)
        )

        copy_file(
            source_file,
            TARGET / relative_path,
            dry_run=args.dry_run,
        )

        imported_files.add(
            source_file
        )

    print()
    print("=== Referenced datasets / images / includes ===")

    for source_file in sorted(dependencies):
        relative_path = (
            source_file.relative_to(SOURCE)
        )

        copy_file(
            source_file,
            TARGET / relative_path,
            dry_run=args.dry_run,
        )

        imported_files.add(
            source_file
        )

    print()
    print("=== Bibliography ===")

    added_references, required_references = (
        merge_references(
            imported_files,
            dry_run=args.dry_run,
        )
    )

    if not args.dry_run:
        print()
        print("=== Verification ===")

        verify_files(
            imported_files
        )

        print(
            f"Verified {len(imported_files)} imported "
            "files byte-for-byte using SHA-256."
        )

    print()
    print("=== Summary ===")
    print(
        f"Source commit:        {source_sha}"
    )
    print(
        f"Content files:        {len(content_files)}"
    )
    print(
        f"Dependencies:         {len(dependencies)}"
    )
    print(
        f"Required references:  {len(required_references)}"
    )
    print(
        f"References added:     {added_references}"
    )

    if args.dry_run:
        print()
        print(
            "Dry run only: no files were changed."
        )

    print()
    print("Add to changelog.qmd:")
    print()
    print(
        "- Source repository: "
        "`fs-ise/analytics-and-big-data`"
    )
    print(
        f"- Source commit: `{source_sha}`"
    )


if __name__ == "__main__":
    main()