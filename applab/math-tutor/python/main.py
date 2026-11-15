"""Tutor Cangur as an Arduino App Lab app: the web page for the student, the LED matrix for feedback.

Linux side of the app. The web_ui brick serves assets/ on port 7000 and the API
below. The tutor runs here, with no language model: answers are checked against
verified labels, and help comes from the catalogue. Every tutor event is drawn on
the 8x13 matrix through the Bridge.

copilot/ (tutor, matrix, assistant, guardrails...), catalog.jsonl, types.json and assets/img/ are copied in by
applab/package.py; they aren't kept in Git (the catalogue holds M3Kang data).
"""
import json
import os
import threading
import urllib.parse

# The model service listens on the board's 127.0.0.1, out of the container's reach:
# board/llm_bridge.py forwards it on the Docker interface, which the container
# knows as msgpack-rpc-router. Set before copilot.slm is imported.
os.environ.setdefault("LLM_URL", "http://msgpack-rpc-router:8081")

import numpy as np  # noqa: E402
from arduino.app_bricks.web_ui import WebUI  # noqa: E402
from arduino.app_utils import App, Bridge, Frame, Leds  # noqa: E402

from copilot.assistant import Assistant  # noqa: E402
from copilot.exam import Exam  # noqa: E402
from copilot.matrix import frame, rgb  # noqa: E402
from copilot.practice import Practice  # noqa: E402
from copilot.skillmap import SkillMap, sample_class  # noqa: E402
from copilot.tutor import Tutor  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SHOW = tuple(os.environ.get("TUTOR_SHOW", "revisado,preparado,generado").split(","))

with open(os.path.join(HERE, "catalog.jsonl")) as f:
    problems = [json.loads(line) for line in f if line.strip()]
with open(os.path.join(HERE, "types.json")) as f:
    types = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

LANGUAGE = problems[0]["language"]
skills = SkillMap(problems, language=LANGUAGE)  # the skill map: fed by the tutor, the practice card and the exam
seats = {}  # pseudonym -> that student's own tutor, practice card, exam and problem on screen
lock = threading.Lock()
first = min(problems, key=lambda p: (p["difficulty"], p["key"]))


def sit(student):
    """Hand the board to a student: each has a tutor, a practice card and an exam of their own."""
    global tutor, practice, exam, assistant, view
    if student not in seats:
        own = Tutor(problems, types, show=SHOW)
        own.observer = lambda kind, problem, detail=None: skills.tutor_event(kind, problem, detail, student)
        own.planner = lambda problem: skills.advice(problem, own.seen, student)  # the map plans too
        seats[student] = {"tutor": own,
                          "practice": Practice(LANGUAGE),  # practice problems made on the spot, apart from the tutor
                          "exam": Exam(problems),  # a timed paper; the page's clock requests move the matrix countdown
                          "assistant": Assistant(own),  # free text, guardrails and the model (port 8081), in threads
                          "view": {"current": own.start(first["key"])}}
    seat = seats[student]
    tutor, practice, exam = seat["tutor"], seat["practice"], seat["exam"]
    assistant, view = seat["assistant"], seat["view"]


sit(skills.student)
assistant.warm()


def draw(events):
    """Show the last tutor event on the blue matrix and onboard RGB LED 1."""
    if not events:
        return
    try:
        event = events[-1]
        grid = np.asarray(frame(event), dtype=np.uint8)
        Bridge.call("draw", Frame(grid).to_board_bytes())
        Leds.set_led1_color(*rgb(event))
    except Exception as error:  # noqa: BLE001
        print(f"LED feedback: {error}", flush=True)


def run(action, *args):
    """Call the tutor under the lock, draw on the matrix, and never raise into the web server."""
    try:
        with lock:
            result = action(*args)
        if result is None:
            return {"error": "no queden problemes"}
        events = result.get("events", [])
        draw(events)
        assistant.warm()  # a new problem: the model reads it ahead, in a thread
        return {**result, "frames": [frame(e) for e in events]}  # the page draws the same matrix
    except (KeyError, ValueError, RuntimeError) as error:
        return {"error": str(error)}


def state():
    return run(lambda: {**view["current"], "session": skills.plan_state()})


def start(key):
    def go():
        view["current"] = tutor.start(urllib.parse.unquote(key))
        return view["current"]
    return run(go)


def next_problem():
    def go():
        nxt = tutor.next_problem()
        if nxt is not None:
            view["current"] = nxt
        return nxt
    return run(go)


def hooked(name, action):
    """An action of the practice card or the exam, with the skill map told of its result."""
    def go(*args):
        result = action(*args)
        skills.after(name, tutor, practice, exam, result)
        return result
    return go


def skill_map():
    return skills.view(seen=tutor.seen, home=tutor.current["problem"]["level"])


def change_student(n=None):
    """The next student at the board (n is None), or one who comes back."""
    if exam.status() == "running":
        raise ValueError("an exam is running")
    sit(skills.new_student() if n is None else skills.switch(n))
    return skill_map()


def session():
    """Today's session: the one under way, or a new plan from the map."""
    plan = skills.plan_state()
    if plan is None or plan["finished"] or not plan["total"]:
        plan = skills.plan_start(seen=tutor.seen, home=tutor.current["problem"]["level"])
    return {"session": plan}


def session_next():
    current = tutor.current["problem"]
    step = skills.plan_advance(seen=tutor.seen,
                               on_screen=current["key"] if practice.available(current["topic"]) else None)
    if "key" in step:
        view["current"] = step = tutor.start(step["key"])
    return {**step, "session": skills.plan_state()}


def session_stop():
    skills.plan_stop()
    return {"session": None}


def exam_review():
    """The next wrong or blank question of the paper handed in, opened in the tutor."""
    step = exam.review_next()
    if "key" in step:
        view["current"] = tutor.start(step["key"])
        return {**view["current"], "review": step}
    return {**step, "events": []}


def chat(text):
    def go():
        result = assistant.chat(urllib.parse.unquote(text))
        if result["kind"] == "next" and result.get("view"):
            view["current"] = result["view"]
        return result
    return run(go)


ui = WebUI()
ui.expose_api("GET", "/api/state", state)
ui.expose_api("GET", "/api/start/{key}", start)
ui.expose_api("GET", "/api/answer/{letter}", lambda letter: run(tutor.answer, letter))
ui.expose_api("GET", "/api/help", lambda: run(tutor.help))
ui.expose_api("GET", "/api/respond/{qid}/{value}",
              lambda qid, value: run(tutor.respond, urllib.parse.unquote(qid), urllib.parse.unquote(value)))
ui.expose_api("GET", "/api/solution", lambda: run(tutor.solution))
ui.expose_api("GET", "/api/next", next_problem)
ui.expose_api("GET", "/api/chat/{text}", chat)
ui.expose_api("GET", "/api/practiceok",
              lambda: run(lambda: {"available": practice.available(tutor.current["problem"]["topic"])}))
ui.expose_api("GET", "/api/practice",
              lambda: run(hooked("practice", lambda: practice.new(tutor.current["problem"]["topic"])
                                 or {"error": "no practice for this kind of problem"})))
ui.expose_api("GET", "/api/practiceanswer/{letter}",
              lambda letter: run(hooked("practiceanswer", lambda x: practice.answer(x)), letter))
ui.expose_api("GET", "/api/practicesolution", lambda: run(practice.solution))
ui.expose_api("GET", "/api/examinfo", lambda: run(exam.info))
ui.expose_api("GET", "/api/examstart/{level}/{paper}", lambda level, paper: run(exam.start, level, paper))
# Every exam request that finds the paper handed in (by the student or by the clock) feeds the skill map, once
ui.expose_api("GET", "/api/examstate", lambda: run(hooked("examstate", lambda: exam.state())))
ui.expose_api("GET", "/api/examanswer/{n}/{letter}",
              lambda n, letter: run(hooked("examanswer", lambda a, b: exam.answer(a, b)), n, letter))
ui.expose_api("GET", "/api/examtick", lambda: run(hooked("examtick", lambda: exam.tick())))
ui.expose_api("GET", "/api/examfinish", lambda: run(hooked("examfinish", lambda: exam.finish())))
ui.expose_api("GET", "/api/examreview", lambda: run(hooked("examreview", exam_review)))
ui.expose_api("GET", "/api/examclose", lambda: run(exam.close))
ui.expose_api("GET", "/api/skillmap", lambda: run(skill_map))
ui.expose_api("GET", "/api/session", lambda: run(session))
ui.expose_api("GET", "/api/sessionnext", lambda: run(session_next))
ui.expose_api("GET", "/api/sessionstop", lambda: run(session_stop))
ui.expose_api("GET", "/api/classmap", lambda: run(skills.classroom))
ui.expose_api("GET", "/api/classsample", lambda: run(sample_class, problems, LANGUAGE))
ui.expose_api("GET", "/api/studentnew", lambda: run(change_student))
ui.expose_api("GET", "/api/student/{n}", lambda n: run(change_student, n))
ui.expose_api("GET", "/api/modelhint",
              lambda: run(lambda: {"kind": "job", "job": assistant.model_hint(), "events": [{"event": "thinking"}]}))
ui.expose_api("GET", "/api/job/{job}", lambda job: run(assistant.job, job))

draw(view["current"]["events"])
App.run()
