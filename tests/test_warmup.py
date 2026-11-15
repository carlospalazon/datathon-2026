"""Warm-up of three on a made-up catalogue: no model, no M3Kang data.

    python3 -m unittest tests.test_warmup -v
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
from copilot.matrix import frame  # noqa: E402
from copilot.practice import Practice, load_generators  # noqa: E402
from copilot.skillmap import WARMUP, WARMUP_DEFAULTS, SkillMap  # noqa: E402
from copilot.tutor import Tutor  # noqa: E402
from copilot.warmup import Warmup  # noqa: E402

TOPICS = ("aritmetica", "conteo", "medida", "numeros", "otros")


def catalogue():
    rows, n = [], 0
    for block in range(3):
        for topic in TOPICS:
            for _ in range(3):
                n += 1
                rows.append({"key": f"lvl-0_2020_{n}_cat", "id": f"lvl-0_2020_{n}", "language": "cat",
                             "stage": "primaria", "level": 0, "grade": 5, "block": block, "question_number": n,
                             "difficulty": block, "topic": topic, "text": f"SECRET TEXT {n}", "label": "C",
                             "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
                             "solution": {"text": "SECRET SOLUTION", "status": "revisado"},
                             "hints": [{"text": "SECRET HINT", "status": "revisado"}], "distractors": {}})
    return rows


def desk():
    problems = catalogue()
    skills = SkillMap(problems)
    tutor = Tutor(problems)
    tutor.observer = skills.tutor_event
    return skills, tutor


def miss(skills, tutor, topic, times=1):
    for key in skills.catalogue[(0, topic)][:times]:
        tutor.start(key)
        tutor.answer("A")


def solve(warm, practice):
    """Answer the warm-up problem on screen right, the way the page does (through the practice card)."""
    return practice.answer(practice.current["problem"]["label"])


class Topics(unittest.TestCase):
    def test_a_new_student_gets_the_defaults(self):
        skills, _ = desk()
        picked = skills.warmup_topics()
        self.assertEqual([p["topic"] for p in picked], [t for t in WARMUP_DEFAULTS if t in TOPICS][:WARMUP])
        self.assertFalse(any(p["from_map"] for p in picked))

    def test_the_topics_that_went_worst_come_first(self):
        skills, tutor = desk()
        miss(skills, tutor, "numeros", 1)        # one miss: begun
        miss(skills, tutor, "medida", 2)         # two misses: to reinforce
        tutor.start(skills.catalogue[(0, "conteo")][0])
        tutor.answer("C")                        # right the first time: not a hard topic
        picked = skills.warmup_topics()
        self.assertEqual([p["topic"] for p in picked][:2], ["medida", "numeros"])
        self.assertEqual([p["from_map"] for p in picked], [True, True, False])
        self.assertNotIn("conteo", [p["topic"] for p in picked[:2]])
        self.assertEqual(len({p["topic"] for p in picked}), WARMUP)
        self.assertEqual(skills.warmup_topics(can=lambda topic: topic == "medida"),
                         [{"topic": "medida", "from_map": True}] * 3)

    def test_only_topics_a_practice_problem_can_be_made_for(self):
        skills, tutor = desk()
        miss(skills, tutor, "otros", 2)
        picked = skills.warmup_topics(can=lambda topic: topic in ("conteo", "medida"))
        self.assertEqual([p["topic"] for p in picked], ["conteo", "medida", "conteo"])   # few topics: one of them twice
        self.assertEqual(skills.warmup_topics(can=lambda topic: False), [])

    def test_each_student_has_topics_of_their_own(self):
        skills, tutor = desk()
        miss(skills, tutor, "medida", 2)
        skills.new_student()
        self.assertFalse(any(p["from_map"] for p in skills.warmup_topics()))
        self.assertTrue(skills.warmup_topics(student=skills.students[0])[0]["from_map"])


@unittest.skipUnless(load_generators(), "the generators are not on this machine")
class TheWarmup(unittest.TestCase):
    def make(self, topics=("aritmetica", "conteo", "medida")):
        practice = Practice("cat", seed=4)
        return Warmup(practice, lambda: [{"topic": t, "from_map": False} for t in topics]), practice

    def test_three_problems_one_per_topic_then_it_is_over(self):
        warm, practice = self.make()
        self.assertEqual(warm.state(), {"pending": True, "active": False, "n": 0, "total": 3,
                                        "topics": ["aritmetica", "conteo", "medida"], "from_map": False})
        seen = []
        for n in (1, 2, 3):
            view = warm.next(level=0)
            self.assertEqual(view["warmup"], {"n": n, "total": 3})
            self.assertEqual(practice.current["level"], 0)
            self.assertTrue(warm.state()["active"] and not warm.state()["pending"])
            for word in ("label", "answer", "rationale", "solution"):
                self.assertNotIn(word, view)
            for event in view["events"]:
                frame(event)
            seen.append(view["topic"])
            self.assertTrue(solve(warm, practice)["correct"])
        self.assertEqual(seen, ["aritmetica", "conteo", "medida"])
        self.assertEqual(warm.next(level=0), {"finished": True, "done": True, "events": []})
        self.assertEqual((warm.state()["pending"], warm.state()["active"]), (False, False))
        self.assertEqual(warm.next(level=0)["done"], False)   # asked again: still over, nothing new made
        self.assertEqual(practice.count, 3)

    def test_the_same_problem_until_it_is_solved(self):
        warm, practice = self.make()
        first = warm.next(level=0)
        wrong = next(letter for letter in "ABCDE" if letter != practice.current["problem"]["label"])
        self.assertFalse(practice.answer(wrong)["correct"])
        self.assertEqual(warm.next(level=0), first)             # a reload, or a double click: not skipped
        solve(warm, practice)
        self.assertEqual(warm.next(level=0)["warmup"]["n"], 2)

    def test_it_can_be_skipped_before_or_in_the_middle(self):
        warm, practice = self.make()
        warm.close()
        self.assertEqual(warm.next(level=0), {"finished": True, "done": False, "events": []})
        self.assertEqual(practice.count, 0)
        warm, practice = self.make()
        warm.next(level=0)
        warm.close()
        self.assertEqual((warm.state()["pending"], warm.state()["active"], warm.state()["topics"]), (False, False, []))

    def test_a_topic_with_no_generator_is_dropped_and_none_at_all_is_no_warm_up(self):
        warm, practice = self.make(("otros", "medida"))
        view = warm.next(level=0)
        self.assertEqual((view["topic"], view["warmup"]), ("medida", {"n": 1, "total": 1}))
        warm, _ = self.make(())
        self.assertFalse(warm.state()["pending"])
        self.assertEqual(warm.next(level=0)["done"], False)


@unittest.skipUnless(load_generators(), "the generators are not on this machine")
class ThroughTheServer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self.tmp.name, "catalog.jsonl")
        with open(path, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in catalogue())
        self.app = server.App(argparse.Namespace(
            catalog=path, types="content/types_primaria.json", images=self.tmp.name, stage="primaria",
            language="cat", show="revisado,preparado,generado", profile=""))

    def tearDown(self):
        self.tmp.cleanup()

    def test_three_problems_that_reach_the_map_then_the_cangur_problem(self):
        call = self.app.call
        offer = call("state", {})["warmup"]
        self.assertTrue(offer["pending"])
        self.assertEqual(offer["total"], 3)
        for n in (1, 2, 3):
            view = call("warmupnext", {})
            self.assertEqual(view["warmup"]["n"], n)
            self.assertTrue(view["reading"]["lines"])
            self.assertTrue(view["frames"])
            self.assertNotIn("SECRET", json.dumps(view))
            self.assertTrue(call("state", {})["warmup"]["active"])
            label = self.app.practice.current["problem"]["label"]
            wrong = next(letter for letter in "ABCDE" if letter != label)
            self.assertFalse(call("practiceanswer", {"letter": wrong})["correct"])
            self.assertEqual(call("warmupnext", {})["warmup"]["n"], n)      # not solved yet: the same one
            self.assertTrue(call("practiceanswer", {"letter": label})["correct"])
        over = call("warmupnext", {})
        self.assertEqual((over["finished"], over["done"]), (True, True))
        self.assertEqual(len(over["frames"]), 1)                              # the matrix is back on the problem
        self.assertEqual((call("state", {})["warmup"]["pending"], call("state", {})["warmup"]["active"]), (False, False))
        cells = call("skillmap", {})["levels"][0]["cells"]
        self.assertEqual(sum(c["practice"] for c in cells), 3)                # each one counted once, by its first click
        self.assertEqual(sum(c["tries"] for c in cells), 0)                   # and no Cangur problem touched

    def test_a_warm_up_topic_the_level_on_screen_lacks_goes_to_the_nearest_tile(self):
        skills = self.app.skills
        skills.practice_answered({"topic": "medida", "level": 7, "problem": {"generator": "film_end_time"}},
                                 {"correct": True, "attempts": 1})
        cells = {c["topic"]: c for c in self.app.call("skillmap", {})["levels"][0]["cells"]}
        self.assertEqual(cells["medida"]["practice"], 1)

    def test_skipping_and_starting_a_cangur_problem_both_end_it(self):
        call = self.app.call
        skipped = call("warmupskip", {})
        self.assertEqual((skipped["finished"], skipped["done"]), (True, False))
        self.assertFalse(call("state", {})["warmup"]["pending"])
        call("studentnew", {})
        self.assertTrue(call("state", {})["warmup"]["pending"])               # the next student gets the offer
        call("warmupnext", {})
        call("answer", {"letter": "A"})                                       # went on to the Cangur problem
        self.assertEqual((call("state", {})["warmup"]["pending"], call("state", {})["warmup"]["active"]), (False, False))
        call("student", {"n": "0"})
        self.assertFalse(call("state", {})["warmup"]["pending"])              # not offered twice in a sitting

    def test_the_topics_follow_the_map_of_the_student_who_comes_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = os.path.join(tmp, "p.db")
            args = argparse.Namespace(**{**vars(self.app.args), "profile": profile})
            first = server.App(args)
            for _ in range(2):   # two misses in the topic on screen
                topic = first.tutor.current["problem"]["topic"]
                first.call("answer", {"letter": "A"})
                first.call("next", {})
            again = server.App(args)   # the next day
            offer = again.call("state", {})["warmup"]
            self.assertTrue(offer["pending"] and offer["from_map"])
            if again.practice.available(topic):
                self.assertEqual(offer["topics"][0], topic)


if __name__ == "__main__":
    unittest.main()
