#!/usr/bin/env python3
"""Check the hints written for each problem and merge them into the catalogue's content.

    python3 laptop/merge_hints.py                      # data/catalog/content/hints_raw/out_*.jsonl
    python3 laptop/build_catalog.py --labels "data/catalog/content/labels/*.jsonl"

Each input line follows data/catalog/content/FORMAT_hints.md: id, final_letter, three
graded hints, and for problems that had none, a solution, checkpoints and distractors.

What is kept:
  - nothing from a line whose final_letter differs from the verified answer: whoever
    solved it wrong can't guide a student to the right answer;
  - a hint only if copilot.tutor.leaks_answer doesn't find the correct option in it;
  - solution, checkpoints and distractors only for problems that have none yet: content
    already in checkpoints.jsonl (some of it reviewed by a person) is never replaced.

Writes content/hints.jsonl (replaced) and appends to content/checkpoints.jsonl, after a
backup. The report holds ids and counts only, never problem or hint text.
"""
import argparse
import glob
import json
import os
import shutil
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copilot.tutor import _number, leaks_answer  # noqa: E402

MAX_WORDS = 45  # the format asks for 30: longer than this isn't a hint a child reads


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def check_hints(row, problem):
    """(hints kept, reasons the others were dropped)."""
    kept, dropped = [], []
    for i, text in enumerate(row.get("hints") or [], 1):
        text = str(text or "").strip()
        if not text:
            dropped.append(f"hint {i}: empty")
        elif len(text.split()) > MAX_WORDS:
            dropped.append(f"hint {i}: too long")
        elif leaks_answer(text, problem):
            dropped.append(f"hint {i}: leaks the answer")
        else:
            kept.append(text)
    return kept, dropped


def check_checkpoints(row):
    """Checkpoints with a question and one number as the answer."""
    return [c for c in row.get("checkpoints") or []
            if str(c.get("question") or "").strip() and _number(c.get("answer")) is not None]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", default="data/catalog/content/hints_raw/out_*.jsonl")
    p.add_argument("--catalog", default="data/catalog/problems.jsonl")
    p.add_argument("--content", default="data/catalog/content")
    p.add_argument("--language", default="cat", help="the language the hints are written in")
    p.add_argument("--status", default="generado:claude-fable", help="who wrote the content")
    args = p.parse_args()

    problems = {r["id"]: r for r in load(os.path.join(ROOT, args.catalog)) if r["language"] == args.language}
    content = os.path.join(ROOT, args.content)
    cp_path = os.path.join(content, "checkpoints.jsonl")
    have_cp = {r["id"] for r in load(cp_path)} if os.path.exists(cp_path) else set()

    hints, new_cp, seen = [], [], set()
    wrong, unknown, dropped, short = [], [], [], []
    for path in sorted(glob.glob(os.path.join(ROOT, args.raw))):
        for row in load(path):
            pid = row.get("id")
            if pid not in problems or pid in seen:
                unknown.append(str(pid))
                continue
            seen.add(pid)
            problem = problems[pid]
            if str(row.get("final_letter", "")).strip().upper() != problem["label"]:
                wrong.append(pid)
                continue
            kept, reasons = check_hints(row, problem)
            dropped += [f"{pid} {r}" for r in reasons]
            if len(kept) < 3:
                short.append(pid)
            if kept:
                hints.append({"id": pid, "hints": kept, "doubts": row.get("doubts"), "content_status": args.status})
            if pid not in have_cp and row.get("solution"):
                new_cp.append({"id": pid, "final_letter": problem["label"], "solution": row["solution"],
                               "checkpoints": check_checkpoints(row), "distractors": row.get("distractors") or {},
                               "doubts": row.get("doubts"), "content_status": args.status})

    with open(os.path.join(content, "hints.jsonl"), "w", encoding="utf-8") as f:
        for row in hints:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if new_cp:
        shutil.copy(cp_path, f"{cp_path}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        with open(cp_path, "a", encoding="utf-8") as f:
            for row in new_cp:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Lines read: {len(seen)}. Hints kept for {len(hints)} problems, "
          f"solution and checkpoints added for {len(new_cp)}.")
    print(f"Discarded, solved with the wrong letter ({len(wrong)}): {' '.join(wrong) or '-'}")
    print(f"Hints dropped ({len(dropped)}): {'; '.join(dropped) or '-'}")
    print(f"Problems left with fewer than 3 hints ({len(short)}): {' '.join(short) or '-'}")
    if unknown:
        print(f"Ids not in the catalogue, or repeated ({len(unknown)}): {' '.join(unknown)}")
    missing = sorted(set(problems) - seen)
    print(f"Catalogue problems in '{args.language}' without a line: {len(missing)}")


if __name__ == "__main__":
    main()
