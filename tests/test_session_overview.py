from datetime import date
import unittest
from scripts.session_overview import session_status

class SessionOverviewTest(unittest.TestCase):
    def test_session_status_values(self):
        self.assertEqual(session_status({'date': '2027-01-01'}, date(2027, 1, 2))[0], '🟢 Completed')
        self.assertEqual(session_status({'date': '2027-01-02'}, date(2027, 1, 2))[0], '🟡 Today')
        self.assertEqual(session_status({'date': '2027-01-03'}, date(2027, 1, 2))[0], '⚪ Upcoming')

if __name__ == '__main__':
    unittest.main()
