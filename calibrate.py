#!/usr/bin/env python3
"""Fit the model's letter position bias from log-probabilities and measure the correction.

    python3 calibrate.py results/eval-X.csv --output results/letter_bias.json

Writes {"A": mean_lp_A, ..., "E": mean_lp_E}: the mean log-probability the model
gives each letter. Correcting means choosing argmax(lp - offset).

Fit the bias on a run over TRAINING problems (python3 eval.py --input data/train.jsonl),
not on the validation run you then judge it on.
"""
import argparse
import json
import math
import sys

from analyze_errors import fmt_ci, load_run

LETTERS = "ABCDE"


def usable_rows(rows):
    """(label, [lp_A..lp_E]) for rows with options and five finite values."""
    out = []
    for r in rows:
        if r["has_options"] is not True:
            continue
        try:
            lps = [float(r[f"lp_{l}"]) for l in LETTERS]
        except (KeyError, TypeError, ValueError):
            continue
        if all(math.isfinite(x) for x in lps):
            out.append((r.get("label", ""), lps))
    return out


def argmax_letter(values):
    return LETTERS[max(range(5), key=lambda i: values[i])]


def offsets(data):
    n = len(data)
    return [sum(lps[i] for _, lps in data) / n for i in range(5)]


def evaluate(data):
    """Hits before, in-sample after, and leave-one-out after correction."""
    n = len(data)
    off = offsets(data)
    sums = [sum(lps[i] for _, lps in data) for i in range(5)]
    before = after = loo = 0
    for label, lps in data:
        before += argmax_letter(lps) == label
        after += argmax_letter([lps[i] - off[i] for i in range(5)]) == label
        if n > 1:
            o = [(sums[i] - lps[i]) / (n - 1) for i in range(5)]
            loo += argmax_letter([lps[i] - o[i] for i in range(5)]) == label
    return off, before, after, loo


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv")
    p.add_argument("--output", default="results/letter_bias.json")
    args = p.parse_args(argv)
    with open(args.csv) as f:
        header = f.readline()
    if not all(f"lp_{l}" in header.split(",") or f"lp_{l}" in header.strip().split(",") for l in LETTERS):
        sys.exit(f"{args.csv} has no lp_A..lp_E columns: rerun eval.py with a pipeline that returns "
                 "logprobs.")
    data = usable_rows(load_run(args.csv))
    if len(data) < 2:
        sys.exit(f"Only {len(data)} usable rows (need has_options true and all five lp_ values).")
    off, before, after, loo = evaluate(data)
    with open(args.output, "w") as f:
        json.dump(dict(zip(LETTERS, off)), f, indent=1)
        f.write("\n")
    n = len(data)
    print(f"Rows used: {n}")
    print("Offsets (mean log-probability per letter): " + ", ".join(f"{l}={o:.3f}" for l, o in zip(LETTERS, off)))
    for name, k in (("Before correction", before), ("After, in-sample", after), ("After, leave-one-out", loo)):
        print(f"{name:22} {k}/{n} = {100 * k / n:.1f}%  (95% CI {fmt_ci(k, n)})")
    print("\nWARNING: fit the bias on a run over training problems (eval.py --input data/train.jsonl), "
          "not on the validation run it is then judged on. In-sample accuracy is optimistic; "
          "leave-one-out is the honest estimate here.")
    print(f"Written: {args.output}")


if __name__ == "__main__":
    main()
