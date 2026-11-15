"""The transfer test set: right answers, and wording that really differs from the trained templates."""
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "laptop"))

import reworded_problems as rp  # noqa: E402
from synthetic_problems import generate  # noqa: E402


def words(text):
    return set(re.findall(r"[#\w]+", re.sub(r"\d+(?:[.,]\d+)?", "#", text.lower())))


def answer(name, q):
    """The answer worked out again from the parameters, independently of the generator."""
    if name == "shopping":
        return q["pay"] - q["a"] * q["p"] - q["b"] * q["q"]
    if name == "sharing":
        return (q["n"] - q["m"]) // q["k"]
    if name == "fraction_two_step":
        rest = q["N"] - q["N"] * q["a"] // q["b"]
        return rest - rest * q["c"] // q["d"]
    if name == "percent_discount":
        return q["P"] * (100 - q["p"]) // 100
    if name == "rect_area":
        return q["w"] * q["h"]
    if name == "ribbon_pieces":
        return q["total"] // q["z"]
    if name == "number_think":
        return q["x"]
    if name == "speed_minutes":
        return q["v"] * q["mins"] // 60
    if name == "coin_count":
        return q["S"] - q["n"]
    raise KeyError(name)


def test_every_family_gives_the_right_answer_among_five_options():
    rng = random.Random(1)
    for name in rp.REWORDED:
        for lang in rp.LANGS:
            for _ in range(40):
                p = rp.reworded(name, rng, lang)
                assert len(set(p["options"].values())) == 5
                assert p["options"][p["label"]] == str(answer(name, p["params"])), (name, lang)
                assert "{" not in p["text"]


def test_the_numbers_of_the_problem_are_in_its_text():
    rng = random.Random(2)
    for name in ("sharing", "percent_discount", "speed_minutes", "coin_count"):
        p = rp.reworded(name, rng, "eng")
        shown = set(re.findall(r"\d+", p["text"]))
        for key, v in p["params"].items():
            assert str(v) in shown, (name, key)


def test_wording_is_far_from_the_trained_templates():
    rng = random.Random(3)
    for name in rp.REWORDED:
        for lang in rp.LANGS:
            new = words(rp.reworded(name, rng, lang)["text"])
            for _ in range(20):
                old = words(generate(name, rng, lang)["text"])
                assert len(new & old) / len(new | old) < 0.4, (name, lang)


def test_build_is_repeatable_and_balanced():
    a, b = rp.build(3, seed=5), rp.build(3, seed=5)
    assert a == b
    assert len(a) == len(rp.REWORDED) * 2 * 2 * 3
    assert len({r["id"] for r in a}) == len(a)
    assert sum(r["wording"] == "rew" for r in a) == len(a) // 2
