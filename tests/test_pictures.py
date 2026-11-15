"""Practice problems for the picture topics: every answer and every slip checked a second way.

No model and no M3Kang data: the problems and their figures come from copilot/pictures.py.

    python3 -m unittest tests.test_pictures -v
"""
import argparse
import json
import os
import random
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "teach"))

import server  # noqa: E402
from copilot import pictures as X  # noqa: E402
from copilot import practice as P  # noqa: E402
from copilot.matrix import frame  # noqa: E402

SEEDS = range(300)


def draws(name, language="cat"):
    for seed in SEEDS:
        yield seed, X.generate(name, random.Random(seed), language)


def slip(problem, code):
    return dict((c, v) for v, c in X.MISTAKES[problem["generator"]](problem["params"])[1])[code]


class EveryProblem(unittest.TestCase):
    def test_five_different_options_in_order_and_the_answer_among_them(self):
        places = {name: set() for name in X.GENERATORS}
        for name in X.GENERATORS:
            for language in ("cat", "eng"):
                for seed, p in draws(name, language):
                    values = [int(p["options"][letter]) for letter in "ABCDE"]
                    self.assertEqual(values, sorted(set(values)), f"{name} seed {seed}")
                    self.assertTrue(all(v > 0 for v in values))
                    self.assertEqual(p["options"][p["label"]], p["answer"])
                    self.assertEqual(str(X.MISTAKES[name](p["params"])[0]), p["answer"])
                    self.assertIn(p["answer"], p["rationale"])
                    places[name].add(p["label"])
        for name, seen in places.items():
            self.assertEqual(seen, set("ABCDE"), f"{name}: the answer is not always in the same place")

    def test_no_slip_gives_the_answer_and_the_slips_named_are_really_those(self):
        for name in X.GENERATORS:
            named = total = 0
            for seed, p in draws(name):
                answer, slips = X.MISTAKES[name](p["params"])
                found = P.mistakes(p)
                self.assertNotIn(p["label"], found)
                for letter, code in found.items():
                    self.assertIn((int(p["options"][letter]), code), slips)
                    self.assertNotEqual(p["options"][letter], p["answer"])
                named += len(found)
                total += 4
            self.assertGreater(named / total, 0.45, name)

    def test_every_slip_has_its_sentence_and_its_way_without_a_number(self):
        for name in X.GENERATORS:
            codes = {code for _, p in draws(name) for _, code in X.MISTAKES[name](p["params"])[1]}
            self.assertEqual(codes, set(X.MESSAGES[name]))
            self.assertLessEqual(set(X.METHODS[name]) - {"right"}, codes)
            for texts in list(X.MESSAGES[name].values()) + list(X.METHODS[name].values()):
                for text in texts:
                    self.assertTrue(text.strip())
                    self.assertIsNone(re.search(r"\d", text), text)

    def test_the_statement_and_the_figure_never_carry_the_answer(self):
        for name in X.GENERATORS:
            for seed, p in draws(name):
                self.assertNotIn(p["answer"], re.findall(r"\d+", p["text"]), f"{name} seed {seed}")
                self.assertNotIn("answer", p["figure"])
                self.assertEqual(set(p["figure"]) - {"kind"}, set(p["params"]))   # only what was drawn, to draw it


class Stairs(unittest.TestCase):
    def test_the_answer_is_the_squares_counted_one_by_one(self):
        for seed, p in draws("stair_squares"):
            heights = p["params"]["heights"]
            cells = set(X.stair_cells(heights))
            self.assertEqual(len(cells), int(p["answer"]), f"seed {seed}")
            self.assertEqual(heights, sorted(heights))             # a staircase: it never goes down
            self.assertTrue(3 <= len(heights) <= 5 and max(heights) <= 6)
            self.assertEqual(p["figure"], {"kind": "stairs", "heights": heights})

    def test_each_slip_is_what_it_says_counted_on_the_cells(self):
        for seed, p in draws("stair_squares"):
            cells = set(X.stair_cells(p["params"]["heights"]))
            width, height = 1 + max(c for c, _ in cells), 1 + max(r for _, r in cells)
            self.assertEqual(slip(p, "whole_rectangle"), width * height)
            edge = sum((c + dc, r + dr) not in cells for c, r in cells for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            self.assertEqual(slip(p, "perimeter"), edge, f"seed {seed}")          # unit sides on the outline
            self.assertEqual(slip(p, "top_squares"), sum((c, r + 1) not in cells for c, r in cells))
            self.assertEqual(slip(p, "row_missing"), sum(r > 0 for _, r in cells))


class Strip(unittest.TestCase):
    def pieces(self, layers, cuts):
        """Fold a strip of `layers` unit segments in a zigzag, cut at each dotted line, unfold, count."""
        points = set()
        for layer in range(layers):
            for f in cuts:   # layer 0 runs left to right, layer 1 comes back, and so on
                points.add(round(layer + (f if layer % 2 == 0 else 1 - f), 6))
        self.assertTrue(all(0 < x < layers for x in points))
        return len(points) + 1

    def test_the_answer_is_the_pieces_of_a_strip_really_folded_and_cut(self):
        seen = set()
        for seed, p in draws("folded_strip"):
            layers, cuts = p["params"]["layers"], p["params"]["cuts"]
            self.assertEqual(self.pieces(layers, cuts), int(p["answer"]), f"seed {seed}")
            self.assertEqual(len(X.strip_cut_points(layers, cuts)), int(p["answer"]) - 1)
            self.assertTrue(all(0.2 < f < 0.8 for f in cuts) and len(set(cuts)) == len(cuts))   # no cut on a fold
            self.assertIn(str(layers), p["text"])
            seen.add((layers, len(cuts)))
        self.assertGreaterEqual(len(seen), 6)

    def test_each_slip_is_what_it_says(self):
        for _, p in draws("folded_strip"):
            layers, cuts = p["params"]["layers"], p["params"]["cuts"]
            self.assertEqual(slip(p, "cuts_counted"), self.pieces(layers, cuts) - 1)
            self.assertEqual(slip(p, "not_folded"), self.pieces(1, cuts))
            self.assertEqual(slip(p, "double"), 2 * len(cuts) * layers)
            self.assertEqual(slip(p, "layers_counted"), layers if len(cuts) > 1 else None)


class Cubes(unittest.TestCase):
    def seen(self, heights):
        """March from every face towards the viewer, along (1, 1, 1): which faces and cubes are in sight?"""
        cubes = set(X.cubes(heights))
        faces = []
        for x, y, z in cubes:
            for side, (cx, cy, cz) in (("top", (x + .5, y + .5, z + 1)), ("x", (x + 1, y + .5, z + .5)),
                                       ("y", (x + .5, y + 1, z + .5))):
                steps = [(cx + t / 8, cy + t / 8, cz + t / 8) for t in range(1, 80)]
                if not any((int(a // 1), int(b // 1), int(c // 1)) in cubes for a, b, c in steps):
                    faces.append((x, y, z, side))
        return faces

    def test_the_answer_is_every_cube_and_the_drawing_settles_it(self):
        for seed, p in draws("cube_stack"):
            heights = p["params"]["heights"]
            cubes = set(X.cubes(heights))
            self.assertEqual(len(cubes), int(p["answer"]), f"seed {seed}")
            self.assertTrue(all((x, y, z - 1) in cubes for x, y, z in cubes if z))            # no holes
            for x, row in enumerate(heights):                                                 # never taller towards the viewer
                for y, h in enumerate(row):
                    self.assertGreaterEqual(heights[x - 1][y] if x else 9, h)
                    self.assertGreaterEqual(row[y - 1] if y else 9, h)
            tops = {(x, y) for x, y, z, side in self.seen(heights) if side == "top"}
            self.assertEqual(tops, {(x, y) for x, y, _ in cubes}, f"seed {seed}")             # the top of every pile is in sight
            self.assertEqual(p["figure"], {"kind": "cubes", "heights": heights})

    def test_each_slip_is_what_it_says_seen_from_the_viewer(self):
        hidden = 0
        for seed, p in draws("cube_stack"):
            heights = p["params"]["heights"]
            faces = self.seen(heights)
            self.assertEqual(sorted(faces), sorted(X.cube_faces(heights)), f"seed {seed}")    # what the page draws is what is seen
            self.assertEqual(slip(p, "faces_counted"), len(faces))
            self.assertEqual(slip(p, "visible_only"), len({f[:3] for f in faces}))
            self.assertEqual(slip(p, "tops_only"), sum(side == "top" for *_, side in faces))
            hidden += int(p["answer"]) - slip(p, "visible_only")
            self.assertGreaterEqual(int(p["answer"]) - slip(p, "visible_only"), 1)             # something is always hidden
        self.assertGreater(hidden, len(SEEDS))


class ThroughPracticeAndTheServer(unittest.TestCase):
    def test_the_card_names_the_slip_asks_how_and_keeps_the_answer(self):
        practice = P.Practice("cat", seed=5, generators=None)
        practice.generators = None   # the picture topics need nothing from the model lab
        figures = set()
        for topic, kinds in X.TOPICS.items():
            for n in range(6):
                view = practice.new(topic)
                self.assertEqual(view["kind"], kinds[n % len(kinds)])
                self.assertNotIn(repr(view["figure"]), figures)   # never the same figure twice
                figures.add(repr(view["figure"]))
                self.assertEqual(set(view), {"n", "topic", "kind", "text", "options", "events", "figure"})
                self.assertNotIn(practice.current["problem"]["answer"], re.findall(r"\d+", view["text"]))
                problem = practice.current["problem"]
                named = 0
                for letter in "ABCDE":
                    if letter == problem["label"]:
                        continue
                    result = practice.answer(letter)
                    self.assertFalse(result["correct"])
                    self.assertIsNone(re.search(r"\d", result["mistake"]["text"]))
                    named += bool(result["mistake"]["code"])
                self.assertGreaterEqual(named, 1)
                result = practice.answer(problem["label"])
                self.assertEqual(len(result["explain"]), 3)
                for event in view["events"] + result["events"]:
                    frame(event)

    def test_the_picture_topics_get_practice_a_warm_up_and_a_place_on_the_map(self):
        rows = []
        for n in range(1, 13):
            topic = ("visual", "geometria_espacial", "aritmetica")[n % 3]
            rows.append({"key": f"lvl-0_2020_{n}_cat", "id": f"lvl-0_2020_{n}", "language": "cat", "stage": "primaria",
                         "level": 0, "grade": 5, "block": n % 3, "question_number": n, "difficulty": 0 if topic == "visual" else 1,
                         "topic": topic, "text": f"SECRET TEXT {n}", "label": "C",
                         "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
                         "solution": {"text": "SECRET SOLUTION", "status": "revisado"}, "hints": [], "distractors": {}})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "catalog.jsonl")
            with open(path, "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in rows)
            app = server.App(argparse.Namespace(
                catalog=path, types="content/types_primaria.json", images=tmp, stage="primaria", language="cat",
                show="revisado,preparado,generado", profile=""))
            call = app.call
            self.assertIn("visual", call("state", {})["warmup"]["topics"])
            call("warmupskip", {})
            self.assertEqual(app.tutor.current["problem"]["topic"], "visual")
            self.assertTrue(call("practiceok", {})["available"])
            view = call("practice", {})
            self.assertEqual(view["figure"]["kind"], "stairs")
            self.assertTrue(view["reading"]["lines"] and view["frames"])
            self.assertNotIn("label", view)
            wrong = next(letter for letter in "ABCDE" if letter != app.practice.current["problem"]["label"])
            call("practiceanswer", {"letter": wrong})
            cells = {c["topic"]: c for c in call("skillmap", {})["levels"][0]["cells"]}
            self.assertEqual((cells["visual"]["practice"], cells["visual"]["state"]), (1, "tried"))


if __name__ == "__main__":
    unittest.main()
