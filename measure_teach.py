#!/usr/bin/env python3
"""Numbers for the teaching side of the copilot: coverage, simulated students, model hints, input rails.

    python3 measure_teach.py coverage [--show revisado,preparado,generado] [--markdown out.md]
    python3 measure_teach.py simulate [--steps 30]
    python3 measure_teach.py hints [--limit 20]        # needs the model server (run it on the board)
    python3 measure_teach.py guards                    # data/guardrail_phrases.jsonl through topics.check_input

Every report holds ids, counts, percentages and seconds only: never problem, option or
hint text, and never model output. Standard library only.
"""
import argparse
import json
import os
import statistics
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from copilot import guardrails, slm, topics  # noqa: E402
from copilot.assistant import restates_question  # noqa: E402
from copilot.tutor import STATUSES, Tutor, correct_value, leaks_answer  # noqa: E402

ALL_KINDS = ("similar", "compare", "method", "guide", "checkpoint", "hint")
PHRASES = "data/guardrail_phrases.jsonl"


# --- Loading ---------------------------------------------------------------------------

def load_problems(catalog, stage, language):
    """The problems a student can work on (same filter as teach/server.py)."""
    path = os.path.join(ROOT, catalog)
    if not os.path.exists(path):
        sys.exit(f"Catalogue not found: {catalog}. Build it with laptop/build_catalog.py.")
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [r for r in rows if r["stage"] == stage and r["language"] == language and r["options"]]


def load_types(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        sys.exit(f"Method cards not found: {path}.")
    with open(full, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


def diff(problem):
    """Difficulty of a problem, falling back to its level."""
    d = problem.get("difficulty")
    return d if d is not None else problem["level"]


def pct(n, total):
    return f"{100 * n / total:.1f}%" if total else "n/a"


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.fmean(values) if values else None


def fmt(x, digits=2):
    return "n/a" if x is None else f"{x:.{digits}f}"


# --- Report: plain text and GitHub Markdown from the same tables ---------------------------------

class Report:
    def __init__(self, title):
        self.title = title
        self.blocks = []  # ("table", name, headers, rows) or ("note", text)

    def table(self, name, headers, rows):
        self.blocks.append(("table", name, [str(h) for h in headers], [[str(c) for c in r] for r in rows]))

    def note(self, text):
        self.blocks.append(("note", text))

    def text(self):
        out = [self.title, "=" * len(self.title)]
        for block in self.blocks:
            if block[0] == "note":
                out.append(block[1])
                continue
            _, name, headers, rows = block
            widths = [max(len(r[i]) for r in [headers] + rows) for i in range(len(headers))]
            out += ["", name]
            for r in [headers] + rows:
                out.append("  " + "  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
        return "\n".join(out)

    def markdown(self):
        out = [f"## {self.title}"]
        for block in self.blocks:
            if block[0] == "note":
                out += ["", block[1]]
                continue
            _, name, headers, rows = block
            out += ["", f"**{name}**", "", "| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
            out += ["| " + " | ".join(r) + " |" for r in rows]
        return "\n".join(out) + "\n"

    def emit(self, markdown_path=None):
        print(self.text())
        if markdown_path:
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(self.markdown())
            print(f"\nMarkdown written to {markdown_path}")


# --- 1. coverage -----------------------------------------------------------------------------------

def step_kind(step):
    """'compare', 'guide', 'checkpoint' come as questions (qid 'guide 2'); the rest by kind."""
    if step["kind"] == "question":
        return step["qid"].split()[0]
    return step["kind"]


def coverage_stats(problems, types, show):
    tutor = Tutor(problems, types, show=show)
    plan_sizes, kinds = Counter(), Counter()
    with_solution = easier = with_similar = rejected_items = rejected_problems = 0
    for p in problems:
        tutor.start(p["key"])
        n = 0
        while True:
            step = tutor.help()
            if step["kind"] == "none":
                break
            n += 1
            kinds[step_kind(step)] += 1
            if step["kind"] == "similar":
                with_similar += 1
                if diff(step["problem"]) < diff(p):
                    easier += 1
        plan_sizes[n] += 1
        rejected = tutor.current["rejected"]  # no public accessor for the tutor's own leak-check rejections
        rejected_items += len(rejected)
        rejected_problems += bool(rejected)
        if tutor.solution()["text"]:
            with_solution += 1
    return {"problems": len(problems), "plan_sizes": plan_sizes, "kinds": kinds,
            "with_solution": with_solution, "with_similar": with_similar, "easier": easier,
            "rejected_items": rejected_items, "rejected_problems": rejected_problems,
            "topics": Counter(p["topic"] for p in problems)}


def run_coverage(problems, types, show):
    given = coverage_stats(problems, types, show)
    contrast = coverage_stats(problems, types, ("revisado",))
    cols = (f"show={','.join(show)}", "revisado only")
    report = Report("Coverage of the help ladder")
    rows = []
    for name, get in (
        ("problems", lambda s: s["problems"]),
        ("with a solution text the student may see", lambda s: f"{s['with_solution']} ({pct(s['with_solution'], s['problems'])})"),
        ("with a 'similar' problem", lambda s: f"{s['with_similar']} ({pct(s['with_similar'], s['problems'])})"),
        ("'similar' strictly easier than the problem", lambda s: f"{s['easier']} ({pct(s['easier'], s['with_similar'])} of similar)"),
        ("help items rejected by the leak check", lambda s: f"{s['rejected_items']} in {s['rejected_problems']} problems"),
    ):
        rows.append([name, get(given), get(contrast)])
    report.table("Summary", ["measure", *cols], rows)
    sizes = sorted(set(given["plan_sizes"]) | set(contrast["plan_sizes"]))
    report.table("Help steps per problem (number of problems)", ["steps", *cols],
                 [[n, given["plan_sizes"].get(n, 0), contrast["plan_sizes"].get(n, 0)] for n in sizes])
    report.table("Steps by kind (total in all problems)", ["kind", *cols],
                 [[k, given["kinds"].get(k, 0), contrast["kinds"].get(k, 0)] for k in ALL_KINDS])
    report.table("Problems by topic", ["topic", "problems"],
                 [[t, n] for t, n in sorted(given["topics"].items())])
    return report


# --- 2. simulate -----------------------------------------------------------------------------------

def wrong_letter(problem):
    return next(c for c in "ABCDE" if c != problem["label"])


def simulate_student(problems, types, show, steps, threshold):
    """threshold None: always right. 'wrong': always wrong. A number T: right on the first try if difficulty <= T."""
    tutor = Tutor(problems, types, show=show)
    first = min(problems, key=lambda p: (diff(p), p["key"]))
    tutor.start(first["key"])
    visited, topics_seq, ran_out = [], [], None
    for i in range(steps):
        p = tutor.current["problem"]
        visited.append(diff(p))
        topics_seq.append(p["topic"])
        right = threshold is None or (threshold != "wrong" and diff(p) <= threshold)
        if right:
            tutor.answer(p["label"])
        else:
            tutor.answer(wrong_letter(p))
            if threshold != "wrong":
                tutor.solution()
        if tutor.next_problem() is None:
            ran_out = i + 1
            break
    stays = [a == b for a, b in zip(topics_seq, topics_seq[1:])]
    settle = None
    if isinstance(threshold, int):
        tail = visited[-max(1, len(visited) // 3):]
        settle = mean([abs(d - threshold) for d in tail])
    return {"visited": visited, "same_topic": sum(stays) / len(stays) if stays else None,
            "settle": settle, "ran_out": ran_out}


def run_simulate(problems, types, show, steps):
    levels = sorted({diff(p) for p in problems})
    students = [("always right", None), ("always wrong", "wrong")] + [(f"threshold {t}", t) for t in levels]
    report = Report(f"Simulated students ({steps} steps, from the easiest problem, show={','.join(show)})")
    rows, sequences = [], []
    for name, t in students:
        r = simulate_student(problems, types, show, steps, t)
        rows.append([name, len(r["visited"]), pct(r["same_topic"] or 0, 1) if r["same_topic"] is not None else "n/a",
                     fmt(r["settle"]), r["ran_out"] if r["ran_out"] else "no"])
        sequences.append([name, " ".join(str(d) for d in r["visited"])])
    report.table("Per student", ["student", "steps run", "same topic as previous", "mean |difficulty - T|, last third",
                                 "pool ran out at step"], rows)
    report.table("Difficulty visited, in order", ["student", "sequence"], sequences)
    return report


# --- 3. hints --------------------------------------------------------------------------------------

def contains_correct_value(text, problem):
    """True if text holds the correct option's value (numbers, or the text of a non-numeric option)."""
    value = str((problem.get("options") or {}).get(problem.get("label"), "")).strip()
    if not value:
        return False
    numbers = guardrails.numbers_in(value)
    if numbers:
        return bool(numbers & guardrails.numbers_in(text))
    value = guardrails.strip_accents(value.lower())
    return len(value) >= 3 and value in guardrails.strip_accents(text.lower())


def judge(reply, problem):
    """(accepted, reason), exactly as copilot/assistant.py Assistant._run decides."""
    ok, reason = guardrails.check(reply["text"], problem) if not reply["error"] else (False, "model_error")
    if ok and leaks_answer(reply["text"], problem):
        ok, reason = False, "tutor_leak_check"
    if ok and restates_question(reply["text"], problem):
        ok, reason = False, "restates_question"
    return ok, reason


def run_hints(problems, limit=20, ask=None, debug_jsonl=None):
    """Ask the model for a hint per problem and judge it. Returns the raw numbers."""
    ask = ask or slm.ask_hint  # looked up now, so a test can replace it
    chosen = problems[:limit] if limit else problems
    reasons, seconds, prompt_tokens, generated_tokens = Counter(), [], [], []
    accepted = leaked = errors = 0
    error_kinds = Counter()
    debug = open(debug_jsonl, "w", encoding="utf-8") if debug_jsonl else None
    try:
        for p in chosen:
            reply = ask(p)
            ok, reason = judge(reply, p)
            if debug:  # full model text: for the team's own inspection, the file must not be committed
                debug.write(json.dumps({"key": p["key"], "ok": ok, "reason": reason, **reply}, ensure_ascii=False) + "\n")
            reasons[reason] += 1
            if reply["error"]:
                errors += 1
                error_kinds[str(reply["error"]).split(":", 1)[0]] += 1
            else:
                seconds.append(reply["seconds"])
                prompt_tokens.append(reply.get("prompt_tokens"))
                generated_tokens.append(reply.get("generated_tokens"))
            if ok:
                accepted += 1
                leaked += contains_correct_value(reply["text"], p)
    finally:
        if debug:
            debug.close()
    return {"total": len(chosen), "accepted": accepted, "leaked": leaked, "errors": errors,
            "error_kinds": error_kinds, "reasons": reasons, "seconds": seconds,
            "prompt_tokens": prompt_tokens, "generated_tokens": generated_tokens}


def hints_report(r):
    report = Report("Model hints through the guardrails")
    s, total = r["seconds"], r["total"]
    report.table("Summary", ["measure", "value"], [
        ["problems asked", total],
        ["accepted", f"{r['accepted']}/{total} ({pct(r['accepted'], total)})"],
        ["model errors", r["errors"]],
        ["accepted hints that still hold the correct value (leak rate)",
         f"{r['leaked']}/{r['accepted']} ({pct(r['leaked'], r['accepted'])})"],
        ["seconds mean / median / max", f"{fmt(mean(s))} / {fmt(statistics.median(s) if s else None)} / {fmt(max(s) if s else None)}"],
        ["prompt tokens mean", fmt(mean(r["prompt_tokens"]), 1)],
        ["generated tokens mean", fmt(mean(r["generated_tokens"]), 1)],
    ])
    report.table("Outcome by reason", ["reason", "count"],
                 [[k, n] for k, n in sorted(r["reasons"].items(), key=lambda kv: (-kv[1], kv[0]))])
    return report


# --- 4. guards -------------------------------------------------------------------------------------

NEUTRAL = {"id": "neutral", "language": "eng", "label": "C",
           "text": "A box holds 4 red and 5 blue marbles. How many marbles are in the box?",
           "options": {"A": "5", "B": "8", "C": "9", "D": "20", "E": "45"}}


def run_guards(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        sys.exit(f"Phrase file not found: {path}.")
    with open(full, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    report = Report("Input guardrails (topics.check_input)")
    results = [(i, row, topics.check_input(row["text"], NEUTRAL)) for i, row in enumerate(rows, 1)]
    intents = Counter(res["intent"] for _, _, res in results)
    report.note(f"{len(rows)} phrases, against one neutral invented problem.")
    if all("ok" in row for row in rows):
        cells = Counter((row["ok"], res["ok"]) for _, row, res in results)
        report.table("Confusion (rows: expected, columns: obtained)", ["expected \\ obtained", "accepted", "rejected"],
                     [["accepted", cells[(True, True)], cells[(True, False)]],
                      ["rejected", cells[(False, True)], cells[(False, False)]]])
        right = cells[(True, True)] + cells[(False, False)]
        report.note(f"agreement: {right}/{len(rows)} ({pct(right, len(rows))})")
        wrong = [(i, row["ok"], res["intent"]) for i, row, res in results if res["ok"] != row["ok"]]
        if wrong:
            report.table("Disagreements (line number in the file)", ["line", "expected ok", "obtained intent"],
                         [[i, e, intent] for i, e, intent in wrong])
    report.table("Obtained intents", ["intent", "count"],
                 [[k, n] for k, n in sorted(intents.items(), key=lambda kv: (-kv[1], kv[0]))])
    return report


# --- Command line ----------------------------------------------------------------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--catalog", default="data/catalog/problems.jsonl")
    common.add_argument("--types", default="content/types_primaria.json")
    common.add_argument("--stage", default="primaria")
    common.add_argument("--language", default="cat")
    common.add_argument("--show", default=",".join(STATUSES), help="comma list of content statuses the student may see")
    common.add_argument("--markdown", metavar="PATH", help="also write the tables as GitHub Markdown")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("coverage", parents=[common], help="help ladder coverage (no model)")
    s = sub.add_parser("simulate", parents=[common], help="simulated students (no model)")
    s.add_argument("--steps", type=int, default=30)
    h = sub.add_parser("hints", parents=[common], help="model hints through the guardrails (needs the model)")
    h.add_argument("--limit", type=int, default=20, help="problems to ask; 0 = all")
    # Full model texts: for the team's own inspection only. The file must NOT be committed.
    h.add_argument("--debug-jsonl", metavar="PATH", default=None)
    sub.add_parser("guards", parents=[common], help="input guardrail phrases (no model)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    show = tuple(x for x in args.show.split(",") if x)
    if args.command == "guards":
        run_guards(PHRASES).emit(args.markdown)
        return 0
    problems = load_problems(args.catalog, args.stage, args.language)
    if not problems:
        sys.exit(f"No problems for stage={args.stage}, language={args.language} in {args.catalog}.")
    if args.command == "coverage":
        run_coverage(problems, load_types(args.types), show).emit(args.markdown)
    elif args.command == "simulate":
        run_simulate(problems, load_types(args.types), show, args.steps).emit(args.markdown)
    else:
        result = run_hints(problems, args.limit, debug_jsonl=args.debug_jsonl)
        if result["total"] and result["errors"] == result["total"]:
            kinds = ", ".join(sorted(result["error_kinds"]))
            print(f"The model server did not answer any of {result['total']} requests ({kinds}). "
                  f"Is llama-server running on {slm.LLM_URL}? No report: 100% rejections would not be a result.",
                  file=sys.stderr)
            return 2
        hints_report(result).emit(args.markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
