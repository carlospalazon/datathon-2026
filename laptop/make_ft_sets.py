#!/usr/bin/env python3
"""Cut fine-tuning sets (train.jsonl + valid.jsonl, chat format) out of data/training/master.jsonl.

    python3 laptop/make_ft_sets.py --name m3k_letter --mode letter --sources m3kang --need-rationale
    python3 laptop/make_ft_sets.py --name m3k_reason --mode reasoning --sources m3kang

--mode letter     the assistant turn is the letter: what predict.py asks for (grammar [A-E], one token)
--mode reasoning  the assistant turn is "<rationale>\\nAnswer: <letter>"; only examples with a rationale

valid.jsonl is always M3Kang training problems (about 6% of the ids, chosen by a hash of the id, all
their copies and languages), so the loss during training is measured on Kangaroo problems. Those ids
are left out of train.jsonl. Nothing from data/val.jsonl can be here: master.jsonl already excludes it.
The output holds M3Kang text: it goes outside the repository (default ~/unoq-local/ft/<name>).
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from laptop.build_training_data import read_jsonl, to_chat, write_jsonl  # noqa: E402

VALID_PER_1000 = 60


def is_valid_id(m3k_id):
    return int(hashlib.sha256(m3k_id.encode("utf-8")).hexdigest()[:8], 16) % 1000 < VALID_PER_1000


def select(records, mode, sources, need_rationale, caps, seed):
    """Return (train, valid) lists of master records."""
    reasoning = mode == "reasoning"
    rng = random.Random(seed)
    train, valid = [], []
    by_source = {}
    for rec in records:
        if rec["source"] not in sources:
            continue
        if (reasoning or need_rationale) and not rec.get("rationale"):
            continue
        if reasoning and not rec.get("options"):
            continue
        by_source.setdefault(rec["source"], []).append(rec)
    for source in sorted(by_source):
        rows = by_source[source]
        if source == "m3kang":
            valid += [r for r in rows if is_valid_id(r["meta"]["m3k_id"])]
            rows = [r for r in rows if not is_valid_id(r["meta"]["m3k_id"])]
        rng.shuffle(rows)
        cap = caps.get(source)
        train += rows[:cap] if cap is not None else rows
    rng.shuffle(train)
    rng.shuffle(valid)
    return train, valid


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--master", default=str(ROOT / "data" / "training" / "master.jsonl"))
    p.add_argument("--name", required=True)
    p.add_argument("--mode", choices=("letter", "reasoning"), required=True)
    p.add_argument("--sources", default="m3kang", help="comma-separated: m3kang,aqua_rat,synthetic")
    p.add_argument("--need-rationale", action="store_true",
                   help="letter mode only: keep just the examples that have a rationale, to pair with a reasoning set")
    p.add_argument("--cap", action="append", default=[], metavar="SOURCE=N", help="at most N examples of a source")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default=str(Path.home() / "unoq-local" / "ft"))
    args = p.parse_args(argv)

    caps = {k: int(v) for k, v in (c.split("=") for c in args.cap)}
    train, valid = select(list(read_jsonl(args.master)), args.mode, set(args.sources.split(",")),
                          args.need_rationale, caps, args.seed)
    if not train or not valid:
        sys.exit("Nothing selected: check --sources (valid.jsonl needs m3kang)")
    out = Path(args.out) / args.name
    out.mkdir(parents=True, exist_ok=True)
    reasoning = args.mode == "reasoning"
    write_jsonl(out / "train.jsonl", [to_chat(r, reasoning) for r in train])
    write_jsonl(out / "valid.jsonl", [to_chat(r, reasoning) for r in valid])
    count = Counter((r["source"], r["language"]) for r in train)
    print(json.dumps({"out": str(out), "mode": args.mode, "train": len(train), "valid": len(valid),
                      "train_by_source_language": {f"{s}/{lang}": n for (s, lang), n in sorted(count.items())},
                      "train_no_options": sum(1 for r in train if not r.get("options"))}, indent=1))


if __name__ == "__main__":
    main()
