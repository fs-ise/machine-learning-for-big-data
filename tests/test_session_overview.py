from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.session_overview import markdown_table, session_status


class SessionOverviewTest(unittest.TestCase):
    def test_session_status_values(self):
        self.assertEqual(session_status({'date': '2027-01-01'}, date(2027, 1, 2))[0], '🟢 Completed')
        self.assertEqual(session_status({'date': '2027-01-02'}, date(2027, 1, 2))[0], '🟡 Today')
        self.assertEqual(session_status({'date': '2027-01-03'}, date(2027, 1, 2))[0], '⚪ Upcoming')

    def test_markdown_table_uses_event_material_title_and_badge(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / 'slides').mkdir()
            (root / 'slides' / 'session_01.qmd').write_text(
                '---\nsession: "Session 1"\ntitle: "Big Data"\n---\n',
                encoding='utf-8',
            )
            (root / 'course.yml').write_text(
                '\n'.join(
                    [
                        'events:',
                        '  - type: lecture',
                        '    date: 2027-01-03',
                        "    start: '10:00'",
                        "    end: '11:30'",
                        '    location: Room 1. Room capacity: 30',
                        '    materials:',
                        '      - type: slides',
                        '        path: slides/session_01.html',
                    ]
                ),
                encoding='utf-8',
            )

            table = markdown_table(root, today=date(2027, 1, 2))

        self.assertIn('[Session 1: Big Data](slides/session_01.html) <span class="event-badge event-badge-lecture">Lecture</span>', table)
        self.assertIn('| Status | Title | Date | Time | Location | Materials |', table)
        self.assertIn(
            '<span class="session-status status-upcoming" '
            'data-date="2027-01-03">⚪ Upcoming</span>',
            table,
        )
        self.assertIn('| 10:00–11:30 | Room 1 |', table)
        self.assertNotIn('Room capacity', table)

    def test_exercise_title_comes_from_canonical_source_without_changing_link(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / 'exercises').mkdir()
            (root / 'exercises' / 'session_01.qmd').write_text(
                '---\nsession: "Session 1"\ntitle: "R Setup"\n---\n',
                encoding='utf-8',
            )
            (root / 'course.yml').write_text(
                '\n'.join(
                    [
                        'events:',
                        '  - type: exercise',
                        '    date: 2027-01-03',
                        '    materials:',
                        '      - type: exercise',
                        '        path: exercises/session_01_assign.qmd',
                    ]
                ),
                encoding='utf-8',
            )

            table = markdown_table(root, today=date(2027, 1, 2))

        self.assertIn(
            '[Session 1: R Setup](exercises/session_01_assign.qmd) '
            '<span class="event-badge event-badge-exercise">Exercise</span>',
            table,
        )


if __name__ == '__main__':
    unittest.main()
