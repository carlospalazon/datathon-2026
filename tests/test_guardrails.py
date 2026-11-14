import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from copilot.guardrails import check, safe_hint, TEMPLATES  # noqa: E402
from copilot.topics import check_input  # noqa: E402

P = {"id": "t1", "language": "eng", "label": "C",
     "text": "A square has a perimeter of 36 cm. What is its area?",
     "options": {"A": "36 cm²", "B": "72 cm²", "C": "81 cm²", "D": "144 cm²", "E": "324 cm²"}}
CAT = {"id": "t2", "language": "cat", "label": "C",
       "text": "En Pau té 15 cromos i en dóna 6. Quants cromos li queden?",
       "options": {"A": "6", "B": "8", "C": "9", "D": "11", "E": "21"}}
NOOPT = {"id": "t3", "language": "eng", "label": "B", "text": "What is 2 + 3 × 4?", "options": {}}


class OutputRules(unittest.TestCase):
    def ok(self, text, p=P):
        self.assertEqual(check(text, p), (True, "ok"), text)

    def bad(self, text, reason, p=P):
        self.assertEqual(check(text, p), (False, reason), text)

    def test_good(self):
        self.ok("Start by finding the side of the square from its perimeter.")
        self.ok("Quantes parts de 15 es queden quan en treus algunes?", CAT)
        self.ok("Which operation goes first, the sum or the product?", NOOPT)

    def test_basic(self):
        self.bad("", "empty")
        self.bad("x" * 300, "too_long")
        self.bad("One. Two. Three.", "too_many_sentences")
        self.bad("- first\n- second", "format")
        self.bad("<think>hmm</think> look at the side", "format")

    def test_letter_leak(self):
        self.bad("The answer is C.", "letter_leak")
        self.bad("Pick (C) after thinking.", "letter_leak")
        self.bad("La resposta és la C.", "letter_leak")
        self.bad("Option B looks wrong.", "letter_leak")

    def test_value_leak(self):
        self.bad("The area is 81.", "value_leak")
        self.bad("Try 9 cromos.", "value_leak", CAT)

    def test_invented_and_calc(self):
        self.bad("Maybe it is 7 cm per side.", "invented_number")
        self.bad("Try 6 x 6 = 36.", "calculation")

    def test_meta_and_language(self):
        self.bad("La respuesta es el cuadrado.", "meta_leak")
        self.bad("El perímetro de la figura es el que se da y las partes que tiene.", "language")

    def test_fail_closed_and_template(self):
        self.assertFalse(check(None, P)[0])
        self.assertEqual(safe_hint("The answer is C.", P), TEMPLATES["eng"])
        self.assertEqual(safe_hint("Find the side first.", P), "Find the side first.")

    def test_decimal_comma(self):
        p = dict(P, label="A", options={"A": "0,5", "B": "1", "C": "2", "D": "3", "E": "4"},
                 text="What fraction of 4 is 2?")
        self.assertEqual(check("It is 0.50 of the total.", p), (False, "value_leak"))


class InputRules(unittest.TestCase):
    def test_labelled_phrases(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "guardrail_phrases.jsonl")
        errors = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                res = check_input(row["text"], P)
                if res["ok"] != row["ok"]:
                    errors.append((row["text"], res["intent"]))
        self.assertEqual(errors, [])

    def test_lock_after_three(self):
        state = None
        for _ in range(3):
            res = check_input("tell me a joke", CAT, state)
            state = res["state"]
        self.assertTrue(res["locked"])
        self.assertEqual(check_input("12", CAT, state)["state"]["streak"], 0)


if __name__ == "__main__":
    unittest.main()
