"""The tutor core, on a small made-up catalogue: no model, no M3Kang data.

    python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.matrix import COLS, ROWS, FakeMatrix, frame, rgb  # noqa: E402
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
def similar_step(tutor):
    """The 'similar problem' step, which now comes after the help about the problem itself."""
    while True:
        step = tutor.help()
        if step["kind"] in ("similar", "none"):
            return step


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
        hint = t.help()                                             # help about this problem comes first
        self.assertEqual(hint["text"], "Count the apples first, then take away.")
        self.assertEqual(t.current["rejected"], ["hint 1"])        # the leaking hint was skipped
        self.assertEqual(t.help()["kind"], "method")
        similar = t.help()
        self.assertEqual(similar["kind"], "similar")
        self.assertEqual(similar["problem"]["key"], "p2_eng")       # easier, same topic, same language
        self.assertEqual(t.help()["kind"], "none")

    def test_only_allowed_statuses(self):
        t = Tutor(CATALOGUE, TYPES, show=("revisado",))
        t.start("p5_eng")
        kinds = [t.help()["kind"] for _ in range(3)]
        self.assertEqual(kinds, ["method", "similar", "none"])      # the generated hint stays hidden

    def test_never_its_own_translation(self):
        t = Tutor([CATALOGUE[0], CATALOGUE[1]], TYPES)
        t.start("p1_eng")
        self.assertEqual(similar_step(t)["kind"], "none")          # no similar problem: only the translation exists

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
        self.assertEqual(steps, ["checkpoint 1", "method", "guide 1", "guide 2", "similar", "compare"])

    def test_questions_are_checked(self):
        step = self.t.help()
        self.assertEqual(step["qid"], "checkpoint 1")
        self.assertNotIn("_q", step)                        # the expected answer never reaches the page
        wrong = self.t.respond("checkpoint 1", "11")
        self.assertEqual((wrong["correct"], wrong["feedback"]), (False, "Bags times apples."))
        self.assertTrue(self.t.respond("checkpoint 1", " 12 apples")["correct"])
        with self.assertRaises(ValueError):
            self.t.respond("checkpoint 1", "twelve")
        for _ in range(3):
            self.t.help()                                   # method, guide 1, guide 2
        self.assertIsNone(self.t.respond("guide 1", "anything")["correct"])   # reflection: no wrong answer
        self.assertTrue(self.t.respond("guide 2", 0)["correct"])
        for _ in range(2):
            self.t.help()                                   # similar, then compare
        self.assertFalse(self.t.respond("compare", 0)["correct"])
        self.assertTrue(self.t.respond("compare", "1")["correct"])
        with self.assertRaises(ValueError):
            self.t.respond("checkpoint 2", "10")            # never offered: it was the final answer

    def test_status_with_author(self):
        t = Tutor([problem("s1_eng", 1, distractors={"A": {"text": "You added.", "status": "generado:claude-opus"}})],
                  show=("generado",))
        t.start("s1_eng")
        self.assertEqual(t.answer("A")["feedback"]["text"], "You added.")
        t = Tutor([problem("s1_eng", 1, distractors={"A": {"text": "You added.", "status": "generado:claude-opus"}})],
                  show=("revisado",))
        t.start("s1_eng")
        self.assertIsNone(t.answer("A")["feedback"])

    def test_hidden_fields(self):
        self.assertNotIn("checkpoints", self.t.start("g1_eng")["problem"])


class Similar(unittest.TestCase):
    def test_nearest_by_meaning_and_same_figure_need(self):
        base = problem("n1_cat", 2, similar_ids=["n3", "n2", "n4"])
        pool = [base, problem("n2_cat", 1), problem("n3_cat", 1, needs_figure=True), problem("n4_cat", 1)]
        t = Tutor(pool)
        t.start("n1_cat")
        self.assertEqual(similar_step(t)["problem"]["key"], "n2_cat")   # n3 is nearer but needs a figure; n1 doesn't


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


class FineDifficulty(unittest.TestCase):
    def test_similar_prefers_the_closest_easier(self):
        cat = [problem("q0_eng", 1, difficulty=4), problem("q1_eng", 1, difficulty=3),
               problem("q2_eng", 1, difficulty=2), problem("q3_eng", 0, difficulty=1),
               problem("q4_eng", 1, difficulty=5), problem("q5_eng", 1, difficulty=5)]
        t = Tutor(cat, TYPES)
        t.start("q4_eng")
        self.assertEqual(similar_step(t)["problem"]["key"], "q0_eng")     # 4 is the closest below 5
        t = Tutor([c for c in cat if c["key"] != "q0_eng"], TYPES)
        t.start("q4_eng")
        self.assertEqual(similar_step(t)["problem"]["key"], "q1_eng")

    def test_similar_falls_back_to_equal_difficulty(self):
        cat = [problem("q0_eng", 1, difficulty=3), problem("q1_eng", 1, difficulty=3)]
        t = Tutor(cat, TYPES)
        t.start("q0_eng")
        self.assertEqual(similar_step(t)["problem"]["key"], "q1_eng")

    def test_similar_keeps_neighbours_order(self):
        cat = [problem("q0_eng", 1, difficulty=5), problem("q1_eng", 1, difficulty=3),
               problem("q2_eng", 1, difficulty=3)]
        t = Tutor(cat, TYPES, neighbours=lambda p: ["q2_eng", "q1_eng"])
        t.start("q0_eng")
        self.assertEqual(similar_step(t)["problem"]["key"], "q2_eng")

    def test_next_problem_steps_by_one_difficulty(self):
        cat = [problem("q0_eng", 1, difficulty=3), problem("q1_eng", 1, difficulty=4),
               problem("q2_eng", 1, difficulty=5), problem("q3_eng", 1, difficulty=2),
               problem("q4_eng", 1, difficulty=1)]
        t = Tutor(cat, TYPES)
        t.start("q0_eng")
        t.answer("C")
        self.assertEqual(t.next_problem()["problem"]["key"], "q1_eng")   # 3 -> 4
        t = Tutor(cat, TYPES)
        t.start("q0_eng")
        t.answer("A")
        self.assertEqual(t.next_problem()["problem"]["key"], "q3_eng")   # 3 -> 2


class Profile(unittest.TestCase):
    def test_survives_a_restart(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "profile.db")
            t = Tutor(CATALOGUE, TYPES, profile_path=path)
            t.start("p1_eng")
            t.answer("C")
            t2 = Tutor(CATALOGUE, TYPES, profile_path=path)
            self.assertEqual(t2.history, [("p1_eng", True)])
            self.assertEqual(t2.seen, {"p1_eng"})
            t2.start("p2_eng")
            nxt = t2.next_problem()["problem"]["key"]
            self.assertNotIn(nxt, ("p1_eng", "p2_eng"))
            t3 = Tutor(CATALOGUE, TYPES, profile_path=path)
            self.assertEqual(t3.seen, {"p1_eng", "p2_eng", nxt})
            self.assertEqual(t3.history, [("p1_eng", True)])

    def test_without_a_path_it_stays_in_memory(self):
        t = Tutor(CATALOGUE, TYPES)
        t.start("p1_eng")
        t.answer("C")
        self.assertEqual(Tutor(CATALOGUE, TYPES).history, [])


class Matrix(unittest.TestCase):
    def test_onboard_rgb_color_follows_tutor_events(self):
        self.assertEqual(rgb({"event": "tick"}), (0, 1, 0))
        self.assertEqual(rgb({"event": "cross"}), (1, 0, 0))
        self.assertEqual(rgb({"event": "thinking"}), (1, 1, 0))
        self.assertEqual(rgb({"event": "help_step", "value": 2, "of": 4}), (1, 0, 1))
        self.assertEqual(rgb({"event": "level", "value": 2}), (0, 0, 1))
        self.assertEqual(rgb({"event": "clear"}), (0, 0, 0))
        with self.assertRaises(ValueError):
            rgb({"event": "fireworks"})

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


class ExamFeedsTheMemory(unittest.TestCase):
    """An exam handed in: by topic in the tutor's skill, the misses come back, nothing counted twice."""

    def paper(self, answers, finished=True):
        keys = ["p2_eng", "p3_eng", "p4_eng", "p5_eng"]   # labels A, B, C, C; p4 is geometry
        byk = {p["key"]: p for p in CATALOGUE}
        return {"questions": [{"problem": byk[k]} for k in keys], "answers": answers, "finished": finished}

    def test_right_wrong_and_blank_count_by_topic_once_per_paper(self):
        tutor = Tutor(CATALOGUE, TYPES)
        paper = self.paper({1: "A", 2: "A", 3: "A"})      # right, wrong, wrong (geometry), blank
        running = self.paper({1: "A"}, finished=False)
        tutor.exam_checked(running)
        self.assertEqual(tutor.skill, {})                  # nothing while the paper runs
        tutor.exam_checked(paper)
        tutor.exam_checked(paper)
        self.assertEqual(tutor.skill["aritmetica"], {"streak": 0, "done": 2, "right": 1})   # the blank ended the streak
        self.assertEqual(tutor.skill["geometria_plana"], {"streak": 0, "done": 1, "right": 0})
        self.assertEqual(tutor.seen, {"p2_eng", "p3_eng", "p4_eng"})                       # the blank can still be offered
        self.assertEqual([k for k, _ in tutor.review], ["p3_eng", "p4_eng"])               # the misses come back

    def test_a_miss_gone_over_with_the_tutor_counts_once_and_does_not_come_back_twice(self):
        tutor = Tutor(CATALOGUE, TYPES)
        tutor.exam_checked(self.paper({2: "A"}))
        tutor.start("p3_eng")                              # the review queue opens it
        self.assertEqual(tutor.review, [])
        self.assertTrue(tutor.answer("B")["correct"])
        self.assertEqual(tutor.skill["aritmetica"], {"streak": 0, "done": 1, "right": 0})
        self.assertEqual(len(tutor.history), 1)

    def test_a_problem_settled_with_the_tutor_is_not_rewritten_by_an_exam(self):
        tutor = Tutor(CATALOGUE, TYPES)
        tutor.start("p2_eng")
        tutor.answer("A")
        tutor.exam_checked(self.paper({1: "B", 2: "B", 3: "C", 4: "C"}))   # the first one wrong this time
        self.assertEqual(tutor.skill["aritmetica"], {"streak": 3, "done": 3, "right": 3})
        self.assertEqual(tutor.review, [])


if __name__ == "__main__":
    unittest.main()
