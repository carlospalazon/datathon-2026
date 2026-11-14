#!/usr/bin/env python3
"""Error analysis of eval runs: accuracy by language, level, topic, ... with 95% intervals.

    python3 analyze_errors.py results/eval-A.csv
    python3 analyze_errors.py results/eval-A.csv --compare results/eval-B.csv
    python3 analyze_errors.py results/eval-A.csv --markdown out.md

Prints ids, counts and percentages only, never problem or option text.
Topics come from the eval CSV when it has them, else from the catalogue
(joined on id and language).
"""
import argparse
import csv
import json
import math
import os
import statistics
from collections import Counter, defaultdict

LIMIT_S = 60.0
LETTERS = "ABCDE"


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes in n trials, as fractions (low, high)."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def load_catalog(path):
    """{(id, language): {"topic", "needs_figure"}}; {} if the file is missing."""
    out = {}
    if not path or not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            out[(r.get("id"), r.get("language"))] = {
                "topic": r.get("topic") or "", "needs_figure": r.get("needs_figure")}
    return out


def to_bool(value):
    """True/False for "True"/"1"/"False"/"0" and real bools; None when unknown or empty."""
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ("true", "1"):
        return True
    if s in ("false", "0"):
        return False
    return None


def load_run(path, catalog=None):
    """Read an eval CSV into dicts with parsed fields, joining the catalogue when topic columns are absent."""
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            r["correct"] = to_bool(r.get("correct")) is True
            r["has_options"] = to_bool(r.get("has_options"))
            r["needs_figure"] = to_bool(r.get("needs_figure", ""))
            r["topic"] = (r.get("topic") or "").strip()
            cat = (catalog or {}).get((r.get("id"), r.get("language")))
            if cat:
                if not r["topic"]:
                    r["topic"] = cat["topic"]
                if r["needs_figure"] is None:
                    r["needs_figure"] = to_bool(cat["needs_figure"])
            try:
                r["seconds"] = float(r.get("seconds") or 0)
            except ValueError:
                r["seconds"] = 0.0
            rows.append(r)
    return rows


def answerable(r):
    if r["has_options"] is None or r["needs_figure"] is None:
        return None
    return bool(r["has_options"] and not r["needs_figure"])


def fmt_ci(k, n):
    lo, hi = wilson(k, n)
    return f"{100 * lo:.1f}-{100 * hi:.1f}"


def group_table(title, rows, keyfn):
    groups = defaultdict(list)
    for r in rows:
        key = keyfn(r)
        if key is None or key == "":
            continue
        groups[str(key)].append(r["correct"])
    if not groups:
        return None
    body = []
    for key in sorted(groups):
        hits = groups[key]
        k, n = sum(hits), len(hits)
        body.append([key, f"{k}/{n}", f"{100 * k / n:.1f}%", fmt_ci(k, n)])
    return (title, ["group", "correct/total", "accuracy", "95% CI"], body)


def accuracy_tables(rows):
    k, n = sum(r["correct"] for r in rows), len(rows)
    tables = [("Overall", ["correct/total", "accuracy", "95% CI"],
               [[f"{k}/{n}", f"{100 * k / max(n, 1):.1f}%", fmt_ci(k, n)]])]
    specs = [("By language", lambda r: r.get("language")),
             ("By level", lambda r: r.get("level")),
             ("By topic", lambda r: r["topic"]),
             ("By has_options", lambda r: r["has_options"]),
             ("By needs_figure", lambda r: r["needs_figure"]),
             ("Answerable from text (has options and no figure needed)", answerable)]
    for title, fn in specs:
        t = group_table(title, rows, fn)
        if t:
            tables.append(t)
    return tables


def letter_tables(rows):
    conf = Counter((r.get("label", ""), r.get("answer", "")) for r in rows)
    body = [[t] + [str(conf[(t, p)]) for p in LETTERS] + [str(sum(conf[(t, p)] for p in LETTERS))]
            for t in LETTERS]
    matrix = ("Letter confusion (rows: true, columns: predicted)",
              ["true \\ pred"] + list(LETTERS) + ["total"], body)
    pred = Counter(r.get("answer", "") for r in rows)
    truth = Counter(r.get("label", "") for r in rows)
    n = max(len(rows), 1)
    share = ("Share of answers per letter", ["letter", "predicted", "predicted %", "true", "true %"],
             [[l, str(pred[l]), f"{100 * pred[l] / n:.1f}%", str(truth[l]), f"{100 * truth[l] / n:.1f}%"]
              for l in LETTERS])
    return [matrix, share]


def percentile(values, q):
    s = sorted(values)
    if not s:
        return 0.0
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def latency_tables(rows):
    sec = [r["seconds"] for r in rows]
    if not sec:
        return []
    lat = ("Latency (seconds)", ["count", "mean", "median", "p90", "max", f"over {LIMIT_S:.0f} s"],
           [[str(len(sec)), f"{statistics.mean(sec):.1f}", f"{statistics.median(sec):.1f}",
             f"{percentile(sec, 0.9):.1f}", f"{max(sec):.1f}", str(sum(s > LIMIT_S for s in sec))]])
    status = Counter((r.get("status") or "").split(":")[0] or "(empty)" for r in rows)
    st = ("Status", ["status", "count"], [[k, str(v)] for k, v in sorted(status.items())])
    return [lat, st]


def compare_tables(rows_a, rows_b, name_a, name_b):
    a = {(r["id"], r["language"]): r["correct"] for r in rows_a}
    b = {(r["id"], r["language"]): r["correct"] for r in rows_b}
    shared = sorted(set(a) & set(b))
    both = sum(a[k] and b[k] for k in shared)
    only_a = sum(a[k] and not b[k] for k in shared)
    only_b = sum(b[k] and not a[k] for k in shared)
    neither = sum(not a[k] and not b[k] for k in shared)
    n = len(shared)
    p = mcnemar_exact(only_a, only_b)
    table = (f"Paired comparison on {n} shared problems (A = {name_a}, B = {name_b})",
             ["both right", "only A right", "only B right", "both wrong", "McNemar exact p"],
             [[str(both), str(only_a), str(only_b), str(neither), f"{p:.4f}"]])
    acc_a, acc_b = (100 * (both + only_a) / max(n, 1)), (100 * (both + only_b) / max(n, 1))
    if n == 0:
        verdict = "No shared problems (same id and language): nothing to compare."
    elif only_a + only_b == 0:
        verdict = "The two runs agree on every shared problem."
    elif p < 0.05:
        verdict = (f"Significant at 5%: A {acc_a:.1f}% vs B {acc_b:.1f}% "
                   f"({only_a} vs {only_b} discordant problems, p = {p:.4f}).")
    else:
        verdict = (f"NOT significant: A {acc_a:.1f}% vs B {acc_b:.1f}% on {n} problems, "
                   f"p = {p:.4f}. The difference could be noise.")
    return [table], verdict


def render_text(tables):
    out = []
    for title, header, body in tables:
        out.append(f"\n{title}")
        widths = [max(len(str(x)) for x in col) for col in zip(header, *body)]
        out.append("  " + "  ".join(h.ljust(w) for h, w in zip(header, widths)))
        for row in body:
            out.append("  " + "  ".join(str(c).ljust(w) for c, w in zip(row, widths)))
    return "\n".join(out)


def render_markdown(tables):
    out = []
    for title, header, body in tables:
        out.append(f"### {title}\n")
        out.append("| " + " | ".join(header) + " |")
        out.append("|" + "|".join("---" for _ in header) + "|")
        for row in body:
            out.append("| " + " | ".join(str(c) for c in row) + " |")
        out.append("")
    return "\n".join(out)


def analyze(path, catalog_path="data/catalog/problems.jsonl", compare=None):
    """Return (tables, notes) for one run, optionally compared with another."""
    catalog = load_catalog(catalog_path)
    rows = load_run(path, catalog)
    notes = []
    if not rows:
        return [], [f"{path}: no rows"]
    if not any(r["topic"] for r in rows):
        notes.append("No topic information: the CSV has no topic column and the catalogue "
                     f"({catalog_path}) is missing or does not match.")
    tables = accuracy_tables(rows) + letter_tables(rows) + latency_tables(rows)
    if len(rows) < 200:
        notes.append(f"n = {len(rows)} < 200: differences smaller than the interval width are noise.")
    if compare:
        other = load_run(compare, catalog)
        extra, verdict = compare_tables(rows, other, os.path.basename(path), os.path.basename(compare))
        tables += extra
        notes.append(verdict)
    return tables, notes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv")
    p.add_argument("--compare", default="", help="a second eval CSV, compared on shared (id, language)")
    p.add_argument("--catalog", default="data/catalog/problems.jsonl")
    p.add_argument("--markdown", default="", help="also write the tables as GitHub Markdown to this file")
    args = p.parse_args(argv)
    tables, notes = analyze(args.csv, args.catalog, args.compare or None)
    print(f"Run: {os.path.basename(args.csv)}")
    print(render_text(tables))
    for note in notes:
        print(f"\nNote: {note}")
    if args.markdown:
        with open(args.markdown, "w") as f:
            f.write(f"## Error analysis: {os.path.basename(args.csv)}\n\n")
            f.write(render_markdown(tables))
            f.write("\n" + "\n".join(f"- {n}" for n in notes) + "\n")
        print(f"\nMarkdown: {args.markdown}")


if __name__ == "__main__":
    main()
