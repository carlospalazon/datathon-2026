"""laptop.find_letter: the letter a model stated in its working. Invented strings only, no server.

    python3 -m unittest tests.test_find_letter
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from laptop.find_letter import find_letter  # noqa: E402

OPTIONS = {"A": "10", "B": "12", "C": "14 cm", "D": "3/4", "E": "12,5"}


class FindLetter(unittest.TestCase):
    def test_forms_the_old_pattern_accepted(self):
        for text in ("Answer: B", "Answer: **B**", "**Answer: B**", "Answer: (B)", "Answer: B) 12"):
            self.assertEqual(find_letter(text), "B", text)

    def test_forms_the_old_pattern_missed(self):
        for text in ("**Answer:** B", "The answer is B.", "Resposta: B", "La resposta és B", "answer: B",
                     "**Answer:**\nB", "Final answer: B", "Answer: $B$", "The correct option is B.",
                     "\\boxed{B}", "\\boxed{\\text{B}}", "Answer: \\boxed{B}"):
            self.assertEqual(find_letter(text), "B", text)

    def test_last_statement_wins(self):
        self.assertEqual(find_letter("Answer: A\nNo, 3 x 4 = 12.\nThe answer is B"), "B")
        self.assertEqual(find_letter("\\boxed{C} ... so the answer is D"), "D")

    def test_no_answer_stated(self):
        for text in ("", None, "3 x 4 = 12", "Option B is too small.", "Answer: A number between 3 and 5",
                     "Answer: 12", "\\boxed{12}", "Answer: Because it is even"):
            self.assertEqual(find_letter(text), "", text)

    def test_a_stated_value_is_matched_to_its_option(self):
        self.assertEqual(find_letter("so \\boxed{12}", OPTIONS), "B")
        self.assertEqual(find_letter("Answer: 14", OPTIONS), "C")
        self.assertEqual(find_letter("The answer is 12.5", OPTIONS), "E")
        self.assertEqual(find_letter("Resposta: 3/4", OPTIONS), "D")

    def test_a_value_that_is_no_option_or_two_options_is_not_an_answer(self):
        self.assertEqual(find_letter("Answer: 13", OPTIONS), "")
        self.assertEqual(find_letter("Answer: 7", {"A": "7", "B": "7", "C": "8", "D": "9", "E": "1"}), "")

    def test_a_letter_named_in_passing_is_not_an_answer(self):
        for text in ("Answer B is too big, so", "The answer cannot be C", "answers A and B are even"):
            self.assertEqual(find_letter(text), "", text)

    def test_more_forms(self):
        self.assertEqual(find_letter("The answer is A because 3 < 4"), "A")
        self.assertEqual(find_letter("La resposta és la B"), "B")
        self.assertEqual(find_letter("\\boxed{\\textbf{(B)}}"), "B")
        self.assertEqual(find_letter("\\boxed{\\frac{3}{4}}", OPTIONS), "D")

    def test_only_the_last_stated_value_counts(self):
        self.assertEqual(find_letter("the answer is 12 ... no, the answer is 13", OPTIONS), "")

    def test_a_letter_beats_a_value(self):
        self.assertEqual(find_letter("\\boxed{12}, which is option B.\nAnswer: A", OPTIONS), "A")


if __name__ == "__main__":
    unittest.main()
