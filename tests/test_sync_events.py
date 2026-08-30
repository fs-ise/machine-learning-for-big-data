import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts import simple_yaml as yaml
from scripts.sync_events import (
    default_materials,
    get_schedule_config,
    main,
    merge_events,
    normalize_event,
    parse_semester,
    select_events,
)


TZ = ZoneInfo("Europe/Berlin")


def remote_event(**overrides):
    event = {
        "title": "Machine Learning for Big Data",
        "start": "2026-09-04 10:00",
        "end": "2026-09-04 11:30",
        "location": "S2.11",
        "source_uid": "stable-uid",
    }
    event.update(overrides)
    return event


class SyncEventsTest(unittest.TestCase):
    def test_source_configuration_is_read_from_course_yml(self):
        config = {
            "schedule": {
                "timezone": "Europe/Berlin",
                "source": {"type": "yaml", "url": "https://example.test/events.yaml"},
                "event_match": {"title_contains": "Course A"},
            }
        }
        url, title, timezone = get_schedule_config(config)
        self.assertEqual(url, "https://example.test/events.yaml")
        self.assertEqual(title, "Course A")
        self.assertEqual(timezone.key, "Europe/Berlin")

    def test_missing_and_invalid_source_configuration_fails_clearly(self):
        cases = [
            ({}, "Missing schedule"),
            ({"schedule": {}}, "schedule.source"),
            ({"schedule": {"source": {"type": "ics", "url": "https://x.test/a"}}}, "source.type"),
            ({"schedule": {"source": {"type": "yaml"}}}, "source.url"),
            ({"schedule": {"source": {"type": "yaml", "url": "not-a-url"}}}, "source.url"),
        ]
        for config, message in cases:
            with self.subTest(config=config), self.assertRaisesRegex(SystemExit, message):
                get_schedule_config(config)

    def test_missing_match_and_invalid_timezone_fail_clearly(self):
        base = {"schedule": {"source": {"type": "yaml", "url": "https://x.test/a"}}}
        with self.assertRaisesRegex(SystemExit, "event_match.title_contains"):
            get_schedule_config(base)
        base["schedule"]["event_match"] = {"title_contains": "Course"}
        base["schedule"]["timezone"] = "Nowhere/Invalid"
        with self.assertRaisesRegex(SystemExit, "schedule.timezone"):
            get_schedule_config(base)

    def test_title_and_semester_filtering(self):
        events = [
            remote_event(),
            remote_event(title="Another Course", source_uid="other"),
            remote_event(start="2027-01-02 10:00", end="2027-01-02 11:00", source_uid="later"),
        ]
        start, end = parse_semester("2026-WiSe")
        self.assertEqual(
            select_events(events, title_match="machine learning", semester_start=start, semester_end=end, timezone=TZ),
            [events[0]],
        )

    def test_uid_matching_updates_controlled_fields_and_preserves_metadata(self):
        existing = [{
            "session_id": "session-custom",
            "event_id": "stable-uid",
            "type": "workshop",
            "date": "2026-09-01",
            "start": "08:00",
            "end": "09:00",
            "location": "Old room",
            "materials": [{"type": "slides", "path": "custom.html", "survey_url": "https://survey.test"}],
            "survey_url": "https://event-survey.test",
        }]
        merged, updated, added = merge_events([remote_event()], existing, TZ)
        self.assertEqual((updated, added), (1, 0))
        self.assertEqual(
            {key: merged[0][key] for key in ("date", "start", "end", "location", "event_id")},
            {"date": "2026-09-04", "start": "10:00", "end": "11:30", "location": "S2.11", "event_id": "stable-uid"},
        )
        self.assertEqual(merged[0]["type"], "workshop")
        self.assertEqual(merged[0]["materials"], existing[0]["materials"])
        self.assertEqual(merged[0]["survey_url"], existing[0]["survey_url"])
        self.assertEqual(merged[0]["session_id"], "session-custom")

    def test_merge_is_idempotent(self):
        first, _, _ = merge_events([remote_event()], [], TZ)
        second, updated, added = merge_events([remote_event()], first, TZ)
        self.assertEqual(second, first)
        self.assertEqual((updated, added), (1, 0))

    def test_timezone_values_are_normalized_to_schedule_timezone(self):
        normalized = normalize_event(
            remote_event(start="2026-09-04T08:00:00+00:00", end="2026-09-04T09:30:00+00:00"),
            TZ,
        )
        self.assertEqual(normalized["date"], "2026-09-04")
        self.assertEqual(normalized["start"], "10:00")
        self.assertEqual(normalized["end"], "11:30")

    def test_main_uses_configured_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = {
                "course": {"semester": "2026-WiSe"},
                "schedule": {
                    "timezone": "Europe/Berlin",
                    "source": {"type": "yaml", "url": "https://configured.test/events.yaml"},
                    "event_match": {"title_contains": "Machine Learning"},
                },
                "events": [],
            }
            (root / "course.yml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            with patch("scripts.sync_events.ROOT", root), patch(
                "scripts.sync_events.load_remote_yaml", return_value=[remote_event()]
            ) as loader:
                main([])
            self.assertEqual(loader.call_args.args[0], "https://configured.test/events.yaml")
            written = yaml.safe_load((root / "course.yml").read_text(encoding="utf-8"))
            self.assertEqual(written["events"][0]["event_id"], "stable-uid")

    def test_default_materials_use_session_paths(self):
        self.assertEqual(default_materials(1, "lecture"), [{"type": "slides", "path": "slides/session_01.html"}])
        self.assertEqual(default_materials(2, "exercise"), [{"type": "exercise", "path": "exercises/session_01.html"}])


if __name__ == "__main__":
    unittest.main()
