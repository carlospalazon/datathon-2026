#!/usr/bin/env python3
"""Summarise one eval.py run without calling the model or publishing M3Kang data.

    python3 error_report.py --eval results/eval-RUN.csv \
        --catalog data/catalog/problems.jsonl

Outputs stay in results/, which Git ignores. The review CSV contains IDs and
answer letters, but no problem text; inspect the selected problems locally.
"""

import argparse
import csv
import json
import math
import os
import statistics
from collections import defaultdict, deque


def key(row):
    return row["id"], row["language"]


def load_catalog(path):
    catalog = {}
    with open(path, encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if key(row) in catalog:
                raise ValueError(f"duplicate catalogue key {key(row)} at line {number}")
            catalog[key(row)] = row
    return catalog


def option_evidence(problem):
    """A review priority, not a claim that OCR text is mathematically correct."""
    if not problem.get("options"):
        return "no options"
    if problem.get("ocr_flags"):
        return "OCR flagged"
    if str(problem.get("options_status", "")).split(":", 1)[0] == "revisado":
        return "human reviewed"
    return "OCR/unreviewed"


def load_results(path, catalog):
    rows, seen = [], set()
    with open(path, newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        required = {"id", "language", "level", "label", "answer", "correct", "seconds", "status"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("evaluation CSV is missing required eval.py columns")
        for number, result in enumerate(reader, 2):
            identity = key(result)
            if identity in seen:
                raise ValueError(f"duplicate evaluation key {identity} at line {number}")
            seen.add(identity)
            if identity not in catalog:
                raise ValueError(f"no catalogue metadata for {identity}")
            problem = catalog[identity]
            if str(problem["level"]) != result["level"] or problem["label"] != result["label"]:
                raise ValueError(f"catalogue and evaluation disagree for {identity}")
            if result["answer"] not in "ABCDE" or len(result["answer"]) != 1:
                raise ValueError(f"invalid predicted answer for {identity}")
            correct = result["answer"] == result["label"]
            if result["correct"] not in ("0", "1") or int(result["correct"]) != correct:
                raise ValueError(f"incorrect correctness flag for {identity}")
            seconds = float(result["seconds"])
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError(f"invalid latency for {identity}")
            rows.append({"id": result["id"], "language": result["language"],
                         "level": int(result["level"]), "difficulty": int(problem["difficulty"]),
                         "topic": problem.get("topic") or "unlabeled",
                         "option_evidence": option_evidence(problem),
                         "needs_figure": bool(problem.get("needs_figure")),
                         "correct": correct, "label": result["label"],
                         "answer": result["answer"], "seconds": seconds,
                         "status": result["status"]})
    if not rows:
        raise ValueError("evaluation CSV has no results")
    return rows


def group_table(rows, field):
    groups = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    lines = ["| Group | Correct | Total | Accuracy | Mean time |",
             "|---|---:|---:|---:|---:|"]
    for label, group in sorted(groups.items(), key=lambda item: item[0]):
        hits = sum(row["correct"] for row in group)
        lines.append(f"| {label} | {hits} | {len(group)} | {hits / len(group):.1%} | "
                     f"{statistics.mean(row['seconds'] for row in group):.1f} s |")
    return "\n".join(lines)


def report(rows, eval_path):
    hits = sum(row["correct"] for row in rows)
    lines = ["# Math Copilot error analysis", "",
             f"Source run: `{os.path.basename(eval_path)}`", "",
             f"**Overall:** {hits}/{len(rows)} correct ({hits / len(rows):.1%}); "
             f"mean {statistics.mean(row['seconds'] for row in rows):.1f} s per problem.", "",
             "These figures cover only this evaluation run. Small groups are descriptive, "
             "not reliable evidence that one language or topic is intrinsically harder.", "",
             "`OCR/unreviewed` means options were extracted but not confirmed against the image. "
             "`OCR flagged` is a warning, not proof of an OCR error. Difficulty is the catalogue's "
             "estimated 0-23 score.", ""]
    for field, title in (("topic", "By topic"), ("language", "By language"),
                         ("level", "By M3Kang level"), ("difficulty", "By estimated difficulty"),
                         ("option_evidence", "By answer-option evidence"),
                         ("needs_figure", "By figure dependency"),
                         ("status", "By prediction status")):
        lines += [f"## {title}", "", group_table(rows, field), ""]
    lines += ["## Manual review", "", "Open the companion review CSV locally. Inspect each original "
              "problem and image, then record one cause: OCR/figure, reading, mathematical reasoning, "
              "retrieval, timeout/service, or unclear. Do not infer a cause from the answer letter alone.", ""]
    return "\n".join(lines)


def review_candidates(rows, limit):
    """Round-robin across topics so the sample is not just the first topic."""
    buckets = defaultdict(deque)
    for row in sorted((r for r in rows if not r["correct"]),
                      key=lambda r: (r["topic"], r["language"], r["difficulty"], r["id"])):
        buckets[row["topic"]].append(row)
    selected = []
    while buckets and len(selected) < limit:
        for topic in sorted(list(buckets)):
            if len(selected) >= limit:
                break
            selected.append(buckets[topic].popleft())
            if not buckets[topic]:
                del buckets[topic]
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--eval", required=True, help="per-problem CSV written by eval.py")
    parser.add_argument("--catalog", default="data/catalog/problems.jsonl")
    parser.add_argument("--out", help="default: results/<eval name>-analysis.md")
    parser.add_argument("--review-out", help="default: results/<eval name>-review.csv")
    parser.add_argument("--review-limit", type=int, default=10)
    args = parser.parse_args()
    if args.review_limit < 0:
        parser.error("--review-limit must be zero or greater")
    rows = load_results(args.eval, load_catalog(args.catalog))
    stem = os.path.splitext(os.path.basename(args.eval))[0]
    args.out = args.out or f"results/{stem}-analysis.md"
    args.review_out = args.review_out or f"results/{stem}-review.csv"
    for path in (args.out, args.review_out):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as output:
        output.write(report(rows, args.eval))
    fields = ["id", "language", "topic", "level", "difficulty", "option_evidence",
              "needs_figure", "label", "answer", "seconds", "status", "suspected_cause", "review_notes"]
    selected = review_candidates(rows, args.review_limit)
    with open(args.review_out, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in selected:
            writer.writerow({field: row.get(field, "") for field in fields})
    print(f"Analysed {len(rows)} evaluated problems; {len(rows) - sum(r['correct'] for r in rows)} wrong.")
    print(f"Summary: {args.out}\nManual review queue ({len(selected)}): {args.review_out}")


if __name__ == "__main__":
    main()
