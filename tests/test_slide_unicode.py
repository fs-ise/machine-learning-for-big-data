from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MATH_ALPHANUMERIC_START = 0x1D400
MATH_ALPHANUMERIC_END = 0x1D7FF


class SlideUnicodeTest(unittest.TestCase):
    def test_slides_do_not_use_unicode_mathematical_alphanumerics(self):
        violations = []

        for slide in sorted((REPOSITORY_ROOT / 'slides').rglob('*.qmd')):
            for line_number, line in enumerate(slide.read_text(encoding='utf-8').splitlines(), 1):
                for character in line:
                    code_point = ord(character)
                    if MATH_ALPHANUMERIC_START <= code_point <= MATH_ALPHANUMERIC_END:
                        relative_path = slide.relative_to(REPOSITORY_ROOT)
                        violations.append(
                            f'{relative_path}:{line_number}: {character} (U+{code_point:04X})'
                        )

        self.assertFalse(
            violations,
            'Unicode Mathematical Alphanumeric Symbols found:\n' + '\n'.join(violations),
        )


if __name__ == '__main__':
    unittest.main()
