#!/usr/bin/env python3
"""Benchmark models on test-like problems under the exam's time limit, simulated for the board.

    python3 laptop/bench_exam.py --input data/demo/train.jsonl \
        --model q35-08=~/unoq-local/models/Qwen_Qwen3.5-0.8B-Q8_0.gguf:11:6 \
        --model qmath15=~/unoq-local/models/Qwen2.5-Math-1.5B-Instruct-Q4_K_M.gguf:5.5:3:boxed

A model is NAME=PATH:READ:WRITE[:STYLE]. READ and WRITE are the board's speeds for that model in
tokens per second (reading the prompt, writing the answer). STYLE picks the prompt: "answer"
(default: work step by step, end with "Answer: <letter>"), "boxed" (Qwen2.5-Math's own prompt) or
"tuned" (the pipeline's prompt, for a model fine-tuned to write short working and "Answer: <letter>").

This computer is much faster than the board, so time is not measured: it is computed. For each
problem the model may write as many tokens as fit in the limit on the board:

    tokens = (LIMIT - MARGIN - prompt_tokens / READ) * WRITE

Two answers are scored for every problem:
  direct  the letter with no working (one token), what predict.py does today
  timed   working within the token budget; if it has not reached an answer when the budget ends,
          the letter is forced right after the working written so far (one more token)

Prints and writes ids, letters, counts and percentages only, never problem text.
"""
import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from analyze_errors import wilson  # noqa: E402
from copilot.client import post  # noqa: E402
from copilot.llm import SYSTEM, format_problem  # noqa: E402

DEFAULT_SERVER = os.path.expanduser("~/unoq-local/llama.cpp/b12383/llama-b12383/llama-server")
SERVER_FLAGS = ["--ctx-size", "4096", "--parallel", "1", "--cache-ram", "0", "--ctx-checkpoints", "2",
                "--jinja", "--reasoning", "off", "--reasoning-budget", "0"]
STYLES = {
    "answer": ("You solve multiple-choice math competition problems for school students. Work it out step "
               "by step, briefly and in plain text, then finish with a line 'Answer: <letter>'.", ""),
    "boxed": ("Please reason step by step, and put your final answer within \\boxed{}.",
              "\nGive the letter of the correct option as the final answer."),
    "tuned": (SYSTEM, "\nAnswer:"),
}
FOUND = re.compile(r"Answer:\s*\**\(?([A-E])\b|boxed\{\\?(?:text\{)?\(?([A-E])\)?\}")


def budget(prompt_tokens, read, write, limit, margin):
    return max(int((limit - margin - prompt_tokens / read) * write), 0)


def letter_in(text):
    hits = FOUND.findall(text)
    return (hits[-1][0] or hits[-1][1]) if hits else ""


def start(server, path, port):
    proc = subprocess.Popen([server, "-m", path, "--host", "127.0.0.1", "--port", str(port), *SERVER_FLAGS],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(300):
        if proc.poll() is not None:
            break
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == 200:
                    return proc
        except Exception:  # noqa: BLE001
            time.sleep(1)
    proc.kill()
    sys.exit(f"llama-server did not start for {path}")


def run_model(spec, problems, args, writer):
    base = f"http://127.0.0.1:{args.port}"
    system, suffix = STYLES[spec["style"]]
    proc = start(args.server, spec["path"], args.port)
    rows = []
    try:
        for n, p in enumerate(problems, 1):
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": format_problem(p) + suffix}]
            prompt = post(base + "/apply-template", {"messages": messages}, timeout=60)["prompt"]
            prompt_tokens = len(post(base + "/tokenize", {"content": prompt}, timeout=60)["tokens"])
            common = {"temperature": 0, "seed": 42, "cache_prompt": True}
            direct_messages = [{"role": "system", "content": SYSTEM},
                               {"role": "user", "content": format_problem(p) + "\nAnswer:"}]
            direct = post(base + "/v1/chat/completions",
                          {"messages": direct_messages, "grammar": "root ::= [A-E]", "max_tokens": 1, **common},
                          timeout=120)["choices"][0]["message"]["content"].strip()
            allowed = budget(prompt_tokens, spec["read"], spec["write"], args.limit, args.margin)
            text, written = "", 0
            if allowed > 1:
                r = post(base + "/completion", {"prompt": prompt, "n_predict": allowed - 1, **common}, timeout=600)
                text, written = r.get("content", ""), int(r.get("tokens_predicted", 0))
            timed, finished = letter_in(text), True
            if not timed:
                finished = False
                r = post(base + "/completion", {"prompt": prompt + text.rstrip() + "\nAnswer: ", "n_predict": 1,
                                                "grammar": "root ::= [A-E]", **common}, timeout=120)
                timed = r.get("content", "").strip()[:1]
                written += 1
            seconds = round(prompt_tokens / spec["read"] + written / spec["write"], 1)
            row = {"model": spec["name"], "id": p["id"], "language": p["language"], "level": p["level"],
                   "text_only": int(bool(p.get("text_only"))), "label": p["label"], "direct": direct,
                   "timed": timed, "finished": int(finished), "prompt_tokens": prompt_tokens,
                   "budget_tokens": allowed, "written_tokens": written, "board_seconds": seconds}
            rows.append(row)
            writer.writerow(row)
            print(f"[{spec['name']} {n}/{len(problems)}] {p['id']} {p['language']}: truth {p['label']} "
                  f"direct {direct} timed {timed or '-'} ({written}/{allowed} tokens, "
                  f"{'finished' if finished else 'forced'}, {seconds} s on the board)", flush=True)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    return rows


def pct(rows, key):
    n = len(rows)
    k = sum(r[key] == r["label"] for r in rows)
    if not n:
        return "-"
    low, high = wilson(k, n)
    return f"{100 * k / n:.0f}% ({k}/{n}, {100 * low:.0f}-{100 * high:.0f})"


def report(all_rows, specs, args):
    lines = [f"# Exam-time benchmark on {args.input}", "",
             f"Limit {args.limit:.0f} s per problem, {args.margin:.0f} s kept free. Board time is computed from the "
             "token counts and the speeds below, not measured. Brackets: correct/total and the 95% interval.", "",
             "| model | board speed read/write (tok/s) | direct letter | with working, in time | finished in time | "
             "mean tokens written | mean board s | worst board s |", "|---|---|---|---|---|---|---|---|"]
    for s in specs:
        rows = [r for r in all_rows if r["model"] == s["name"]]
        if not rows:
            continue
        lines.append(f"| {s['name']} | {s['read']:g} / {s['write']:g} | {pct(rows, 'direct')} | {pct(rows, 'timed')} | "
                     f"{sum(r['finished'] for r in rows)}/{len(rows)} | "
                     f"{sum(r['written_tokens'] for r in rows) / len(rows):.0f} | "
                     f"{sum(r['board_seconds'] for r in rows) / len(rows):.0f} | "
                     f"{max(r['board_seconds'] for r in rows):.0f} |")
    groups = [("text only", lambda r: r["text_only"] == 1), ("needs the figure", lambda r: r["text_only"] == 0),
              ("English", lambda r: r["language"] == "eng"), ("Catalan", lambda r: r["language"] == "cat"),
              ("levels 0-3", lambda r: int(r["level"]) <= 3), ("levels 4-7", lambda r: int(r["level"]) >= 4),
              ("finished in time", lambda r: r["finished"] == 1), ("letter forced", lambda r: r["finished"] == 0)]
    lines += ["", "## With working, in time, by group", "", "| model | " + " | ".join(g for g, _ in groups) + " |",
              "|---|" + "---|" * len(groups)]
    for s in specs:
        rows = [r for r in all_rows if r["model"] == s["name"]]
        if rows:
            lines.append(f"| {s['name']} | " + " | ".join(pct([r for r in rows if f(r)], "timed") for _, f in groups) + " |")
    letters = "ABCDE"
    lines += ["", "## Letters chosen with working (true counts first)", "",
              "| model | " + " | ".join(letters) + " |", "|---|" + "---|" * 5]
    first = [r for r in all_rows if r["model"] == specs[0]["name"]]
    lines.append("| true | " + " | ".join(str(sum(r["label"] == c for r in first)) for c in letters) + " |")
    for s in specs:
        rows = [r for r in all_rows if r["model"] == s["name"]]
        if rows:
            lines.append(f"| {s['name']} | " + " | ".join(str(sum(r["timed"] == c for r in rows)) for c in letters) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/demo/train.jsonl")
    p.add_argument("--model", action="append", required=True, metavar="NAME=PATH:READ:WRITE[:STYLE]")
    p.add_argument("--limit", type=float, default=60.0)
    p.add_argument("--margin", type=float, default=3.0)
    p.add_argument("--max-problems", type=int, default=0, help="0 means all")
    p.add_argument("--port", type=int, default=8281)
    p.add_argument("--server", default=DEFAULT_SERVER)
    p.add_argument("--out", default="results/exam_bench")
    args = p.parse_args(argv)

    specs = []
    for m in args.model:
        name, _, rest = m.partition("=")
        parts = rest.split(":")
        if len(parts) < 3:
            sys.exit(f"--model wants NAME=PATH:READ:WRITE[:STYLE], got {m!r}")
        style = parts[3] if len(parts) > 3 else "answer"
        if style not in STYLES:
            sys.exit(f"Unknown style {style!r}: use one of {sorted(STYLES)}")
        specs.append({"name": name, "path": os.path.expanduser(parts[0]), "read": float(parts[1]),
                      "write": float(parts[2]), "style": style})
        if not os.path.isfile(specs[-1]["path"]) or not all(math.isfinite(specs[-1][k]) and specs[-1][k] > 0
                                                            for k in ("read", "write")):
            sys.exit(f"Bad model: {m!r}")
    with open(os.path.join(ROOT, args.input), encoding="utf-8") as f:
        problems = sorted((json.loads(line) for line in f if line.strip()), key=lambda x: (x["id"], x["language"]))
    problems = [q for q in problems if q.get("options")]
    if args.max_problems:
        problems = problems[:args.max_problems]
    os.makedirs(os.path.join(ROOT, os.path.dirname(args.out)), exist_ok=True)
    fields = ["model", "id", "language", "level", "text_only", "label", "direct", "timed", "finished",
              "prompt_tokens", "budget_tokens", "written_tokens", "board_seconds"]
    all_rows = []
    with open(os.path.join(ROOT, args.out + ".csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for spec in specs:
            all_rows += run_model(spec, problems, args, writer)
            f.flush()
    text = report(all_rows, specs, args)
    with open(os.path.join(ROOT, args.out + ".md"), "w", encoding="utf-8") as f:
        f.write(text)
    print("\n" + text)


if __name__ == "__main__":
    main()
