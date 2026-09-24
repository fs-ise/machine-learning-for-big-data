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

    def test_markdown_table_separates_lecture_badge_title_and_materials(self):
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

        status = (
            '<span class="session-status status-upcoming" '
            'data-date="2027-01-03">⚪ Upcoming</span>'
        )
        badge = '<span class="event-badge event-badge-lecture">Lecture</span>'
        self.assertIn('| Status | | Title | Date | Time | Location | Materials |', table)
        self.assertIn('|---|---:|---|---|---|---|---|', table)
        self.assertIn(
            f'| {status} | {badge} | Session 1: Big Data | 2027-01-03 | '
            '10:00–11:30 | Room 1 | [Slides](slides/session_01.html) |',
            table,
        )
        self.assertNotIn('[Session 1: Big Data]', table)
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

        status = (
            '<span class="session-status status-upcoming" '
            'data-date="2027-01-03">⚪ Upcoming</span>'
        )
        badge = '<span class="event-badge event-badge-exercise">Exercise</span>'
        self.assertIn(
            f'| {status} | {badge} | Session 1: R Setup | 2027-01-03 | '
            'TBD | TBD | [Notebook](exercises/session_01_assign.qmd) |',
            table,
        )
        self.assertNotIn('[Session 1: R Setup]', table)
        self.assertNotIn('[Exercise](exercises/session_01_assign.qmd)', table)

    def test_group_presentation_has_separate_badge_and_material_link(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / 'slides').mkdir()
            (root / 'slides' / 'presentations.qmd').write_text(
                '---\ntitle: "Group presentations"\n---\n',
                encoding='utf-8',
            )
            (root / 'course.yml').write_text(
                '\n'.join(
                    [
                        'events:',
                        '  - type: group presentation',
                        '    date: 2027-01-03',
                        '    materials:',
                        '      - type: slides',
                        '        path: slides/presentations.html',
                    ]
                ),
                encoding='utf-8',
            )

            table = markdown_table(root, today=date(2027, 1, 2))

        badge = (
            '<span class="event-badge event-badge-group-presentation">'
            'Group presentation</span>'
        )
        self.assertIn(
            f'| {badge} | Group presentations | 2027-01-03 | TBD | TBD | '
            '[Slides](slides/presentations.html) |',
            table,
        )
        self.assertNotIn('[Group presentations]', table)
        self.assertNotIn(f'[Slides](slides/presentations.html) {badge}', table)


if __name__ == '__main__':
    unittest.main()
