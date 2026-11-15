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
