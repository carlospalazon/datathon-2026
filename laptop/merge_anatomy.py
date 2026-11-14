#!/usr/bin/env python3
"""Check the annotations of the solved problems and merge them into one content file.

    python3 laptop/merge_anatomy.py        # data/catalog/content/anatomy_raw/out_*.jsonl and reout_*.jsonl

Each line follows data/catalog/content/FORMAT_anatomy.md: what in a verified solution decides
the problem (key data, key condition, strategy from the closed list in content/strategies.json,
first step) and the three hints that follow from it.

Writes content/anatomy.jsonl (first annotator, with hints) and content/anatomy_second.jsonl (the
independent second annotation of the level 0-1 problems, used to measure agreement). A strategy
outside the list becomes "altra". Hints in which copilot.tutor.leaks_answer finds the correct
option are listed in "leaks" (1-based), so nothing downstream shows them.
The report holds ids and counts only, never problem or hint text.
"""
import glob
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copilot.tutor import leaks_answer  # noqa: E402

CONTENT = os.path.join(ROOT, "data/catalog/content")


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    with open(os.path.join(ROOT, "content/strategies.json"), encoding="utf-8") as f:
        codes = {s["code"] for s in json.load(f)["strategies"]}
    problems = {r["id"]: r for r in load(os.path.join(ROOT, "data/catalog/problems.jsonl")) if r["language"] == "cat"}

    for pattern, name, with_hints in (("out_*.jsonl", "anatomy.jsonl", True),
                                      ("reout_*.jsonl", "anatomy_second.jsonl", False)):
        rows, seen, fixed, short, leaking = [], set(), [], [], []
        for path in sorted(glob.glob(os.path.join(CONTENT, "anatomy_raw", pattern))):
            for row in load(path):
                pid = row.get("id")
                if pid not in problems or pid in seen:
                    continue
                seen.add(pid)
                for field in ("strategy", "strategy2"):
                    if row.get(field) and row[field] not in codes and row[field] != "altra":
                        fixed.append(pid)
                        row[field] = "altra" if field == "strategy" else None
                if not row.get("strategy"):
                    row["strategy"] = "altra"
                row["text_only"] = bool(row.get("text_only"))
                if with_hints:
                    hints = [str(h or "").strip() for h in row.get("hints") or []]
                    if len(hints) != 3 or not all(hints):
                        short.append(pid)
                        continue
                    row["hints"] = hints
                    row["leaks"] = [i for i, h in enumerate(hints, 1) if leaks_answer(h, problems[pid])]
                    if row["leaks"]:
                        leaking.append(pid)
                    row["content_status"] = "generado:claude-fable"
                rows.append(row)
        with open(os.path.join(CONTENT, name), "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} problems; with doubts {sum(bool(r.get('doubts')) for r in rows)}; "
              f"text only {sum(r['text_only'] for r in rows)}")
        print("  strategies: " + ", ".join(f"{c} {n}" for c, n in Counter(r["strategy"] for r in rows).most_common()))
        if fixed:
            print(f"  strategy code outside the list ({len(fixed)}): {' '.join(sorted(set(fixed)))}")
        if with_hints:
            print(f"  left out, not 3 hints ({len(short)}): {' '.join(short) or '-'}")
            print(f"  with a hint the leak check stops ({len(leaking)}): {' '.join(leaking) or '-'}")


if __name__ == "__main__":
    main()
