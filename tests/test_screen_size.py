import sys
import unittest

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from recommender import parse_screen_size


class TestScreenSizeParsing(unittest.TestCase):
    def test_parse_screen_size_examples(self):
        cases = [
            ("Lenovo Ideapad 15.6\" FHD", 15.6),
            ("14 in\u00e7", 14.0),
            ("16.0-inch QHD", 16.0),
            ("13.Nesil i5 15.6 FHD", 15.6),
            ("144Hz 15.6 FHD", 15.6),
            ("512GB SSD 14\" IPS", 14.0),
            ("Ekran 15,6 FHD", 15.6),
            ("Notebook Windows 11 Pro", None),
        ]

        for text, expected in cases:
            result = parse_screen_size(text)
            if expected is None:
                self.assertIsNone(result)
            else:
                self.assertIsInstance(result, float)
                self.assertEqual(result, expected)
