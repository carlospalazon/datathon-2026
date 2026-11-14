#!/usr/bin/env python3
"""Build the teaching catalogue: every M3Kang problem in one standard format, with its exercise type.

    python3 laptop/build_catalog.py --labels path/to/labels/*.jsonl

Reads data/train.jsonl and data/val.jsonl (from prepare_m3kang.py) and the topic
labels (one JSON line per problem id: id, topic, secondary, confidence,
needs_figure, note). Writes data/catalog/problems.jsonl, one problem per id and
language, and data/catalog/types.json, one empty teaching card per exercise type.

Everything goes to data/, which Git ignores: M3Kang is research use only.

Every piece of teaching content carries a status, so nobody mistakes it for checked work:
  "revisado"  checked by a person on the team
  "preparado" written by a person, not yet checked by a second one
  "generado"  written by a model (Claude or Qwen), not checked
"""
import argparse
import glob
import json
import os
import re
from collections import Counter

TOPICS = ["aritmetica", "numeros", "algebra", "conteo", "logica", "patrones",
          "geometria_plana", "geometria_espacial", "medida", "visual", "otros"]
LEADING_NUMBER = re.compile(r"^\s*\d{1,2}\s*[.)]\s*")


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def ocr_flags(options):
    """Cheap signs that OCR misread the options. Not proof either way: check the image."""
    if not options:
        return []
    values = [options[k].strip() for k in "ABCDE"]
    flags = []
    if len(set(v.lower() for v in values)) < 5:
        flags.append("duplicate")
    if any(len(v) > 40 for v in values):
        flags.append("too_long")
    return flags


def question_number(problem_id):
    return int(problem_id.rsplit("_", 1)[1])


def difficulty(problem_id, level, exam_size):
    """Where a problem sits: school grade, stage, and a 0..23 difficulty.

    The dataset card says the 8 levels go from grade 5 to grade 12, so level 0 is
    5th of primary school. Within an exam, Kangaroo questions come in three blocks
    (3, 4 and 5 points) of growing difficulty: that's the competition's rule, not
    something the dataset states, so treat `difficulty` as an estimate.
    """
    number = question_number(problem_id)
    block = min(2, (number - 1) * 3 // exam_size)
    grade = level + 5
    stage = "primaria" if grade <= 6 else "eso" if grade <= 10 else "batxillerat"
    return {"grade": grade, "stage": stage, "question_number": number, "block": block,
            "difficulty": level * 3 + block}


def load_content(path):
    return {row["id"]: row for row in load(path)} if os.path.exists(path) else {}


def apply_content(record, fig, cp):
    """Lay prepared content over a catalogue record, keeping each item's status.

    fig: options read from the image and a figure description (both languages).
    cp: a Catalan solution, checkpoints and distractor explanations, so only
    Catalan rows get them.
    """
    if fig:
        record["options"] = fig["options"]
        record["options_status"] = fig["options_status"]
        record["ocr_flags"] = []
        if fig.get("figure_cat"):
            record["figure"] = {"cat": fig["figure_cat"], "eng": fig["figure_eng"], "status": fig["figure_status"]}
        if fig.get("needs_figure") is not None:
            record["needs_figure"] = fig["needs_figure"]
    if cp and record["language"] == "cat":
        status = cp["content_status"]
        # A person's review can set the status of each item; otherwise the whole entry's
        record["solution"] = {"text": cp["solution"], "status": cp.get("solution_status", status)}
        record["checkpoints"] = [{**c, "status": c.get("status", status)} for c in cp["checkpoints"]]
        record["distractors"] = {k: {"text": v, "status": cp.get("distractors_status", status)}
                                 for k, v in cp["distractors"].items()}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data")
    p.add_argument("--labels", nargs="+", required=True, help="topic label files (JSON Lines)")
    p.add_argument("--label-source", default="generado:claude-sonnet",
                   help="who made the topic labels, stored with each problem")
    p.add_argument("--out", default="data/catalog")
    args = p.parse_args()

    labels = {}
    for pattern in args.labels:
        for path in sorted(glob.glob(pattern)):
            for row in load(path):
                if row["topic"] not in TOPICS:
                    raise SystemExit(f"{path}: unknown topic {row['topic']!r} for {row['id']}")
                if row["id"] in labels:
                    raise SystemExit(f"{path}: {row['id']} labelled twice")
                labels[row["id"]] = row

    problems = []
    for split in ("train", "val"):
        for x in load(os.path.join(args.data, f"{split}.jsonl")):
            x["split"] = split
            problems.append(x)
    missing = sorted({x["id"] for x in problems} - set(labels))
    if missing:
        raise SystemExit(f"{len(missing)} problem ids have no label, e.g. {missing[:5]}")

    # Questions per exam differ by level (24 or 30): take the largest number seen
    exam_size = {}
    for x in problems:
        exam_size[x["level"]] = max(exam_size.get(x["level"], 0), question_number(x["id"]))

    # Teaching content prepared separately (see apply_content), keyed by problem id
    content = os.path.join(args.out, "content")
    figures = load_content(os.path.join(content, "figures.jsonl"))
    checkpoints = load_content(os.path.join(content, "checkpoints.jsonl"))

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "problems.jsonl")
    with open(out_path, "w") as f:
        for x in problems:
            lab = labels[x["id"]]
            key = f"{x['id']}_{x['language']}"
            record = {
                "key": key,
                "id": x["id"],
                "language": x["language"],
                "level": x["level"],
                **difficulty(x["id"], x["level"], exam_size[x["level"]]),
                "year": x["year"],
                "split": x["split"],
                "text": x["text"],
                "question": LEADING_NUMBER.sub("", x["text"]).strip(),
                "image": f"{key}.png",
                "text_only": x["text_only"],
                "options": x["options"],
                "options_status": "ocr" if x["options"] else "none",
                "ocr_flags": ocr_flags(x["options"]),
                "label": x["label"],
                "topic": lab["topic"],
                "secondary": lab.get("secondary"),
                "topic_confidence": lab["confidence"],
                "topic_status": args.label_source,
                "needs_figure": lab["needs_figure"],
                # Teaching content, filled in later, each item with its own status
                "solution": None,
                "hints": [],
                "distractors": {},
            }
            apply_content(record, figures.get(x["id"]), checkpoints.get(x["id"]))
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    types_path = os.path.join(args.out, "types.json")
    if not os.path.exists(types_path):  # never overwrite cards people have written
        cards = {t: {"name": {"cat": "", "eng": ""}, "method": "", "steps": [], "typical_errors": [],
                     "example": None, "status": "vacío"} for t in TOPICS}
        with open(types_path, "w") as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)

    eng = [labels[i] for i in sorted({x["id"] for x in problems})]
    print(f"Wrote {out_path}: {len(problems)} rows, {len(eng)} problem ids")
    print("Topics:     " + ", ".join(f"{t} {n}" for t, n in Counter(r["topic"] for r in eng).most_common()))
    print("Confidence: " + ", ".join(f"{c} {n}" for c, n in Counter(r["confidence"] for r in eng).most_common()))
    print(f"Needs the figure to solve: {sum(r['needs_figure'] for r in eng)}/{len(eng)}")
    print(f"Teaching cards: {types_path}")


if __name__ == "__main__":
    main()
