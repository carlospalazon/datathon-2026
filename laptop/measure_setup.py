#!/usr/bin/env python3
"""Can a model set a problem up? It writes one arithmetic expression, Python computes it.

    python3 laptop/measure_setup.py --models b08=~/unoq-local/models/a.gguf q2b=~/unoq-local/models/b.gguf

The idea being measured: the small model is bad at arithmetic and biased towards some letters,
so let it only write the calculation ("3 * 5 - 4"), forced by a grammar to be a valid expression,
and let code compute it and pick the option with that value.

For each model, on the same problems:
  set-up right     the expression's value is the value of the correct option
  wrong option     its value is another option's: a confident wrong answer
  no option        its value matches no option (the copilot would fall back to its usual answer)
  letter, direct   the usual prompt that answers with a letter, for comparison

Two sets, text-only problems whose correct option is a number:
  synthetic        problems whose answer the code computed (laptop/synthetic_problems.py)
  m3kang           validation problems that need no figure, with their five options read

Each model runs in its own llama-server with the board's flags. Speed here is not the board's:
the report gives tokens read and written, to turn into board seconds with the board's measured rates.
Prints ids, counts and percentages only, never problem text. Standard library only.
"""
import argparse
import ast
import json
import os
import random
import re
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from analyze_errors import wilson  # noqa: E402
from copilot.pipeline import solve  # noqa: E402

DEFAULT_SERVER = os.path.expanduser("~/unoq-local/llama.cpp/b12383/llama-b12383/llama-server")
FLAGS = ["--ctx-size", "4096", "--parallel", "1", "--cache-ram", "0", "--ctx-checkpoints", "2", "--jinja",
         "--reasoning", "off", "--reasoning-budget", "0", "-ngl", "0", "--threads", "4"]

SYSTEM = {
    "eng": ("You turn a maths problem into ONE arithmetic expression that computes its answer. Write only the "
            "expression, with the numbers of the problem and + - * / ( ). Do not compute the result.\n\n"
            "Problem: Laia has 3 boxes with 5 pencils in each and gives 4 away. How many pencils are left?\n"
            "Expression: 3 * 5 - 4\n\n"
            "Problem: Marc is 12 and his sister is half his age. How old will his sister be in 5 years?\n"
            "Expression: 12 / 2 + 5\n\n"
            "Problem: A rectangle is 8 cm long and 3 cm wide. What is its perimeter in cm?\n"
            "Expression: 2 * (8 + 3)"),
    "cat": ("Converteixes un problema de matemàtiques en UNA expressió aritmètica que en calcula la resposta. Escriu "
            "només l'expressió, amb els números del problema i + - * / ( ). No calculis el resultat.\n\n"
            "Problema: La Laia té 3 capses amb 5 llapis a cada una i en regala 4. Quants llapis li queden?\n"
            "Expressió: 3 * 5 - 4\n\n"
            "Problema: En Marc té 12 anys i la seva germana la meitat. Quants anys tindrà la germana d'aquí a 5 anys?\n"
            "Expressió: 12 / 2 + 5\n\n"
            "Problema: Un rectangle fa 8 cm de llarg i 3 cm d'ample. Quin és el seu perímetre en cm?\n"
            "Expressió: 2 * (8 + 3)"),
}
LABEL = {"eng": ("Problem: ", "Options: ", "Expression:"), "cat": ("Problema: ", "Opcions: ", "Expressió:")}
# A valid arithmetic expression and nothing else. The length is capped by max_tokens.
GRAMMAR = r'''root ::= expr
expr ::= term (" " [-+*/] " " term)*
term ::= num | "(" expr ")"
num ::= [0-9] [0-9]? [0-9]? [0-9]? [0-9]? ("." [0-9] [0-9]?)?'''
NUMBER = re.compile(r"^\D{0,3}?(-?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?)\s*[^\d/]{0,12}$")
LEADING = re.compile(r"^\s*\d{1,2}\s*[.)]\s*")


def value_of(text):
    """The number an option stands for ("12", "12 cm", "3,5", "1/2"), or None if it isn't just a number."""
    match = NUMBER.match(str(text).strip())
    if not match:
        return None
    token = match.group(1).replace(",", ".").replace(" ", "")
    try:
        if "/" in token:
            a, b = token.split("/")
            return Fraction(a) / Fraction(b)
        return Fraction(token)
    except (ValueError, ZeroDivisionError):
        return None


def evaluate(expression):
    """The exact value of an arithmetic expression, or None. Only numbers, + - * / and brackets."""
    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Fraction(str(node.value))
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            return a * b if isinstance(node.op, ast.Mult) else a / b
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        raise ValueError("not arithmetic")
    try:
        return walk(ast.parse(expression.strip(), mode="eval"))
    except (ValueError, SyntaxError, ZeroDivisionError, TypeError):
        return None


# --- The problems ----------------------------------------------------------------------------

def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def usable(row):
    """Five options that are all numbers, all different."""
    options = row.get("options") or {}
    values = [value_of(options.get(c, "")) for c in "ABCDE"]
    return set(options) == set("ABCDE") and None not in values and len(set(values)) == 5


def synthetic(limit, seed):
    """Synthetic problems in English and Catalan, the same number from every generator."""
    rows = [r for r in load(os.path.join(ROOT, "data/training/master.jsonl"))
            if r.get("source") == "synthetic" and r["language"] in SYSTEM and usable(r)
            and r["meta"].get("copy", 0) == 0]
    by_generator = {}
    for r in rows:
        by_generator.setdefault(r["meta"]["generator"], []).append(r)
    rng = random.Random(seed)
    per = max(1, limit // len(by_generator))
    picked = []
    for name in sorted(by_generator):
        picked += rng.sample(by_generator[name], min(per, len(by_generator[name])))
    return [{"id": r["uid"], "language": r["language"], "text": r["text"], "options": r["options"],
             "label": r["label"], "group": r["meta"]["generator"]} for r in picked]


def m3kang():
    """Validation problems that need no figure, with five numeric options."""
    rows = [r for r in load(os.path.join(ROOT, "data/catalog/problems.jsonl"))
            if r["split"] == "val" and r["language"] in SYSTEM and not r["needs_figure"] and usable(r)]
    return [{"id": r["key"], "language": r["language"], "text": LEADING.sub("", r["text"]).strip(),
             "options": r["options"], "label": r["label"], "group": f"level {r['level']}"} for r in rows]


# --- The model ---------------------------------------------------------------------------------

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(server, model, port, log):
    process = subprocess.Popen([server, "-m", model, "--host", "127.0.0.1", "--port", str(port), *FLAGS],
                               stdout=log, stderr=subprocess.STDOUT)
    for _ in range(240):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if json.loads(response.read()).get("status") == "ok":
                    return process
        except OSError:
            pass
        if process.poll() is not None:
            raise SystemExit(f"llama-server stopped while loading {model}")
        time.sleep(0.5)
    process.terminate()
    raise SystemExit(f"llama-server never became ready for {model}")


def ask_expression(problem, url, with_options):
    problem_label, options_label, expression_label = LABEL[problem["language"]]
    parts = [problem_label + problem["text"]]
    if with_options:
        parts.append(options_label + ", ".join(problem["options"][c] for c in "ABCDE"))
    parts.append(expression_label)
    payload = {"messages": [{"role": "system", "content": SYSTEM[problem["language"]]},
                            {"role": "user", "content": "\n".join(parts)}],
               "max_tokens": 40, "temperature": 0, "seed": 42, "cache_prompt": True, "grammar": GRAMMAR}
    request = urllib.request.Request(url + "/v1/chat/completions", json.dumps(payload).encode(),
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        reply = json.loads(response.read())
    timings = reply.get("timings", {})
    return {"text": reply["choices"][0]["message"]["content"].strip(),
            "read": (timings.get("prompt_n") or 0), "cached": timings.get("cache_n") or 0,
            "written": timings.get("predicted_n") or 0}


def judge(expression, problem):
    """'right', 'wrong option', 'no option' or 'invalid'."""
    value = evaluate(expression)
    if value is None:
        return "invalid"
    values = {c: value_of(problem["options"][c]) for c in "ABCDE"}
    if value == values[problem["label"]]:
        return "right"
    return "wrong option" if value in values.values() else "no option"


def rate(k, n):
    if not n:
        return "n/a"
    low, high = wilson(k, n)
    return f"{100 * k / n:.1f}% ({k}/{n}, {100 * low:.0f}-{100 * high:.0f}%)"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="+", required=True, help="name=path/to/model.gguf")
    p.add_argument("--server", default=DEFAULT_SERVER)
    p.add_argument("--synthetic", type=int, default=300, help="about how many synthetic problems")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="results/setup", help="folder for one JSON Lines file per model (ids, no text)")
    args = p.parse_args()

    sets = {"synthetic": synthetic(args.synthetic, args.seed), "m3kang": m3kang()}
    for name, problems in sets.items():
        print(f"{name}: {len(problems)} problems, {dict(Counter(x['language'] for x in problems))}")
    out_dir = os.path.join(ROOT, args.out)
    os.makedirs(out_dir, exist_ok=True)

    summary, tokens, groups = [], [], []
    for spec in args.models:
        model, path = spec.split("=", 1)
        port = free_port()
        url = f"http://127.0.0.1:{port}"
        with open(os.path.join(out_dir, f"server-{model}.log"), "w") as log:
            process = start(args.server, os.path.expanduser(path), port, log)
            try:
                rows = []
                for set_name, problems in sets.items():
                    for problem in problems:
                        row = {"model": model, "set": set_name, "id": problem["id"], "group": problem["group"],
                               "language": problem["language"]}
                        for key, with_options in (("plain", False), ("options", True)):
                            reply = ask_expression(problem, url, with_options)
                            row[key] = judge(reply["text"], problem)
                            row[key + "_one_number"] = bool(re.fullmatch(r"[\d.]+", reply["text"]))
                            row[key + "_read"], row[key + "_written"] = reply["read"], reply["written"]
                        direct = solve(problem, llm_url=url)
                        row["direct"] = direct["answer"] == problem["label"]
                        row["direct_read"] = direct.get("prompt_tokens") or 0
                        rows.append(row)
            finally:
                process.terminate()
                process.wait()
        with open(os.path.join(out_dir, f"{model}.jsonl"), "w") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        for set_name in sets:
            mine = [r for r in rows if r["set"] == set_name]
            n = len(mine)
            for key, label in (("plain", "statement only"), ("options", "statement and options")):
                count = Counter(r[key] for r in mine)
                summary.append([model, set_name, label, n, rate(count["right"], n), rate(count["wrong option"], n),
                                rate(count["no option"] + count["invalid"], n),
                                rate(sum(r[key + "_one_number"] for r in mine), n),
                                rate(sum(r["direct"] for r in mine), n)])
            tokens.append([model, set_name, round(statistics.mean(r["plain_read"] for r in mine)),
                           round(statistics.mean(r["plain_written"] for r in mine), 1),
                           max(r["plain_written"] for r in mine),
                           round(statistics.mean(r["direct_read"] for r in mine))])
            by_group = {}
            for r in mine:
                by_group.setdefault(r["group"], []).append(r["plain"] == "right")
            for group in sorted(by_group):
                groups.append([model, set_name, group, f"{sum(by_group[group])}/{len(by_group[group])}"])

    print("\n**The expression the model writes**\n")
    print(table(["model", "set", "the model sees", "n", "set-up right", "another option's value",
                 "no option's value", "just one number", "letter, direct prompt"], summary))
    print("\n**Tokens per problem, statement only** (the fixed instructions are read once and reused)\n")
    print(table(["model", "set", "new tokens read, mean", "written, mean", "written, most",
                 "tokens read by the direct prompt"], tokens))
    print("\n**Set-up right by group, statement only**\n")
    print(table(["model", "set", "group", "right"], groups))


if __name__ == "__main__":
    main()
