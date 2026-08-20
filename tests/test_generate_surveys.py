from pathlib import Path
import tempfile
import unittest

from scripts.generate_surveys import configured_surveys, generate


class GenerateSurveysTest(unittest.TestCase):
    def test_todo_is_not_a_configured_survey(self):
        course = {"events": [{"session_id": "session-06-lecture", "materials": [{"survey_url": "TODO"}]}]}
        self.assertEqual(configured_surveys(course), {})

    def test_generates_url_from_course_and_hides_todo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "course.yml").write_text(
                """events:
  - session_id: session-06-lecture
    materials:
      - survey_url: https://example.test/survey-6
  - session_id: session-07-lecture
    materials:
      - survey_url: TODO
""",
                encoding="utf-8",
            )
            generate(root)

            session_6 = (root / "_generated/surveys/session_06-slide.qmd").read_text()
            session_7 = (root / "_generated/surveys/session_07-slide.qmd").read_text()

        self.assertIn('qrcode "https://example.test/survey-6"', session_6)
        self.assertIn("[https://example.test/survey-6](https://example.test/survey-6)", session_6)
        self.assertEqual(session_7, "<!-- No survey URL configured. -->\n")


if __name__ == "__main__":
    unittest.main()
