"""The rule diagnosis of wrong choices, on made-up problems: no model, no M3Kang data.

    python3 -m unittest tests.test_diagnose
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot import diagnose as d  # noqa: E402
from copilot.tutor import Tutor  # noqa: E402

APPLES = {"key": "a_eng", "id": "a", "language": "eng", "level": 0, "topic": "aritmetica", "label": "C",
          "text": "Anna has 3 bags with 4 apples in each bag. She eats 2 apples. How many apples does she have left?",
          "options": {"A": "8", "B": "9", "C": "10", "D": "12", "E": "14"}}
PRIORITY = {"key": "b_eng", "id": "b", "language": "eng", "level": 2, "topic": "aritmetica", "label": "B",
            "text": "What is the value of 2 + 3 × 4?",
            "options": {"A": "20", "B": "14", "C": "24", "D": "9", "E": "10"}}
SQUARE = {"key": "c_eng", "id": "c", "language": "eng", "level": 4, "topic": "geometria_plana", "label": "C",
          "text": "A square has a perimeter of 36 cm. What is its area?",
          "options": {"A": "36 cm²", "B": "72 cm²", "C": "81 cm²", "D": "144 cm²", "E": "324 cm²"}}


def codes(problem, letter, **kw):
    return [f["code"] for f in d.diagnose(problem, letter, **kw)]


class DiagnoseTest(unittest.TestCase):
    def test_one_step_done_is_intermediate(self):
        self.assertEqual(codes(APPLES, "D"), ["intermediate"])       # 12 = 3 × 4, before eating

    def test_sum_of_all_the_numbers(self):
        self.assertEqual(codes(APPLES, "B")[0], "sum_all")           # 9 = 3 + 4 + 2

    def test_last_step_the_other_way(self):
        self.assertEqual(codes(APPLES, "E"), ["wrong_op"])           # 14 = 12 + 2

    def test_no_operator_priority(self):
        self.assertEqual(codes(PRIORITY, "A"), ["left_to_right"])    # (2 + 3) × 4

    def test_perimeter_given_as_area(self):
        self.assertEqual(codes(SQUARE, "A"), ["perimeter_area"])

    def test_checkpoint_value_unless_rejected(self):
        p = {**APPLES, "text": "How many?", "checkpoints": [{"question": "q", "answer": 12, "status": "revisado"}]}
        self.assertEqual(codes(p, "D"), ["intermediate"])
        p["checkpoints"][0]["status"] = "rebutjat"
        self.assertEqual(codes(p, "D"), [])

    def test_silent_when_it_cannot_tell(self):
        self.assertEqual(codes(APPLES, "C"), [])                     # the right answer
        self.assertEqual(codes({**APPLES, "options": {}}, "A"), [])  # options only in the picture
        self.assertEqual(codes(SQUARE, "D"), [])
        five = {**APPLES, "text": "Which one?", "label": "C",
                "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}}
        self.assertEqual(codes(five, "B"), [])                       # five numbers in a row: no off_by_one

    def test_off_by_one_only_where_counting_matters(self):
        self.assertEqual(codes(APPLES, "B"), ["sum_all"])            # 9 is one from 10, but it's arithmetic
        self.assertEqual(codes({**APPLES, "text": "How many posts?", "topic": "conteo"}, "B"), ["off_by_one"])

    def test_messages_have_no_digits(self):
        for code in d.CODES:
            for text in d.MESSAGES[code].values():
                self.assertNotRegex(text, r"\d")

    def test_card_hint_wins_in_catalan(self):
        card = {"status": "revisado", "typical_errors": [{"code": "sum_all", "hint": "De la fitxa."}]}
        self.assertEqual(d.message("sum_all", "cat", card), ("De la fitxa.", "revisado"))
        self.assertEqual(d.message("sum_all", "eng", card)[1], "regla")
        self.assertEqual(d.message("wrong_op", "cat", card)[1], "regla")


class TutorDiagnosisTest(unittest.TestCase):
    def test_wrong_answer_gets_the_rule_feedback(self):
        t = Tutor([APPLES])
        t.start("a_eng")
        feedback = t.answer("B")["feedback"]
        self.assertEqual((feedback["kind"], feedback["code"], feedback["status"]), ("diagnosis", "sum_all", "regla"))
        self.assertEqual(t.current["errors"], ["sum_all"])

    def test_a_written_distractor_note_comes_first(self):
        note = {"B": {"text": "You added everything.", "status": "revisado"}}
        t = Tutor([{**APPLES, "distractors": note}])
        t.start("a_eng")
        self.assertEqual(t.answer("B")["feedback"]["source"], "distractor B")


def apples(key, topic="aritmetica", difficulty=1):
    return {**APPLES, "key": key, "id": key.rsplit("_", 1)[0], "topic": topic, "difficulty": difficulty}


class StudentModelTest(unittest.TestCase):
    TYPES = {"aritmetica": {"method": "Name each quantity first.", "steps": [], "status": "revisado"}}

    def test_the_same_mistake_twice_brings_the_method_first(self):
        t = Tutor([apples("a1_eng"), apples("a2_eng")], self.TYPES)
        t.start("a1_eng")
        self.assertFalse(t.answer("B")["feedback"]["repeated"])
        t.answer("B")                                       # the same problem again doesn't count twice
        self.assertEqual(t.errors[("aritmetica", "sum_all")], 1)
        t.start("a2_eng")
        self.assertTrue(t.answer("B")["feedback"]["repeated"])
        self.assertEqual(t.help()["kind"], "method")        # before the similar problem

    def test_a_failed_problem_comes_back_for_review(self):
        t = Tutor([apples(f"a{i}_eng") for i in range(6)])
        t.start("a0_eng")
        t.answer("B")
        t.answer("C")
        keys = []
        for _ in range(4):
            view = t.next_problem()
            keys.append(view["problem"]["key"])
            t.answer("C")
        self.assertNotIn("a0_eng", keys[:3])                 # three other problems first
        self.assertEqual((keys[3], view.get("review")), ("a0_eng", True))

    def test_a_mastered_topic_gives_way_to_another(self):
        cat = [apples(f"a{i}_eng") for i in range(5)] + [apples("g0_eng", topic="geometria_plana")]
        t = Tutor(cat)
        t.start("a0_eng")
        topics = []
        for _ in range(3):
            t.answer("C")
            topics.append(t.next_problem()["problem"]["topic"])
        self.assertEqual(topics, ["aritmetica", "aritmetica", "geometria_plana"])

    def test_skill_and_errors_survive_a_restart(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "profile.db")
            t = Tutor([apples("a1_eng")], profile_path=path)
            t.start("a1_eng")
            t.answer("B")
            t.answer("C")
            t2 = Tutor([apples("a1_eng")], profile_path=path)
            self.assertEqual(t2.errors, {("aritmetica", "sum_all"): 1})
            self.assertEqual(t2.skill["aritmetica"], {"streak": 0, "done": 1, "right": 0})


if __name__ == "__main__":
    unittest.main()
