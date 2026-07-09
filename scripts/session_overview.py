from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from scripts import simple_yaml as yaml
except ModuleNotFoundError:
    import simple_yaml as yaml


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text()) or {}


def session_status(
    session: dict[str, Any],
    today: date | None = None,
) -> tuple[str, str]:
    today = today or date.today()
    value = session.get("date") or session.get("start_date")

    if not value:
        return "⚪ Upcoming", "status-upcoming"

    if isinstance(value, datetime):
        day = value.date()
    elif isinstance(value, date):
        day = value
    else:
        day = datetime.fromisoformat(str(value)).date()

    if day < today:
        return "🟢 Completed", "status-completed"

    if day == today:
        return "🟡 Today", "status-today"

    return "⚪ Upcoming", "status-upcoming"


def load_events(root: Path = ROOT) -> list[dict[str, Any]]:
    config = load_yaml(root / "course.yml")
    return config.get("events", config.get("sessions", []))


# Backward-compatible name for existing imports.
def load_sessions(root: Path = ROOT) -> list[dict[str, Any]]:
    return load_events(root)


def material_source_path(path: str) -> str:
    material_path = Path(path)

    if material_path.suffix == ".html":
        return str(material_path.with_suffix(".qmd"))

    return path


def read_material_title(root: Path, path: str) -> str | None:
    source = root / material_source_path(path)

    if not source.exists() or not source.is_file():
        return None

    in_front_matter = False

    for line in source.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped == "---":
            if in_front_matter:
                break

            in_front_matter = True
            continue

        if not in_front_matter:
            continue

        if stripped.startswith("title:"):
            return stripped.split(":", 1)[1].strip().strip('"\'')

    return None


def primary_material(event: dict[str, Any]) -> dict[str, Any] | None:
    preferred = {
        "lecture": ["slides"],
        "exercise": ["exercise"],
        "group presentation": ["slides", "presentation"],
        "group_presentation": ["slides", "presentation"],
    }

    materials = event.get("materials", [])

    if not isinstance(materials, list):
        return None

    event_type = str(event.get("type", "")).strip().casefold()
    preferred_types = preferred.get(event_type, [])

    for material_type in preferred_types:
        for material in materials:
            if str(material.get("type", "")).casefold() == material_type:
                return material

    for material in materials:
        if str(material.get("type", "")).casefold() in {"slides", "exercise"}:
            return material

    return materials[0] if materials else None


def event_badge(event_type: str) -> str:
    labels = {
        "lecture": "Lecture",
        "exercise": "Exercise",
        "group presentation": "Group presentation",
        "group_presentation": "Group presentation",
    }
    label = labels.get(
        event_type.strip().casefold(),
        event_type.replace("_", " ").title() or "Event",
    )
    badge_slug = (
        event_type.strip()
        .casefold()
        .replace("_", "-")
        .replace(" ", "-")
    )
    class_name = f"event-badge event-badge-{badge_slug}"
    return f'<span class="{class_name}">{label}</span>'


def event_title(event: dict[str, Any], root: Path = ROOT) -> str:
    material = primary_material(event)
    title = None

    if material and material.get("path"):
        title = read_material_title(root, str(material["path"]))

    title = title or event.get("title") or event.get("event_id") or "Event"
    badge = event_badge(str(event.get("type", "event")))

    if material and material.get("path"):
        return f"[{title}]({material['path']}) {badge}"

    return f"{title} {badge}"


def material_links(session: dict[str, Any]) -> str:
    labels = {
        "slides": "Slides",
        "notes": "Notes",
        "exercise": "Exercise",
    }

    links = []

    for material in session.get("materials", []):
        material_type = str(material.get("type", "")).strip()
        path = material.get("path")

        if not material_type or not path:
            continue

        label = labels.get(
            material_type,
            material_type.replace("_", " ").title(),
        )
        links.append(f"[{label}]({path})")

    return " · ".join(links)


def markdown_table(
    root: Path = ROOT,
    today: date | None = None,
) -> str:
    rows = [
        "| Status | Title | Date | Time | Location | Materials |",
        "|---|---|---|---|---|---|",
    ]

    for event in load_events(root):
        status, _ = session_status(event, today)

        date_text = str(
            event.get("date")
            or event.get("start_date")
            or "TBD"
        )

        time_text = (
            "–".join(
                value
                for value in [
                    str(event.get("start", "")),
                    str(event.get("end", "")),
                ]
                if value
            )
            or "TBD"
        )

        location = event.get("location") or "TBD"
        materials = material_links(event)

        rows.append(
            f"| {status} | {event_title(event, root)} | {date_text} | "
            f"{time_text} | {location} | {materials} |"
        )

    return "\n".join(rows)
