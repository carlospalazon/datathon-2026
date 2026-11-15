"""copilot.prior: the statistical prior over letters and option shapes. Synthetic problems only.

    python3 -m unittest tests.test_prior
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "laptop"))

import build_prior  # noqa: E402
from copilot import pipeline, prior  # noqa: E402
from copilot.config import CONFIG  # noqa: E402

TABLE = os.path.join(ROOT, "copilot", "prior_table.json")


def problem(n, label, options=None, level=4, text=None, language="eng"):
    return {"id": f"lvl-{level}_2020_{n}", "language": language, "level": level, "year": 2020,
            "text": text if text is not None else f"{n}. A synthetic question.", "options": options or {},
            "label": label}


def options(*values):
    return dict(zip("ABCDE", (str(v) for v in values)))


class Parsing(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(prior.number("12"), 12.0)
        self.assertEqual(prior.number("3,5"), 3.5)
        self.assertEqual(prior.number("3/4"), 0.75)
        self.assertEqual(prior.number("14 km"), 14.0)
        self.assertEqual(prior.number("$-2$"), -2.0)
        self.assertIsNone(prior.number("12 3"))
        self.assertIsNone(prior.number("a>0"))
        self.assertIsNone(prior.number("1/0"))

    def test_one_noisy_option_keeps_its_leading_number(self):
        self.assertEqual(prior.numbers(options(21, 22, 24, 25, "23 7 7 9")), [21, 22, 24, 25, 23])
        self.assertIsNone(prior.numbers(options(21, "x", 24, 25, "23 7 7 9")))
        self.assertIsNone(prior.numbers(options("red", "blue", "green", "pink", "grey")))

    def test_shape(self):
        self.assertEqual(prior.shape([1, 2, 3, 4, 5]), "asc")
        self.assertEqual(prior.shape([5, 4, 3, 2, 1]), "desc")
        self.assertEqual(prior.shape([2, 1, 4, 5, 3]), "mixed")

    def test_question_number_and_section(self):
        self.assertEqual(prior.question_number("17. A square"), 17)
        self.assertEqual(prior.question_number(" 3) What"), 3)
        self.assertIsNone(prior.question_number("A square has 4 sides"))
        self.assertIsNone(prior.question_number("2015 was a year"))
        last = {"4": 30, "0": 24}
        self.assertEqual(prior.section(problem(1, "A"), last), 0)
        self.assertEqual(prior.section(problem(11, "A"), last), 1)
        self.assertEqual(prior.section(problem(30, "A"), last), 2)
        self.assertEqual(prior.section(problem(9, "A", level=0), last), 1)
        self.assertIsNone(prior.section(problem(1, "A", text="No number here."), last))

    def test_level_from_the_field_or_from_the_id(self):
        self.assertEqual(prior.level_of({"id": "x", "level": 3}), 3)
        self.assertEqual(prior.level_of({"id": "lvl-6_2019_4"}), 6)
        self.assertIsNone(prior.level_of({"id": "problem-9"}))


class Features(unittest.TestCase):
    def test_rank_only_when_the_options_are_not_in_order(self):
        mixed = problem(1, "A", options(30, 10, 50, 20, 40))
        ctx = prior.context(mixed, {})
        self.assertEqual(prior.f_rank_mixed(mixed, ctx), {"A": "r2", "B": "r0", "C": "r4", "D": "r1", "E": "r3"})
        ordered = problem(1, "A", options(1, 2, 3, 4, 5))
        self.assertIsNone(prior.f_rank_mixed(ordered, prior.context(ordered, {})))
        words = problem(1, "A", options("red", "blue", "green", "pink", "grey"))
        self.assertIsNone(prior.f_rank_mixed(words, prior.context(words, {})))

    def test_outlier_needs_exactly_one(self):
        p = problem(1, "A", options(1, 2, 3, 4, 90))
        self.assertEqual(prior.f_outlier(p, prior.context(p, {}))["E"], "out")
        even = problem(1, "A", options(1, 2, 3, 4, 5))
        self.assertIsNone(prior.f_outlier(even, prior.context(even, {})))

    def test_keys_never_hold_problem_or_option_text(self):
        p = problem(7, "B", options("zebra", "quagga", "okapi", "tapir", "none of these"),
                    text="7. Which striped animal is shown in the figure?")
        found = prior.keys(p, list(prior.FEATURES), {"4": 30})
        self.assertIn("letter", found)
        for by_letter in found.values():
            for key in by_letter.values():
                for word in ("zebra", "quagga", "okapi", "tapir", "none", "striped", "animal"):
                    self.assertNotIn(word, key)

    def test_a_broken_feature_is_skipped(self):
        p = problem(1, "A", {"A": None, "B": [], "C": {}, "D": 4, "E": 5.5})
        self.assertIn("letter", prior.keys(p, list(prior.FEATURES), {}))


class FitAndChoose(unittest.TestCase):
    def setUp(self):
        # Without options the answer is mostly B; with unordered numbers it is the middle value.
        rows = [problem(n, "B" if n % 4 else "E") for n in range(1, 41)]
        for n in range(1, 41):
            values = [30, 10, 50, 20, 40][n % 5:] + [30, 10, 50, 20, 40][:n % 5]
            rows.append(problem(n + 100, "ABCDE"[values.index(30)], options(*values)))
        self.rows = rows
        self.table = prior.fit(rows, options_features=("letter", "rank_mixed"))

    def test_weight_is_zero_at_the_base_rate_and_shrinks_small_cells(self):
        self.assertAlmostEqual(prior.weight(20, 100), 0.0)
        self.assertGreater(prior.weight(50, 100), prior.weight(5, 10))
        self.assertGreater(prior.weight(5, 10), 0.0)
        self.assertLess(prior.weight(0, 100), 0.0)

    def test_without_options_the_most_frequent_training_letter(self):
        letter, scores = prior.choose({"id": "new", "text": "No options here."}, self.table)
        self.assertEqual(letter, "B")
        self.assertEqual(set(scores), set("ABCDE"))

    def test_with_options_the_middle_value_wherever_it_is(self):
        for values in ([10, 50, 30, 40, 20], [30, 50, 10, 20, 40], [50, 40, 10, 20, 30]):
            asked = {"id": "new", "text": "Which?", "options": options(*values)}
            self.assertEqual(prior.choose(asked, self.table)[0], "ABCDE"[values.index(30)])

    def test_deterministic_and_ties_go_to_the_letter_order(self):
        empty = prior.fit([])
        self.assertEqual(prior.choose({"id": "x", "text": "t"}, empty)[0], empty["letter_order"][0])
        asked = {"id": "new", "text": "Which?", "options": options(10, 50, 30, 40, 20)}
        self.assertEqual(prior.choose(asked, self.table), prior.choose(dict(asked), self.table))

    def test_the_id_and_the_label_of_the_asked_problem_do_not_matter(self):
        asked = {"text": "Which?", "options": options(10, 50, 30, 40, 20)}
        letters = {prior.choose({**asked, "id": i, "label": label}, self.table)[0]
                   for i in ("a", "lvl-4_2020_101") for label in "AE"}
        self.assertEqual(len(letters), 1)

    def test_table_has_counts_and_weights_only(self):
        text = json.dumps(self.table)
        self.assertNotIn("synthetic", text)
        for part in self.table["parts"].values():
            for cells in part["cells"].values():
                for right, total, weight in cells.values():
                    self.assertLessEqual(right, total)
                    self.assertAlmostEqual(weight, prior.weight(right, total), places=4)

    def test_round_trip_through_json(self):
        table = json.loads(json.dumps(self.table))
        asked = {"id": "new", "text": "Which?", "options": options(10, 50, 30, 40, 20)}
        self.assertEqual(prior.choose(asked, table)[0], prior.choose(asked, self.table)[0])

    def test_strange_problems_still_get_a_letter(self):
        for asked in ({}, {"id": 5, "text": None}, {"id": "x", "text": "t", "options": {"A": "1", "B": "2"}},
                      {"id": "x", "text": "t", "options": {"A": None, "B": 2, "C": [], "D": "", "E": "x"}}):
            self.assertIn(prior.choose(asked, self.table)[0], tuple("ABCDE"))


class Builder(unittest.TestCase):
    def test_folds_keep_both_languages_of_an_id_together_and_are_stable(self):
        a, b = problem(3, "A"), problem(3, "A", language="cat")
        self.assertEqual(build_prior.fold_by_id(a), build_prior.fold_by_id(b))
        self.assertEqual(build_prior.fold_by_id({"id": "lvl-0_2015_1"}), 4)  # crc32, not Python's hash()

    def test_paired_difference_counts_an_id_once(self):
        rows = [problem(1, "A"), problem(1, "A", language="cat"), problem(2, "A"), problem(3, "A")]
        gain, low, high, z = build_prior.paired(rows, [True, True, False, False], [False, False, False, False])
        self.assertAlmostEqual(gain, 100 / 3)
        self.assertLess(low, gain)

    def test_a_feature_that_carries_the_answer_is_kept_and_noise_is_not(self):
        rows = []
        for n in range(1, 201):
            values = [30, 10, 50, 20, 40][n % 5:] + [30, 10, 50, 20, 40][:n % 5]
            rows.append(problem(n, "ABCDE"[values.index(30)], options(*values)))
        kept, hits = build_prior.select(rows, ("rank_mixed", "language", "none"), True)
        self.assertEqual(kept, ["rank_mixed"])
        self.assertEqual(sum(hits), len(rows))


@unittest.skipUnless(os.path.exists(TABLE), "copilot/prior_table.json not built")
class CommittedTable(unittest.TestCase):
    def test_loads_and_answers(self):
        table = prior.load(TABLE)
        self.assertEqual(table["source"], "data/train.jsonl")
        self.assertIn(prior.choose({"id": "x", "text": "No options."}, table)[0], tuple("ABCDE"))
        asked = {"id": "x", "text": "5. Which?", "level": 4, "options": options(10, 50, 30, 40, 20)}
        self.assertIn(prior.choose(asked, table)[0], tuple("ABCDE"))

    def test_holds_no_text(self):
        table = prior.load(TABLE)
        for part in table["parts"].values():
            for cells in part["cells"].values():
                for key, cell in cells.items():
                    self.assertRegex(key, r"^[A-Za-z0-9|]{1,12}$")
                    self.assertEqual(len(cell), 3)

    def test_load_rejects_an_unknown_feature(self):
        table = prior.load(TABLE)
        table["parts"]["options"]["features"].append("not_a_feature")
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(table, f)
        try:
            with self.assertRaises(ValueError):
                prior.load(f.name)
        finally:
            os.unlink(f.name)


class Model:
    """A fake post(): counts the calls and always answers C."""

    def __init__(self):
        self.calls = 0

    def __call__(self, url, payload, timeout):
        self.calls += 1
        return {"choices": [{"message": {"content": "C"}}], "timings": {"prompt_n": 7}}


class Pipeline(unittest.TestCase):
    """ANSWER_PRIOR=1 in copilot.pipeline.solve: the prior answers, the model is never called."""

    OFF = {"ANSWER_PRIOR": "", "PRESOLVE": "", "NO_OPTIONS_PRIOR": "", "LETTER_BIAS_FILE": "",
           "OPTION_ORDERS": "1", "ANSWER_MODE": "", "SAVE_TEXTS": ""}
    ASKED = {"id": "new-1", "language": "eng", "text": "Which?", "options": options(10, 50, 30, 40, 20)}

    def setUp(self):
        for cache in (pipeline._PRIOR_TABLE, pipeline._PRESOLVE_INDEX):
            cache.clear()
            self.addCleanup(cache.clear)
        rows = [problem(n, "B" if n % 4 else "E") for n in range(1, 41)]
        for n in range(1, 41):
            values = [30, 10, 50, 20, 40][n % 5:] + [30, 10, 50, 20, 40][:n % 5]
            rows.append(problem(n + 100, "ABCDE"[values.index(30)], options(*values)))
        self.table_path = self.temp(json.dumps(prior.fit(rows, options_features=("letter", "rank_mixed"))), ".json")
        self.on = {**self.OFF, "ANSWER_PRIOR": "1", "PRIOR_TABLE": self.table_path}

    def temp(self, text, suffix):
        f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def run_solve(self, settings, asked=None, **kw):
        model = Model()
        with mock.patch("copilot.llm.post", model), mock.patch.dict(CONFIG, settings):
            out = pipeline.solve(asked or self.ASKED, llm_url="http://127.0.0.1:9/x", **kw)
        return out, model.calls

    def test_off_by_default_the_model_answers_and_no_table_is_read(self):
        self.assertEqual(CONFIG["ANSWER_PRIOR"], "")
        out, calls = self.run_solve({**self.OFF, "PRIOR_TABLE": self.table_path})
        self.assertEqual((out["answer"], out["status"], calls), ("C", "ok", 1))
        self.assertEqual(pipeline._PRIOR_TABLE, {})

    def test_on_answers_with_and_without_options_and_never_calls_the_model(self):
        out, calls = self.run_solve(self.on)
        self.assertEqual((out["answer"], out["status"], calls, out["passes"]), ("C", "prior", 0, 0))
        out, calls = self.run_solve(self.on, {"id": "new-2", "text": "No options."})
        self.assertEqual((out["answer"], out["status"], calls), ("B", "prior", 0))
        self.assertIn("seconds", out)

    def test_same_letter_as_the_module(self):
        table = prior.load(self.table_path)
        for values in ([10, 50, 30, 40, 20], [50, 40, 10, 20, 30], [1, 2, 3, 4, 5]):
            asked = {**self.ASKED, "options": options(*values)}
            self.assertEqual(self.run_solve(self.on, asked)[0]["answer"], prior.choose(asked, table)[0])

    def test_missing_or_broken_table_goes_to_the_model(self):
        out, calls = self.run_solve({**self.on, "PRIOR_TABLE": "/nonexistent/prior.json"})
        self.assertEqual((out["answer"], out["status"], calls, out["prior_error"]),
                         ("C", "ok", 1, "FileNotFoundError"))
        pipeline._PRIOR_TABLE.clear()
        out, calls = self.run_solve({**self.on, "PRIOR_TABLE": self.temp("{not json", ".json")})
        self.assertEqual((out["status"], calls, out["prior_error"]), ("ok", 1, "JSONDecodeError"))

    def test_presolve_goes_first_and_its_copied_letter_counts(self):
        train = [{"id": "t1", "language": "eng", "text": "How many legs do three green spiders have in total?",
                  "options": options(12, 16, 24, 32, 40), "label": "C"}]
        settings = {**self.on, "PRESOLVE": "1",
                    "PRESOLVE_DATA": self.temp("\n".join(json.dumps(p) for p in train) + "\n", ".jsonl")}
        twin = {"id": "new-3", "language": "eng", "text": train[0]["text"], "options": options(24, 12, 40, 16, 32)}
        out, calls = self.run_solve(settings, twin)
        self.assertEqual((out["answer"], out["status"], calls), ("A", "presolve", 0))
        out, calls = self.run_solve(settings, {**twin, "options": {}})
        self.assertEqual((out["answer"], out["status"], calls), ("C", "presolve", 0))
        out, calls = self.run_solve(settings)
        self.assertEqual((out["answer"], out["status"], calls), ("C", "prior", 0))


if __name__ == "__main__":
    unittest.main()
