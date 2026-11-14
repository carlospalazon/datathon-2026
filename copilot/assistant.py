"""Put the pieces together: the student's free text, the guardrails, the tutor and the model.

    assistant = Assistant(tutor)
    assistant.chat("dona'm una pista")   # input guardrails -> the right tutor action
    job = assistant.model_hint()         # a model hint, in a thread: poll assistant.job(job)

Input: copilot.topics.check_input decides what the text is (hint, answer letter,
next, solution, a maths question, off topic, injection...). Only a maths question
about the current problem reaches the model.
Output: whatever the model writes goes through copilot.guardrails.check and the
tutor's own leak check. If it fails, the student gets the fixed template instead.
Every reply carries a "debug" block so the team can see what the rails decided.
"""
import itertools
import re
import threading
import unicodedata

from . import guardrails, slm, topics
from .tutor import base_status, leaks_answer

APP_HELP = {
    "cat": "Respon amb els botons A–E. Si et costa, demana una pista: t'aniré guiant pas a pas.",
    "eng": "Answer with the A–E buttons. If you're stuck, ask for a hint: I'll guide you step by step.",
}


def _words(text):
    text = "".join(c for c in unicodedata.normalize("NFD", str(text).lower()) if unicodedata.category(c) != "Mn")
    return set(re.findall(r"[a-z]{4,}", text))


def restates_question(hint, problem, limit=0.6):
    """True if the hint mostly repeats what the problem asks (its last question)."""
    text = (problem.get("question") or problem.get("text", "")).strip()
    sentences = [s for s in re.split(r"(?<=[.?!])\s+", text) if s]
    asked = ([s for s in sentences if s.endswith("?")] or sentences or [""])[-1]
    words = _words(hint)
    return bool(words) and len(words & _words(asked)) / len(words) >= limit


def answer_letter(text):
    """The letter the student chose ("opcio b", "crec que és la c"), or None."""
    return topics.choice_letter(text)


class Assistant:
    def __init__(self, tutor, ask=slm.ask_hint):
        self.tutor = tutor
        self.ask = ask  # replaceable in tests
        self.state = {"streak": 0}
        self.jobs = {}
        self.ids = itertools.count(1)
        self.lock = threading.Lock()

    def _problem(self):
        return self.tutor._session()["problem"]

    def chat(self, text):
        """Route the student's text. Returns a reply, or {"job": id} when the model is working."""
        problem = self._problem()
        letter = answer_letter(text)
        if letter:
            self.state = {"streak": 0}
            return {"kind": "answer", **self.tutor.answer(letter),
                    "debug": {"input": text, "intent": "eleccion", "locked": False}}
        verdict = topics.check_input(text, problem, self.state)
        self.state = verdict["state"]
        debug = {"input": text, "intent": verdict["intent"], "locked": verdict.get("locked", False)}
        if not verdict["ok"]:
            return {"kind": "rail", "text": verdict["reply"], "locked": verdict.get("locked", False),
                    "debug": debug, "events": [{"event": "letter", "value": "?"}]}
        intent = verdict["intent"]
        if intent == "eleccion":
            letter = topics.choice_letter(text)
            return {"kind": "answer", **self.tutor.answer(letter), "debug": debug}
        if intent in ("pista", "repetir"):
            step = self.tutor.help()
            return {"kind": "help", "step": step, "debug": debug, "events": step["events"]}
        if intent == "solucion":
            return {"kind": "solution", **self.tutor.solution(), "debug": debug}
        if intent == "siguiente":
            view = self.tutor.next_problem()
            return {"kind": "next", "view": view, "debug": debug, "events": view["events"] if view else []}
        if intent in ("progreso", "ayuda_app"):
            language = problem.get("language") if problem.get("language") in APP_HELP else "eng"
            return {"kind": "rail", "text": APP_HELP[language], "debug": debug, "events": []}
        return {"kind": "job", "job": self.model_hint(text, debug), "debug": debug,
                "events": [{"event": "thinking"}]}

    # --- The model, in the background ---------------------------------------------

    def model_hint(self, student_text="", debug=None):
        job = next(self.ids)
        problem = self._problem()
        with self.lock:
            self.jobs[job] = {"done": False, "events": [{"event": "thinking"}]}
        threading.Thread(target=self._run, args=(job, problem, student_text, dict(debug or {})),
                         daemon=True).start()
        return job

    def _run(self, job, problem, student_text, debug):
        reply = self.ask(problem, student_text)
        ok, reason = guardrails.check(reply["text"], problem) if not reply["error"] else (False, "model_error")
        if ok and leaks_answer(reply["text"], problem):
            ok, reason = False, "tutor_leak_check"
        if ok and restates_question(reply["text"], problem):
            ok, reason = False, "restates_question"
        if ok:
            text, status = reply["text"].strip(), "generado:qwen"
        else:
            text, status = self._fallback(problem)
        debug.update(model_text=reply["text"], model_error=reply["error"], rail=reason, accepted=ok,
                     seconds=reply["seconds"], prompt_tokens=reply["prompt_tokens"],
                     generated_tokens=reply.get("generated_tokens"))
        result = {"done": True, "kind": "model_hint", "text": text, "status": status, "debug": debug,
                  "events": [{"event": "help_step", "value": 1, "of": 1} if ok else {"event": "letter", "value": "?"}]}
        with self.lock:
            self.jobs[job] = result

    def _fallback(self, problem):
        """When the model fails: a curated step for this problem, never a bare template if we have one."""
        show = self.tutor.show
        for c in problem.get("checkpoints") or []:
            if base_status(c.get("status")) in show:
                return c["question"], c["status"]
        card = self.tutor.types.get(problem.get("topic")) or {}
        if card.get("method") and base_status(card.get("status")) in show:
            return card["method"], card["status"]
        return guardrails.TEMPLATES.get(problem.get("language"), guardrails.TEMPLATES["eng"]), "plantilla"

    def job(self, job):
        with self.lock:
            return self.jobs.get(int(job), {"done": True, "error": "unknown job"})
