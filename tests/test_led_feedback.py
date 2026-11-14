"""Run with: python3 -m unittest discover -s tests -v"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "led_demo" / "python"))
from led_feedback import BRIGHTNESS, COLS, EVENTS, ROWS, publish, render_frame, rgb_for_event  # noqa: E402


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
                self.assertTrue(all(pixel in (0, BRIGHTNESS[event]) for row in frame for pixel in row))
                self.assertGreater(sum(pixel > 0 for row in frame for pixel in row), 0)

    def test_color_mapping_and_brightness_match_learning_state(self):
        self.assertEqual(rgb_for_event("correct"), (0, 1, 0))
        self.assertEqual(rgb_for_event("incorrect"), (1, 0, 0))
        self.assertEqual(rgb_for_event("thinking"), (1, 1, 0))
        self.assertEqual(rgb_for_event("hint"), (1, 0, 1))
        self.assertLess(BRIGHTNESS["thinking"], BRIGHTNESS["selected"])
        self.assertEqual(BRIGHTNESS["correct"], 7)
        with self.assertRaises(ValueError):
            rgb_for_event("unknown")

    def test_publish_sends_matrix_frame_and_onboard_rgb_color(self):
        bridge = types.SimpleNamespace(call=Mock())
        leds = types.SimpleNamespace(set_led1_color=Mock())

        class FakeFrame:
            def __init__(self, values):
                self.values = values

            def to_board_bytes(self):
                return bytes(pixel for row in self.values for pixel in row)

        fake_arduino = types.ModuleType("arduino")
        fake_utils = types.ModuleType("arduino.app_utils")
        fake_utils.Bridge = bridge
        fake_utils.Frame = FakeFrame
        fake_utils.Leds = leds
        fake_numpy = types.ModuleType("numpy")
        fake_numpy.uint8 = "uint8"
        fake_numpy.asarray = lambda values, dtype: values
        with patch.dict(sys.modules, {"arduino": fake_arduino,
                                      "arduino.app_utils": fake_utils,
                                      "numpy": fake_numpy}):
            publish("correct")
        bridge.call.assert_called_once_with(
            "draw", bytes(pixel for row in render_frame("correct") for pixel in row))
        leds.set_led1_color.assert_called_once_with(0, 1, 0)

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
