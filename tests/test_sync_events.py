import unittest
from scripts.sync_events import default_materials, normalize, select

class SyncEventsTest(unittest.TestCase):
    def test_select_explicit_title_contains(self):
        events = [{'title': 'Course A', 'start': '2027-01-01 09:00', 'end': '2027-01-01 10:00'}]
        self.assertEqual(select(events, {'title_contains': 'Course A'}), events)

    def test_default_materials_use_session_paths(self):
        self.assertEqual(
            default_materials(1, 'lecture'),
            [{'type': 'slides', 'path': 'slides/session_01.html'}],
        )
        self.assertEqual(
            default_materials(2, 'exercise'),
            [{'type': 'exercise', 'path': 'exercises/session_01.html'}],
        )

    def test_normalize_adds_generated_id(self):
        event = normalize({'title': 'Course A', 'start': '2027-01-01 09:00', 'end': '2027-01-01 10:00'})
        self.assertTrue(event['event_id'].startswith('generated-'))
        self.assertEqual(event['date'], '2027-01-01')

if __name__ == '__main__':
    unittest.main()
