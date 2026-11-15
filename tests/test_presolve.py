"""copilot.presolve: copy the answer value of a near-identical training problem. Invented problems only.

    python3 -m unittest tests.test_presolve
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from copilot.presolve import build, nearest, presolve  # noqa: E402

TEXT = "A farmer has twelve hens and each hen lays three eggs a day. How many eggs does she collect in a day?"
TRAIN = [
    {"id": "t1", "language": "eng", "text": TEXT, "label": "C",
     "options": {"A": "15", "B": "24", "C": "36", "D": "39", "E": "48"}},
    {"id": "t1", "language": "cat", "text": "Una pagesa té dotze gallines i cada gallina pon tres ous.",
     "label": "C", "options": {"A": "15", "B": "24", "C": "36", "D": "39", "E": "48"}},
    {"id": "t2", "language": "eng", "text": "How many diagonals does a regular hexagon have in total?",
     "label": "B", "options": {"A": "6", "B": "9", "C": "12", "D": "15", "E": "18"}},
    {"id": "t3", "language": "eng", "text": "No label here, so it is not indexed.", "label": "", "options": {}},
]


def ask(options, text=TEXT, ident="q1", language="eng"):
    return {"id": ident, "language": language, "text": text, "options": options}


class Presolve(unittest.TestCase):
    def setUp(self):
        self.index = build(TRAIN)

    def test_the_value_is_copied_not_the_letter(self):
        hit = presolve(ask({"A": "36", "B": "15", "C": "24", "D": "48", "E": "39"}), self.index)
        self.assertEqual((hit["answer"], hit["kind"], hit["source"]), ("A", "value", "t1"))

    def test_values_are_compared_as_written_loosely(self):
        hit = presolve(ask({"A": "15", "B": " 36. ", "C": "24", "D": "48", "E": "39"}), self.index)
        self.assertEqual(hit["answer"], "B")

    def test_abstains_when_the_value_is_no_option_or_two_options(self):
        self.assertIsNone(presolve(ask({"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}), self.index))
        self.assertIsNone(presolve(ask({"A": "36", "B": "36", "C": "3", "D": "4", "E": "5"}), self.index))

    def test_abstains_on_a_different_problem(self):
        problem = ask({"A": "36", "B": "9", "C": "3", "D": "4", "E": "5"},
                      text="A train leaves at noon and travels for two hours. When does it arrive?")
        self.assertIsNone(presolve(problem, self.index))

    def test_never_matches_its_own_id_or_the_excluded_one(self):
        options = {"A": "36", "B": "15", "C": "24", "D": "48", "E": "39"}
        self.assertIsNone(presolve(ask(options, ident="t1"), self.index))
        self.assertIsNone(presolve(ask(options), self.index, exclude_id="t1"))

    def test_only_the_same_language_is_searched(self):
        self.assertIsNone(presolve(ask({"A": "36", "B": "15", "C": "24", "D": "48", "E": "39"}, language="spa"),
                                   self.index))

    def test_without_options_the_letter_comes_back_marked(self):
        hit = presolve(ask({}), self.index)
        self.assertEqual((hit["answer"], hit["kind"]), ("C", "letter"))

    def test_same_input_same_output_and_unlabelled_rows_are_left_out(self):
        self.assertEqual(len(self.index), 3)
        problem = ask({"A": "36", "B": "15", "C": "24", "D": "48", "E": "39"})
        self.assertEqual(presolve(problem, self.index), presolve(problem, build(list(reversed(TRAIN)))))
        self.assertEqual(nearest({"text": "", "language": "eng"}, self.index), (0.0, None))


if __name__ == "__main__":
    unittest.main()
