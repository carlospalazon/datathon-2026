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

from . import guardrails, slm, topics
from .tutor import leaks_answer

APP_HELP = {
    "cat": "Respon amb els botons A–E. Si et costa, demana una pista: t'aniré guiant pas a pas.",
    "eng": "Answer with the A–E buttons. If you're stuck, ask for a hint: I'll guide you step by step.",
}


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
        verdict = topics.check_input(text, problem, self.state)
        self.state = verdict["state"]
        debug = {"input": text, "intent": verdict["intent"], "locked": verdict.get("locked", False)}
        if not verdict["ok"]:
            return {"kind": "rail", "text": verdict["reply"], "locked": verdict.get("locked", False),
                    "debug": debug, "events": [{"event": "letter", "value": "?"}]}
        intent = verdict["intent"]
        if intent == "eleccion":
            letter = re.search(r"[a-e]", topics.clean(text)).group().upper()
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
        text = reply["text"].strip() if ok else guardrails.TEMPLATES.get(problem.get("language"),
                                                                         guardrails.TEMPLATES["eng"])
        debug.update(model_text=reply["text"], model_error=reply["error"], rail=reason, accepted=ok,
                     seconds=reply["seconds"], prompt_tokens=reply["prompt_tokens"],
                     generated_tokens=reply.get("generated_tokens"))
        result = {"done": True, "kind": "model_hint", "text": text,
                  "status": "generado:qwen" if ok else "plantilla", "debug": debug,
                  "events": [{"event": "help_step", "value": 1, "of": 1} if ok else {"event": "letter", "value": "?"}]}
        with self.lock:
            self.jobs[job] = result

    def job(self, job):
        with self.lock:
            return self.jobs.get(int(job), {"done": True, "error": "unknown job"})
