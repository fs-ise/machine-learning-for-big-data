from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Any
try:
    from scripts import simple_yaml as yaml
except ModuleNotFoundError:
    import simple_yaml as yaml
ROOT = Path(__file__).resolve().parents[1]
def load_yaml(path: Path) -> Any: return yaml.safe_load(path.read_text()) or {}
def session_status(session: dict[str, Any], today: date | None = None) -> tuple[str, str]:
    today = today or date.today(); value = session.get('date') or session.get('start_date')
    if not value: return '⚪ Upcoming', 'status-upcoming'
    day = value.date() if isinstance(value, datetime) else value if isinstance(value, date) else datetime.fromisoformat(str(value)).date()
    return ('🟢 Completed','status-completed') if day < today else ('🟡 Today','status-today') if day == today else ('⚪ Upcoming','status-upcoming')
def load_sessions(root: Path = ROOT) -> list[dict[str, Any]]:
    generated = root / 'data' / 'sessions.generated.yml'
    return (load_yaml(generated).get('sessions', []) if generated.exists() else load_yaml(root / 'course.yml').get('sessions', []))
def markdown_table(root: Path = ROOT, today: date | None = None) -> str:
    rows = ['| Status | Session | Date | Time | Location | Materials |', '|---|---|---|---|---|---|']
    for s in load_sessions(root):
        status, _ = session_status(s, today); title = s.get('title', s.get('session_id', 'Session')); subtitle = s.get('subtitle')
        name = f"{title}: {subtitle}" if subtitle else title; date_text = str(s.get('date') or s.get('start_date') or 'TBD')
        time_text = '–'.join(x for x in [str(s.get('start','')), str(s.get('end',''))] if x) or 'TBD'; location = s.get('location') or 'TBD'
        links = [f"[{label}]({s[key]})" for label, key in [('Slides','slides'),('Notes','notes'),('Exercise','exercise')] if s.get(key)]
        rows.append(f"| {status} | {name} | {date_text} | {time_text} | {location} | {' · '.join(links)} |")
    return '\n'.join(rows)
