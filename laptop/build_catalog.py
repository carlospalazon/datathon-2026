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
