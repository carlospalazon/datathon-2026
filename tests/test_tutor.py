"""The tutor core, on a small made-up catalogue: no model, no M3Kang data.

    python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.matrix import COLS, ROWS, FakeMatrix, frame  # noqa: E402
from copilot.tutor import Tutor, leaks_answer  # noqa: E402


def problem(key, level, topic="aritmetica", label="C", options=None, **extra):
    pid, language = key.rsplit("_", 1)
    record = {"key": key, "id": pid, "language": language, "level": level, "topic": topic,
              "text": f"Problem {key}", "label": label,
              "options": options if options is not None else {"A": "8", "B": "9", "C": "10", "D": "12", "E": "14"},
              "solution": None, "hints": [], "distractors": {}}
    record.update(extra)
    return record


CATALOGUE = [
    problem("p1_eng", 2,
            hints=[{"text": "The answer is 10 apples.", "status": "generado"},      # leaks: must never show
                   {"text": "Count the apples first, then take away.", "status": "revisado"}],
            distractors={"D": {"text": "12 is all the apples before she eats any.", "status": "revisado"}},
            solution={"text": "3 x 4 = 12, and 12 - 2 = 10.", "status": "revisado"}),
    problem("p1_cat", 2),                      # same problem in Catalan: never a "similar" problem
    problem("p2_eng", 1, label="A"),           # same topic, one level easier
    problem("p3_eng", 3, label="B"),           # same topic, one level harder
    problem("p4_eng", 1, topic="geometria_plana"),
    problem("p5_eng", 2, hints=[{"text": "Draft hint", "status": "generado"}]),
]
TYPES = {"aritmetica": {"method": "Write down each quantity, then do the operations in order.",
                        "steps": ["Read", "Compute"], "status": "revisado"}}


class LeakCheck(unittest.TestCase):
    def setUp(self):
        self.p = CATALOGUE[0]  # correct answer C = 10

    def test_value_leaks(self):
        self.assertTrue(leaks_answer("So she has 10 left.", self.p))
        self.assertTrue(leaks_answer("The answer is C", self.p))
        self.assertTrue(leaks_answer("la resposta és c", self.p))

    def test_other_numbers_do_not(self):
        self.assertFalse(leaks_answer("Start with 3 bags of 4.", self.p))
        self.assertFalse(leaks_answer("It is not 100 or 1.0", self.p))

    def test_unknown_without_options(self):
        self.assertIsNone(leaks_answer("anything", problem("x_eng", 1, options={})))


class Answers(unittest.TestCase):
    def test_right_and_wrong(self):
        t = Tutor(CATALOGUE, TYPES)
        view = t.start("p1_eng")
        self.assertNotIn("label", view["problem"])
        self.assertNotIn("solution", view["problem"])
        wrong = t.answer("D")
        self.assertFalse(wrong["correct"])
        self.assertEqual(wrong["feedback"]["source"], "distractor D")
        self.assertEqual(wrong["events"], [{"event": "cross"}])
        right = t.answer("c")
        self.assertTrue(right["correct"])
        self.assertEqual(right["events"], [{"event": "tick"}])

    def test_rejects_other_input(self):
        t = Tutor(CATALOGUE, TYPES)
        t.start("p1_eng")
        for bad in ("F", "AB", ""):
            with self.assertRaises(ValueError):
                t.answer(bad)


class HelpLadder(unittest.TestCase):
    def test_order_and_leak_filter(self):
        t = Tutor(CATALOGUE, TYPES)
        t.start("p1_eng")
        similar = t.help()
        self.assertEqual(similar["kind"], "similar")
        self.assertEqual(similar["problem"]["key"], "p2_eng")       # easier, same topic, same language
        self.assertEqual(t.help()["kind"], "method")
        hint = t.help()
        self.assertEqual(hint["text"], "Count the apples first, then take away.")
        self.assertEqual(t.current["rejected"], ["hint 1"])        # the leaking hint was skipped
        self.assertEqual(t.help()["kind"], "none")

    def test_only_allowed_statuses(self):
        t = Tutor(CATALOGUE, TYPES, show=("revisado",))
        t.start("p5_eng")
        kinds = [t.help()["kind"] for _ in range(3)]
        self.assertEqual(kinds, ["similar", "method", "none"])      # the generated hint stays hidden

    def test_never_its_own_translation(self):
        t = Tutor([CATALOGUE[0], CATALOGUE[1]], TYPES)
        t.start("p1_eng")
        self.assertEqual(t.help()["kind"], "method")               # no similar problem: only the translation exists

    def test_solution_only_on_request(self):
        t = Tutor(CATALOGUE, TYPES)
        t.start("p1_eng")
        for _ in range(4):
            self.assertNotIn("10 left", str(t.help()))
        sol = t.solution()
        self.assertEqual(sol["label"], "C")
        self.assertEqual(sol["events"], [{"event": "letter", "value": "C"}])


GUIDED_TYPES = {"aritmetica": {
    "method": "Write down each quantity, then do the operations in order.", "steps": [], "status": "revisado",
    "compare": {"question": "What do they have in common?", "choices": ["Same numbers", "Same method"], "answer": 1,
                "explain": "The method."},
    "guide": [{"kind": "reflect", "question": "Write down the data."},
              {"kind": "choice", "question": "Then?", "choices": ["Check the question", "Add everything"], "answer": 0}]}}

GUIDED = [
    problem("g1_eng", 2, checkpoints=[
        {"question": "How many apples in the bags?", "answer": 12, "error_hint": "Bags times apples.", "status": "revisado"},
        {"question": "And at the end?", "answer": 10, "status": "revisado"},              # = final answer: dropped
        {"question": "Draft step", "answer": 3, "status": "generado"}]),                  # not shown in a demo
    problem("g2_eng", 1, label="A"),
]


class Guide(unittest.TestCase):
    def setUp(self):
        self.t = Tutor(GUIDED, GUIDED_TYPES, show=("revisado",))
        self.t.start("g1_eng")

    def test_order(self):
        steps = []
        while True:
            step = self.t.help()
            if step["kind"] == "none":
                break
            steps.append(step.get("qid") or step["kind"])
        self.assertEqual(steps, ["similar", "compare", "method", "guide 1", "guide 2", "checkpoint 1"])

    def test_questions_are_checked(self):
        for _ in range(2):
            self.t.help()                                   # similar, then compare
        self.assertFalse(self.t.respond("compare", 0)["correct"])
        self.assertTrue(self.t.respond("compare", "1")["correct"])
        for _ in range(3):
            self.t.help()                                   # method, guide 1, guide 2
        self.assertIsNone(self.t.respond("guide 1", "anything")["correct"])   # reflection: no wrong answer
        self.assertTrue(self.t.respond("guide 2", 0)["correct"])
        step = self.t.help()
        self.assertEqual(step["qid"], "checkpoint 1")
        self.assertNotIn("_q", step)                        # the expected answer never reaches the page
        wrong = self.t.respond("checkpoint 1", "11")
        self.assertEqual((wrong["correct"], wrong["feedback"]), (False, "Bags times apples."))
        self.assertTrue(self.t.respond("checkpoint 1", " 12 apples")["correct"])
        with self.assertRaises(ValueError):
            self.t.respond("checkpoint 1", "twelve")
        with self.assertRaises(ValueError):
            self.t.respond("checkpoint 2", "10")            # never offered: it was the final answer

    def test_hidden_fields(self):
        self.assertNotIn("checkpoints", self.t.start("g1_eng")["problem"])


class Adaptive(unittest.TestCase):
    def test_up_after_right_down_after_wrong(self):
        t = Tutor(CATALOGUE, TYPES)
        t.start("p1_eng")
        t.answer("C")
        self.assertEqual(t.next_problem()["problem"]["key"], "p3_eng")   # level 2 -> 3
        t = Tutor(CATALOGUE, TYPES)
        t.start("p1_eng")
        t.answer("A")
        t.answer("C")
        self.assertEqual(t.next_problem()["problem"]["key"], "p2_eng")   # level 2 -> 1


class Matrix(unittest.TestCase):
    def test_every_event_fits(self):
        m = FakeMatrix()
        for e in ({"event": "letter", "value": "B"}, {"event": "number", "value": 42}, {"event": "tick"},
                  {"event": "cross"}, {"event": "thinking"}, {"event": "help_step", "value": 2, "of": 4},
                  {"event": "level", "value": 7}, {"event": "clear"}):
            m.show(e)
        for _event, grid in m.frames:
            self.assertEqual(len(grid), ROWS)
            self.assertTrue(all(len(row) == COLS for row in grid))
            self.assertTrue(all(0 <= v <= 7 for row in grid for v in row))
        self.assertIn("#", FakeMatrix.render(frame({"event": "letter", "value": "A"})))

    def test_unknown_event(self):
        with self.assertRaises(ValueError):
            frame({"event": "fireworks"})


if __name__ == "__main__":
    unittest.main()
