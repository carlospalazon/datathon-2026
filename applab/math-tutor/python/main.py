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
from copilot.matrix import frame, rgb  # noqa: E402
from copilot.tutor import Tutor  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SHOW = tuple(os.environ.get("TUTOR_SHOW", "revisado,preparado,generado").split(","))

with open(os.path.join(HERE, "catalog.jsonl")) as f:
    problems = [json.loads(line) for line in f if line.strip()]
with open(os.path.join(HERE, "types.json")) as f:
    types = {k: v for k, v in json.load(f).items() if not k.startswith("_")}

tutor = Tutor(problems, types, show=SHOW)
assistant = Assistant(tutor)  # free text, guardrails and the model (port 8081), in threads
lock = threading.Lock()
first = min(problems, key=lambda p: (p["difficulty"], p["key"]))
view = {"current": tutor.start(first["key"])}
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
ui.expose_api("GET", "/api/modelhint",
              lambda: run(lambda: {"kind": "job", "job": assistant.model_hint(), "events": [{"event": "thinking"}]}))
ui.expose_api("GET", "/api/job/{job}", lambda job: run(assistant.job, job))

draw(view["current"]["events"])
App.run()
