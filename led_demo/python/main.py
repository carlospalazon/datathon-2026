"""Standalone App Lab demo of the LED feedback contract, using an original math example."""

import threading
import time

from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App

from led_feedback import publish

ANSWER = "B"  # 2 + 3 x 4 = 14; this is a synthetic demo, not M3Kang data.
HINTS = (
    "Which operation should you do first?",
    "Multiplication comes before addition.",
    "Calculate 3 x 4, then add 2.",
)

lock = threading.Lock()
state = {"busy": False, "phase": "ready", "message": "Choose A-E.", "hint_level": 0}


def snapshot():
    with lock:
        return dict(state)


def _finish_answer(letter):
    try:
        time.sleep(0.7)
        publish("thinking")
        with lock:
            state.update(phase="thinking", message="Checking your answer...")
        time.sleep(0.7)
        correct = letter == ANSWER
        publish("correct" if correct else "incorrect")
        with lock:
            state.update(phase="correct" if correct else "incorrect",
                         message="Correct!" if correct else "Try a hint and reason it through.",
                         hint_level=0)
    except Exception:
        try:
            publish("error")
        except Exception:
            pass  # The Bridge may itself be the failed component.
        with lock:
            state.update(phase="error", message="LED display error. Check App Lab logs.")
    finally:
        with lock:
            state["busy"] = False


def answer(letter):
    if letter not in "ABCDE" or len(letter) != 1:
        return {"error": "Choose A-E."}
    with lock:
        if state["busy"]:
            return {"error": "Still checking the previous answer."}
        state.update(busy=True, phase="selected", message=f"You chose {letter}.", hint_level=0)
    try:
        publish("selected", answer=letter)
    except Exception:
        with lock:
            state.update(busy=False, phase="error", message="LED display error. Check App Lab logs.")
        return {"error": "LED display unavailable."}
    threading.Thread(target=_finish_answer, args=(letter,), daemon=True).start()
    return {"ok": True}


def hint():
    with lock:
        if state["busy"]:
            return {"error": "Wait for the answer check."}
        if state["phase"] not in ("incorrect", "hint"):
            return {"error": "Hints are available after an incorrect answer."}
        level = min(state["hint_level"] + 1, 3)
    try:
        publish("hint", hint_level=level)
    except Exception:
        return {"error": "LED display unavailable."}
    with lock:
        state.update(phase="hint", hint_level=level, message=HINTS[level - 1])
    return {"ok": True}


def reset():
    with lock:
        if state["busy"]:
            return {"error": "Wait for the answer check."}
    try:
        publish("ready")
    except Exception:
        return {"error": "LED display unavailable."}
    with lock:
        state.update(phase="ready", hint_level=0, message="Choose A-E.")
    return {"ok": True}


ui = WebUI()
ui.expose_api("GET", "/answer/{letter}", answer)
ui.expose_api("GET", "/hint", hint)
ui.expose_api("GET", "/reset", reset)
ui.expose_api("GET", "/status", snapshot)
publish("ready")
App.run()
