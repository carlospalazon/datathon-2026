#!/usr/bin/env python3
"""Compare base language models on this computer, with the board's answer-affecting server flags.

    python3 laptop/compare_models.py --models b08=~/unoq-local/models/a.gguf b2=~/unoq-local/models/b.gguf \
        --languages eng --limit 0

For each model in turn: start llama-server on 127.0.0.1:<port>, run eval.py against it, stop the server.
Then print one summary table and a paired comparison of every model against the first.
Prints ids, letters, counts and percentages only, never problem text. Speed here is not the board's speed.
"""
import argparse
import csv
import json
import os
import re
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from analyze_errors import wilson  # noqa: E402

DEFAULT_SERVER = os.path.expanduser("~/unoq-local/llama.cpp/b12383/llama-b12383/llama-server")
SERVER_FLAGS = ["--ctx-size", "4096", "--parallel", "1", "--cache-ram", "0", "--ctx-checkpoints", "2",
                "--jinja", "--reasoning", "off", "--reasoning-budget", "0"]


def port_free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_healthy(port, proc, timeout=300):
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == 200 and json.load(r).get("status") == "ok":
                    return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    return False


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def run_model(name, path, args, bias_file, log_dir):
    """Start the server, run eval.py, stop the server. Return the eval CSV path or None."""
    log_path = os.path.join(log_dir, f"server-{name}.log")
    cmd = [args.server, "-m", path, "--host", "127.0.0.1", "--port", str(args.port), *SERVER_FLAGS,
           "--alias", name]
    csv_path = None
    with open(log_path, "w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        try:
            print(f"\n=== {name}: starting llama-server (log: {log_path})", flush=True)
            if not wait_healthy(args.port, proc):
                print(f"{name}: the server never became healthy; see {log_path}", file=sys.stderr)
                return None
            env = {**os.environ, "LLM_PORT": str(args.port), "LETTER_BIAS_FILE": bias_file}
            ev = subprocess.Popen([sys.executable, "eval.py", "--input", "data/val.jsonl",
                                   "--languages", args.languages, "--limit", str(args.limit),
                                   "--name", f"{args.prefix}-{name}"],
                                  cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True)
            for line in ev.stdout:
                print(line, end="", flush=True)
                m = re.match(r"Details: (\S+)", line)
                if m:
                    csv_path = os.path.join(ROOT, m.group(1))
            if ev.wait() != 0:
                print(f"{name}: eval.py exited with {ev.returncode}", file=sys.stderr)
                return None
        finally:
            stop(proc)
    return csv_path


def summarize(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    n = len(rows)
    k = sum(int(r["correct"]) for r in rows)
    low, high = wilson(k, n)
    mean_s = statistics.mean(float(r["seconds"]) for r in rows) if rows else 0.0
    bad = sum(r["status"] != "ok" for r in rows)
    return n, k, low, high, mean_s, bad


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="+", required=True, metavar="NAME=PATH.gguf")
    p.add_argument("--limit", type=int, default=0, help="0 means every problem")
    p.add_argument("--languages", default="eng")
    p.add_argument("--port", type=int, default=8181)
    p.add_argument("--server", default=DEFAULT_SERVER, help="path to llama-server")
    p.add_argument("--prefix", default="base", help="experiment names are <prefix>-<model name>")
    p.add_argument("--report", default="base_models.md", help="file name of the summary in results/")
    args = p.parse_args(argv)

    models = []
    for spec in args.models:
        name, sep, path = spec.partition("=")
        path = os.path.expanduser(path)
        if not sep or not name or not path:
            sys.exit(f"--models wants NAME=PATH, got {spec!r}")
        if not os.path.isfile(path):
            sys.exit(f"Model file not found: {path}")
        models.append((name, path))
    if len({n for n, _ in models}) != len(models):
        sys.exit("Model names must be different")
    if not (os.path.isfile(args.server) and os.access(args.server, os.X_OK)):
        sys.exit(f"llama-server not found or not executable: {args.server}")
    if not port_free(args.port):
        sys.exit(f"Port {args.port} is already in use; stop that server or pass --port")

    results = []
    with tempfile.TemporaryDirectory(prefix="compare_models_") as tmp:
        bias_file = os.path.join(tmp, "zero_bias.json")
        with open(bias_file, "w") as f:
            json.dump({c: 0 for c in "ABCDE"}, f)
        for name, path in models:
            csv_path = run_model(name, path, args, bias_file, tmp)
            if csv_path and os.path.isfile(csv_path):
                results.append((name, csv_path))
            else:
                print(f"{name}: no result", file=sys.stderr)
            time.sleep(1)

    if not results:
        sys.exit("No model produced a result")

    lines = ["| model | n | accuracy | 95% interval | mean s/problem | not ok |", "|---|---|---|---|---|---|"]
    for name, path in results:
        n, k, low, high, mean_s, bad = summarize(path)
        lines.append(f"| {name} | {n} | {100 * k / n:.1f}% ({k}/{n}) | {100 * low:.1f}-{100 * high:.1f}% "
                     f"| {mean_s:.2f} | {bad} |")
    table = "\n".join(lines)
    print("\n" + table)
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", args.report), "w") as f:
        f.write(f"# Models on {args.languages or 'all'} validation problems "
                f"(seconds are from this computer, not the board)\n\n{table}\n")
    print(f"\nWritten: results/{args.report}")

    first_name, first_path = results[0]
    for name, path in results[1:]:
        print(f"\n--- {first_name} vs {name}")
        out = subprocess.run([sys.executable, "analyze_errors.py", first_path, "--compare", path],
                             cwd=ROOT, capture_output=True, text=True).stdout
        i = out.find("Paired comparison")
        print(out[i:].rstrip() if i >= 0 else "(no paired comparison produced)")


if __name__ == "__main__":
    main()
