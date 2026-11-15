"""The skill map on a small made-up catalogue: no model, no M3Kang data.

    python3 -m unittest tests.test_skillmap -v
"""
import argparse
import json
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "teach"))

import server  # noqa: E402
from copilot.exam import Exam  # noqa: E402
from copilot.matrix import COLS, ROWS, frame, rgb  # noqa: E402
from copilot.skillmap import ANIMALS, SkillMap, sample_class, state  # noqa: E402
from copilot.tutor import Tutor  # noqa: E402

TOPICS = ("aritmetica", "conteo", "medida")


def catalogue(per_block=2):
    """Two levels, three blocks, three topics: per_block problems of each topic in each block."""
    rows = []
    for level in (0, 1):
        n = 0
        for block in range(3):
            for topic in TOPICS:
                for _ in range(per_block):
                    n += 1
                    rows.append({"key": f"lvl-{level}_2020_{n}_cat", "id": f"lvl-{level}_2020_{n}", "language": "cat",
                                 "stage": "primaria", "level": level, "grade": 5 + level, "block": block,
                                 "question_number": n, "difficulty": level * 3 + block, "topic": topic,
                                 "text": f"SECRET TEXT {n}", "label": "C",
                                 "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
                                 "solution": {"text": "SECRET SOLUTION", "status": "revisado"},
                                 "hints": [{"text": "SECRET HINT", "status": "revisado"}], "distractors": {}})
    return rows


def desk():
    """A skill map and a tutor that reports to it."""
    problems = catalogue()
    skills = SkillMap(problems)
    tutor = Tutor(problems)
    tutor.observer = skills.tutor_event
    return skills, tutor


def keys(skills, level, topic):
    return skills.catalogue[(level, topic)]


def cell(view, level, topic):
    row = next(r for r in view["levels"] if r["level"] == level)
    return next(c for c in row["cells"] if c["topic"] == topic)


def solve(tutor, key, *letters):
    tutor.start(key)
    for letter in letters:
        tutor.answer(letter)


class Words(unittest.TestCase):
    def test_the_word_for_a_topic(self):
        self.assertEqual(state(0, 0), "new")
        self.assertEqual(state(0, 0, other=1), "tried")   # only practice or an exam blank
        self.assertEqual(state(1, 1), "tried")
        self.assertEqual(state(2, 2), "tried")            # two are not enough to call it solid
        self.assertEqual(state(3, 3), "solid")
        self.assertEqual(state(3, 4), "solid")
        self.assertEqual(state(3, 5), "tried")
        self.assertEqual(state(4, 5), "solid")
        self.assertEqual(state(0, 1), "tried")            # one miss is not a pattern
        self.assertEqual(state(0, 2), "shaky")
        self.assertEqual(state(2, 5), "shaky")
        self.assertEqual(state(1, 2), "tried")


class FromTheTutor(unittest.TestCase):
    def test_an_empty_map_still_says_what_to_try(self):
        skills, tutor = desk()
        tutor.start(keys(skills, 0, "aritmetica")[0])
        view = skills.view(seen=tutor.seen, home=0)
        self.assertFalse(view["started"])
        self.assertEqual([len(r["cells"]) for r in view["levels"]], [3, 3])
        self.assertTrue(all(c["state"] == "new" and c["problems"] == 6 for r in view["levels"] for c in r["cells"]))
        self.assertEqual(len(view["next"]), 3)
        self.assertTrue(all(n["level"] == 0 and n["state"] == "new" for n in view["next"]))
        self.assertNotIn(view["next"][0]["key"], tutor.seen)  # starting a problem is not trying it
        self.assertEqual(view["events"][0]["value"], [0, 0, 0])

    def test_right_first_time_right_later_left_open_and_solution_shown(self):
        skills, tutor = desk()
        a = keys(skills, 0, "aritmetica")
        solve(tutor, a[0], "C")            # right the first time
        solve(tutor, a[1], "A", "C")       # right after a miss
        solve(tutor, a[2], "B")            # wrong, then on to the next problem
        tutor.start(a[3])
        tutor.solution()                   # gave up
        got = [i["outcome"] for i in skills.items[skills.student].values()]
        self.assertEqual(got, ["first", "later", "open", "shown"])
        c = cell(skills.view(), 0, "aritmetica")
        self.assertEqual((c["clean"], c["tries"], c["state"]), (1, 4, "shaky"))

    def test_solid_takes_three_first_time_answers_and_the_last_five_count(self):
        skills, tutor = desk()
        a = keys(skills, 0, "aritmetica") + keys(skills, 1, "aritmetica")
        solve(tutor, a[0], "A")
        solve(tutor, a[1], "A")
        self.assertEqual(cell(skills.view(), 0, "aritmetica")["state"], "shaky")
        for key in a[2:6]:
            solve(tutor, key, "C")
        c = cell(skills.view(), 0, "aritmetica")
        self.assertEqual((c["clean"], c["tries"], c["done"], c["state"]), (4, 5, 6, "solid"))
        self.assertEqual(cell(skills.view(), 0, "conteo")["state"], "new")

    def test_a_problem_met_twice_is_one_record(self):
        skills, tutor = desk()
        key = keys(skills, 0, "conteo")[0]
        solve(tutor, key, "A")
        solve(tutor, key, "C")  # back to it later: right, but not the first time it was met
        items = skills.items[skills.student]
        self.assertEqual(len(items), 1)
        self.assertEqual(items["cangur:" + key]["outcome"], "later")
        solve(tutor, key, "A")  # a settled problem is not rewritten
        self.assertEqual(items["cangur:" + key]["outcome"], "later")

    def test_a_slip_the_tutor_names_twice_in_a_topic_is_shown(self):
        skills, tutor = desk()
        a = keys(skills, 0, "aritmetica")
        for key in a[:2]:   # the tutor names the slip while it checks the wrong answer, then reports the answer
            skills.tutor_event("slip", skills.problems[key], {"code": "sum_all"})
            skills.tutor_event("answer", skills.problems[key], {"correct": False})
        c = cell(skills.view(), 0, "aritmetica")
        self.assertEqual((c["tries"], c["clean"]), (2, 0))
        self.assertTrue(c["slip"] and not re.search(r"\d", c["slip"]))
        self.assertIsNone(cell(skills.view(), 0, "conteo")["slip"])

    def test_what_to_try_next_starts_where_it_goes_worst(self):
        skills, tutor = desk()
        for key in keys(skills, 1, "medida")[:2]:
            solve(tutor, key, "A")                     # shaky, on the other level
        solve(tutor, keys(skills, 0, "conteo")[0], "C")  # just begun
        view = skills.view(seen=tutor.seen, home=0)
        self.assertEqual([(n["topic"], n["level"], n["state"]) for n in view["next"]],
                         [("medida", 1, "shaky"), ("conteo", 0, "tried"), ("aritmetica", 0, "new")])
        self.assertTrue(all(n["key"] not in tutor.seen for n in view["next"]))
        self.assertEqual(view["events"][0]["next"], skills.topics.index("medida"))

    def test_nothing_left_to_suggest_when_every_topic_tried_is_solid(self):
        problems = [p for p in catalogue() if p["level"] == 0 and p["topic"] == "medida"]
        skills = SkillMap(problems)
        tutor = Tutor(problems)
        tutor.observer = skills.tutor_event
        for key in keys(skills, 0, "medida")[:3]:
            solve(tutor, key, "C")
        view = skills.view(seen=tutor.seen, home=0)
        self.assertEqual(cell(view, 0, "medida")["state"], "solid")
        self.assertEqual(view["next"], [])
        self.assertTrue(view["started"])


class FromPracticeAndTheExam(unittest.TestCase):
    def practice(self, skills, correct, attempts=1, code="spent_not_change"):
        current = {"topic": "aritmetica", "level": 0, "problem": {"generator": "shopping"}}
        mistake = None if correct else {"code": code}
        skills.practice_answered(current, {"correct": correct, "attempts": attempts, "mistake": mistake})

    def test_practice_counts_once_and_never_makes_a_topic_solid(self):
        skills, _ = desk()
        self.practice(skills, False)
        self.practice(skills, True, attempts=2)   # a second click on the same card: the student reading the slips
        c = cell(skills.view(), 0, "aritmetica")
        self.assertEqual((c["practice"], c["tries"], c["state"]), (1, 0, "tried"))
        for _ in range(5):
            self.practice(skills, True)
        c = cell(skills.view(), 0, "aritmetica")
        self.assertEqual((c["practice"], c["tries"], c["state"]), (6, 0, "tried"))

    def test_a_slip_that_comes_back_is_named_without_a_number(self):
        skills, _ = desk()
        self.practice(skills, False)
        self.assertIsNone(cell(skills.view(), 0, "aritmetica")["slip"])   # once is not a pattern
        self.practice(skills, False)
        slip = cell(skills.view(), 0, "aritmetica")["slip"]
        self.assertTrue(slip and len(slip) > 20)
        self.assertIsNone(re.search(r"\d", slip))
        self.practice(skills, False, code="no such slip")
        self.practice(skills, False, code="no such slip")
        self.practice(skills, False, code="no such slip")  # an unknown code says nothing rather than breaking
        self.assertIsNone(cell(skills.view(), 0, "aritmetica")["slip"])

    def test_a_practice_slip_reaches_the_tutors_memory_on_the_first_click_only(self):
        from types import SimpleNamespace
        skills, tutor = desk()
        tutor.start(keys(skills, 0, "aritmetica")[0])
        card = SimpleNamespace(current={"topic": "aritmetica", "level": 0, "problem": {"generator": "shopping"}})
        wrong = lambda attempts, code="spent_not_change": {"correct": False, "attempts": attempts, "mistake": {"code": code}}
        first = wrong(1)
        skills.after("practiceanswer", tutor, card, None, first)
        self.assertEqual((first["again"], first["method_next"]), (False, False))
        later = wrong(2)                                   # a second click on the same card: reading the slips
        skills.after("practiceanswer", tutor, card, None, later)
        self.assertNotIn("again", later)
        unnamed = wrong(1, code=None)                      # a wrong option no slip explains
        skills.after("practiceanswer", tutor, card, None, unnamed)
        self.assertNotIn("again", unnamed)
        right = {"correct": True, "attempts": 1, "mistake": None}
        skills.after("practiceanswer", tutor, card, None, right)
        self.assertNotIn("again", right)
        self.assertEqual(tutor.errors, {("aritmetica", "practice:shopping:spent_not_change"): 1})
        again = wrong(1)                                   # another card, the same slip
        skills.after("practiceanswer", tutor, card, None, again)
        self.assertTrue(again["again"])
        self.assertEqual(tutor.errors, {("aritmetica", "practice:shopping:spent_not_change"): 2})

    def test_a_practice_card_with_no_level_is_left_out(self):
        skills, _ = desk()
        skills.practice_answered({"topic": "aritmetica", "problem": {"generator": "shopping"}},
                                 {"correct": True, "attempts": 1})
        self.assertFalse(skills.view()["started"])

    def sit(self, skills, answers):
        clock = [1000.0]
        exam = Exam(catalogue(), clock=lambda: clock[0], seed=1)
        exam.start(0, "tast")
        for n, letter in answers.items():
            exam.answer(n, letter)
        return exam, clock

    def test_an_exam_is_recorded_once_and_a_blank_is_not_a_miss(self):
        skills, tutor = desk()
        exam, _ = self.sit(skills, {1: "C", 2: "A"})   # right, wrong, blank
        skills.after("examtick", tutor, None, exam, exam.tick())
        self.assertFalse(skills.view()["started"])     # nothing while the paper runs
        for action in ("examfinish", "examstate", "examstate"):
            skills.after(action, tutor, None, exam, exam.finish())
        got = sorted(i["outcome"] for i in skills.items[skills.student].values())
        self.assertEqual(got, ["blank", "first", "open"])
        cells = [c for r in skills.view()["levels"] for c in r["cells"]]
        self.assertEqual(sum(c["blank"] for c in cells), 1)
        self.assertEqual(sum(c["tries"] for c in cells), 2)

    def test_a_paper_the_clock_handed_in_is_recorded_too(self):
        skills, tutor = desk()
        exam, clock = self.sit(skills, {1: "C"})
        clock[0] += 10000
        skills.after("examtick", tutor, None, exam, exam.tick())
        self.assertEqual(len(skills.items[skills.student]), 3)

    def test_a_paper_left_without_handing_in_records_nothing(self):
        skills, tutor = desk()
        exam, _ = self.sit(skills, {1: "C"})
        skills.after("examclose", tutor, None, exam, exam.close())
        self.assertFalse(skills.view()["started"])

    def test_an_exam_miss_solved_with_the_tutor_is_one_problem_that_improved(self):
        skills, tutor = desk()
        exam, _ = self.sit(skills, {1: "A"})
        skills.after("examfinish", tutor, None, exam, exam.finish())
        missed = exam.paper["questions"][0]["problem"]["key"]
        blank = exam.paper["questions"][1]["problem"]["key"]
        solve(tutor, missed, "C")
        solve(tutor, blank, "C")
        items = skills.items[skills.student]
        self.assertEqual(len(items), 3)
        self.assertEqual(items["cangur:" + missed]["outcome"], "later")
        self.assertEqual(items["cangur:" + blank]["outcome"], "first")  # a blank had not been tried


class TheMapPlans(unittest.TestCase):
    def mixed(self):
        """A map with a shaky topic (on the other level), one just begun, and one new."""
        skills, tutor = desk()
        for key in keys(skills, 1, "medida")[:2]:
            solve(tutor, key, "A")
        solve(tutor, keys(skills, 0, "conteo")[0], "C")
        return skills, tutor

    def test_a_session_is_one_shaky_one_begun_and_one_new_topic(self):
        skills, tutor = self.mixed()
        plan = skills.plan_start(seen=tutor.seen, home=0)
        self.assertEqual([(s["topic"], s["level"], s["state"]) for s in plan["steps"]],
                         [("medida", 1, "shaky"), ("conteo", 0, "tried"), ("aritmetica", 0, "new")])
        self.assertEqual((plan["at"], plan["total"], plan["active"], plan["finished"]), (-1, 3, False, False))
        self.assertTrue(all(s["status"] == "todo" and s["outcome"] is None for s in plan["steps"]))

    def test_an_empty_map_gives_three_new_topics_and_one_topic_gives_three_problems(self):
        skills, tutor = desk()
        plan = skills.plan_start(seen=tutor.seen, home=0)
        self.assertEqual([s["state"] for s in plan["steps"]], ["new"] * 3)
        self.assertEqual(len({s["topic"] for s in plan["steps"]}), 3)
        problems = [p for p in catalogue() if p["level"] == 0 and p["topic"] == "medida"]
        alone = SkillMap(problems)
        self.assertEqual(alone.plan_start(home=0)["total"], 3)
        got = [alone.plan_advance(seen=())["key"] for _ in range(3)]   # nothing answered: the same one is offered
        self.assertEqual(len(got), 3)

    def test_each_step_starts_a_problem_not_yet_seen_and_the_plan_ends(self):
        skills, tutor = self.mixed()
        skills.plan_start(seen=tutor.seen, home=0)
        self.assertIsNone(SkillMap(catalogue()).plan_state())
        started = []
        for n in range(3):
            step = skills.plan_advance(seen=tutor.seen)
            self.assertNotIn(step["key"], tutor.seen)
            started.append(step["key"])
            solve(tutor, step["key"], "C")
            state = skills.plan_state()
            self.assertEqual((state["at"], state["active"]), (n, True))
            self.assertEqual(state["steps"][n]["status"], "now")
            self.assertEqual(state["steps"][n]["outcome"], "first")
        self.assertEqual([skills.problems[k]["topic"] for k in started], ["medida", "conteo", "aritmetica"])
        self.assertEqual(skills.plan_advance(seen=tutor.seen), {"finished": True})
        state = skills.plan_state()
        self.assertEqual((state["active"], state["finished"]), (False, True))
        self.assertTrue(all(s["status"] == "done" for s in state["steps"]))
        skills.plan_stop()
        self.assertIsNone(skills.plan_state())
        with self.assertRaises(ValueError):
            skills.plan_advance()

    def test_a_slip_that_came_back_gets_a_practice_offer_once_before_moving_on(self):
        skills, tutor = desk()
        a = keys(skills, 0, "aritmetica")
        skills.tutor_event("slip", skills.problems[a[0]], {"code": "sum_all"})
        skills.tutor_event("answer", skills.problems[a[0]], {"correct": False})
        skills.plan_start(seen={a[0]}, home=0)
        key = skills.plan_advance(seen={a[0]})["key"]
        self.assertEqual(skills.problems[key]["topic"], "aritmetica")
        self.assertIn("key", dict(skills.plans[skills.student]["steps"][0]))
        skills.tutor_event("slip", skills.problems[key], {"code": "sum_all"})      # the same slip, on the step's problem
        skills.tutor_event("answer", skills.problems[key], {"correct": False})
        seen = {a[0], key}
        step = skills.plan_advance(seen=seen, on_screen=key)
        self.assertEqual(step["offer"]["topic"], "aritmetica")
        self.assertIsNone(re.search(r"\d", step["offer"]["slip"]))
        self.assertEqual(skills.plan_state()["at"], 0)                             # still on the same step
        self.assertIn("key", skills.plan_advance(seen=seen, on_screen=key))        # asked again: on to the next one

    def test_no_offer_without_a_practice_problem_or_for_a_slip_seen_once(self):
        skills, tutor = desk()
        skills.plan_start(home=0)
        key = skills.plan_advance()["key"]
        skills.tutor_event("slip", skills.problems[key], {"code": "sum_all"})
        self.assertIn("key", skills.plan_advance(seen={key}, on_screen=key))       # once is not a pattern
        skills, tutor = desk()
        a = keys(skills, 0, "aritmetica")
        skills.tutor_event("slip", skills.problems[a[0]], {"code": "sum_all"})
        skills.plan_start(seen={a[0]}, home=0)
        key = skills.plan_advance(seen={a[0]})["key"]
        skills.tutor_event("slip", skills.problems[key], {"code": "sum_all"})
        self.assertIn("key", skills.plan_advance(seen={a[0], key}, on_screen=None))  # no practice for this topic

    def test_each_student_has_a_session_of_their_own(self):
        skills, tutor = self.mixed()
        skills.plan_start(seen=tutor.seen, home=0)
        skills.new_student()
        self.assertIsNone(skills.plan_state())
        skills.switch(0)
        self.assertEqual(skills.plan_state()["total"], 3)

    def test_the_tutor_reads_the_map_for_its_next_problem(self):
        skills, tutor = desk()
        tutor.planner = lambda problem: skills.advice(problem, tutor.seen)
        exam = Exam(catalogue(), clock=lambda: 0.0, seed=1)   # an exam makes "conteo" of the other level shaky
        for key in keys(skills, 1, "conteo")[:2]:
            skills._cangur(skills.student, skills.problems[key], "wrong")
        a = keys(skills, 0, "aritmetica")
        for key in a[:2]:
            solve(tutor, key, "C")
            self.assertEqual(tutor.next_problem()["problem"]["topic"], "aritmetica")   # two are not solid yet
        solve(tutor, a[2], "C")
        self.assertTrue(skills.advice(skills.problems[a[2]], tutor.seen)["solid"])
        self.assertEqual(skills.advice(skills.problems[a[2]], tutor.seen)["topics"][0], "conteo")
        self.assertEqual(tutor.next_problem()["problem"]["topic"], "conteo")           # where the map says it goes worst
        del exam

    def test_a_topic_the_map_calls_solid_is_left_before_the_streak(self):
        skills, tutor = desk()
        tutor.planner = lambda problem: skills.advice(problem, tutor.seen)
        a = keys(skills, 0, "aritmetica")
        for key in a[:3]:   # three right the first time in an exam: solid on the map, no streak in the tutor
            skills._cangur(skills.student, skills.problems[key], "right")
        solve(tutor, a[3], "C")
        self.assertNotEqual(tutor.next_problem()["problem"]["topic"], "aritmetica")
        plain = Tutor(catalogue())   # without a map the tutor's own rule is untouched
        solve(plain, a[3], "C")
        self.assertEqual(plain.next_problem()["problem"]["topic"], "aritmetica")


class NothingLeaks(unittest.TestCase):
    def test_no_text_no_solution_and_no_right_letter_in_what_is_sent(self):
        skills, tutor = desk()
        solve(tutor, keys(skills, 0, "aritmetica")[0], "A", "C")
        skills.new_student()
        plan = skills.plan_start(seen=tutor.seen, home=0)
        step = skills.plan_advance(seen=tutor.seen)
        self.assertEqual(set(step), {"key"})
        for sent in (skills.view(seen=tutor.seen, home=0), skills.classroom(), sample_class(catalogue()),
                     plan, skills.plan_state(), skills.advice(skills.problems[step["key"]])):
            text = json.dumps(sent)
            self.assertNotIn("SECRET", text)
            self.assertNotIn('"label"', text)
            self.assertNotIn('"options"', text)


class TheClass(unittest.TestCase):
    def test_students_are_animals_and_each_has_a_map_of_their_own(self):
        skills, tutor = desk()
        first = skills.student
        solve(tutor, keys(skills, 0, "medida")[0], "C")
        second = skills.new_student()
        self.assertNotEqual(first, second)
        self.assertEqual([first, second], list(ANIMALS[:2]))
        self.assertFalse(skills.view()["started"])
        self.assertEqual(skills.switch(0), first)
        self.assertTrue(skills.view()["started"])
        with self.assertRaises(ValueError):
            skills.switch(7)
        with self.assertRaises(ValueError):
            skills.switch("x")

    def test_pseudonyms_never_repeat(self):
        skills = SkillMap(catalogue())
        for _ in range(len(ANIMALS) + 3):
            skills.new_student()
        self.assertEqual(len(set(skills.students)), len(skills.students))

    def test_the_class_view_is_in_seating_order_and_says_where_the_class_is_stuck(self):
        skills, _ = desk()
        problems = skills.problems
        names = [skills.student, skills.new_student(), skills.new_student()]
        for name, letters in zip(names, ("AAA", "AAC", "CCC")):
            for key, letter in zip(keys(skills, 0, "conteo"), letters):
                skills.tutor_event("answer", problems[key], {"correct": letter == "C"}, student=name)
        room = skills.classroom()
        self.assertEqual([s["name"] for s in room["students"]], names)   # not sorted by how it went
        self.assertEqual([s["current"] for s in room["students"]], [False, False, True])
        self.assertEqual(room["topics"], list(TOPICS))
        states = [next(c["state"] for c in s["cells"] if c["topic"] == "conteo") for s in room["students"]]
        self.assertEqual(states, ["shaky", "shaky", "solid"])
        self.assertEqual(room["stuck"], [{"topic": "conteo", "shaky": 2, "tried": 3}])
        self.assertFalse(room["sample"])
        for s in room["students"]:   # no mark and no total per student: only topic cells
            self.assertEqual(set(s), {"name", "current", "cells"})

    def test_the_sample_class_is_marked_and_kept_nowhere(self):
        a, b = sample_class(catalogue()), sample_class(catalogue())
        self.assertEqual(a, b)
        self.assertTrue(a["sample"])
        self.assertEqual(len(a["students"]), 8)
        self.assertFalse(any(s["current"] for s in a["students"]))

    def test_the_map_survives_a_restart_with_a_profile_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "profile.sqlite")
            problems = catalogue()
            skills = SkillMap(problems, path=path)
            tutor = Tutor(problems, profile_path=path)   # the tutor's own tables live in the same file
            tutor.observer = skills.tutor_event
            solve(tutor, keys(skills, 0, "medida")[0], "A", "C")
            skills.new_student()
            skills.practice_answered({"topic": "conteo", "level": 1, "problem": {"generator": "outfits"}},
                                     {"correct": True, "attempts": 1})
            again = SkillMap(problems, path=path)
            self.assertEqual(again.students, skills.students)
            self.assertEqual(again.items, skills.items)
            self.assertEqual(again.student, skills.students[0])
            self.assertEqual(Tutor(problems, profile_path=path).seen, tutor.seen)


class OnTheMatrix(unittest.TestCase):
    def test_a_column_per_topic_and_a_dot_for_what_to_try(self):
        grid = frame({"event": "skills", "value": [0, 1, 6, 3], "next": 0})
        self.assertEqual((len(grid), {len(row) for row in grid}), (ROWS, {COLS}))
        left = (COLS - 4) // 2
        lit = [sum(1 for r in range(1, ROWS) if grid[r][left + i]) for i in range(4)]
        self.assertEqual(lit, [0, 1, 6, 3])
        self.assertTrue(grid[0][left])
        self.assertEqual(sum(1 for v in grid[0] if v), 1)
        self.assertEqual(rgb({"event": "skills"}), (0, 0, 1))

    def test_every_map_event_draws_even_with_all_eleven_topics_and_odd_values(self):
        for event in ({"event": "skills", "value": [9] * 11, "next": 10}, {"event": "skills", "value": [], "next": None},
                      {"event": "skills", "value": [1] * 20, "next": 19}):
            grid = frame(event)
            self.assertEqual((len(grid), {len(row) for row in grid}), (ROWS, {COLS}))
            self.assertFalse(any(grid[1]))   # a gap between the dot and the columns
        skills, tutor = desk()
        solve(tutor, keys(skills, 0, "medida")[0], "C")
        for sent in (skills.view(), skills.classroom()):
            self.assertTrue(any(v for row in frame(sent["events"][0]) for v in row))


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

    def test_tutor_practice_and_exam_all_reach_the_map(self):
        call = self.app.call
        self.assertFalse(call("skillmap", {})["started"])
        call("answer", {"letter": "A"})
        topic, level = self.app.tutor.current["problem"]["topic"], self.app.tutor.current["problem"]["level"]
        if call("practiceok", {})["available"]:
            call("practice", {})
            for letter in "ABCDE":   # the student reads every option: one practice problem, not five
                call("practiceanswer", {"letter": letter})
        call("examstart", {"level": 1, "paper": "tast"})
        call("examanswer", {"n": 1, "letter": "C"})
        call("examfinish", {})
        call("examstate", {})
        view = call("skillmap", {})
        mine = cell(view, level, topic)
        self.assertEqual((mine["tries"], mine["clean"]), (1, 0))
        self.assertEqual(mine["practice"], int(call("practiceok", {})["available"]))
        other = [c for c in next(r for r in view["levels"] if r["level"] == 1)["cells"]]
        self.assertEqual((sum(c["tries"] for c in other), sum(c["blank"] for c in other)), (1, 2))
        self.assertEqual(len(view["frames"]), 1)
        self.assertNotIn('"label"', json.dumps(view))

    def test_the_board_goes_from_one_student_to_the_next_and_back(self):
        call = self.app.call
        call("answer", {"letter": "A"})
        call("next", {})
        mine = call("state", {})["problem"]["key"]
        first = call("skillmap", {})["student"]
        view = call("studentnew", {})
        self.assertNotEqual(view["student"], first)
        self.assertFalse(view["started"])
        self.assertNotEqual(call("state", {})["problem"]["key"], mine)   # a tutor of their own, from the start
        self.assertEqual(len(self.app.tutor.seen), 1)
        call("answer", {"letter": "C"})
        room = call("classmap", {})
        self.assertEqual([s["name"] for s in room["students"]], [first, view["student"]])
        self.assertEqual([s["current"] for s in room["students"]], [False, True])
        back = call("student", {"n": "0"})
        self.assertEqual(back["student"], first)
        self.assertTrue(back["started"])
        self.assertEqual(call("state", {})["problem"]["key"], mine)      # their problem is still on screen
        with self.assertRaises(ValueError):
            call("student", {"n": "9"})
        self.assertTrue(call("classsample", {})["sample"])
        self.assertEqual(len(call("classmap", {})["students"]), 2)       # the sample class is kept nowhere

    def test_a_session_through_the_server(self):
        call = self.app.call
        self.assertIsNone(call("state", {})["session"])
        plan = call("session", {})["session"]
        self.assertEqual((plan["total"], plan["at"]), (3, -1))
        self.assertEqual(call("session", {})["session"], plan)            # asking again keeps the plan
        topics = []
        for n in range(3):
            view = call("sessionnext", {})
            self.assertEqual(view["session"]["at"], n)
            self.assertEqual(call("state", {})["problem"]["key"], view["problem"]["key"])
            self.assertEqual(call("state", {})["session"]["at"], n)
            self.assertTrue(view["frames"])
            self.assertNotIn('"label"', json.dumps(view))
            self.assertNotIn("SECRET SOLUTION", json.dumps(view))   # the tutor's own view of the problem, no more
            self.assertNotIn("SECRET HINT", json.dumps(view))
            topics.append(view["problem"]["topic"])
            call("answer", {"letter": "C"})
        self.assertEqual(len(set(topics)), 3)
        end = call("sessionnext", {})
        self.assertTrue(end["finished"] and end["session"]["finished"])
        self.assertEqual(call("session", {})["session"]["at"], -1)          # a finished session makes room for a new one
        self.assertIsNone(call("sessionstop", {})["session"])
        with self.assertRaises(ValueError):
            call("sessionnext", {})

    def test_no_change_of_student_in_the_middle_of_a_paper(self):
        call = self.app.call
        call("examstart", {"level": 0, "paper": "tast"})
        with self.assertRaises(ValueError):
            call("studentnew", {})
        call("examfinish", {})
        self.assertEqual(len(call("studentnew", {})["students"]), 2)


if __name__ == "__main__":
    unittest.main()
