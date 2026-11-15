"""Exam mode on a small made-up catalogue: no model, no M3Kang data.

    python3 -m unittest tests.test_exam -v
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.exam import SETTINGS, Exam  # noqa: E402
from copilot.matrix import COLS, ROWS, frame, rgb  # noqa: E402


def catalogue(per_block=4, levels=(0, 1)):
    rows = []
    for level in levels:
        for block in range(3):
            for i in range(per_block):
                n = block * 8 + i + 1
                rows.append({"key": f"lvl-{level}_2020_{n}_cat", "id": f"lvl-{level}_2020_{n}", "language": "cat",
                             "level": level, "grade": 5 + level, "block": block, "question_number": n,
                             "topic": "aritmetica", "text": f"Made-up problem {n}", "label": "C",
                             "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
                             "solution": {"text": "SECRET SOLUTION", "status": "revisado"},
                             "hints": [{"text": "SECRET HINT", "status": "revisado"}], "distractors": {}})
    return rows


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def sit(paper="tast", **kw):
    clock = Clock()
    exam = Exam(catalogue(**kw), clock=clock, seed=1)
    return exam, clock, exam.start(0, paper)


class Paper(unittest.TestCase):
    def test_a_paper_takes_the_same_number_from_each_block_in_order(self):
        _, _, state = sit("curt")
        self.assertEqual([q["points"] for q in state["questions"]], [3, 3, 3, 4, 4, 4, 5, 5, 5])
        self.assertEqual([q["n"] for q in state["questions"]], list(range(1, 10)))
        self.assertTrue(all("lvl-0_" in q["key"] for q in state["questions"]))
        self.assertEqual(state["left"], SETTINGS["papers"]["curt"]["minutes"] * 60)

    def test_only_papers_the_catalogue_can_fill_are_offered(self):
        exam = Exam(catalogue(per_block=4))
        info = exam.info()
        self.assertEqual([l["papers"] for l in info["levels"]], [["tast", "curt"], ["tast", "curt"]])
        self.assertEqual(info["levels"][1]["grade"], 6)
        self.assertEqual(info["rules"]["points"], [3, 4, 5])
        with self.assertRaises(ValueError):
            exam.start(0, "complet")
        with self.assertRaises(ValueError):
            exam.start(9, "tast")
        with self.assertRaises(ValueError):
            exam.start("x", "tast")
        with self.assertRaises(ValueError):
            exam.start(0, "nope")

    def test_problems_without_a_block_or_options_are_left_out(self):
        rows = catalogue(per_block=1, levels=(0,))
        rows.append({**rows[0], "key": "x_cat", "options": {}})
        rows.append({k: v for k, v in rows[0].items() if k != "block"} | {"key": "y_cat"})
        exam = Exam(rows)
        self.assertEqual(sum(len(v) for v in exam.pool[0].values()), 3)

    def test_a_second_paper_takes_new_problems_first(self):
        exam = Exam(catalogue(per_block=4), seed=3)
        seen = []
        for _ in range(4):
            seen += [q["key"] for q in exam.start(0, "tast")["questions"]]
        self.assertEqual(len(set(seen)), 12)  # all 12 problems of the level before any repeat
        exam.start(0, "tast")                 # and it keeps going once they are all used


class NoLeaks(unittest.TestCase):
    def test_nothing_sent_while_the_paper_runs_tells_the_answer(self):
        exam, _, state = sit("curt")
        sent = [state, exam.answer(1, "C"), exam.answer(2, "A"), exam.tick(), exam.state()]
        text = json.dumps(sent)
        self.assertNotIn("label", json.dumps(exam.info()))
        for word in ("label", "SECRET", "solution", "hints", "correct", "outcome", "right", "wrong"):
            self.assertNotIn(word, text)
        self.assertEqual(set(state["questions"][0]), {"n", "points", "key", "id", "grade", "options"})

    def test_the_result_never_holds_a_right_letter(self):
        exam, _, _ = sit("curt")
        exam.answer(1, "A")
        result = exam.finish()
        self.assertNotIn("label", json.dumps(result))
        self.assertNotIn("SECRET", json.dumps(result))
        for row in result["questions"]:
            self.assertEqual(set(row), {"n", "key", "id", "points", "given", "outcome", "delta"})
            if row["outcome"] != "right":
                self.assertNotEqual(row["given"], "C")


class Answers(unittest.TestCase):
    def test_an_answer_can_be_changed_and_cleared(self):
        exam, _, _ = sit()
        self.assertEqual(exam.answer(1, "a")["letter"], "A")
        self.assertEqual(exam.answer(1, "B")["letter"], "B")
        self.assertEqual(exam.state()["answers"], {"1": "B"})
        cleared = exam.answer(1, "-")
        self.assertIsNone(cleared["letter"])
        self.assertEqual(cleared["answered"], 0)
        self.assertEqual(exam.answer(1, "-")["answered"], 0)  # clearing a blank is fine

    def test_bad_answers_are_refused(self):
        exam, _, _ = sit()
        for n, letter in ((0, "A"), (4, "A"), ("x", "A"), (1, "F"), (1, "AB"), (1, "")):
            with self.assertRaises(ValueError):
                exam.answer(n, letter)
        with self.assertRaises(RuntimeError):
            Exam(catalogue()).answer(1, "A")
        with self.assertRaises(RuntimeError):
            exam.results()  # still running


class Scoring(unittest.TestCase):
    def test_right_wrong_and_blank(self):
        exam, _, _ = sit("curt")
        exam.answer(1, "C")   # right, 3 points
        exam.answer(4, "C")   # right, 4 points
        exam.answer(5, "A")   # wrong, loses 1
        exam.answer(7, "B")   # wrong, loses 1.25
        r = exam.finish()
        self.assertEqual((r["right"], r["wrong"], r["blank"]), (2, 2, 5))
        self.assertEqual((r["start"], r["gained"], r["lost"]), (9, 7, 2.25))
        self.assertEqual(r["score"], 13.75)
        self.assertEqual(r["if_blank"], 16)
        self.assertEqual(r["maximum"], 9 + 3 * (3 + 4 + 5))
        self.assertEqual([q["delta"] for q in r["questions"]], [3, 0, 0, 4, -1, 0, -1.25, 0, 0])
        self.assertIsInstance(r["score"], float)
        self.assertIsInstance(r["start"], int)

    def test_all_blank_keeps_the_starting_points_and_all_wrong_cannot_go_below_zero(self):
        exam, _, _ = sit("curt")
        self.assertEqual(exam.finish()["score"], 9)
        exam.start(0, "curt")
        for n in range(1, 10):
            exam.answer(n, "A")
        self.assertEqual(exam.finish()["score"], 9 - 3 * (3 + 4 + 5) / 4)
        self.assertGreaterEqual(exam.results()["score"], 0)

    def test_the_rules_are_settings(self):
        settings = {**SETTINGS, "points": (1, 2, 3), "wrong_fraction": (1, 2), "start_per_question": 0}
        exam = Exam(catalogue(), settings=settings, seed=1)
        exam.start(0, "tast")
        exam.answer(1, "C")
        exam.answer(3, "A")
        r = exam.finish()
        self.assertEqual((r["start"], r["score"], r["maximum"]), (0, -0.5, 6))
        self.assertEqual(r["guess"]["sign_with_none_out"], -1)
        self.assertEqual(r["guess"]["pays_from"], 3)  # only with two options left

    def test_guessing_blind_gains_nothing_on_average_with_the_default_rules(self):
        g = Exam(catalogue()).guess()
        self.assertEqual(g["mean"][0], 0)
        self.assertEqual(g["sign_with_none_out"], 0)
        self.assertEqual(g["pays_from"], 1)
        self.assertEqual(g["mean"][-1], 0.375)  # two options left: 1/2 - 1/2 * 1/4


class Time(unittest.TestCase):
    def test_the_server_clock_counts_down_and_hands_the_paper_in(self):
        exam, clock, state = sit()
        total = state["seconds"]
        clock.now += 30.2
        self.assertEqual(exam.tick()["left"], total - 30)
        self.assertEqual(exam.tick()["events"], [{"event": "clock", "value": total - 30, "of": total}])
        exam.answer(1, "C")
        clock.now += total
        late = exam.answer(2, "C")   # too late: not counted, and the result comes back
        self.assertEqual(late["status"], "finished")
        self.assertTrue(late["timed_out"])
        self.assertEqual((late["right"], late["blank"]), (1, 2))
        self.assertEqual(exam.tick()["status"], "finished")
        self.assertEqual(exam.state()["status"], "finished")
        self.assertEqual(exam.info()["status"], "finished")

    def test_handing_in_early_is_not_a_timeout_and_close_forgets_the_paper(self):
        exam, _, _ = sit()
        self.assertFalse(exam.finish()["timed_out"])
        self.assertEqual(exam.finish()["status"], "finished")  # twice is the same
        self.assertEqual(exam.close()["status"], "none")
        self.assertEqual(exam.state(), {"status": "none", "events": []})


class Matrix(unittest.TestCase):
    def shape(self, grid):
        self.assertEqual(len(grid), ROWS)
        self.assertTrue(all(len(row) == COLS for row in grid))

    def test_every_exam_event_draws(self):
        exam, _, state = sit()
        for result in (state, exam.answer(1, "A"), exam.tick(), exam.finish(), exam.close()):
            for event in result["events"]:
                self.shape(frame(event))
                self.assertEqual(len(rgb(event)), 3)

    def test_the_countdown_shows_minutes_then_seconds_and_a_shrinking_bar(self):
        full = frame({"event": "clock", "value": 3600, "of": 3600})
        self.assertEqual(full[:7], frame({"event": "number", "value": 60})[:7])
        self.assertEqual(sum(1 for v in full[7] if v), COLS)
        half = frame({"event": "clock", "value": 1741, "of": 3600})  # 29:01 left reads 30
        self.assertEqual(half[:7], frame({"event": "number", "value": 30})[:7])
        self.assertEqual(sum(1 for v in half[7] if v), 7)
        last = frame({"event": "clock", "value": 59, "of": 3600})
        self.assertEqual(last[:7], frame({"event": "number", "value": 59})[:7])
        self.assertEqual(sum(1 for v in last[7] if v), 1)
        self.assertEqual(sum(1 for v in frame({"event": "clock", "value": 0, "of": 180})[7] if v), 0)
        self.shape(frame({"event": "clock", "value": 9999, "of": 9999}))


if __name__ == "__main__":
    unittest.main()
