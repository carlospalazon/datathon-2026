"""measure_teach.py on a small made-up catalogue and a fake model: no server, no M3Kang data.

    python3 -m unittest tests.test_measure_teach
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import measure_teach as m  # noqa: E402


def problem(key, level, topic="aritmetica", label="C", difficulty=None, **extra):
    pid, language = key.rsplit("_", 1)
    record = {"key": key, "id": pid, "language": language, "level": level, "topic": topic,
              "difficulty": level if difficulty is None else difficulty,
              "text": f"A farmer has 4 cows and 5 pigs ({key}). How many animals?", "label": label,
              "options": {"A": "8", "B": "9", "C": "10", "D": "12", "E": "14"},
              "solution": None, "hints": [], "distractors": {}}
    record.update(extra)
    return record


CATALOGUE = [
    problem("p1_eng", 2, hints=[{"text": "The answer is 10 apples.", "status": "generado"},
                                {"text": "Count the apples first.", "status": "revisado"}],
            solution={"text": "Add them up.", "status": "revisado"}),
    problem("p2_eng", 1, label="A"),
    problem("p3_eng", 3, label="B"),
    problem("p4_eng", 1, topic="geometria"),
    problem("p5_eng", 2, topic="geometria"),
]
TYPES = {"aritmetica": {"method": "Write each quantity, then operate.", "steps": [], "status": "revisado"}}


class Coverage(unittest.TestCase):
    def test_numbers(self):
        s = m.coverage_stats(CATALOGUE, TYPES, ("revisado", "preparado", "generado"))
        self.assertEqual(s["problems"], 5)
        self.assertEqual(s["with_solution"], 1)
        self.assertEqual(s["rejected_items"], 1)  # "The answer is 10 apples."
        self.assertEqual(s["topics"], {"aritmetica": 3, "geometria": 2})
        self.assertEqual(sum(s["plan_sizes"].values()), 5)
        self.assertGreaterEqual(s["kinds"]["similar"], 1)
        self.assertLessEqual(s["easier"], s["with_similar"])

    def test_revisado_contrast_drops_generated(self):
        s = m.coverage_stats(CATALOGUE, TYPES, ("revisado",))
        self.assertEqual(s["rejected_items"], 0)  # the generated leaky hint is hidden before the leak check

    def test_report_holds_no_text(self):
        text = m.run_coverage(CATALOGUE, TYPES, m.STATUSES).text()
        self.assertNotIn("farmer", text)
        self.assertNotIn("Count the apples", text)
        self.assertIn("revisado only", text)


class Simulate(unittest.TestCase):
    def test_always_right_climbs_and_wrong_descends(self):
        right = m.simulate_student(CATALOGUE, TYPES, m.STATUSES, 30, None)
        wrong = m.simulate_student(CATALOGUE, TYPES, m.STATUSES, 30, "wrong")
        self.assertEqual(right["visited"][0], 1)
        self.assertEqual(right["ran_out"], 5)  # five problems, then the pool is empty
        self.assertEqual(len(wrong["visited"]), 5)

    def test_deterministic(self):
        a = m.simulate_student(CATALOGUE, TYPES, m.STATUSES, 30, 2)
        b = m.simulate_student(CATALOGUE, TYPES, m.STATUSES, 30, 2)
        self.assertEqual(a, b)
        self.assertIsNotNone(a["settle"])

    def test_report(self):
        text = m.run_simulate(CATALOGUE, TYPES, m.STATUSES, 30).text()
        self.assertIn("threshold 3", text)
        self.assertIn("always wrong", text)


class Hints(unittest.TestCase):
    def fake(self, texts, error=None):
        replies = iter(texts)

        def ask(p, student_text=""):
            text = next(replies)
            return {"text": "" if error else text, "seconds": 2.0, "prompt_tokens": 100,
                    "generated_tokens": 20, "error": error}
        return ask

    def test_counts(self):
        ps = CATALOGUE[:3]
        ask = self.fake(["Which animals does the farmer have?",   # fine
                         "So there are 8 animals.",               # value leak
                         "Which animals do we count here and why?"])
        r = m.run_hints(ps, limit=0, ask=ask)
        self.assertEqual((r["total"], r["accepted"], r["leaked"], r["errors"]), (3, 2, 0, 0))
        self.assertEqual(r["reasons"]["value_leak"], 1)
        text = m.hints_report(r).text()
        self.assertIn("2/3 (66.7%)", text)

    def test_limit_and_errors(self):
        r = m.run_hints(CATALOGUE, limit=2, ask=self.fake(["x", "y"], error="URLError: refused"))
        self.assertEqual((r["total"], r["errors"]), (2, 2))
        self.assertEqual(r["reasons"]["model_error"], 2)
        self.assertEqual(r["error_kinds"], {"URLError": 2})

    def test_unreachable_exits_non_zero(self):
        real_ask, real_load = m.slm.ask_hint, m.load_problems
        m.slm.ask_hint = lambda *a, **k: {"text": "", "seconds": 0.1, "prompt_tokens": None,
                                          "generated_tokens": None, "error": "URLError: refused"}
        m.load_problems = lambda *a: CATALOGUE
        try:
            code = m.main(["hints", "--limit", "2"])
        finally:
            m.slm.ask_hint, m.load_problems = real_ask, real_load
        self.assertEqual(code, 2)

    def test_debug_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "debug.jsonl")
            m.run_hints(CATALOGUE[:1], ask=self.fake(["Which animals?"]), debug_jsonl=path)
            with open(path, encoding="utf-8") as f:
                self.assertIn("Which animals?", f.read())


class Guards(unittest.TestCase):
    def test_real_phrase_file_agrees(self):
        text = m.run_guards(m.PHRASES).text()
        self.assertIn("Confusion", text)
        self.assertIn("agreement", text)

    def test_markdown(self):
        md = m.run_guards(m.PHRASES).markdown()
        self.assertIn("| expected \\ obtained |", md)


class Loading(unittest.TestCase):
    def test_missing_catalogue_names_the_script(self):
        with self.assertRaises(SystemExit) as cm:
            m.load_problems("data/catalog/nope.jsonl", "primaria", "cat")
        self.assertIn("laptop/build_catalog.py", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
