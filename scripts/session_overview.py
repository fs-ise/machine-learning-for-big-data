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


def load_sessions(root: Path = ROOT) -> list[dict[str, Any]]:
    return load_yaml(root / "course.yml").get("sessions", [])


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
        "| Status | Session | Date | Time | Location | Materials |",
        "|---|---|---|---|---|---|",
    ]

    for session in load_sessions(root):
        status, _ = session_status(session, today)

        title = session.get(
            "title",
            session.get("session_id", "Session"),
        )
        subtitle = session.get("subtitle")

        name = f"{title}: {subtitle}" if subtitle else title

        date_text = str(
            session.get("date")
            or session.get("start_date")
            or "TBD"
        )

        time_text = (
            "–".join(
                value
                for value in [
                    str(session.get("start", "")),
                    str(session.get("end", "")),
                ]
                if value
            )
            or "TBD"
        )

        location = session.get("location") or "TBD"
        materials = material_links(session)

        rows.append(
            f"| {status} | {name} | {date_text} | "
            f"{time_text} | {location} | {materials} |"
        )

    return "\n".join(rows)