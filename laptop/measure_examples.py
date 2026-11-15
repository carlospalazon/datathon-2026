#!/usr/bin/env python3
"""Does a similar solved problem, shown with its worked solution, help the model solve a new one?

    EMBED_PORT=8392 python3 laptop/measure_examples.py --name tuned --port 8391 [--limit 0]

Needs two servers already running: an embedding server (bge-small, EMBED_PORT) and the language
model under test (--port). For every validation problem that has options it finds the most similar
TRAINING problem that has a checked worked solution (same language, never the same id), shows it as
one solved example in the trained format, and asks for the working and the letter. The working may
use the tokens that fit the board's 60 seconds after reading the longer prompt.

The same problems are also asked with no example, so the two are compared on equal terms.
Development measurement: it does not go through predict.py. Writes ids, letters and counts only.
"""
import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from analyze_errors import wilson  # noqa: E402
from copilot.client import post  # noqa: E402
from copilot.embed import embed  # noqa: E402
from copilot.find_letter import find_letter  # noqa: E402
from copilot.llm import REASON_GRAMMAR, SYSTEM, format_problem  # noqa: E402
from laptop.build_training_data import option_line  # noqa: E402

LIMIT_S, MARGIN_S, READ_TPS, WRITE_TPS = 60.0, 3.0, 11.0, 6.0


def read_jsonl(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def solved_training_problems():
    """Training problems with five options and a checked worked solution, in their original order."""
    rationale = {}
    for path in ("data/training/m3kang_rationales.jsonl", "data/training/m3kang_rationales_images.jsonl"):
        for r in read_jsonl(path):
            rationale[(r["id"], r["language"])] = r["rationale"]
    recovered = {(r["id"], r["language"]): r["options"] for r in read_jsonl("data/training/m3kang_options.jsonl")}
    held_out = {r["id"] for r in read_jsonl("data/val.jsonl")} | {r["id"] for r in read_jsonl("data/demo/train.jsonl")}
    out = []
    for p in read_jsonl("data/train.jsonl"):
        key = (p["id"], p["language"])
        options = p.get("options") or recovered.get(key)
        if p["id"] in held_out or key not in rationale or not options or len(options) != 5:
            continue
        out.append({**p, "options": options, "rationale": rationale[key]})
    return out


def embed_all(problems, batch=16):
    vectors = []
    for i in range(0, len(problems), batch):
        vectors += embed([format_problem(p) for p in problems[i:i + batch]])
    return vectors


def ask(base, messages, problem):
    """(letter, finished, prompt tokens, tokens written, board seconds)."""
    prompt = post(base + "/apply-template", {"messages": messages}, timeout=60)["prompt"]
    prompt_tokens = len(post(base + "/tokenize", {"content": prompt}, timeout=60)["tokens"])
    allowed = max(int((LIMIT_S - MARGIN_S - prompt_tokens / READ_TPS) * WRITE_TPS), 0)
    common = {"temperature": 0, "seed": 42, "cache_prompt": True}
    text, written = "", 0
    if allowed > 1:
        r = post(base + "/completion", {"prompt": prompt, "n_predict": allowed - 1, "grammar": REASON_GRAMMAR,
                                        **common}, timeout=600)
        text, written = r.get("content", ""), int(r.get("tokens_predicted", 0))
    tail = text.rsplit("\nAnswer: ", 1)
    letter = tail[1].strip()[:1] if len(tail) == 2 else ""
    finished = letter in tuple("ABCDE")
    if not finished:
        r = post(base + "/completion", {"prompt": prompt + text.rstrip() + "\nAnswer: ", "n_predict": 1,
                                        "grammar": "root ::= [A-E]", **common}, timeout=120)
        letter, written = r.get("content", "").strip()[:1], written + 1
    return letter, int(finished), prompt_tokens, written, round(prompt_tokens / READ_TPS + written / WRITE_TPS, 1)


def pct(rows, key):
    n, k = len(rows), sum(r[key] == r["label"] for r in rows)
    if not n:
        return "-"
    low, high = wilson(k, n)
    return f"{100 * k / n:.0f}% ({k}/{n}, {100 * low:.0f}-{100 * high:.0f})"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", required=True)
    p.add_argument("--port", type=int, required=True, help="port of the language model server")
    p.add_argument("--input", default="data/val.jsonl")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args(argv)
    base = f"http://127.0.0.1:{args.port}"

    solved = solved_training_problems()
    vectors = embed_all(solved)
    problems = sorted((q for q in read_jsonl(args.input) if q.get("options") and q["language"] in ("eng", "cat")),
                      key=lambda x: (x["id"], x["language"]))
    if args.limit:
        problems = problems[:args.limit]
    print(f"{len(solved)} solved training problems, {len(problems)} problems to ask", flush=True)

    out_path = os.path.join(ROOT, "results", f"examples-{args.name}.csv")
    fields = ["id", "language", "level", "text_only", "label", "similarity", "example_id", "example_same_value",
              "plain", "plain_finished", "plain_seconds", "with_example", "example_finished", "example_seconds",
              "example_prompt_tokens"]
    rows = []
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for n, q in enumerate(problems, 1):
            query = embed([format_problem(q)], query=True)[0]
            best, score = None, -1.0
            for s, v in zip(solved, vectors):
                if s["language"] != q["language"] or s["id"] == q["id"]:
                    continue
                c = sum(a * b for a, b in zip(query, v))
                if c > score:
                    best, score = s, c
            user = {"role": "user", "content": format_problem(q) + "\nAnswer:"}
            plain = ask(base, [{"role": "system", "content": SYSTEM}, user], q)
            shown = [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": format_problem(best) + "\nAnswer:"},
                     {"role": "assistant",
                      "content": f"{best['rationale']}\n{option_line(best)}\nAnswer: {best['label']}"}, user]
            with_ex = ask(base, shown, q)
            same_value = int(str(best["options"][best["label"]]).strip() == str(q["options"][q["label"]]).strip())
            row = {"id": q["id"], "language": q["language"], "level": q["level"], "text_only": int(bool(q["text_only"])),
                   "label": q["label"], "similarity": round(score, 3), "example_id": best["id"],
                   "example_same_value": same_value, "plain": plain[0], "plain_finished": plain[1],
                   "plain_seconds": plain[4], "with_example": with_ex[0], "example_finished": with_ex[1],
                   "example_seconds": with_ex[4], "example_prompt_tokens": with_ex[2]}
            rows.append(row)
            writer.writerow(row)
            f.flush()
            if n % 20 == 0:
                print(f"[{n}/{len(problems)}] plain {pct(rows, 'plain')} | with example {pct(rows, 'with_example')}",
                      flush=True)

    bands = [("all", lambda r: True), ("similarity >= 0.90", lambda r: r["similarity"] >= 0.90),
             ("0.80 to 0.90", lambda r: 0.80 <= r["similarity"] < 0.90), ("0.70 to 0.80", lambda r: 0.70 <= r["similarity"] < 0.80),
             ("below 0.70", lambda r: r["similarity"] < 0.70), ("text only", lambda r: r["text_only"] == 1),
             ("needs the figure", lambda r: r["text_only"] == 0), ("English", lambda r: r["language"] == "eng"),
             ("Catalan", lambda r: r["language"] == "cat"),
             ("example has the same answer value", lambda r: r["example_same_value"] == 1)]
    lines = [f"# One solved similar problem as an example: {args.name} on {args.input}", "",
             "Brackets: correct/total and the 95% interval. Same problems in both columns.", "",
             "| group | no example | with the example |", "|---|---|---|"]
    for label, keep in bands:
        sub = [r for r in rows if keep(r)]
        lines.append(f"| {label} | {pct(sub, 'plain')} | {pct(sub, 'with_example')} |")
    both = sum(r["plain"] == r["label"] and r["with_example"] == r["label"] for r in rows)
    only_plain = sum(r["plain"] == r["label"] and r["with_example"] != r["label"] for r in rows)
    only_ex = sum(r["plain"] != r["label"] and r["with_example"] == r["label"] for r in rows)
    lines += ["", f"Right in both {both}; only without the example {only_plain}; only with it {only_ex}.",
              f"Finished in time: no example {sum(r['plain_finished'] for r in rows)}/{len(rows)}, "
              f"with example {sum(r['example_finished'] for r in rows)}/{len(rows)}. "
              f"Mean board seconds: {sum(r['plain_seconds'] for r in rows) / len(rows):.0f} and "
              f"{sum(r['example_seconds'] for r in rows) / len(rows):.0f}; worst with example "
              f"{max(r['example_seconds'] for r in rows):.0f}."]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(ROOT, "results", f"examples-{args.name}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print("\n" + text)


if __name__ == "__main__":
    main()
