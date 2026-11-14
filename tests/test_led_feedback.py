"""Run with: python3 -m unittest discover -s tests -v"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "led_demo" / "python"))
from led_feedback import COLS, EVENTS, ROWS, render_frame  # noqa: E402


class LedFeedbackTests(unittest.TestCase):
    def test_every_state_has_valid_pixels(self):
        cases = [("ready", {}), ("thinking", {}), ("correct", {}),
                 ("incorrect", {}), ("error", {})]
        cases += [("selected", {"answer": letter}) for letter in "ABCDE"]
        cases += [("hint", {"hint_level": level}) for level in (1, 2, 3)]
        self.assertEqual(set(EVENTS), {event for event, _ in cases})
        for event, arguments in cases:
            with self.subTest(event=event, arguments=arguments):
                frame = render_frame(event, **arguments)
                self.assertEqual(len(frame), ROWS)
                self.assertTrue(all(len(row) == COLS for row in frame))
                self.assertTrue(all(pixel in (0, 7) for row in frame for pixel in row))
                self.assertGreater(sum(pixel > 0 for row in frame for pixel in row), 0)

    def test_distinct_feedback_and_hint_levels(self):
        self.assertNotEqual(render_frame("correct"), render_frame("incorrect"))
        self.assertEqual(len({render_frame("hint", hint_level=n) for n in (1, 2, 3)}), 3)
        self.assertEqual(len({render_frame("selected", answer=c) for c in "ABCDE"}), 5)

    def test_invalid_events_and_arguments_are_rejected(self):
        invalid = [("solved", {}), ("selected", {}), ("selected", {"answer": "F"}),
                   ("selected", {"answer": "AB"}), ("hint", {"hint_level": 0}),
                   ("hint", {"hint_level": True}), ("correct", {"answer": "B"}),
                   ("ready", {"hint_level": 1})]
        for event, arguments in invalid:
            with self.subTest(event=event, arguments=arguments):
                with self.assertRaises(ValueError):
                    render_frame(event, **arguments)


if __name__ == "__main__":
    unittest.main()
