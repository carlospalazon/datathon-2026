"""Reading modes on made-up statements: no model, no M3Kang data.

    python3 -m unittest tests.test_reading -v
"""
import argparse
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "teach"))

import server  # noqa: E402
from copilot import reading as R  # noqa: E402

STATEMENT = ("La Pompeu té 12 capses amb 7 llapis cadascuna.  En regala 2 capses senceres; les altres les desa.\n"
             "Quants llapis desa?")


def problem(**changes):
    row = {"key": "lvl-0_2020_1_cat", "id": "lvl-0_2020_1", "language": "cat", "stage": "primaria", "level": 0,
           "grade": 5, "block": 0, "question_number": 1, "difficulty": 0, "topic": "aritmetica",
           "text": "1. " + STATEMENT, "question": STATEMENT, "label": "C", "needs_figure": False,
           "options": {"A": "84", "B": "14", "C": "70", "D": "19", "E": "98"},
           "solution": {"text": "SECRET SOLUTION", "status": "revisado"},
           "hints": [{"text": "SECRET HINT", "status": "revisado"}], "distractors": {},
           "anatomy": {"key_data": "12 capses; 7 llapis a cada capsa; en regala 2.",
                       "key_condition": "Es demanen els llapis que desa, no els que regala.",
                       "first_step": "SECRET STEP", "strategy": "SECRET STRATEGY", "status": "generado:test"}}
    row.update(changes)
    return row


def texts(view):
    return ["".join(piece["t"] for piece in line) for line in view["lines"]]


class Lines(unittest.TestCase):
    def test_one_idea_per_line_and_nothing_rewritten(self):
        found = R.lines(STATEMENT)
        self.assertEqual(found, ["La Pompeu té 12 capses amb 7 llapis cadascuna.", "En regala 2 capses senceres;",
                                 "les altres les desa.", "Quants llapis desa?"])
        self.assertEqual(" ".join(found), " ".join(STATEMENT.split()))

    def test_numbers_with_a_point_a_comma_a_colon_or_a_slash_stay_whole(self):
        text = "El tren surt a les 17:45 del 5/5/2015. Pesa 3,5 kg. Costa 2.50 € i fa 12 cm."
        self.assertEqual(len(R.lines(text)), 3)
        self.assertEqual([(n["n"], n["what"]) for n in R.numbers(text)],
                         [("17:45", ""), ("5/5/2015", ""), ("3,5", "kg"), ("2.50", "€"), ("12", "cm")])

    def test_the_word_after_a_number_only_when_it_says_what_is_counted(self):
        found = {n["n"]: n["what"] for n in R.numbers("Són 4 amics, 3 més que ahir, a 5è, 9 s'han quedat i 6 Pomes.")}
        self.assertEqual(found, {"4": "amics", "3": "", "9": "", "6": ""})  # 5è is not a number of the problem

    def test_an_empty_statement_is_no_lines(self):
        self.assertEqual(R.of_text(""), {"lines": [], "numbers": []})
        self.assertEqual(R.of_text(None), {"lines": [], "numbers": []})


class OfAProblem(unittest.TestCase):
    def test_the_statement_the_numbers_and_the_key_data(self):
        view = R.of_problem(problem())
        self.assertEqual(texts(view), R.lines(STATEMENT))
        self.assertEqual([(n["n"], n["what"]) for n in view["numbers"]], [("12", "capses"), ("7", "llapis"), ("2", "capses")])
        self.assertEqual(view["key_data"], ["12 capses", "7 llapis a cada capsa", "en regala 2"])
        self.assertTrue(view["key_condition"].startswith("Es demanen"))
        self.assertEqual(view["status"], "generado:test")
        self.assertFalse(view["figure"])
        marked = [piece["t"] for line in view["lines"] for piece in line if piece.get("key")]
        self.assertEqual(marked, ["12", "7", "2"])

    def test_only_the_numbers_the_key_data_names_are_marked(self):
        view = R.of_problem(problem(anatomy={"key_data": "12 capses de 7 llapis.", "key_condition": "", "status": "revisado"}))
        marked = [piece["t"] for line in view["lines"] for piece in line if piece.get("key")]
        self.assertEqual(marked, ["12", "7"])
        self.assertIsNone(view["key_condition"])

    def test_never_the_first_step_the_strategy_the_answer_or_the_help(self):
        sent = json.dumps(R.of_problem(problem()))
        self.assertNotIn("SECRET", sent)
        self.assertNotIn('"label"', sent)
        self.assertNotIn('"options"', sent)

    def test_key_data_that_gives_the_answer_away_is_left_out(self):
        view = R.of_problem(problem(anatomy={"key_data": "12 capses; en queden 10, que fan 70 llapis.",
                                             "key_condition": "La resposta és C.", "status": "revisado"}))
        self.assertEqual(view["key_data"], [])
        self.assertIsNone(view["key_condition"])
        self.assertIsNone(view["status"])
        self.assertTrue(all(piece.get("key") for line in view["lines"] for piece in line if piece.get("n")))

    def test_key_data_of_a_status_not_shown_is_left_out(self):
        view = R.of_problem(problem(), show={"revisado"})
        self.assertEqual((view["key_data"], view["key_condition"]), ([], None))
        self.assertEqual(texts(view), R.lines(STATEMENT))   # the statement is still there

    def test_a_problem_without_anatomy_or_question_still_reads(self):
        row = problem(needs_figure=True)
        del row["anatomy"], row["question"]
        view = R.of_problem(row)
        self.assertEqual(texts(view)[0], "1.")
        self.assertEqual(view["key_data"], [])
        self.assertTrue(view["figure"])


class TheChoice(unittest.TestCase):
    def test_switches_are_kept_per_student_and_only_known_ones(self):
        choices = R.Choices()
        self.assertEqual(choices.get("Guineu"), [])
        self.assertEqual(choices.set("Guineu", "numbers-lines-dyslexia"), ["lines", "numbers"])
        self.assertEqual(choices.get("Mussol"), [])
        self.assertEqual(choices.set("Guineu", "none"), [])

    def test_the_choice_survives_a_restart_with_a_profile_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "profile.db")
            R.Choices(path).set("Guineu", ["space", "key"])
            self.assertEqual(R.Choices(path).get("Guineu"), ["space", "key"])
            self.assertEqual(R.Choices(path).get("Mussol"), [])


class ThroughTheServer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self.tmp.name, "catalog.jsonl")
        rows = [problem(key=f"lvl-0_2020_{n}_cat", id=f"lvl-0_2020_{n}", question_number=n, block=n % 3,
                        difficulty=n % 3, topic=("aritmetica", "conteo", "medida")[n % 3]) for n in range(1, 13)]
        with open(path, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in rows)
        self.app = server.App(argparse.Namespace(
            catalog=path, types="content/types_primaria.json", images=self.tmp.name, stage="primaria",
            language="cat", show="revisado,preparado,generado", profile=os.path.join(self.tmp.name, "p.db")))

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_choice_is_remembered_per_student_and_never_reaches_the_map(self):
        call = self.app.call
        first = call("reading", {})
        self.assertEqual(first["modes"], [])
        self.assertEqual(len(first["lines"]), 4)
        self.assertEqual(call("readingmode", {"modes": "lines-key"})["modes"], ["lines", "key"])
        call("next", {})
        self.assertEqual(call("reading", {})["modes"], ["lines", "key"])       # the next problem keeps them
        call("studentnew", {})
        self.assertEqual(call("reading", {})["modes"], [])                      # a new student starts plain
        call("readingmode", {"modes": "numbers"})
        call("student", {"n": "0"})
        self.assertEqual(call("reading", {})["modes"], ["lines", "key"])       # and the first one comes back to theirs
        for sent in (call("skillmap", {}), call("classmap", {}), call("classsample", {}), call("state", {}),
                     call("session", {}), call("examinfo", {})):
            text = json.dumps(sent)
            for word in ("modes", "lines", "numbers", "reading", "display"):
                self.assertNotIn(f'"{word}"', text)
        self.assertEqual(call("readingmode", {"modes": "none"})["modes"], [])

    def test_the_practice_card_gets_its_text_for_reading_and_no_answer(self):
        call = self.app.call
        if not call("practiceok", {})["available"]:
            self.skipTest("no generators on this machine")
        view = call("practice", {})
        self.assertEqual(" ".join("".join(p["t"] for p in line) for line in view["reading"]["lines"]),
                         " ".join(view["text"].split()))
        self.assertTrue(view["reading"]["numbers"])
        self.assertNotIn("label", view)

    def test_nothing_secret_in_what_reading_sends(self):
        sent = json.dumps(self.app.call("reading", {}))
        self.assertNotIn("SECRET", sent)
        self.assertNotIn('"label"', sent)


if __name__ == "__main__":
    unittest.main()
