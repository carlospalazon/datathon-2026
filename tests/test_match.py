"""Written help picked for what the student typed: no model, a small made-up problem.

    python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot import match  # noqa: E402
from copilot.assistant import Assistant  # noqa: E402
from copilot.tutor import Tutor  # noqa: E402

PROBLEM = {
    "key": "m1_cat", "id": "m1", "language": "cat", "level": 0, "topic": "aritmetica",
    "text": "L'Anna té 3 bosses amb 4 pomes a cada bossa. Se'n menja 2. Quantes pomes li queden?",
    "label": "C", "options": {"A": "8", "B": "9", "C": "10", "D": "12", "E": "14"}, "solution": None,
    "hints": [{"text": "Fixa't que les pomes van dins de bosses iguals.", "status": "revisado"},
              {"text": "Compta primer totes les pomes de les bosses.", "status": "revisado"},
              {"text": "A les bosses hi ha 12 pomes. Què passa després?", "status": "revisado"}],
    "checkpoints": [{"question": "Quantes pomes hi ha a les bosses?", "answer": 12, "unit": "pomes",
                     "status": "revisado"}],
    "distractors": {"D": {"text": "12 són les pomes abans que se'n mengi cap.", "status": "revisado"}},
    "anatomy": {"key_data": "3 bosses, 4 pomes a cada una, se'n menja 2.",
                "key_condition": "Pregunten les que queden, no les que hi havia.", "status": "revisado"},
}


def model_must_not_be_called(problem, student_text=""):
    raise AssertionError("the model was asked: " + student_text)


class Kinds(unittest.TestCase):
    def test_kind_of_question(self):
        for text, kind in (("per on començo?", "start"), ("no se como empezar", "start"),
                           ("no entenc què em demanen", "look"), ("i ara què faig", "next"),
                           ("he de multiplicar?", "next"), ("per què no pot ser 12?", "why"),
                           ("què vol dir bossa", "word"), ("consecutius vol dir seguits?", "word"),
                           ("les pomes són verdes", None)):
            self.assertEqual(match.kind(text), kind, text)

    def test_a_number_from_the_statement_is_not_an_attempt(self):
        self.assertEqual(match.attempt("m'ha donat 12", PROBLEM), 12)
        self.assertEqual(match.attempt("3x4=12 no?", PROBLEM), 12)
        self.assertIsNone(match.attempt("les 3 bosses", PROBLEM))
        self.assertIsNone(match.attempt("per què no pot ser 12 si hi ha tantes pomes?", PROBLEM))


class Picked(unittest.TestCase):
    def setUp(self):
        self.tutor = Tutor([PROBLEM])
        self.tutor.start("m1_cat")
        self.a = Assistant(self.tutor, ask=model_must_not_be_called, warmer=lambda problem: None)

    def test_how_to_start_gets_the_second_hint_and_the_button_never_repeats_it(self):
        r = self.a.chat("per on començo?")
        self.assertEqual((r["kind"], r["step"]["source"]), ("help", "hint 2"))
        self.assertEqual([self.tutor.help()["source"] for _ in range(3)], ["hint 1", "hint 3", "checkpoint 1"])

    def test_what_it_asks_gets_the_key_condition_once(self):
        r = self.a.chat("no entenc què em demanen")
        self.assertEqual(r["kind"], "reply")
        self.assertIn("les que queden", r["text"])
        again = self.a.chat("no entenc què em demanen")
        self.assertEqual(again["step"]["source"], "hint 1")

    def test_a_right_intermediate_number_is_confirmed_and_not_asked_again(self):
        r = self.a.chat("m'ha donat 12")
        self.assertEqual((r["kind"], r["tone"], r["events"]), ("reply", "ok", [{"event": "tick"}]))
        self.assertNotIn("checkpoint 1", [source for source, _ in self.tutor.waiting()])

    def test_the_final_answer_is_never_confirmed_or_denied(self):
        for number in ("m'ha donat 10", "m'ha donat 8"):      # the correct option and a wrong one
            tutor = Tutor([PROBLEM])
            tutor.start("m1_cat")
            r = Assistant(tutor, ask=model_must_not_be_called).chat(number)
            self.assertEqual(r["text"], match.LEAD["option"]["cat"], number)

    def test_an_unknown_number_gets_a_checkpoint_not_a_verdict(self):
        r = self.a.chat("m'ha donat 7")
        self.assertEqual((r["kind"], r["step"]["source"]), ("help", "checkpoint 1"))
        self.assertEqual(r["before"], match.LEAD["unknown_number"]["cat"])

    def test_why_not_a_wrong_option_gets_its_note(self):
        r = self.a.chat("per què no pot ser 12 si hi ha tantes pomes?")
        self.assertEqual((r["kind"], r["debug"]["matched"]), ("reply", "distractor D"))

    def test_a_question_with_no_keyword_takes_the_item_that_shares_words(self):
        r = self.a.chat("totes les pomes de les bosses es compten juntes?")
        self.assertEqual(r["step"]["source"], "hint 2")

    def test_not_a_request_for_the_next_problem(self):
        r = self.a.chat("i si es menja les pomes de la següent bossa què passa?")
        self.assertNotEqual(r["kind"], "next")

    def test_a_question_without_maths_words_is_still_about_the_problem(self):
        self.assertEqual(self.a.chat("puc fer un dibuix de les bosses per començar?")["kind"], "help")

    def test_off_topic_is_still_redirected(self):
        r = self.a.chat("quin temps fa avui a barcelona")
        self.assertEqual((r["kind"], r["debug"]["intent"]), ("rail", "offtopic"))

    def test_nothing_that_leaks_is_shown(self):
        leaky = {**PROBLEM, "anatomy": {"key_condition": "Al final en queden 10.", "status": "revisado"}}
        tutor = Tutor([leaky])
        tutor.start("m1_cat")
        r = Assistant(tutor, ask=model_must_not_be_called).chat("no entenc què em demanen")
        self.assertNotIn("10", str(r.get("text") or r["step"]["text"]))


if __name__ == "__main__":
    unittest.main()
