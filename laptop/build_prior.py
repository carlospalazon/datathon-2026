#!/usr/bin/env python3
"""Build copilot/prior_table.json, the table of copilot.prior, from the training split only.

    python3 laptop/build_prior.py                 # select features by cross-validation, report, write
    python3 laptop/build_prior.py --no-write      # report only
    python3 laptop/build_prior.py --measure data/val.jsonl --languages eng,cat
                                                  # ONE final measurement of the committed table

It reads data/train.jsonl and nothing else to build. `--measure` only reads the file it is given and
the committed table (plus the training split for the presolve index, as the pipeline does); it never
changes the table. The table holds counts and weights of categories (letters, ranks, bands): no text.

Selection. Features are tried in the fixed order of copilot.prior.*_CANDIDATES on top of the letter
counts. One is kept only if, in 5-fold cross-validation by problem id (both languages of an id in the
same fold), it gains correct answers and the gain is larger than its own noise: paired by id, z >= 1.64.
The honest cross-validated figure is the NESTED one (selection redone inside each fold); the plain one
has seen its own selection and is a little optimistic.
"""
import argparse
import json
import math
import os
import sys
import zlib
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copilot import presolve as presolver  # noqa: E402
from copilot import prior  # noqa: E402

FOLDS = 5
KEEP_Z = 1.64
TABLE = os.path.join(ROOT, "copilot", "prior_table.json")


def read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def fold_by_id(problem):
    return zlib.crc32(str(problem["id"]).encode()) % FOLDS


def fold_by_year(problem):
    """Whole years together: a problem reused at a neighbouring level of its year stays in one fold."""
    return zlib.crc32(str(prior.year_of(problem)).encode()) % FOLDS


def wilson(right, n, z=1.96):
    if not n:
        return 0.0, 0.0
    p = right / n
    centre, half = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half) / (1 + z * z / n), (centre + half) / (1 + z * z / n)


def by_id(rows, hits):
    """{id: mean of hits over that id's rows}: the two languages of a problem are one observation."""
    groups = defaultdict(list)
    for p, hit in zip(rows, hits):
        groups[p["id"]].append(float(hit))
    return {i: sum(v) / len(v) for i, v in groups.items()}


def clustered(rows, hits):
    """(share, low, high) with a 95% interval that counts each id once."""
    means = list(by_id(rows, hits).values())
    n = len(means)
    if n < 2:
        return (means[0] if means else 0.0), 0.0, 1.0
    mean = sum(means) / n
    se = math.sqrt(sum((m - mean) ** 2 for m in means) / (n - 1) / n)
    return mean, mean - 1.96 * se, mean + 1.96 * se


def paired(rows, hits, base):
    """(difference in points, low, high, z) of hits against base on the same rows, paired by id."""
    a, b = by_id(rows, hits), by_id(rows, base)
    diffs = [a[i] - b[i] for i in a]
    n = len(diffs)
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / max(n - 1, 1))
    se = sd / math.sqrt(n)
    z = mean / se if se else 0.0
    return 100 * mean, 100 * (mean - 1.96 * se), 100 * (mean + 1.96 * se), z


def line(title, rows, hits):
    right, n = sum(hits), len(hits)
    if not n:
        return f"  {title:44} no rows"
    low, high = wilson(right, n)
    _, clow, chigh = clustered(rows, hits)
    return (f"  {title:44} {right:4}/{n:<4} {100 * right / n:5.1f}%  rows 95% {100 * low:4.1f}-{100 * high:4.1f}"
            f"  by id 95% {100 * clow:4.1f}-{100 * chigh:4.1f}")


def cv_hits(rows, features, fold=fold_by_id, with_options=True):
    """Out-of-fold right/wrong for each row of one kind (with or without options)."""
    part = "options" if with_options else "no_options"
    hits = [False] * len(rows)
    for k in range(FOLDS):
        train = [p for p in rows if fold(p) != k]
        table = prior.fit(train, **{f"{part}_features": ("letter", *features)})
        for i, p in enumerate(rows):
            if fold(p) == k:
                hits[i] = prior.choose(p, table)[0] == p["label"]
    return hits


def select(rows, candidates, with_options, fold=fold_by_id, log=None):
    """Greedy, in the given order: keep a feature if its paired gain beats its noise."""
    kept = []
    best = cv_hits(rows, kept, fold, with_options)
    for name in candidates:
        tried = cv_hits(rows, [*kept, name], fold, with_options)
        gain, low, high, z = paired(rows, tried, best)
        keep = gain > 0 and z >= KEEP_Z
        if log is not None:
            log.append(f"  {'+' if keep else ' '} {name:18} {sum(tried):4}/{len(tried)} "
                       f"gain {gain:+5.1f} points (95% {low:+.1f} to {high:+.1f}, z {z:+.2f})"
                       f"{'  kept' if keep else ''}")
        if keep:
            kept.append(name)
            best = tried
    return kept, best


def nested_hits(rows, candidates, with_options, fold=fold_by_id):
    """Out-of-fold hits where the feature selection itself only saw the other folds."""
    part = "options" if with_options else "no_options"
    hits = [False] * len(rows)
    chosen = []
    for k in range(FOLDS):
        train = [p for p in rows if fold(p) != k]
        kept, _ = select(train, candidates, with_options, fold)
        chosen.append(kept)
        table = prior.fit(train, **{f"{part}_features": ("letter", *kept)})
        for i, p in enumerate(rows):
            if fold(p) == k:
                hits[i] = prior.choose(p, table)[0] == p["label"]
    return hits, chosen


def slices(rows, hits, out):
    def part(title, keep):
        chosen = [(p, h) for p, h in zip(rows, hits) if keep(p)]
        if chosen:
            out.append(line(title, [p for p, _ in chosen], [h for _, h in chosen]))

    part("without options", lambda p: not prior.has_options(p))
    part("with options", prior.has_options)
    part("  numeric options", lambda p: prior.has_options(p) and prior.numbers(p["options"]) is not None)
    part("  text options", lambda p: prior.has_options(p) and prior.numbers(p["options"]) is None)
    for band, name in enumerate(("levels 0-1", "levels 2-3", "levels 4-5", "levels 6-7")):
        part(name, lambda p, band=band: prior.level_of(p) is not None and prior.level_of(p) // 2 == band)


def build(train_path, write=True):
    rows = read(train_path)
    without = [p for p in rows if not prior.has_options(p)]
    with_options = [p for p in rows if prior.has_options(p)]
    out = [f"{train_path}: {len(rows)} rows, {len({p['id'] for p in rows})} ids; "
           f"{len(without)} without options, {len(with_options)} with; {FOLDS} folds by id"]

    selected = {}
    for title, part_rows, candidates, flag in (
            ("without options", without, prior.NO_OPTIONS_CANDIDATES, False),
            ("with options", with_options, prior.OPTIONS_CANDIDATES, True)):
        out.append(f"\nSelection, {title} (start: the letter counts alone)")
        d_hits = [p["label"] == "D" for p in part_rows]
        out.append(line("always D", part_rows, d_hits))
        out.append(line("letter counts only", part_rows, cv_hits(part_rows, [], fold_by_id, flag)))
        log = []
        kept, hits = select(part_rows, candidates, flag, log=log)
        out.extend(log)
        out.append(line(f"selected: letter + {kept or 'nothing'}", part_rows, hits))
        nested, chosen = nested_hits(part_rows, candidates, flag)
        out.append(line("nested (selection inside the folds)", part_rows, nested))
        out.append(f"    features chosen per fold: {chosen}")
        gain, low, high, z = paired(part_rows, nested, d_hits)
        out.append(f"    nested against always D: {gain:+.1f} points (95% {low:+.1f} to {high:+.1f}, z {z:+.2f})")
        yearly = cv_hits(part_rows, kept, fold_by_year, flag)
        out.append(line("selected, folds by whole year", part_rows, yearly))
        selected[flag] = (kept, hits, nested)

    out.append("\nCross-validated on training, selected features (plain; nested in brackets above)")
    everything = without + with_options
    slices(everything, selected[False][1] + selected[True][1], out)
    out.append(line("all rows", everything, selected[False][1] + selected[True][1]))
    out.append(line("all rows, nested", everything, selected[False][2] + selected[True][2]))
    out.append(line("all rows, always D", everything, [p["label"] == "D" for p in everything]))

    table = prior.fit(rows, no_options_features=("letter", *selected[False][0]),
                      options_features=("letter", *selected[True][0]))
    table["source"] = "data/train.jsonl"
    cells = sum(len(c) for part in table["parts"].values() for c in part["cells"].values())
    out.append(f"\nTable: {cells} cells; without options {table['parts']['no_options']['features']}; "
               f"with options {table['parts']['options']['features']}")
    if write:
        with open(TABLE, "w", encoding="utf-8") as f:
            json.dump(table, f, indent=1, sort_keys=True)
            f.write("\n")
        out.append(f"Written: {os.path.relpath(TABLE, ROOT)}")
    return table, out


def measure(path, languages, train_path):
    """The final measurement of the committed table on one file. Prints; changes nothing."""
    table = prior.load(TABLE)
    rows = read(path)
    if languages:
        rows = [p for p in rows if p.get("language") in languages]
    index = presolver.build(read(train_path))
    without = [p for p in rows if not prior.has_options(p)]
    with_options = [p for p in rows if prior.has_options(p)]
    letter = table["parts"]["no_options"]["cells"]["letter"]
    fixed = max(prior.LETTERS, key=lambda c: (letter[f"none|{c}"][0], c))  # training's letter without options

    always_d = {id(p): "D" for p in rows}
    chosen = {id(p): prior.choose(p, table)[0] for p in rows}
    only_without = {id(p): chosen[id(p)] if not prior.has_options(p) else "D" for p in rows}
    only_with = {id(p): chosen[id(p)] if prior.has_options(p) else "D" for p in rows}
    copied, value_hits, letter_hits = dict(chosen), [], []
    for p in rows:
        hit = presolver.presolve(p, index, exclude_id=p["id"])
        if hit:  # as the pipeline with PRESOLVE=1 and a prior that answers every problem without options
            copied[id(p)] = hit["answer"]
            (value_hits if hit["kind"] == "value" else letter_hits).append(hit["answer"] == p["label"])

    def hits(answers, part=rows):
        return [answers[id(p)] == p["label"] for p in part]

    out = [f"{path}: {len(rows)} rows, {len({p['id'] for p in rows})} ids; {len(without)} without options, "
           f"{len(with_options)} with. Table from {table.get('source')} ({table['rows']} rows)."]
    base = hits(always_d)
    systems = (("always D", always_d), ("prior on rows without options, D elsewhere", only_without),
               ("prior on rows with options, D elsewhere", only_with), ("prior on every row", chosen),
               ("presolve first, then the prior", copied))
    for title, answers in systems:
        out.append(line(title, rows, hits(answers)))
        if answers is not always_d:
            gain, low, high, z = paired(rows, hits(answers), base)
            out.append(f"      against always D, paired by id: {gain:+.1f} points "
                       f"(95% {low:+.1f} to {high:+.1f}, z {z:+.2f}) -> "
                       f"{'beats always D' if low > 0 else 'worse than always D' if high < 0 else 'inside the noise'}")
    out.append(f"  presolve: value copies {sum(value_hits)}/{len(value_hits)} right, "
               f"letter copies (no options) {sum(letter_hits)}/{len(letter_hits)} right")
    out.append("\nBy slice")
    out.append(line(f"without options: always D", without, hits(always_d, without)))
    out.append(line(f"without options: training's letter ({fixed})", without, [p["label"] == fixed for p in without]))
    out.append(line("without options: prior", without, hits(chosen, without)))
    out.append(line("with options: always D", with_options, hits(always_d, with_options)))
    out.append(line("with options: prior", with_options, hits(chosen, with_options)))
    out.append("Prior on every row, by slice")
    slices(rows, hits(chosen), out)
    counts = {c: sum(chosen[id(p)] == c for p in rows) for c in prior.LETTERS}
    truth = {c: sum(p["label"] == c for p in rows) for c in prior.LETTERS}
    out.append("Letters chosen/true: " + "  ".join(f"{c}:{counts[c]}/{truth[c]}" for c in prior.LETTERS))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", default=os.path.join(ROOT, "data", "train.jsonl"))
    p.add_argument("--no-write", action="store_true")
    p.add_argument("--measure", default="", help="a file to measure the committed table on, once")
    p.add_argument("--languages", default="", help="with --measure, e.g. eng,cat")
    args = p.parse_args(argv)
    if args.measure:
        out = measure(args.measure, set(filter(None, args.languages.split(","))), args.train)
    else:
        _, out = build(args.train, write=not args.no_write)
    print("\n".join(out))


if __name__ == "__main__":
    main()
