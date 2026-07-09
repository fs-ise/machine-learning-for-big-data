from __future__ import annotations

import argparse
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from scripts import simple_yaml as yaml
except ModuleNotFoundError:
    import simple_yaml as yaml


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_URL = (
    "https://raw.githubusercontent.com/fs-ise/handbook/"
    "main/data/events.yaml"
)


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(
        path.read_text(encoding="utf-8")
    ) or []


def load_remote_yaml(
    url: str,
    *,
    cache_path: Path,
    max_attempts: int = 5,
) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "fs-ise-course-event-sync/1.0",
            "Accept": "text/plain, application/yaml, */*",
        },
    )

    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:
                content_bytes = response.read()

            content = content_bytes.decode("utf-8")
            events = yaml.safe_load(content) or []

            cache_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            cache_path.write_text(
                content,
                encoding="utf-8",
            )

            return events

        except urllib.error.HTTPError as exc:
            last_error = exc

            retryable = (
                exc.code == 429
                or 500 <= exc.code < 600
            )

            if not retryable:
                raise

            retry_after = exc.headers.get(
                "Retry-After"
            )

            if (
                retry_after
                and retry_after.isdigit()
            ):
                delay = int(retry_after)
            else:
                delay = min(2**attempt, 30)

            print(
                f"Remote events request failed with "
                f"HTTP {exc.code}; retrying after "
                f"{delay}s "
                f"({attempt + 1}/{max_attempts})."
            )

            time.sleep(delay)

        except urllib.error.URLError as exc:
            last_error = exc

            delay = min(2**attempt, 30)

            print(
                f"Remote events request failed: "
                f"{exc.reason}; retrying after "
                f"{delay}s "
                f"({attempt + 1}/{max_attempts})."
            )

            time.sleep(delay)

        except UnicodeDecodeError as exc:
            raise SystemExit(
                f"Could not decode remote YAML from "
                f"{url} as UTF-8."
            ) from exc

    if cache_path.exists():
        print(
            "WARNING: Remote events unavailable. "
            f"Using cached events from {cache_path}."
        )

        return load_yaml(cache_path)

    raise SystemExit(
        f"Could not download events from {url} "
        "and no cached copy is available. "
        f"Last error: {last_error}"
    )


def parse_semester(
    semester: str,
) -> tuple[date, date]:
    try:
        year_text, term = semester.split(
            "-",
            maxsplit=1,
        )
        year = int(year_text)

    except (ValueError, AttributeError) as exc:
        raise SystemExit(
            "Invalid course.semester. "
            "Expected format YYYY-WiSe or YYYY-SuSe."
        ) from exc

    if term == "WiSe":
        return (
            date(year, 8, 20),
            date(year, 12, 30),
        )

    if term == "SuSe":
        return (
            date(year, 2, 1),
            date(year, 5, 15),
        )

    raise SystemExit(
        "Invalid course.semester. "
        "Expected format YYYY-WiSe or YYYY-SuSe."
    )


def get_title_match(
    course_config: dict[str, Any],
) -> str:
    match = (
        course_config
        .get("schedule", {})
        .get("handbook_event_match")
    )

    if isinstance(match, str) and match.strip():
        return match.strip()

    if isinstance(match, dict):
        title_contains = match.get(
            "title_contains"
        )

        if (
            isinstance(title_contains, str)
            and title_contains.strip()
        ):
            return title_contains.strip()

    raise SystemExit(
        "Configure schedule.handbook_event_match "
        "as a title substring."
    )


def select_events(
    events: list[dict[str, Any]],
    *,
    title_match: str,
    semester_start: date,
    semester_end: date,
) -> list[dict[str, Any]]:
    title_match_folded = title_match.casefold()

    selected: list[dict[str, Any]] = []

    for event in events:
        title = str(
            event.get("title", "")
        )

        if (
            title_match_folded
            not in title.casefold()
        ):
            continue

        try:
            start = datetime.fromisoformat(
                str(event["start"])
            )

            datetime.fromisoformat(
                str(event["end"])
            )

        except (KeyError, ValueError) as exc:
            raise SystemExit(
                "Matched event has invalid or "
                f"missing start/end: {event!r}"
            ) from exc

        if (
            semester_start
            <= start.date()
            <= semester_end
        ):
            selected.append(event)

    if not selected:
        raise SystemExit(
            "No handbook events matched "
            f"title={title_match!r} in "
            f"{semester_start.isoformat()}.."
            f"{semester_end.isoformat()}."
        )

    selected.sort(
        key=lambda event: (
            datetime.fromisoformat(
                str(event["start"])
            ),
            datetime.fromisoformat(
                str(event["end"])
            ),
            str(event.get("source_uid", "")),
        )
    )

    return selected


def normalize_event(
    event: dict[str, Any],
) -> dict[str, Any]:
    start = datetime.fromisoformat(
        str(event["start"])
    )

    end = datetime.fromisoformat(
        str(event["end"])
    )

    source_uid = event.get("source_uid")

    if (
        source_uid is None
        or not str(source_uid).strip()
    ):
        raise SystemExit(
            "Matched handbook event has no source_uid: "
            f"{event!r}"
        )

    return {
        "date": start.date().isoformat(),
        "start": start.strftime("%H:%M"),
        "end": end.strftime("%H:%M"),
        "location": str(
            event.get("location")
            or "Room TBD"
        ),
        "event_id": str(source_uid),
    }


def default_event_type(
    position: int,
) -> str:
    """
    Return the initial event type based on its
    one-based position:

        1 -> lecture
        2 -> exercise
        3 -> lecture
        4 -> exercise
        ...
    """

    if position % 2 == 1:
        return "lecture"

    return "exercise"


def default_materials(
    position: int,
    event_type: str,
) -> list[dict[str, str]]:
    """
    Generate initial material references.

    Lecture and exercise numbers are based on the
    alternating lecture/exercise sequence.
    """

    material_number = (position + 1) // 2

    if event_type == "lecture":
        return [
            {
                "type": "slides",
                "path": (
                    f"slides/"
                    f"session_{material_number:02d}.html"
                ),
            },
        ]

    return [
        {
            "type": "exercise",
            "path": (
                f"exercises/"
                f"session_{material_number:02d}.html"
            ),
        },
    ]


def apply_missing_event_defaults(
    events: list[dict[str, Any]],
) -> None:
    """
    Add type and materials only when the fields are missing.

    Existing user changes are preserved, including an explicitly
    empty materials list.
    """

    for position, event in enumerate(
        events,
        start=1,
    ):
        if "type" not in event:
            event["type"] = default_event_type(
                position
            )

        if "materials" not in event:
            event["materials"] = default_materials(
                position,
                str(event["type"]),
            )


def get_next_event_number(
    events: list[dict[str, Any]],
) -> int:
    numbers: list[int] = []

    for event in events:
        event_id = str(
            event.get("event_id", "")
        )

        match = re.fullmatch(
            r"event-(\d+)",
            event_id,
        )

        if match:
            numbers.append(
                int(match.group(1))
            )

    return max(numbers, default=0) + 1


def merge_events(
    handbook_events: list[dict[str, Any]],
    existing_events: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    int,
    int,
]:
    events = [
        dict(event)
        for event in existing_events
    ]

    # Backfill defaults for events created before
    # type/materials were introduced.
    apply_missing_event_defaults(events)

    event_index_by_event_id: dict[str, int] = {}

    for index, event in enumerate(events):
        event_id = event.get("event_id")

        if event_id is None:
            continue

        event_id_string = str(event_id)

        if (
            event_id_string
            in event_index_by_event_id
        ):
            raise SystemExit(
                "Duplicate event_id in existing events: "
                f"{event_id_string}"
            )

        event_index_by_event_id[
            event_id_string
        ] = index

    next_event_number = get_next_event_number(
        events
    )

    n_updated = 0
    n_added = 0

    seen_source_uids: set[str] = set()

    for handbook_event in handbook_events:
        event_data = normalize_event(handbook_event)

        event_id = str(
            event_data["event_id"]
        )

        if event_id in seen_source_uids:
            raise SystemExit(
                "Duplicate source_uid in matched events: "
                f"{event_id}"
            )

        seen_source_uids.add(event_id)

        existing_index = (
            event_index_by_event_id.get(
                event_id
            )
        )

        if existing_index is not None:
            updated_event = dict(
                events[existing_index]
            )

            # Only update event-controlled fields.
            # User-controlled type and materials are preserved.
            updated_event.update(
                event_data
            )

            events[existing_index] = (
                updated_event
            )

            n_updated += 1
            continue

        position = len(events) + 1

        event_type = default_event_type(
            position
        )

        new_event = {
            "event_id": (
                f"event-{next_event_number:02d}"
            ),
            "type": event_type,
            **event_data,
            "materials": default_materials(
                position,
                event_type,
            ),
        }

        events.append(new_event)

        event_index_by_event_id[
            event_id
        ] = len(events) - 1

        next_event_number += 1
        n_added += 1

    return (
        events,
        n_updated,
        n_added,
    )


def compact_list_item_dashes(
    rendered: str,
) -> str:
    """
    Convert:

        -
          key: value

    into:

        - key: value

    at every indentation level.
    """

    lines = rendered.splitlines()

    result: list[str] = []

    index = 0

    while index < len(lines):
        line = lines[index]

        if (
            line.strip() == "-"
            and index + 1 < len(lines)
        ):
            next_line = lines[index + 1]

            current_indent = (
                len(line) - len(line.lstrip())
            )

            next_indent = (
                len(next_line)
                - len(next_line.lstrip())
            )

            if next_indent > current_indent:
                indent = " " * current_indent

                result.append(
                    f"{indent}- "
                    f"{next_line.lstrip()}"
                )

                index += 2
                continue

        result.append(line)
        index += 1

    return "\n".join(result)


def render_events(
    events: list[dict[str, Any]],
) -> str:
    rendered = yaml.safe_dump(
        {
            "events": events,
        },
        sort_keys=False,
        allow_unicode=True,
    ).rstrip()

    return compact_list_item_dashes(
        rendered
    )


def find_top_level_events_blocks(
    lines: list[str],
) -> list[tuple[int, int]]:
    """
    Find all top-level events or legacy sessions blocks.

    Handles both:

        events: []

    and:

        events:
          - event_id: ...
    """

    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(
            r"^(events|sessions)\s*:",
            line,
        )
    ]

    blocks: list[tuple[int, int]] = []

    for start in starts:
        end = start + 1

        while end < len(lines):
            line = lines[end]

            if (
                line.strip()
                and not line[0].isspace()
            ):
                break

            end += 1

        blocks.append(
            (start, end)
        )

    return blocks


def replace_events_blocks(
    course_text: str,
    events: list[dict[str, Any]],
) -> str:
    """
    Replace all top-level events blocks with exactly one
    synchronized events block.

    Also repairs files containing duplicate events blocks.
    """

    lines = course_text.splitlines()

    blocks = find_top_level_events_blocks(
        lines
    )

    rendered_lines = render_events(
        events
    ).splitlines()

    if not blocks:
        result = list(lines)

        while (
            result
            and not result[-1].strip()
        ):
            result.pop()

        result.append("")
        result.extend(rendered_lines)

        return "\n".join(result) + "\n"

    first_start = blocks[0][0]

    indices_to_remove: set[int] = set()

    for start, end in blocks:
        indices_to_remove.update(
            range(start, end)
        )

    result: list[str] = []

    inserted = False

    for index, line in enumerate(lines):
        if (
            index == first_start
            and not inserted
        ):
            result.extend(rendered_lines)
            inserted = True

        if index in indices_to_remove:
            continue

        result.append(line)

    if not inserted:
        result.extend(rendered_lines)

    while (
        len(result) >= 2
        and not result[-1].strip()
        and not result[-2].strip()
    ):
        result.pop()

    return "\n".join(result) + "\n"


def load_events(
    *,
    source: Path,
    url: str,
    cache_path: Path,
) -> tuple[list[dict[str, Any]], str]:
    if source.exists():
        events = load_yaml(source)

        try:
            source_label = str(
                source.relative_to(ROOT)
            )

        except ValueError:
            source_label = str(source)

        return events, source_label

    events = load_remote_yaml(
        url,
        cache_path=cache_path,
    )

    return events, url



# Backward-compatible aliases for older tests and helper scripts.
merge_sessions = merge_events
render_sessions = render_events
find_top_level_sessions_blocks = find_top_level_events_blocks
replace_sessions_blocks = replace_events_blocks


def select(
    events: list[dict[str, Any]],
    match: dict[str, Any],
) -> list[dict[str, Any]]:
    title_contains = str(match.get("title_contains", ""))

    return [
        event
        for event in events
        if title_contains.casefold() in str(event.get("title", "")).casefold()
    ]


def normalize(event: dict[str, Any]) -> dict[str, Any]:
    event = dict(event)

    if not event.get("source_uid"):
        event["source_uid"] = (
            "generated-"
            f"{event.get('title', 'event')}-"
            f"{event.get('start', '')}"
        )

    return normalize_event(event)

def main(
    argv: list[str] | None = None,
) -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--events",
        help=(
            "Optional path to a local events.yaml. "
            "Defaults to schedule.source_path."
        ),
    )

    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
    )

    args = parser.parse_args(argv)

    course_path = ROOT / "course.yml"

    course_text = course_path.read_text(
        encoding="utf-8"
    )

    course_config = (
        yaml.safe_load(course_text)
        or {}
    )

    semester = str(
        course_config
        .get("course", {})
        .get("semester", "")
    )

    if not semester:
        raise SystemExit(
            "Missing course.semester in course.yml."
        )

    semester_start, semester_end = (
        parse_semester(semester)
    )

    title_match = get_title_match(
        course_config
    )

    source_path_value = (
        args.events
        or course_config
        .get("schedule", {})
        .get(
            "source_path",
            "data/events.yaml",
        )
    )

    source = Path(source_path_value)

    if not source.is_absolute():
        source = ROOT / source

    cache_path = (
        ROOT
        / ".cache"
        / "handbook-events.yaml"
    )

    events, source_label = load_events(
        source=source,
        url=args.url,
        cache_path=cache_path,
    )

    if not isinstance(events, list):
        raise SystemExit(
            "events.yaml must contain "
            "a list of events."
        )

    selected_events = select_events(
        events,
        title_match=title_match,
        semester_start=semester_start,
        semester_end=semester_end,
    )

    existing_events = (
        course_config.get("events")
        or course_config.get("sessions")
        or []
    )

    if not isinstance(
        existing_events,
        list,
    ):
        raise SystemExit(
            "course.yml events must be "
            "a list or empty."
        )

    (
        events,
        n_updated,
        n_added,
    ) = merge_events(
        selected_events,
        existing_events,
    )

    updated_course_text = replace_events_blocks(
        course_text,
        events,
    )

    course_path.write_text(
        updated_course_text,
        encoding="utf-8",
    )

    print(
        f"Updated {course_path}: "
        f"{n_updated} events updated, "
        f"{n_added} events added, "
        f"{len(events)} events total."
    )

    print(
        f"Event source: {source_label}"
    )


if __name__ == "__main__":
    main()