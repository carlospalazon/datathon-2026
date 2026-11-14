#!/usr/bin/env python3
"""Cut a fine-tuning set for hints (problem -> the hint that says where to look, or how to start).

    python3 laptop/make_hint_ft_set.py [--hold-out 2023,2024] [--out ~/unoq-local/ft/hints]

From data/catalog/content/anatomy.jsonl (laptop/merge_anatomy.py): each problem gives two examples,
one per hint kind, with the system prompt the tutor's model already uses (copilot/slm.py). The third
hint is left out: it states an intermediate result, which a model that can't solve the problem would
make up. Problems of the held-out years go to valid.jsonl only, whole, so a model trained on
train.jsonl can be measured on problems it has never seen in any level.
The output holds M3Kang text: it goes outside the repository.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copilot import slm  # noqa: E402

ASK = {1: "On m'he de fixar?", 2: "Com puc començar?"}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--hold-out", default="2023,2024", help="years kept for validation only")
    p.add_argument("--out", default="~/unoq-local/ft/hints")
    args = p.parse_args()
    held = set(args.hold_out.split(","))
    with open(os.path.join(ROOT, "data/catalog/problems.jsonl"), encoding="utf-8") as f:
        problems = {r["id"]: r for r in map(json.loads, f) if r["language"] == "cat"}
    sets = {"train": [], "valid": []}
    with open(os.path.join(ROOT, "data/catalog/content/anatomy.jsonl"), encoding="utf-8") as f:
        for row in map(json.loads, f):
            if not row["text_only"]:  # the board's model never sees the figure
                continue
            problem = {"language": "cat", "question": problems[row["id"]]["question"]}
            for kind, ask in ASK.items():
                if kind in row.get("leaks", []):
                    continue
                messages = slm.build_messages(problem, ask)
                messages.append({"role": "assistant", "content": row["hints"][kind - 1]})
                sets["valid" if row["id"].split("_")[1] in held else "train"].append({"messages": messages})
    out = os.path.expanduser(args.out)
    os.makedirs(out, exist_ok=True)
    for name, rows in sets.items():
        with open(os.path.join(out, name + ".jsonl"), "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} examples -> {os.path.join(out, name + '.jsonl')}")


if __name__ == "__main__":
    main()
