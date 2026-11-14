#!/usr/bin/env python3
"""The teaching copilot as a web page: one student, one problem at a time.

    python3 teach/server.py                         # primary school, Catalan, on 127.0.0.1:8010
    python3 teach/server.py --language eng --show revisado

The page shows the problem image, takes an answer A to E, climbs the help ladder,
and draws the LED matrix on screen. No language model is called: answers are
checked against the verified labels and help comes from the catalogue.
Standard library only. Runs on the laptop now, and on the board later.
"""
import argparse
import json
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copilot.assistant import Assistant  # noqa: E402
from copilot.matrix import frame  # noqa: E402
from copilot.tutor import STATUSES, Tutor  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalog", default="data/catalog/problems.jsonl")
    p.add_argument("--types", default="content/types_primaria.json")
    p.add_argument("--images", default="data/images")
    p.add_argument("--stage", default="primaria")
    p.add_argument("--language", default="cat")
    p.add_argument("--show", default=",".join(STATUSES), help="content statuses the student may see")
    p.add_argument("--profile", default="", help="SQLite file that keeps what the student has done (empty: off)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8010)
    return p.parse_args()


def load_problems(args):
    """The problems a student can work on: right stage and language, with options as text."""
    with open(os.path.join(ROOT, args.catalog)) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [r for r in rows if r["stage"] == args.stage and r["language"] == args.language and r["options"]]


def with_frames(result):
    """Add the LED frames for the events, so the page can draw the matrix."""
    result["frames"] = [frame(e) for e in result.get("events", [])]
    return result


class App:
    def __init__(self, args):
        self.args = args
        self.problems = load_problems(args)
        with open(os.path.join(ROOT, args.types)) as f:
            types = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
        self.tutor = Tutor(self.problems, types, show=set(args.show.split(",")),
                           profile_path=args.profile or None)
        self.assistant = Assistant(self.tutor)
        self.lock = threading.Lock()
        first = min(self.problems, key=lambda p: (p["difficulty"], p["key"]))
        self.view = self.tutor.start(first["key"])

    def call(self, action, body):
        with self.lock:
            if action == "state":
                return with_frames({**self.view, "events": self.view["events"]})
            if action == "answer":
                return with_frames(self.tutor.answer(body.get("letter", "")))
            if action == "help":
                return with_frames(self.tutor.help())
            if action == "respond":
                return with_frames(self.tutor.respond(body.get("qid"), body.get("value", "")))
            if action == "solution":
                return with_frames(self.tutor.solution())
            if action == "next":
                view = self.tutor.next_problem()
                if view is None:
                    return {"error": "no queden problemes"}
                self.view = view
                return with_frames(view)
            if action == "chat":
                result = self.assistant.chat(body.get("text", ""))
                if result["kind"] == "next" and result.get("view"):
                    self.view = result["view"]
                return with_frames(result)
            if action == "modelhint":
                return with_frames({"kind": "job", "job": self.assistant.model_hint(),
                                    "events": [{"event": "thinking"}]})
            if action == "job":
                return with_frames(self.assistant.job(body.get("id", 0)))
            if action == "start" and body.get("key") in self.tutor.problems:
                self.view = self.tutor.start(body["key"])
                return with_frames(self.view)
        raise KeyError(action)


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("  " + fmt % args + "\n")

        def send(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")
            parts = [urllib.parse.unquote(x) for x in self.path.split("?")[0].strip("/").split("/")]
            if parts[0] == "api" and len(parts) >= 2:
                names = {"answer": ["letter"], "respond": ["qid", "value"], "start": ["key"],
                         "chat": ["text"], "job": ["id"]}.get(parts[1], [])
                body = dict(zip(names, parts[2:]))
                try:
                    return self.send(200, app.call(parts[1], body))
                except (KeyError, ValueError, RuntimeError) as error:
                    return self.send(200, {"error": str(error)})
            if parts[0] == "img" and len(parts) == 2 and parts[1].endswith(".png"):
                key = parts[1][:-4]
                # Only catalogue keys reach the disk, so a request can't name any other file
                if key in app.tutor.problems:
                    path = os.path.join(ROOT, app.args.images, key + ".png")
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            return self.send(200, f.read(), "image/png")
            return self.send(404, {"error": "not found"})

    return Handler


def main():
    args = parse_args()
    os.chdir(ROOT)
    app = App(args)
    print(f"{len(app.problems)} problems ({args.stage}, {args.language}), showing: {args.show}")
    print(f"Open http://{args.host}:{args.port} (Ctrl+C to stop)", flush=True)
    ThreadingHTTPServer((args.host, args.port), make_handler(app)).serve_forever()


if __name__ == "__main__":
    main()
