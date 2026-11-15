"""'One like this, but yours': practice problems made on the spot, with the slip named.

No model and no M3Kang data: the problems come from the generators.

    python3 -m unittest tests.test_practice -v
"""
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot import practice as P  # noqa: E402
from copilot.matrix import frame  # noqa: E402

GEN = P.load_generators()
COVERED = [name for names in P.TOPICS.values() for name in names]
SEEDS = range(200)


class Mistakes(unittest.TestCase):
    def test_every_topic_generator_exists(self):
        for name in COVERED:
            self.assertIn(name, GEN.GENERATORS)

    def test_every_code_has_a_message_in_both_languages(self):
        for name, rule in P.MISTAKES.items():
            problem = GEN.generate(name, random.Random(0), "cat")
            _, slips = rule(problem["params"])
            for _, code in slips:
                cat, eng = P.MESSAGES[name][code]
                self.assertTrue(cat.strip() and eng.strip())
        for name, codes in P.MESSAGES.items():
            for texts in codes.values():
                for text in texts:  # a message with no number in it cannot contain the answer
                    self.assertIsNone(re.search(r"\d", text), text)

    def test_the_answer_worked_out_here_is_the_generators_answer(self):
        """The alarm for a generator that changed: its params no longer mean what we think."""
        for name, rule in P.MISTAKES.items():
            for language in ("cat", "eng"):
                for seed in SEEDS:
                    problem = GEN.generate(name, random.Random(seed), language)
                    answer, _ = rule(problem["params"])
                    self.assertEqual(str(answer), problem["answer"], f"{name} seed {seed}")

    def test_a_named_option_is_wrong_and_really_comes_from_that_slip(self):
        for name, rule in P.MISTAKES.items():
            for seed in SEEDS:
                problem = GEN.generate(name, random.Random(seed), "cat")
                named = P.mistakes(problem)
                self.assertNotIn(problem["label"], named)
                _, slips = rule(problem["params"])
                for letter, code in named.items():
                    self.assertNotEqual(problem["options"][letter], problem["answer"])
                    self.assertIn((problem["options"][letter], code), [(str(v), c) for v, c in slips])

    def test_most_wrong_options_get_a_name(self):
        named = total = 0
        for name in P.MISTAKES:
            for seed in SEEDS:
                named += len(P.mistakes(GEN.generate(name, random.Random(seed), "cat")))
                total += 4
        self.assertGreater(named / total, 0.55)

    def test_a_changed_generator_gets_no_names(self):
        problem = GEN.generate("shopping", random.Random(1), "cat")
        problem["params"]["pay"] += 1  # as if the generator now meant something else by "pay"
        self.assertEqual(P.mistakes(problem), {})


class ExplainItBack(unittest.TestCase):
    def test_every_way_is_a_slip_of_its_generator_and_has_no_number_in_it(self):
        self.assertNotIn("film_end_time", P.METHODS)
        self.assertNotIn("race_logic", P.METHODS)
        for name, ways in P.METHODS.items():
            _, slips = P.MISTAKES[name](GEN.generate(name, random.Random(0), "cat")["params"])
            self.assertIn("right", ways)
            self.assertGreaterEqual(len(ways), 3, name)
            for code, texts in ways.items():
                if code != "right":
                    self.assertIn(code, [c for _, c in slips], f"{name}: {code}")
                    self.assertIn(code, P.MESSAGES[name])
                for text in texts:
                    self.assertTrue(text.strip())
                    self.assertIsNone(re.search(r"\d", text), text)
            self.assertEqual(len({t for texts in ways.values() for t in texts}), 2 * len(ways), name)

    def test_the_three_ways_are_the_checked_one_and_two_slips_with_two_other_numbers(self):
        asked = total = 0
        for name in P.METHODS:
            for seed in SEEDS:
                problem = GEN.generate(name, random.Random(seed), "cat")
                items = P.explanations(problem, random.Random(seed))
                total += 1
                if items is None:
                    continue
                asked += 1
                _, slips = P.MISTAKES[name](problem["params"])
                self.assertEqual(len(items), 3)
                self.assertEqual([i["value"] for i in items if i["code"] == "right"], [problem["answer"]])
                wrong = [i for i in items if i["code"] != "right"]
                self.assertEqual(len({i["code"] for i in wrong}), 2)
                self.assertEqual(len({i["value"] for i in wrong} | {problem["answer"]}), 3, f"{name} seed {seed}")
                for item in wrong:   # the number is really what that slip gives for this draw
                    self.assertIn((item["value"], item["code"]), [(str(v), c) for v, c in slips])
        self.assertGreater(asked / total, 0.7)

    def test_a_changed_generator_is_not_asked_about(self):
        problem = GEN.generate("shopping", random.Random(1), "cat")
        self.assertIsNotNone(P.explanations(problem, random.Random(1)))
        problem["params"]["pay"] += 1
        self.assertIsNone(P.explanations(problem, random.Random(1)))


class PracticeFlow(unittest.TestCase):
    def test_the_view_never_carries_the_answer(self):
        practice = P.Practice("cat", seed=3)
        for topic in P.TOPICS:
            for _ in range(6):
                view = practice.new(topic)
                self.assertEqual(set(view), {"n", "topic", "kind", "text", "options", "events"})
                self.assertEqual(sorted(view["options"]), list("ABCDE"))
                self.assertEqual(len(set(view["options"].values())), 5)
                for event in view["events"]:
                    frame(event)  # every event is one the matrix can draw

    def test_topics_without_a_generator_get_nothing(self):
        practice = P.Practice("cat", seed=3)
        for topic in ("visual", "geometria_espacial", "otros", "nope"):
            self.assertFalse(practice.available(topic))
            self.assertIsNone(practice.new(topic))

    def test_without_the_generators_practice_is_off_not_broken(self):
        practice = P.Practice("cat", generators=None)
        practice.generators = None
        self.assertFalse(practice.available("aritmetica"))
        self.assertIsNone(practice.new("aritmetica"))

    def test_never_the_same_problem_twice_and_the_kinds_rotate(self):
        practice = P.Practice("cat", seed=5)
        views = [practice.new("aritmetica") for _ in range(12)]
        self.assertEqual(len({v["text"] for v in views}), 12)
        self.assertEqual([v["kind"] for v in views[:4]], P.TOPICS["aritmetica"])

    def test_a_wrong_answer_names_the_slip_without_the_answer(self):
        for language in ("cat", "eng"):
            practice = P.Practice(language, seed=7)
            for topic in P.TOPICS:
                for _ in range(4):
                    practice.new(topic)
                    problem = practice.current["problem"]
                    for letter in "ABCDE":
                        if letter == problem["label"]:
                            continue
                        result = practice.answer(letter)
                        self.assertFalse(result["correct"])
                        self.assertNotIn("solution", result)
                        self.assertEqual(result["mistake"]["status"], "regla")
                        self.assertTrue(result["mistake"]["text"])
                        self.assertNotIn(problem["answer"], result["mistake"]["text"])
                        self.assertEqual(result["events"], [{"event": "cross"}])

    def test_a_known_slip_is_named(self):
        practice = P.Practice("eng", seed=1)
        practice.new("aritmetica")  # the first kind of this topic is the shopping problem
        current = practice.current
        params = current["problem"]["params"]
        spent = str(params["a"] * params["p"] + params["b"] * params["q"])
        letter = next((k for k, v in current["problem"]["options"].items() if v == spent), None)
        self.assertIsNotNone(letter, "the draw shown prefers problems whose wrong options have a name")
        result = practice.answer(letter)
        self.assertEqual(result["mistake"]["code"], "spent_not_change")
        self.assertIn("costs", result["mistake"]["text"])

    def test_the_right_answer_gives_the_worked_solution(self):
        practice = P.Practice("cat", seed=2)
        practice.new("medida")
        problem = practice.current["problem"]
        result = practice.answer(problem["label"].lower())
        self.assertTrue(result["correct"])
        self.assertEqual(result["solution"], problem["rationale"])
        self.assertEqual(result["events"], [{"event": "tick"}])

    def test_the_solution_is_only_given_on_request(self):
        practice = P.Practice("cat", seed=2)
        with self.assertRaises(RuntimeError):
            practice.solution()
        practice.new("numeros")
        shown = practice.solution()
        self.assertEqual(shown["label"], practice.current["problem"]["label"])
        self.assertEqual(shown["answer"], practice.current["problem"]["answer"])
        frame(shown["events"][0])

    def test_a_right_answer_asks_how_it_was_solved_and_one_tap_answers(self):
        for language in ("cat", "eng"):
            practice = P.Practice(language, seed=11)
            practice.new("aritmetica")  # the shopping problem: several slips, so it can always be asked
            problem = practice.current["problem"]
            with self.assertRaises(ValueError):
                practice.explain(0)                                  # nothing to explain before it is solved
            wrong = next(letter for letter in "ABCDE" if letter != problem["label"])
            self.assertNotIn("explain", practice.answer(wrong))
            result = practice.answer(problem["label"])
            self.assertEqual([item["id"] for item in result["explain"]], [0, 1, 2])
            self.assertEqual([set(item) for item in result["explain"]], [{"id", "text"}] * 3)   # no code, no number
            self.assertEqual(len({item["text"] for item in result["explain"]}), 3)
            right = next(i for i, item in enumerate(practice.current["explain"]) if item["code"] == "right")
            for bad in ("", "x", 3, -1, None):
                with self.assertRaises(ValueError):
                    practice.explain(bad)
            told = practice.explain(str(right))
            self.assertEqual((told["correct"], told["right"], told["picked"]), (True, right, right))
            self.assertEqual(told["events"], [{"event": "tick"}])
            with self.assertRaises(ValueError):
                practice.explain(right)                              # one tap

    def test_picking_a_wrong_way_is_told_gently_with_the_number_it_gives(self):
        practice = P.Practice("cat", seed=12)
        practice.new("aritmetica")
        problem = practice.current["problem"]
        practice.answer(problem["label"])
        items = practice.current["explain"]
        other = next(i for i, item in enumerate(items) if item["code"] != "right")
        told = practice.explain(other)
        self.assertFalse(told["correct"])
        self.assertEqual(told["events"], [])                         # no cross: it never counts against the student
        self.assertIn(items[other]["value"], told["text"])
        self.assertIn(problem["answer"], told["text"])               # the answer is already theirs
        self.assertEqual(items[told["right"]]["code"], "right")

    def test_no_explaining_back_after_the_solution_was_shown_or_where_it_cannot_be_honest(self):
        practice = P.Practice("cat", seed=13)
        practice.new("aritmetica")
        practice.solution()
        self.assertNotIn("explain", practice.answer(practice.current["problem"]["label"]))
        practice.new("logica")       # the race: its wrong options are not slips
        self.assertNotIn("explain", practice.answer(practice.current["problem"]["label"]))
        practice.new("medida")       # the film: its wrong options are distances from the answer, not ways of solving
        self.assertEqual(practice.current["problem"]["generator"], "film_end_time")
        self.assertNotIn("explain", practice.answer(practice.current["problem"]["label"]))

    def test_bad_letters_are_refused(self):
        practice = P.Practice("cat", seed=2)
        with self.assertRaises(RuntimeError):
            practice.answer("A")
        practice.new("conteo")
        for bad in ("", "F", "AB", "1"):
            with self.assertRaises(ValueError):
                practice.answer(bad)

    def test_other_languages_fall_back_to_english(self):
        self.assertEqual(P.Practice("esp").language, "eng")


if __name__ == "__main__":
    unittest.main()
