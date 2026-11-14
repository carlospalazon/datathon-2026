"""Tutor Cangur as an Arduino App Lab app: the web page for the student, the LED matrix for feedback.

Linux side of the app. The web_ui brick serves assets/ on port 7000 and the API
below. The tutor runs here, with no language model: answers are checked against
verified labels, and help comes from the catalogue. Every tutor event is drawn on
the 8x13 matrix through the Bridge.

tutor.py, matrix.py, catalog.jsonl, types.json and assets/img/ are copied in by
applab/package.py; they aren't kept in Git (the catalogue holds M3Kang data).
"""
import json
import os
import threading
import urllib.parse

import numpy as np
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App, Bridge, Frame

from matrix import frame
from tutor import Tutor

HERE = os.path.dirname(os.path.abspath(__file__))
SHOW = tuple(os.environ.get("TUTOR_SHOW", "revisado,preparado,generado").split(","))

with open(os.path.join(HERE, "catalog.jsonl")) as f:
    problems = [json.loads(line) for line in f if line.strip()]
with open(os.path.join(HERE, "types.json")) as f:
    types = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

tutor = Tutor(problems, types, show=SHOW)
lock = threading.Lock()
first = min(problems, key=lambda p: (p["difficulty"], p["key"]))
view = {"current": tutor.start(first["key"])}


def draw(events):
    """Show the last event on the matrix. A Bridge failure must never break the lesson."""
    if not events:
        return
    try:
        grid = np.asarray(frame(events[-1]), dtype=np.uint8)
        Bridge.call("draw", Frame(grid).to_board_bytes())
    except Exception as error:  # noqa: BLE001
        print(f"LED matrix: {error}", flush=True)


def run(action, *args):
    """Call the tutor under the lock, draw on the matrix, and never raise into the web server."""
    try:
        with lock:
            result = action(*args)
        if result is None:
            return {"error": "no queden problemes"}
        events = result.get("events", [])
        draw(events)
        return {**result, "frames": [frame(e) for e in events]}  # the page draws the same matrix
    except (KeyError, ValueError, RuntimeError) as error:
        return {"error": str(error)}


def state():
    return run(lambda: view["current"])


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


ui = WebUI()
ui.expose_api("GET", "/api/state", state)
ui.expose_api("GET", "/api/start/{key}", start)
ui.expose_api("GET", "/api/answer/{letter}", lambda letter: run(tutor.answer, letter))
ui.expose_api("GET", "/api/help", lambda: run(tutor.help))
ui.expose_api("GET", "/api/respond/{qid}/{value}",
              lambda qid, value: run(tutor.respond, urllib.parse.unquote(qid), urllib.parse.unquote(value)))
ui.expose_api("GET", "/api/solution", lambda: run(tutor.solution))
ui.expose_api("GET", "/api/next", next_problem)

draw(view["current"]["events"])
App.run()
