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
from copilot.exam import Exam  # noqa: E402
from copilot.matrix import frame  # noqa: E402
from copilot.practice import Practice  # noqa: E402
from copilot.skillmap import SkillMap, sample_class  # noqa: E402
from copilot.tutor import STATUSES, Tutor  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
THINK = 20  # think-first seconds on a new problem, unless --think says otherwise


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalog", default="data/catalog/problems.jsonl")
    p.add_argument("--types", default="content/types_primaria.json")
    p.add_argument("--images", default="data/images")
    p.add_argument("--stage", default="primaria")
    p.add_argument("--language", default="cat")
    p.add_argument("--show", default=",".join(STATUSES), help="content statuses the student may see")
    p.add_argument("--profile", default="", help="SQLite file that keeps what the student has done (empty: off)")
    p.add_argument("--think", type=int, default=THINK,
                   help="think-first seconds before the hint button appears on a new problem (0: off)")
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
        self.types = types
        self.think = max(0, int(getattr(args, "think", THINK)))
        # The skill map: fed by the tutor, the practice card and the exam; kept in the profile file if there is one
        self.skills = SkillMap(self.problems, path=args.profile or None, language=args.language)
        self.seats = {}  # pseudonym -> that student's own tutor, practice card, exam and problem on screen
        self.lock = threading.Lock()
        self.sit(self.skills.student)

    def sit(self, student):
        """Hand the board to a student: each has a tutor, a practice card and an exam of their own."""
        if getattr(self, "seat", None):
            self.seat["view"] = self.view
        if student not in self.seats:
            # The profile file keeps the tutor's memory of the first student; the others live in memory
            tutor = Tutor(self.problems, self.types, show=set(self.args.show.split(",")),
                          profile_path=(self.args.profile or None) if not self.seats else None)
            tutor.observer = lambda kind, problem, detail=None: self.skills.tutor_event(kind, problem, detail, student)
            tutor.planner = lambda problem: self.skills.advice(problem, tutor.seen, student)  # the map plans too
            first = min(self.problems, key=lambda p: (p["difficulty"], p["key"]))
            self.seats[student] = {"tutor": tutor, "assistant": Assistant(tutor),
                                   "practice": Practice(self.args.language),  # "one like this, but yours"
                                   "exam": Exam(self.problems),               # exam mode: a timed paper
                                   "view": tutor.start(first["key"])}
        self.seat = self.seats[student]
        self.tutor, self.assistant = self.seat["tutor"], self.seat["assistant"]
        self.practice, self.exam, self.view = self.seat["practice"], self.seat["exam"], self.seat["view"]

    def map(self):
        return with_frames(self.skills.view(seen=self.tutor.seen, home=self.tutor.current["problem"]["level"]))

    def call(self, action, body):
        with self.lock:
            result = self.act(action, body)
            self.skills.after(action, self.tutor, self.practice, self.exam, result)
            return result

    def act(self, action, body):
        if action == "state":
            return with_frames({**self.view, "session": self.skills.plan_state()})
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
        if action == "think":  # the think-first time left; asking also moves the ring on the board
            return with_frames(self.tutor.think(self.think))
        if action == "thinkskip":  # the student made an attempt and wants the hint button now
            return with_frames(self.tutor.think(self.think, skip=True))
        if action == "practiceok":  # can the page offer a practice problem for the one on screen?
            return {"available": self.practice.available(self.tutor.current["problem"]["topic"])}
        if action == "practice":
            view = self.practice.new(self.tutor.current["problem"]["topic"])
            return with_frames(view) if view else {"error": "no practice for this kind of problem"}
        if action == "practiceanswer":
            return with_frames(self.practice.answer(body.get("letter", "")))
        if action == "practicesolution":
            return with_frames(self.practice.solution())
        if action == "examinfo":
            return self.exam.info()
        if action == "examstart":
            return with_frames(self.exam.start(body.get("level"), body.get("paper", "")))
        if action == "examstate":
            return with_frames(self.exam.state())
        if action == "examanswer":
            return with_frames(self.exam.answer(body.get("n"), body.get("letter", "")))
        if action == "examtick":
            return with_frames(self.exam.tick())
        if action == "examfinish":
            return with_frames(self.exam.finish())
        if action == "examreview":  # the next wrong or blank question of the paper, opened in the tutor
            step = self.exam.review_next()
            if "key" in step:
                self.view = self.tutor.start(step["key"])
                return with_frames({**self.view, "review": step})
            return with_frames({**step, "events": []})
        if action == "examclose":
            return with_frames(self.exam.close())
        if action == "skillmap":
            return self.map()
        if action == "session":  # today's session: the one under way, or a new plan from the map
            plan = self.skills.plan_state()
            if plan is None or plan["finished"] or not plan["total"]:
                plan = self.skills.plan_start(seen=self.tutor.seen, home=self.tutor.current["problem"]["level"])
            return {"session": plan}
        if action == "sessionnext":
            current = self.tutor.current["problem"]
            step = self.skills.plan_advance(
                seen=self.tutor.seen, on_screen=current["key"] if self.practice.available(current["topic"]) else None)
            if "key" in step:
                self.view = self.tutor.start(step["key"])
                step = self.view
            return with_frames({**step, "session": self.skills.plan_state()})
        if action == "sessionstop":
            self.skills.plan_stop()
            return {"session": None}
        if action == "classmap":
            return with_frames(self.skills.classroom())
        if action == "classsample":  # a made-up class, marked as such, to see the view
            return with_frames(sample_class(self.problems, self.args.language))
        if action in ("studentnew", "student"):  # the next student at the board, or one who comes back
            if self.exam.status() == "running":
                raise ValueError("an exam is running")
            self.sit(self.skills.new_student() if action == "studentnew" else self.skills.switch(body.get("n")))
            return self.map()
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
                names = {"answer": ["letter"], "practiceanswer": ["letter"], "respond": ["qid", "value"], "start": ["key"],
                         "chat": ["text"], "job": ["id"], "examstart": ["level", "paper"],
                         "examanswer": ["n", "letter"], "student": ["n"]}.get(parts[1], [])
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
