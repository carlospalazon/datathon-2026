"""Tests for laptop/build_training_data.py and laptop/synthetic_problems.py (invented data, no network)."""
import json
import math
import random
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from copilot.llm import SYSTEM, build_messages  # noqa: E402
from laptop import build_training_data as btd  # noqa: E402
from laptop import synthetic_problems as sp  # noqa: E402

LETTERS = "ABCDE"


def invented(i, lang="eng"):
    return {"id": f"lvl-9_2001_{i}", "language": lang, "level": 9, "year": 2001, "text_only": True,
            "text": f"{i}. Invented problem number {i} about {i * 7 + 3} imaginary snails in a garden of zebras.",
            "options": {c: str(10 * i + k) for k, c in enumerate(LETTERS)}, "label": LETTERS[i % 5]}


def write(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def aqua_row(i, rationale="First compute the total.\n3*4=12\nThen subtract 5 to get 7.\nAnswer: B"):
    return {"question": f"A made-up shop sells widgets number {i} for {i + 2} coins; how many coins for {i + 3} widgets?",
            "options": [f"A){i}", f"B){i + 1}", f"C){i + 2}", f"D){i + 3}", f"E){i + 4}"],
            "rationale": rationale, "correct": "B"}


class Workdir:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_build(self, train, val, aqua, out="out", extra=()):
        write(self.dir / "train.jsonl", train)
        write(self.dir / "val.jsonl", val)
        write(self.dir / "aqua.json", aqua)
        args = btd.parse_args(["--train", str(self.dir / "train.jsonl"), "--val", str(self.dir / "val.jsonl"),
                               "--aqua-file", str(self.dir / "aqua.json"), "--out", str(self.dir / out),
                               "--aqua", "50", "--synthetic", "100", *extra])
        btd.build(args)
        return self.dir / out


class ShuffleTests(unittest.TestCase):
    def test_label_follows_the_correct_value(self):
        values = ["alpha", "beta", "gamma", "delta", "epsilon"]
        deck = btd.Deck(random.Random(1))
        for label in LETTERS:
            for perm, new in btd.make_variants(values, label, "u1", 4, 42, deck, True):
                self.assertEqual(sorted(perm), sorted(values))
                self.assertEqual(perm[LETTERS.index(new)], values[LETTERS.index(label)])

    def test_copies_differ_and_letters_balance(self):
        values = list("vwxyz")
        deck = btd.Deck(random.Random(2))
        counts = {c: 0 for c in LETTERS}
        for i in range(200):
            copies = btd.make_variants(values, "A", f"u{i}", 3, 42, deck, True)
            self.assertEqual(len({tuple(p) for p, _ in copies}), len(copies))
            for _, new in copies:
                counts[new] += 1
        self.assertLess(max(counts.values()) - min(counts.values()), 12)

    def test_no_shuffle_exception(self):
        for text, vals in [("Which is true?", ["A and B", "B", "C", "D", "E and A"]),
                           ("Pick one.", ["1", "2", "3", "4", "None of the above"]),
                           ("Both numbers are even.", list("12345")),
                           ("Quin és cert?", ["1", "2", "3", "4", "cap de les anteriors"]),
                           ("¿Cuál?", ["1", "2", "3", "4", "ninguna de las anteriores"]),
                           ("Say the first option.", list("12345"))]:
            self.assertIsNotNone(btd.no_shuffle_reason(text, vals), (text, vals))
        self.assertIsNone(btd.no_shuffle_reason("How many apples are there?", list("12345")))
        deck = btd.Deck(random.Random(3))
        out = btd.make_variants(list("12345"), "C", "u", 3, 42, deck, False)
        self.assertEqual(out, [(list("12345"), "C")])

    def test_exception_counted_in_build(self):
        drops = {}
        from collections import Counter
        drops = Counter()
        base = dict(uid="x:1", source="aqua_rat", language="eng", text="Pick.", values=["1", "2", "3", "4", "none of the above"],
                    label="B", rationale=None, no_options=False, meta={})
        recs = btd.expand([base], 3, 42, btd.Deck(random.Random(1)), drops)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["options"]["E"], "none of the above")
        self.assertEqual(sum(drops.values()), 1)


class RationaleTests(unittest.TestCase):
    def test_answer_statements_stripped(self):
        cases = {"3x=12\nx=4\nThe answer is B.": "3x=12 x=4",
                 "x=4, hence (C)": "x=4",
                 "x = 4 so 2x = 8\nAnswer: D": "x = 4 so 2x = 8",
                 "Compute 5*5=25. ANSWER:C": "Compute 5*5=25",
                 "Total is 25\nOption E": "Total is 25",
                 "Total is 25\nB": "Total is 25"}
        for raw, want in cases.items():
            self.assertEqual(btd.clean_rationale(raw), want, raw)

    def test_letter_references_drop_the_rationale(self):
        ok, why = btd.validate_rationale("We get 12 apples in total, so the total is twelve.")
        self.assertIsNone(why)
        for bad in ["Only option C works because 4*3=12 and the rest fail.",
                    "Check (B): 4*3=12 so this is the value we need here.",
                    "A is wrong since 4*3 is not 11, and the total is twelve."]:
            text, why = btd.validate_rationale(bad)
            self.assertIsNone(text)
            self.assertEqual(why, "letter_reference")

    def test_too_long_dropped(self):
        self.assertEqual(btd.validate_rationale("x " * 300)[1], "too_long")

    def test_aqua_row_without_letter_refs_keeps_rationale(self):
        d = Workdir()
        self.addCleanup(d.tearDown)
        out = d.run_build([invented(1)], [invented(2)], [aqua_row(1), aqua_row(2, "Because option C is the only one that fits, the value is seven here.")])
        recs = [json.loads(l) for l in open(out / "master.jsonl", encoding="utf-8")]
        aq = [r for r in recs if r["source"] == "aqua_rat"]
        self.assertEqual(len(aq), 2)
        self.assertEqual(sum(1 for r in aq if r["rationale"]), 1)
        for r in aq:
            if r["rationale"]:
                self.assertNotIn("Answer", r["rationale"])


class LeakTests(unittest.TestCase):
    def test_planted_validation_id_aborts(self):
        rec = {"uid": "m3k:lvl-9_2001_2:eng#0", "source": "m3kang", "text": "something else entirely",
               "meta": {"m3k_id": "lvl-9_2001_2"}}
        with self.assertRaises(AssertionError):
            btd.assert_no_leaks([rec], {"lvl-9_2001_2"}, set())

    def test_planted_validation_text_aborts(self):
        val_norms = set(btd.norm_variants("7. How many invented snails sit in the garden?"))
        rec = {"uid": "aqua:1#0", "source": "aqua_rat", "text": "how many INVENTED snails sit in the garden?!", "meta": {}}
        with self.assertRaises(AssertionError):
            btd.assert_no_leaks([rec], set(), val_norms)
        btd.assert_no_leaks([dict(rec, text="a different question")], set(), val_norms)

    def test_external_copy_of_validation_problem_is_dropped(self):
        d = Workdir()
        self.addCleanup(d.tearDown)
        val = invented(2)
        copy = aqua_row(5)
        copy["question"] = val["text"].split(". ", 1)[1]
        out = d.run_build([invented(1)], [val], [aqua_row(1), copy])
        text = (out / "STATS.md").read_text(encoding="utf-8")
        self.assertIn("aqua:text_equals_validation | 1", text)
        for line in open(out / "master.jsonl", encoding="utf-8"):
            self.assertNotEqual(json.loads(line)["meta"].get("m3k_id"), val["id"])


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.w = Workdir()
        self.addCleanup(self.w.tearDown)
        self.train = [invented(i, l) for i in range(1, 9) for l in ("eng", "cat")]
        self.train.append({**invented(30), "options": {}})
        self.train.append({**invented(31), "options": {"A": "1", "B": "2"}})
        self.val = [invented(100), invented(101, "cat")]
        self.aqua = [aqua_row(i) for i in range(1, 30)]

    def test_deterministic(self):
        a = self.w.run_build(self.train, self.val, self.aqua, "a")
        b = self.w.run_build(self.train, self.val, self.aqua, "b")
        for name in ("master", "letter", "reasoning", "dev_letter", "dev_reasoning"):
            self.assertEqual((a / f"{name}.jsonl").read_bytes(), (b / f"{name}.jsonl").read_bytes(), name)
        c = self.w.run_build(self.train, self.val, self.aqua, "c", ("--seed", "7"))
        self.assertNotEqual((a / "letter.jsonl").read_bytes(), (c / "letter.jsonl").read_bytes())

    def test_chat_shape_matches_inference(self):
        out = self.w.run_build(self.train, self.val, self.aqua)
        masters = {json.loads(l)["uid"]: json.loads(l) for l in open(out / "master.jsonl", encoding="utf-8")}
        rows = [json.loads(l) for l in open(out / "letter.jsonl", encoding="utf-8")]
        self.assertTrue(rows)
        for row in rows:
            m = row["messages"]
            self.assertEqual([x["role"] for x in m], ["system", "user", "assistant"])
            self.assertEqual(m[0]["content"], SYSTEM)
            self.assertIn(m[2]["content"], list(LETTERS))
        rec = next(r for r in masters.values() if r["source"] == "m3kang")
        want = build_messages({"text": rec["text"], "options": rec["options"]})
        row = next(r for r in rows if r["messages"][1] == want[1])
        self.assertEqual(row["messages"][:2], want)

    def test_reasoning_export_ends_with_answer_line(self):
        out = self.w.run_build(self.train, self.val, self.aqua)
        rows = [json.loads(l) for l in open(out / "reasoning.jsonl", encoding="utf-8")]
        self.assertTrue(rows)
        for row in rows:
            content = row["messages"][2]["content"]
            self.assertRegex(content, r"\nAnswer: [A-E]$")
            body, option_line = content.rsplit("\nAnswer:", 1)[0].rsplit("\n", 1)
            self.assertLessEqual(len(body), 350)
            self.assertFalse(btd.refers_to_option(body))
            self.assertRegex(option_line, rf"(option|opció|opción) {content[-1]}\.$")  # the one line with a letter

    def test_filters_and_no_val_in_output(self):
        out = self.w.run_build(self.train, self.val, self.aqua)
        recs = [json.loads(l) for l in open(out / "master.jsonl", encoding="utf-8")]
        ids = {r["meta"].get("m3k_id") for r in recs}
        self.assertFalse(ids & {"lvl-9_2001_100", "lvl-9_2001_101"})
        self.assertNotIn("lvl-9_2001_30", ids)   # no options
        self.assertNotIn("lvl-9_2001_31", ids)   # two options only
        self.assertEqual(sum(1 for r in recs if r["source"] == "m3kang"), 16 * 3)
        with_opts = self.w.run_build(self.train, self.val, self.aqua, "n", ("--include-no-options",))
        recs = [json.loads(l) for l in open(with_opts / "master.jsonl", encoding="utf-8")]
        self.assertTrue(any(r["options"] == {} and r["rationale"] is None for r in recs))

    def test_dev_is_only_external(self):
        out = self.w.run_build(self.train, self.val, self.aqua)
        for name in ("dev_letter", "dev_reasoning"):
            self.assertTrue((out / f"{name}.jsonl").exists())
        master_uids = {json.loads(l)["uid"] for l in open(out / "master.jsonl", encoding="utf-8")}
        self.assertTrue(all(not btd.is_dev({"uid": u, "source": "m3kang"}) for u in master_uids))

    def test_rationales_mismatching_answer_is_dropped(self):
        t = [invented(1), invented(2)]
        # invented(1) label is B, invented(2) label is C
        rat = [{"id": "lvl-9_2001_1", "language": "eng", "rationale": "Add the parts and read off the sum carefully.", "answer": "B"},
               {"id": "lvl-9_2001_2", "language": "eng", "rationale": "Add the parts and read off the sum carefully.", "answer": "A"}]
        write(self.w.dir / "rat.jsonl", rat)
        out = self.w.run_build(t, self.val, self.aqua, "r", ("--rationales", str(self.w.dir / "rat.jsonl")))
        recs = [json.loads(l) for l in open(out / "master.jsonl", encoding="utf-8")]
        got = {r["meta"]["m3k_id"]: r["rationale"] for r in recs if r["source"] == "m3kang"}
        self.assertIsNotNone(got["lvl-9_2001_1"])
        self.assertIsNone(got["lvl-9_2001_2"])
        self.assertIn("m3kang:rationale_answer_mismatch | 1", (out / "STATS.md").read_text(encoding="utf-8"))


class SyntheticTests(unittest.TestCase):
    def test_enough_generators(self):
        self.assertGreaterEqual(len(sp.GENERATOR_NAMES), 15)
        self.assertEqual(len(set(sp.GENERATOR_NAMES)), len(sp.GENERATOR_NAMES))

    def test_every_generator(self):
        for name in sp.GENERATOR_NAMES:
            for lang in sp.LANGS:
                texts = set()
                for seed in range(150):
                    ex = sp.generate(name, random.Random(seed), lang)
                    ctx = f"{name} {lang} seed {seed}"
                    opts = ex["options"]
                    self.assertEqual(list(opts), list(LETTERS), ctx)
                    self.assertEqual(len(set(opts.values())), 5, ctx)
                    self.assertTrue(all(v.strip() for v in opts.values()), ctx)
                    self.assertEqual(opts[ex["label"]], ex["answer"], ctx)
                    r = ex["rationale"]
                    self.assertLessEqual(len(r), 350, ctx)
                    self.assertFalse(btd.refers_to_option(r), ctx)
                    self.assertIsNone(re.search(r"(?-i:\b[A-E]\b)", r), ctx)
                    sentences = [s for s in re.split(r"(?<=\.)\s", r) if s]
                    self.assertTrue(2 <= len(sentences) <= 4, (ctx, len(sentences)))
                    self.assertIn(ex["answer"], sentences[-1], ctx)
                    self.assertTrue(r.endswith("."), ctx)
                    self.assertNotIn("{", ex["text"] + r, ctx)
                    self.assertIsNone(btd.no_shuffle_reason(ex["text"], list(opts.values())), ctx)
                    texts.add(ex["text"])
                self.assertGreater(len(texts), 3, f"{name} {lang} has hardly any variety")

    def test_deterministic(self):
        for name in sp.GENERATOR_NAMES:
            a = sp.generate(name, random.Random(5), "cat")
            b = sp.generate(name, random.Random(5), "cat")
            self.assertEqual(a, b)

    def test_independent_rederivation(self):
        def gen(name, seed, lang="eng"):
            return sp.generate(name, random.Random(seed), lang)

        for seed in range(60):
            for lang in sp.LANGS:
                e = gen("shopping", seed, lang)["params"]
                p = gen("shopping", seed, lang)
                self.assertEqual(int(p["answer"]), e["pay"] - e["a"] * e["p"] - e["b"] * e["q"])

                p = gen("handshakes", seed, lang)
                n = p["params"]["n"]
                self.assertEqual(int(p["answer"]), sum(1 for i in range(n) for j in range(i + 1, n)))

                p = gen("grid_routes", seed, lang)
                a, b = p["params"]["a"], p["params"]["b"]
                routes = {(0, 0): 1}
                for x in range(a + 1):
                    for y in range(b + 1):
                        if (x, y) != (0, 0):
                            routes[(x, y)] = routes.get((x - 1, y), 0) + routes.get((x, y - 1), 0)
                self.assertEqual(int(p["answer"]), routes[(a, b)])

                p = gen("digit_sum_count", seed, lang)
                S = p["params"]["S"]
                self.assertEqual(int(p["answer"]), sum(1 for x in range(10, 100) if x // 10 + x % 10 == S))

                p = gen("multiples_in_range", seed, lang)
                k, lo, hi = (p["params"][x] for x in ("k", "lo", "hi"))
                self.assertEqual(int(p["answer"]), sum(1 for x in range(lo, hi + 1) if x % k == 0))

                p = gen("remainder", seed, lang)
                self.assertEqual(int(p["answer"]), p["params"]["N"] % p["params"]["k"])

                p = gen("arithmetic_sequence", seed, lang)
                a_, d_, n_ = (p["params"][x] for x in ("a", "d", "n"))
                term = a_
                for _ in range(n_ - 1):
                    term += d_
                self.assertEqual(int(p["answer"]), term)

                p = gen("film_end_time", seed, lang)
                end = p["params"]["start"] + p["params"]["dur"]
                self.assertEqual(p["answer"], f"{end // 60}:{end % 60:02d}")

                p = gen("line_up_together", seed, lang)
                n = p["params"]["n"]
                self.assertEqual(int(p["answer"]), 2 * math.factorial(n - 1))

                p = gen("average_missing", seed, lang)
                s = p["params"]["s"]
                self.assertEqual(int(p["answer"]) + sum(s), 5 * p["params"]["m"])

                p = gen("coin_count", seed, lang)
                n, S = p["params"]["n"], p["params"]["S"]
                twos = int(p["answer"])
                self.assertEqual((n - twos) + 2 * twos, S)

                p = gen("race_logic", seed, lang)
                self.assertEqual(p["answer"], p["params"]["names"][p["params"]["pos"] - 1])

    def test_hard_generators_rederived(self):
        """Every grade 9-12 generator: the answer is recomputed here from the givens in
        params, by brute force where that is possible, and the givens appear in the text."""
        from fractions import Fraction
        from itertools import combinations, count, permutations

        def digits(x):
            return [int(ch) for ch in str(x)]

        def only(values):
            values = list(values)
            self.assertEqual(len(values), 1, values)
            return values[0]

        def root(x, power=2):
            r = round(x ** (1 / power))
            self.assertEqual(r ** power, x)
            return r

        cache = {}

        def cached(key, fn):
            if key not in cache:
                cache[key] = fn()
            return cache[key]

        def divisor_count(p):
            return sum(1 for d in range(1, p["N"] + 1) if p["N"] % d == 0), [p["N"]]

        def last_digit_power(p):
            return pow(p["a"], p["n"], 10), [f"{p['a']}^{p['n']}"]

        def gcd_lcm(p):
            a, b = p["a"], p["b"]
            if p["kind"] == "squares":
                side = max(s for s in range(1, min(a, b) + 1) if a % s == 0 and b % s == 0)
                return (a // side) * (b // side), [a, b]
            return next(t for t in count(1) if t % a == 0 and t % b == 0), [a, b]

        def consecutive_sum(p):
            k, S = p["k"], p["S"]
            first = only(f for f in range(-500, 500) if sum(range(f, f + k)) == S)
            return (first + k - 1 if p["largest"] else first), [k, S]

        def digit_extreme(p):
            nd = p["nd"]
            xs = [x for x in range(10 ** (nd - 1), 10 ** nd)
                  if len(set(str(x))) == nd and sum(digits(x)) == p["S"] and x % 2 == p["parity"]]
            return (max(xs) if p["largest"] else min(xs)), [p["S"]]

        def remainder_ops(p):
            m = p["m"]
            a, b = p["r1"] + 3 * m, p["r2"] + 5 * m
            value = {"sum": a + b, "product": a * b, "combo": p["u"] * a + p["v"] * b}[p["kind"]]
            return value % m, [m, p["r1"], p["r2"]]

        def count_div_digit(p):
            nd = p["nd"]
            return sum(1 for x in range(10 ** (nd - 1), 10 ** nd)
                       if x % p["k"] == 0 and str(x)[-1] == str(p["d"])), [p["k"], p["d"]]

        def two_equations(p):
            (a, b, P), (c, d, Q) = p["eq1"], p["eq2"]
            x, y = only((x, y) for x in range(0, 60) for y in range(0, 60)
                        if a * x + b * y == P and c * x + d * y == Q)
            return (x + y if p["kind"] == "each" else x), [P, Q]

        def sum_product_squares(p):
            if p["kind"] == "recip":
                x = (p["k"] + (p["k"] ** 2 - 4) ** 0.5) / 2
                return round(x * x + 1 / (x * x)), [p["k"]]
            if p["kind"] == "sum":
                x, y = only((x, y) for x in range(-40, 41) for y in range(-40, x + 1)
                            if x + y == p["s"] and x * y == p["p"])
                return x * x + y * y, [p["s"], p["p"]]
            x, y = only((x, y) for x in range(1, 41) for y in range(1, 41)
                        if x - y == p["d"] and x * y == p["p"])
            return x * x + y * y, [p["d"], p["p"]]

        def power_simplify(p):
            value = Fraction(p["copies"])
            for base, e in p["mul"]:
                value *= base ** e
            for base, e in p["div"]:
                value /= base ** e
            exponent = only(n for n in range(200) if p["B"] ** n == value)
            return exponent, [f"{base}^{e}" for base, e in p["mul"] + p["div"]]

        def successive_percent(p):
            price = Fraction(100)
            for pct, up in ((p["p"], p["up1"]), (p["q"], p["up2"])):
                price += price * pct / 100 * (1 if up else -1)
            return price, [f"{p['p']}%", f"{p['q']}%"]

        def average_speed(p):
            d = p["d"] or 7
            return Fraction(2 * d) / (Fraction(d, p["v1"]) + Fraction(d, p["v2"])), [p["v1"], p["v2"]] + ([p["d"]] if p["d"] else [])

        def mean_change(p):
            n, m, m2 = p["n"], p["m"], p["m2"]
            if p["remove"]:
                x = only(x for x in range(1, 1000) if Fraction(n * m - x, n - 1) == m2)
            else:
                x = only(x for x in range(1, 1000) if Fraction(n * m + x, n + 1) == m2)
            return x, [n, m, m2]

        def inequality_count(p):
            def holds(left, sign, right):
                return left < right or (sign == "≤" and left == right)
            return sum(1 for n in range(-1000, 1001)
                       if holds(p["lo"], p["s1"], p["k"] * n + p["c"]) and holds(p["k"] * n + p["c"], p["s2"], p["hi"])), \
                [p["lo"], p["hi"], f"{p['k']}n"]

        def geometric_sequence(p):
            if p["kind"] == "term":
                ratio = Fraction(p["t3"], p["t2"])
                term = p["t2"] / ratio
                for _ in range(p["n"] - 1):
                    term *= ratio
                return term, [p["t2"], p["t3"], p["n"]]
            term, total = p["a"], 0
            for _ in range(p["n"]):
                total += term
                term *= p["r"]
            return total, [p["a"], p["r"], p["n"]]

        def arith_two_terms(p):
            step = Fraction(p["tj"] - p["ti"], p["j"] - p["i"])
            term = p["ti"]
            for _ in range(p["n"] - p["i"]):
                term += step
            return term, [p["i"], p["j"], p["n"], p["ti"], p["tj"]]

        def arrangements_restricted(p):
            n, kind = p["n"], p["kind"]
            test = {"apart": lambda s: abs(s[0] - s[1]) != 1, "end": lambda s: s[0] in (0, n - 1),
                    "left": lambda s: s[0] < s[1]}[kind]  # s[i] is the seat of friend i
            return cached(("arr", n, kind), lambda: sum(1 for s in permutations(range(n)) if test(s))), [n]

        def committee(p):
            b, g, k = p["b"], p["g"], p["k"]
            def girls(team):
                return sum(1 for person in team if person >= b)
            if p["kind"] == "exact":
                return cached(("com", b, g, k, p["j"]), lambda: sum(
                    1 for team in combinations(range(b + g), k) if girls(team) == p["j"])), [b, g, k, p["j"]]
            return cached(("com1", b, g, k), lambda: sum(
                1 for team in combinations(range(b + g), k) if girls(team) >= 1)), [b, g, k]

        def dice_probability(p):
            v = p["v"]
            test = {"sum_eq": lambda a, b: a + b == v, "sum_gt": lambda a, b: a + b > v,
                    "sum_lt": lambda a, b: a + b < v, "prod_eq": lambda a, b: a * b == v,
                    "prod_gt": lambda a, b: a * b > v, "diff_eq": lambda a, b: max(a, b) - min(a, b) == v,
                    "max_eq": lambda a, b: max(a, b) == v, "sum_mult": lambda a, b: (a + b) % v == 0,
                    "prod_mult": lambda a, b: (a * b) % v == 0}[p["kind"]]
            fav = sum(1 for a in range(1, 7) for b in range(1, 7) if test(a, b))
            return Fraction(fav, 36), ([] if (p["kind"], v) == ("diff_eq", 0) else [v])

        def balls_probability(p):
            bag = ["x"] * p["first"] + ["y"] * p["second"]
            draws = [(bag[i], bag[j]) for i in range(len(bag)) for j in range(len(bag)) if i != j]
            test = {"same": lambda u, w: u == w, "diff": lambda u, w: u != w,
                    "two": lambda u, w: u == w == "x", "atleast": lambda u, w: "x" in (u, w)}[p["kind"]]
            return Fraction(sum(1 for u, w in draws if test(u, w)), len(draws)), [p["first"], p["second"]]

        def routes_via(p):
            a, b, c, d = p["a"], p["b"], p["c"], p["d"]
            def walk():
                n = 0
                for east in combinations(range(a + b), a):
                    x = y = 0
                    hit = False
                    for step in range(a + b):
                        if step in east:
                            x += 1
                        else:
                            y += 1
                        hit = hit or (x, y) == (c, d)
                    n += hit
                return n
            return cached(("via", a, b, c, d), walk), [a, b, c, d]

        def numbers_from_digits(p):
            allowed, ln = set(p["digits"]), p["length"]
            test = {"any": lambda x: True, "even": lambda x: x % 2 == 0, "odd": lambda x: x % 2 == 1,
                    "mult5": lambda x: x % 5 == 0}[p["cond"]]
            return sum(1 for x in range(10 ** (ln - 1), 10 ** ln)
                       if set(digits(x)) <= allowed and len(set(digits(x))) == ln and test(x)), p["digits"]

        def isosceles_angle(p):
            x, kind = p["x"], p["kind"]
            triangles = [(u, 180 - 2 * u) for u in range(1, 90)]  # (repeated angle, other angle)
            if kind == "apex":
                return only(u for u, w in triangles if w == x), [x]
            if kind == "base":
                return only(w for u, w in triangles if u == x), [x]
            if kind == "obtuse":
                return only({min(u, w) for u, w in triangles if x in (u, w)}), [x]
            return only(u for u, w in triangles if w == 180 - x), [x]

        def regular_polygon(p):
            x, kind = p["x"], p["kind"]
            if kind == "interior":
                return Fraction(180 * (x - 2), x), [x]
            if kind == "sides_int":
                return only(n for n in range(3, 400) if 180 * (n - 2) == x * n), [x]
            if kind == "sides_ext":
                return only(n for n in range(3, 400) if n * x == 360), [x]
            if kind == "diagonals":
                return sum(1 for i in range(x) for j in range(i + 1, x) if (j - i) % x not in (1, x - 1)), [x]
            return only(n for n in range(3, 400) if 180 * (n - 2) == x), [x]

        def pythagoras(p):
            u, w = p["given"]
            return {"walk": lambda: root(u * u + w * w), "ladder": lambda: root(u * u - w * w),
                    "rhombus": lambda: 4 * root((u // 2) ** 2 + (w // 2) ** 2),
                    "rect": lambda: w * root(u * u - w * w)}[p["kind"]](), [u, w]

        def scale_ratio(p):
            q, f = p["q"], p["factor"]
            return {"area": lambda: (f * 1) * (f * q), "volume": lambda: (f * 1) * (f * 1) * (f * q),
                    "perimeter": lambda: q * root(f)}[p["kind"]](), [q, f]

        def painted_cuboid(p):
            a, b, c = p["a"], p["b"], p["c"]
            def painted(x, y, z):
                return sum(v in (0, top - 1) for v, top in ((x, a), (y, b), (z, c)))
            return sum(1 for x in range(a) for y in range(b) for z in range(c)
                       if painted(x, y, z) == p["faces"]), [a, b, c]

        def cube_measures(p):
            x, kind = p["x"], p["kind"]
            s = only(s for s in range(1, 200) if {"s2v": 6 * s * s, "v2s": s ** 3, "e2v": 12 * s, "e2s": 12 * s}[kind] == x)
            return (s ** 3 if kind in ("s2v", "e2v") else 6 * s * s), [x]

        def rect_square(p):
            if p["kind"] == "ratio":
                w = only(w for w in range(1, 500) if 2 * (w + p["k"] * w) == p["P"])
                return w * p["k"] * w, [p["k"], p["P"]]
            if p["kind"] == "same":
                side = Fraction(2 * (p["w"] + p["h"]), 4)
                return side * side, [p["w"], p["h"]]
            t = only(t for t in range(1, 500) if 2 * (t + p["n"] * t) == p["P"])
            return 4 * p["n"] * t, [p["n"], p["P"]]

        def clock_angle(p):
            minute = Fraction(p["m"], 60)
            hour = Fraction(p["h"] % 12, 12) + Fraction(p["m"], 720)
            turn = abs(minute - hour)
            return min(turn, 1 - turn) * 360, [f"{p['h']}:{p['m']:02d}"]

        def truth_one(p):
            def true(statement, speaker, culprit):
                kind, x, y = statement
                if kind == "is":
                    return culprit == x
                if kind == "not":
                    return culprit != x
                if kind == "me":
                    return culprit == speaker
                if kind == "notme":
                    return culprit != speaker
                return culprit == x or culprit == y
            culprit = only(c for c in range(5) if sum(true(st, who, c) for who, st in enumerate(p["statements"])) == p["true_count"])
            return p["names"][culprit], p["names"]

        def order_clues(p):
            def fits(order, clue):
                kind, x, y = clue
                if kind == "notlast":
                    return order[-1] != x
                if kind == "notfirst":
                    return order[0] != x
                gap = order.index(y) - order.index(x)
                return {"before": gap > 0, "just": gap == 1, "between": abs(gap) == 2}[kind]
            order = only(o for o in permutations(p["names"]) if all(fits(o, cl) for cl in p["clues"]))
            return order[p["pos"] - 1], p["names"]

        checks = [divisor_count, last_digit_power, gcd_lcm, consecutive_sum, digit_extreme, remainder_ops,
                  count_div_digit, two_equations, sum_product_squares, power_simplify, successive_percent,
                  average_speed, mean_change, inequality_count, geometric_sequence, arith_two_terms,
                  arrangements_restricted, committee, dice_probability, balls_probability, routes_via,
                  numbers_from_digits, isosceles_angle, regular_polygon, pythagoras, scale_ratio,
                  painted_cuboid, cube_measures, rect_square, clock_angle, truth_one, order_clues]
        self.assertEqual({fn.__name__ for fn in checks}, set(sp.HARD_NAMES))
        self.assertGreaterEqual(len(sp.HARD_NAMES), 25)
        kinds = {}
        for fn in checks:
            name = fn.__name__
            for seed in range(150 if name == "dice_probability" else 30):
                for lang in sp.LANGS:
                    ex = sp.generate(name, random.Random(1000 + seed), lang)
                    ctx = (name, lang, seed, ex["params"])
                    expected, givens = fn(ex["params"])
                    self.assertEqual(ex["answer"], str(expected), ctx)
                    for given in givens:
                        self.assertIn(str(given), ex["text"], ctx)
                    kinds.setdefault(name, set()).add(ex["params"].get("kind"))
        for name, want in {"gcd_lcm": 2, "remainder_ops": 3, "two_equations": 2, "sum_product_squares": 3,
                           "geometric_sequence": 2, "arrangements_restricted": 3, "committee": 2,
                           "dice_probability": 9, "balls_probability": 4, "isosceles_angle": 4,
                           "regular_polygon": 5, "pythagoras": 4, "scale_ratio": 3, "cube_measures": 4,
                           "rect_square": 3}.items():
            self.assertEqual(len(kinds[name]), want, (name, kinds[name]))


if __name__ == "__main__":
    unittest.main()


class OptionLine(unittest.TestCase):
    """The reasoning target names the option that holds the value, after the shuffle."""

    def test_line_names_the_shuffled_letter_in_the_row_language(self):
        for lang, word in (("eng", "is option"), ("cat", "és l'opció"), ("esp", "es la opción")):
            rec = {"text": "Made-up question about nine zebras?", "language": lang, "label": "D",
                   "options": {"A": "1", "B": "2", "C": "3", "D": "44 cm", "E": "5"}, "rationale": "Four elevens make 44 cm."}
            turn = btd.to_chat(rec, reasoning=True)["messages"][-1]["content"].split("\n")
            self.assertEqual(turn, ["Four elevens make 44 cm.", f"44 cm {word} D.", "Answer: D"])
            self.assertEqual(btd.to_chat(rec, reasoning=False)["messages"][-1]["content"], "D")

    def test_every_held_out_file_is_guarded(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.jsonl", Path(d) / "b.jsonl"
            write(a, [invented(1)]); write(b, [invented(2)])
            ids, norms = btd.load_val([str(a), str(b)])
            self.assertEqual(ids, {"lvl-9_2001_1", "lvl-9_2001_2"})
            self.assertTrue(norms)
