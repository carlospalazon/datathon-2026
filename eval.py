#!/usr/bin/env python3
"""Measure accuracy and latency on the board, the way the official run does.

    python3 eval.py --limit 50                    # baseline on 50 validation problems
    python3 eval.py --limit 50 --rag 1 --name rag1
    python3 eval.py --languages cat --limit 100

Every run writes per-problem results to results/ and adds one line to
results/ablations.csv, so you can build your ablation table as you go.
"""
import argparse
import csv
import json
import os
import random
import statistics
import subprocess
import time
from collections import Counter, defaultdict

from analyze_errors import load_catalog, wilson
from copilot.config import CONFIG
from copilot.pipeline import TIME_LIMIT, solve

LETTERS = "ABCDE"
EXPERIMENT_ENV = ("NO_OPTIONS_PRIOR", "LETTER_BIAS_FILE", "OPTION_ORDERS", "ANSWER_MODE", "REASON_MAX_TOKENS",
                  "BOARD_READ_TPS", "BOARD_WRITE_TPS", "PRESOLVE", "PRESOLVE_DATA", "SAVE_TEXTS")
DETAIL_COLUMNS = ["id", "language", "level", "has_options", "label", "answer", "correct", "seconds",
                  "status", "prompt_tokens", "retrieved", "topic", "needs_figure", "passes",
                  *[f"lp_{l}" for l in LETTERS],
                  # Working modes only (ANSWER_MODE): the token budget, what was written, whether the working
                  # reached its answer, how the budget was set (budget/fixed) and where the letter came from
                  # (working/forced/direct).
                  "budget_tokens", "written_tokens", "finished", "working", "letter_from"]
ABLATION_COLUMNS = ["time", "name", "commit", "input", "languages", "n", "rag_k", "accuracy", "mean_s",
                    "worst_s", "over_limit", "ci_low", "ci_high", "env"]


def experiment_env():
    return ";".join(f"{k}={os.environ[k]}" for k in EXPERIMENT_ENV if k in os.environ)


def append_ablation(path, values):
    """Add one row to the ablation log; an older, shorter header is extended and old rows padded."""
    old_rows = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            old_rows = list(csv.reader(f))
    if old_rows and old_rows[0] != ABLATION_COLUMNS:
        old_header = old_rows[0]
        migrated = []
        for r in old_rows[1:]:
            by_name = dict(zip(old_header, r))
            migrated.append([by_name.get(c, "") for c in ABLATION_COLUMNS])
        old_rows = [ABLATION_COLUMNS] + migrated
        with open(path, "w", newline="") as f:
            csv.writer(f).writerows(old_rows)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if not old_rows:
            writer.writerow(ABLATION_COLUMNS)
        writer.writerow(values)


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def table(title, groups):
    print(f"\n{title}")
    for key in sorted(groups, key=str):
        hits = groups[key]
        print(f"  {str(key):12} {sum(hits):4}/{len(hits):<4} {100 * sum(hits) / len(hits):5.1f}%")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--limit", type=int, default=50, help="0 means every problem")
    p.add_argument("--languages", default="", help="e.g. eng,cat")
    p.add_argument("--rag", type=int, default=0, metavar="K")
    p.add_argument("--index", default="data/index.db")
    p.add_argument("--name", default="", help="a label for this experiment in ablations.csv")
    p.add_argument("--catalog", default="data/catalog/problems.jsonl",
                   help="topics and needs_figure per (id, language); optional")
    p.add_argument("--one-per-id", action="store_true",
                   help="keep one language per problem id (the first after the language filter and shuffle)")
    args = p.parse_args(argv)

    with open(args.input) as f:
        problems = [json.loads(line) for line in f if line.strip()]
    languages = set(filter(None, args.languages.split(",")))
    if languages:
        problems = [x for x in problems if x["language"] in languages]
    random.Random(42).shuffle(problems)  # the same sample every run, so runs compare
    if args.one_per_id:
        seen, unique = set(), []
        for x in problems:
            if x["id"] not in seen:
                seen.add(x["id"])
                unique.append(x)
        problems = unique
    if args.limit:
        problems = problems[:args.limit]

    index = None
    if args.rag:
        from copilot.rag import Index
        index = Index(args.index)

    os.makedirs("results", exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = args.name or (f"rag{args.rag}" if args.rag else "baseline")
    detail_path = f"results/eval-{stamp}-{name}.csv"

    catalog = load_catalog(args.catalog)
    if not catalog:
        print(f"No catalogue at {args.catalog}: topic and needs_figure stay empty.")

    rows = []
    with open(detail_path, "w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(DETAIL_COLUMNS)
        for n, problem in enumerate(problems, 1):
            result = solve(problem, index=index, k=args.rag, exclude_id=problem["id"])
            correct = result["answer"] == problem["label"]
            cat = catalog.get((problem["id"], problem["language"]), {})
            topic = cat.get("topic", "")
            needs_figure = cat.get("needs_figure", "")
            logprobs = result.get("logprobs") or {}
            row = {**problem, **result, "correct": correct, "has_options": bool(problem.get("options")),
                   "topic": topic}
            rows.append(row)
            writer.writerow([problem["id"], problem["language"], problem["level"], row["has_options"],
                             problem["label"], result["answer"], int(correct), result["seconds"],
                             result["status"], result["prompt_tokens"], result["retrieved"],
                             topic, needs_figure, result.get("passes", ""),
                             *[logprobs[l] if l in logprobs else "" for l in LETTERS],
                             result.get("budget_tokens", ""), result.get("written_tokens", ""),
                             int(result["finished"]) if "finished" in result else "",
                             result.get("working", ""), result.get("letter_from", "")])
            out.flush()
            running = 100 * sum(r["correct"] for r in rows) / len(rows)
            print(f"[{n}/{len(problems)}] {problem['id']} {problem['language']}: "
                  f"{result['answer']} (truth {problem['label']}) {result['seconds']:.1f} s, "
                  f"running accuracy {running:.1f}%", flush=True)

    hits = [r["correct"] for r in rows]
    seconds = [r["seconds"] for r in rows]
    floor = sum(r["label"] == CONFIG["FALLBACK_ANSWER"] for r in rows)
    over = sum(s > TIME_LIMIT for s in seconds)
    accuracy = 100 * sum(hits) / len(hits)

    print("\n" + "=" * 60)
    low, high = (100 * x for x in wilson(sum(hits), len(hits)))
    print(f"Accuracy: {sum(hits)}/{len(hits)} = {accuracy:.1f}%  (95% CI {low:.1f}-{high:.1f})")
    if len(hits) < 200:
        print(f"  n = {len(hits)} < 200: differences smaller than {high - low:.0f} points are noise.")
    print(f"  floor, always {CONFIG['FALLBACK_ANSWER']}: {100 * floor / len(rows):.1f}%   random guess: 20.0%")
    print(f"Latency: mean {statistics.mean(seconds):.1f} s, median {statistics.median(seconds):.1f} s, "
          f"worst {max(seconds):.1f} s, over {TIME_LIMIT:.0f} s: {over}")
    print(f"Status: {dict(Counter(r['status'] for r in rows))}")
    for source in ("working", "forced", "direct"):  # working modes only
        part = [r["correct"] for r in rows if r.get("letter_from") == source]
        if part:
            print(f"  letter from {source:8} {sum(part):4}/{len(part):<4} {100 * sum(part) / len(part):5.1f}%")
    worked = [r for r in rows if r.get("working")]
    if worked:
        print(f"  working: budget set from the prompt's tokens in {sum(r['working'] == 'budget' for r in worked)}"
              f"/{len(worked)}, mean written {statistics.mean(r.get('written_tokens', 0) for r in worked):.0f} "
              f"of {statistics.mean(r.get('budget_tokens', 0) for r in worked):.0f} tokens")
    copied = [r["correct"] for r in rows if r["status"] == "presolve"]
    if copied:
        print(f"  presolve (no model): {sum(copied)}/{len(copied)} right")

    for field, title in (("language", "By language"), ("level", "By level"),
                         ("has_options", "By whether OCR found the options"), ("topic", "By topic")):
        groups = defaultdict(list)
        for r in rows:
            if r[field] != "":
                groups[r[field]].append(r["correct"])
        if groups:
            table(title, groups)

    predicted = Counter(r["answer"] for r in rows)
    truth = Counter(r["label"] for r in rows)
    print("\nLetters   " + "  ".join(f"{l}:{predicted[l]:>3}/{truth[l]:<3}" for l in "ABCDE"))
    print("          (predicted/true; a model that loves one letter shows up here)")

    log = "results/ablations.csv"
    append_ablation(log, [stamp, name, git_commit(), args.input, args.languages or "all", len(rows),
                          args.rag, f"{accuracy:.1f}", f"{statistics.mean(seconds):.1f}",
                          f"{max(seconds):.1f}", over, f"{low:.1f}", f"{high:.1f}", experiment_env()])
    print(f"\nDetails: {detail_path}\nAblation log: {log}")


if __name__ == "__main__":
    main()
