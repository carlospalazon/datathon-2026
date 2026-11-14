#!/usr/bin/env python3
"""Hints for a problem the catalogue has never seen: measure the alternatives on held-out problems.

    python3 measure_newproblem.py retrieval           # strategy found by nearest problems (no model)
    python3 measure_newproblem.py payloads            # requests for the board: the model with near examples
    python3 measure_newproblem.py choose              # strategy chosen by the board's model
    python3 measure_newproblem.py pack                # every alternative's hint, blind, for a judge
    python3 measure_newproblem.py judged              # the judge's verdicts, per alternative

The held-out problems are the catalogue's level 0 and 1 problems (the tutor's students). Each one
is treated as new: it only gives its Catalan statement, never its topic label, figure description
or options, and every problem of the same year is taken out of the index, because Kangaroo repeats
problems between levels of one year.

"Gold" is the strategy a first annotator read from the verified solution. A second annotator did the
same on the held-out problems: their agreement is the ceiling for any score here.

Reports hold ids, counts, percentages and seconds only: never problem or hint text.
Standard library only.
"""
import argparse
import json
import math
import os
import random
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from copilot import guardrails  # noqa: E402
from copilot.assistant import restates_question  # noqa: E402
from copilot.tutor import leaks_answer  # noqa: E402

DATA = os.path.join(ROOT, "data/newproblem")
CONTENT = os.path.join(ROOT, "data/catalog/content")
HELD_OUT_LEVELS = (0, 1)


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(k, n):
    low, high = wilson(k, n)
    return f"{100 * k / n:.1f}% ({k}/{n}, {100 * low:.0f}-{100 * high:.0f}%)" if n else "n/a"


def year(pid):
    return pid.split("_")[1]


def level(pid):
    return int(pid.split("_")[0].split("-")[1])


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


# --- Loading -------------------------------------------------------------------------------

def load_gold():
    """id -> the first annotation (strategy, hints...)."""
    return {r["id"]: r for r in load(os.path.join(CONTENT, "anatomy.jsonl"))}


def load_second():
    path = os.path.join(CONTENT, "anatomy_second.jsonl")
    return {r["id"]: r for r in load(path)} if os.path.exists(path) else {}


def load_vectors():
    """(id, language) -> vector."""
    vectors = {}
    for r in load(os.path.join(DATA, "vectors.jsonl")):
        pid, language = r["key"].rsplit("_", 1)
        vectors[pid, language] = r["vector"]
    return vectors


def load_problems():
    """(id, language) -> catalogue record."""
    return {(r["id"], r["language"]): r for r in load(os.path.join(ROOT, "data/catalog/problems.jsonl"))}


def held_out(gold):
    return sorted(pid for pid in gold if level(pid) in HELD_OUT_LEVELS)


# --- Retrieval -------------------------------------------------------------------------------

def neighbours(pid, vectors, gold, index_language, max_level, query_language="cat"):
    """Index problems nearest to pid's statement, best first, never from its own year."""
    q = vectors[pid, query_language]
    scored = []
    for other in gold:
        if year(other) == year(pid) or level(other) > max_level or (other, index_language) not in vectors:
            continue
        v = vectors[other, index_language]
        scored.append((sum(a * b for a, b in zip(q, v)), other))
    scored.sort(reverse=True)
    return scored


def vote(near, gold, k):
    """The strategy with the most similarity among the k nearest; ties go to the nearest."""
    weight, first = Counter(), {}
    for rank, (score, other) in enumerate(near[:k]):
        s = gold[other]["strategy"]
        weight[s] += score
        first.setdefault(s, rank)
    return min(weight, key=lambda s: (-weight[s], first[s]))


def matches(strategy, annotation, lenient):
    return strategy == annotation["strategy"] or (lenient and strategy == annotation.get("strategy2"))


def cmd_retrieval(args):
    gold, second, vectors = load_gold(), load_second(), load_vectors()
    test = held_out(gold)
    print(f"Held-out problems: {len(test)} (levels {HELD_OUT_LEVELS}); annotated problems in all: {len(gold)}\n")

    groups = {"all": test, "text only": [p for p in test if gold[p].get("text_only")],
              "needs the figure": [p for p in test if not gold[p].get("text_only")]}

    # Ceiling and floor
    both = [p for p in test if p in second]
    rows = []
    for name, ids in groups.items():
        ids2 = [p for p in ids if p in second]
        agree = sum(second[p]["strategy"] == gold[p]["strategy"] for p in ids2)
        lenient = sum(matches(second[p]["strategy"], gold[p], True) or matches(gold[p]["strategy"], second[p], True)
                      for p in ids2)
        floor = 0  # the most common strategy among level 0-3 problems of other years
        for p in ids:
            common = Counter(gold[o]["strategy"] for o in gold if level(o) <= 3 and year(o) != year(p))
            floor += common.most_common(1)[0][0] == gold[p]["strategy"]
        rows.append([name, len(ids), rate(agree, len(ids2)), rate(lenient, len(ids2)), rate(floor, len(ids))])
    print("**Ceiling and floor**\n")
    print(table(["problems", "n", "two annotators agree (same main strategy)", "agree, counting the second strategy",
                 "always the most common strategy"], rows))
    print(f"\nSecond annotation available for {len(both)} of {len(test)}.\n")

    print("**Strategy found by the nearest problems** (query: the Catalan statement)\n")
    rows = []
    for index_language in ("cat", "eng"):
        for max_level, label in ((3, "levels 0-3"), (7, "all levels")):
            near = {p: neighbours(p, vectors, gold, index_language, max_level) for p in test}
            size = len({o for p in test for _, o in near[p]})
            for k in (1, 3, 5, 10):
                picked = {p: vote(near[p], gold, k) for p in test}
                row = [index_language, f"{label} ({size})", k]
                for name, ids in groups.items():
                    row.append(rate(sum(matches(picked[p], gold[p], False) for p in ids), len(ids)))
                row.append(rate(sum(matches(picked[p], gold[p], True) for p in test), len(test)))
                rows.append(row)
    print(table(["index language", "index", "k", "all: main strategy", "text only", "needs the figure",
                 "all: main or second strategy"], rows))
    spread = Counter(gold[p]["strategy"] for p in test)
    print("\n**Gold strategies in the held-out problems**\n")
    print(table(["strategy", "problems"], spread.most_common()))


# --- Rules: a hint from the statement alone ----------------------------------------------------

def rules_hint(question):
    """Point at what is asked and at the numbers given. No model, no retrieval, always safe."""
    text = re.sub(r"\s+", " ", question).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]
    asked = ([s for s in sentences if s.endswith("?")] or sentences or [""])[-1]
    numbers = []
    for n in re.findall(r"(?<![\w/])\d+(?:[.,]\d+)?", text.replace(asked, "")):
        if n not in numbers:
            numbers.append(n)
    hint = f"Torna a llegir què et demanen: «{asked}»"
    if 1 < len(numbers) <= 6:
        hint += f" Les dades són {', '.join(numbers[:-1])} i {numbers[-1]}: què vol dir cadascuna i quines necessites?"
    elif len(numbers) == 1:
        hint += f" L'enunciat et dona el {numbers[0]}: què vol dir exactament?"
    else:
        hint += " Quina part de l'enunciat o del dibuix et dona la informació per respondre-ho?"
    return hint


# --- Requests for the board ---------------------------------------------------------------------

FEWSHOT_SYSTEM = ("Ets un tutor de matemàtiques per a nens de 10 a 12 anys. No resols mai el problema ni dius la "
                  "resposta: dones UNA pista curta que ajuda l'alumne a començar, com als exemples.")


def model_sample():
    with open(os.path.join(DATA, "model_sample.json")) as f:
        return json.load(f)


def cmd_payloads(args):
    """The model with the hints of the nearest problems as examples, and choosing among retrieved strategies."""
    gold, vectors, problems = load_gold(), load_vectors(), load_problems()
    with open(os.path.join(ROOT, "content/strategies.json"), encoding="utf-8") as f:
        names = {s["code"]: s["name"]["cat"] for s in json.load(f)["strategies"]}
    out = os.path.join(DATA, "payloads_B.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for pid in model_sample():
            question = problems[pid, "cat"]["question"]
            near = neighbours(pid, vectors, gold, "cat", args.max_level)
            # B: two near problems with their "how to start" hint, nearest last (closest to the question)
            parts = []
            for _, other in reversed(near[:2]):
                parts.append("Problema: " + problems[other, "cat"]["question"][:400] + "\nPista: " + gold[other]["hints"][1])
            parts.append("Problema: " + question + "\nPista:")
            payload = {"messages": [{"role": "system", "content": FEWSHOT_SYSTEM},
                                    {"role": "user", "content": "\n\n".join(parts)}],
                       "max_tokens": 70, "temperature": 0, "seed": 42, "cache_prompt": True, "stop": ["\n"]}
            f.write(json.dumps({"key": "B|" + pid, "payload": payload}, ensure_ascii=False) + "\n")
            # G: the model picks among the three strategies the nearest problems suggest
            ranked = []
            for _, other in near[:10]:
                if gold[other]["strategy"] in names and gold[other]["strategy"] not in ranked:
                    ranked.append(gold[other]["strategy"])
            ranked = ranked[:3]
            if len(ranked) > 1:
                lines = "\n".join(f"{i} {names[c]}" for i, c in enumerate(ranked, 1))
                payload = {"messages": [
                    {"role": "system", "content": "Ets un tutor de matemàtiques. Llegeix el problema i tria l'estratègia "
                                                  "que més ajuda a resoldre'l. Respon només amb el número."},
                    {"role": "user", "content": f"Problema: {question}\n\n{lines}\n\nEstratègia:"}],
                    "max_tokens": 2, "temperature": 0, "seed": 42, "cache_prompt": True,
                    "grammar": "root ::= " + " | ".join(f'"{i}"' for i in range(1, len(ranked) + 1))}
                f.write(json.dumps({"key": "G|" + pid, "payload": payload, "choices": ranked}, ensure_ascii=False) + "\n")
    print(f"Wrote {out}")


def results(name):
    path = os.path.join(DATA, name)
    return {r["key"]: r for r in load(path)} if os.path.exists(path) else {}


def seconds(rows):
    values = sorted(r["seconds"] for r in rows)
    if not values:
        return "n/a"
    return f"{sum(values) / len(values):.1f} mean, {values[len(values) // 2]:.1f} median, {values[-1]:.1f} worst"


def cmd_choose(args):
    """How often the strategy the board's model picks is the gold one, next to retrieval on the same problems."""
    gold, vectors = load_gold(), load_vectors()
    with open(os.path.join(DATA, "choose_prompt.json"), encoding="utf-8") as f:
        codes = json.load(f)["codes"]
    sample = model_sample()
    res = {**results("results_AF.jsonl"), **results("results_B.jsonl")}
    payloads = {r["key"]: r for r in load(os.path.join(DATA, "payloads_B.jsonl"))} if os.path.exists(
        os.path.join(DATA, "payloads_B.jsonl")) else {}
    picked = {"model chooses among 15": {}, "model chooses among the 3 retrieved": {}, "retrieval, k=5": {}}
    times = {name: [] for name in picked}
    for pid in sample:
        r = res.get("F|" + pid)
        if r and not r["error"] and r["text"].strip().isdigit() and 1 <= int(r["text"]) <= len(codes):
            picked["model chooses among 15"][pid] = codes[int(r["text"]) - 1]
            times["model chooses among 15"].append(r)
        r, p = res.get("G|" + pid), payloads.get("G|" + pid)
        if r and p and not r["error"] and r["text"].strip().isdigit():
            picked["model chooses among the 3 retrieved"][pid] = p["choices"][int(r["text"]) - 1]
            times["model chooses among the 3 retrieved"].append(r)
        picked["retrieval, k=5"][pid] = vote(neighbours(pid, vectors, gold, "cat", args.max_level), gold, 5)
    rows = []
    for name, got in picked.items():
        ids = [p for p in sample if p in got]
        spread = Counter(got.values()).most_common(3)
        rows.append([name, len(ids), rate(sum(matches(got[p], gold[p], False) for p in ids), len(ids)),
                     rate(sum(matches(got[p], gold[p], True) for p in ids), len(ids)),
                     ", ".join(f"{c} {n}" for c, n in spread), seconds(times[name])])
    print(table(["alternative", "n", "main strategy", "main or second strategy", "most picked", "seconds on the board"],
                rows))


# --- Every alternative's hint, for a blind judge --------------------------------------------------

def rails(text, problem):
    """The checks the tutor runs on a model hint before a student sees it."""
    ok, reason = guardrails.check(text, problem)
    if ok and leaks_answer(text, problem):
        ok, reason = False, "leak"
    if ok and restates_question(text, problem):
        ok, reason = False, "restates"
    return ok, reason


def cmd_pack(args):
    gold, vectors, problems = load_gold(), load_vectors(), load_problems()
    with open(os.path.join(ROOT, "content/strategies.json"), encoding="utf-8") as f:
        templates = {s["code"]: s["hint"]["cat"] for s in json.load(f)["strategies"]}
    with open(os.path.join(DATA, "choose_prompt.json"), encoding="utf-8") as f:
        codes = json.load(f)["codes"]
    res = {**results("results_AF.jsonl"), **results("results_B.jsonl")}
    rng = random.Random(42)
    items, key_rows, auto = [], [], []
    for pid in model_sample():
        problem = problems[pid, "cat"]
        hints = {}
        for name, key in (("model as it is", "A|"), ("model with near examples", "B|")):
            r = res.get(key + pid)
            if r and not r["error"] and r["text"].strip():
                hints[name] = r["text"].strip()
                ok, reason = rails(r["text"], problem)
                auto.append((name, ok, reason, r["seconds"]))
        strategy = vote(neighbours(pid, vectors, gold, "cat", args.max_level), gold, 5)
        hints["retrieval: strategy template"] = templates.get(strategy, "")
        r = res.get("F|" + pid)
        if r and not r["error"] and r["text"].strip().isdigit():
            hints["model chooses: strategy template"] = templates[codes[int(r["text"]) - 1]]
        hints["rules on the statement"] = rules_hint(problem["question"])
        hints["written for this problem (reference)"] = gold[pid]["hints"][1]
        names = sorted(hints)
        rng.shuffle(names)
        for slot, name in enumerate(names, 1):
            if not hints[name]:
                continue
            item = f"{pid}#{slot}"
            items.append({"item": item, "question": problem["question"],
                          "figure": (problem.get("figure") or {}).get("cat"),
                          "solution": (problem.get("solution") or {}).get("text"),
                          "correct_option": (problem.get("options") or {}).get(problem["label"]),
                          "key_data": gold[pid].get("key_data"), "key_condition": gold[pid].get("key_condition"),
                          "hint": hints[name]})
            key_rows.append({"item": item, "id": pid, "alternative": name, "text_only": bool(gold[pid].get("text_only"))})
    with open(os.path.join(DATA, "judge_items.jsonl"), "w", encoding="utf-8") as f:
        for row in items:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(os.path.join(DATA, "judge_key.jsonl"), "w", encoding="utf-8") as f:
        for row in key_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(items)} hints to judge, for {len(model_sample())} problems\n")
    rows = []
    for name in sorted({a[0] for a in auto}):
        mine = [a for a in auto if a[0] == name]
        reasons = Counter(a[2] for a in mine if not a[1]).most_common(3)
        rows.append([name, len(mine), rate(sum(a[1] for a in mine), len(mine)),
                     ", ".join(f"{r} {n}" for r, n in reasons) or "-",
                     seconds([{"seconds": a[3]} for a in mine])])
    print("**The tutor's own checks on what the model wrote**\n")
    print(table(["alternative", "n", "passes the rails", "main reasons to reject", "seconds on the board"], rows))


VERDICTS = ("useful", "generic", "misleading", "leak", "nonsense")


def cmd_judged(args):
    key = {r["item"]: r for r in load(os.path.join(DATA, "judge_key.jsonl"))}
    verdicts = {r["item"]: r["verdict"] for r in load(os.path.join(DATA, "judge_verdicts.jsonl")) if r["item"] in key}
    for title, keep in (("All problems", lambda r: True), ("Text only", lambda r: r["text_only"]),
                        ("Needs the figure", lambda r: not r["text_only"])):
        rows = []
        for name in sorted({r["alternative"] for r in key.values()}):
            mine = [verdicts[i] for i, r in key.items() if r["alternative"] == name and keep(r) and i in verdicts]
            count = Counter(mine)
            rows.append([name, len(mine), rate(count["useful"], len(mine))] +
                        [count[v] for v in VERDICTS[1:]] +
                        [rate(count["misleading"] + count["leak"] + count["nonsense"], len(mine))])
        print(f"**{title}**\n")
        print(table(["alternative", "n", "useful", "generic", "misleading", "leak", "nonsense", "harmful or useless"],
                    rows))
        print()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=("retrieval", "payloads", "choose", "pack", "judged"))
    p.add_argument("--max-level", type=int, default=3, help="highest level kept in the index (default 3)")
    args = p.parse_args()
    {"retrieval": cmd_retrieval, "payloads": cmd_payloads, "choose": cmd_choose, "pack": cmd_pack,
     "judged": cmd_judged}[args.command](args)


if __name__ == "__main__":
    main()
