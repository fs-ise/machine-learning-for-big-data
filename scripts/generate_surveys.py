"""Generate Quarto survey fragments from the canonical course metadata."""

from pathlib import Path
import re

import yaml


SESSION_RE = re.compile(r"^(session-\d+)-")


def configured_surveys(course: dict) -> dict[str, str]:
    """Return configured lecture survey URLs, rejecting conflicting values."""
    surveys: dict[str, str] = {}
    for event in course.get("events", []):
        match = SESSION_RE.match(event.get("session_id", ""))
        if not match:
            continue
        session = match.group(1).replace("-", "_")
        for material in event.get("materials", []):
            value = material.get("survey_url")
            if not isinstance(value, str) or not value.strip() or value.strip().upper() == "TODO":
                continue
            url = value.strip()
            previous = surveys.get(session)
            if previous is not None and previous != url:
                raise ValueError(f"Conflicting survey URLs for {session}")
            surveys[session] = url
    return surveys


def generate(root: Path) -> None:
    course = yaml.safe_load((root / "course.yml").read_text(encoding="utf-8"))
    surveys = configured_surveys(course)
    output = root / "_generated" / "surveys"
    output.mkdir(parents=True, exist_ok=True)

    sessions = {
        match.group(1).replace("-", "_")
        for event in course.get("events", [])
        if (match := SESSION_RE.match(event.get("session_id", "")))
    }
    for session in sessions:
        number = int(session.removeprefix("session_"))
        url = surveys.get(session)
        slide = "<!-- No survey URL configured. -->\n"
        exercise = "<!-- No survey URL configured. -->\n"
        if url:
            slide = f'''## Survey: Session {number} {{data-state="hide-menubar"}}

<br><br>

::: {{style="display:flex; justify-content:center;"}}

{{{{< qrcode "{url}" width=400 height=400 >}}}}

:::

<br><br>

[{url}]({url})

::: aside
Note: Responses may be analyzed and published in anonymized form.

Please complete the survey before you leave today — thank you 🙏
:::
'''
            exercise = (
                f"Before you wrap up, please complete the Session {number} survey "
                f'here: [{url}]({url}){{target="_blank"}}. Thank you 🙏\n'
            )
        (output / f"{session}-slide.qmd").write_text(slide, encoding="utf-8")
        (output / f"{session}-exercise.qmd").write_text(exercise, encoding="utf-8")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1])
