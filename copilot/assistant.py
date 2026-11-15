"""Put the pieces together: the student's free text, the guardrails, the tutor and the model.

    assistant = Assistant(tutor)
    assistant.chat("dona'm una pista")   # input guardrails -> the right tutor action
    job = assistant.model_hint()         # a model hint, in a thread: poll assistant.job(job)

Input: copilot.topics.check_input decides what the text is (hint, answer letter, next,
solution, a question about the problem, off topic, injection...).
A question about the syllabus ("what is a prime number?") gets a written definition from
copilot.glossary. A question about the problem gets written help first: copilot.match picks the hint,
checkpoint or note that fits it. Only a question about what a word or a phrase means
reaches the model, with the teacher's notes on the problem.
Output: whatever the model writes goes through copilot.guardrails.check, the tutor's leak
check and two more (restating the question, echoing the student). If it fails, the student
gets the next step of the guide instead.
Every reply carries a "debug" block so the team can see what the rails decided.
"""
import itertools
import re
import threading
import unicodedata

from . import glossary, guardrails, match, slm, topics
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


def echoes_student(hint, student_text, limit=0.6):
    """True if the model only gave the student's own words back."""
    words = _words(hint)
    return bool(words) and bool(student_text) and len(words & _words(student_text)) / len(words) >= limit


def about_problem(text, problem):
    """True if a text the input rails found off topic is still about the problem on screen."""
    if match.kind(text) or match.attempt(text, problem) is not None:
        return True
    statement = problem.get("question") or problem.get("text", "")
    shared_numbers = set(re.findall(r"\d+", text)) & set(re.findall(r"\d+", statement))
    names = {w for w in re.findall(r"[^\W\d_]{3,}", match.clean(statement))}
    shared_words = {w for w in re.findall(r"[^\W\d_]{3,}", match.clean(text))} & names
    return bool(shared_numbers) or len(shared_words) >= 2


def syllabus(text, problem):
    """The written definition, if the text asks about the syllabus and not about the step the student is on."""
    kind = match.kind(text)
    if kind == "next" or (kind in ("look", "start", "why") and not glossary.ASKS.search(glossary.clean(text))):
        return None  # "he de dividir?", "no entenc el perímetre d'aquesta figura": about this problem
    return glossary.lookup(text, problem)


def answer_letter(text):
    """The letter the student chose ("opcio b", "crec que és la c"), or None."""
    return topics.choice_letter(text)


class Assistant:
    def __init__(self, tutor, ask=slm.ask_hint, warmer=slm.warm):
        self.tutor = tutor
        self.ask = ask  # replaceable in tests
        self.warmer = warmer
        self.warmed = None  # key of the last problem the model was asked to read ahead
        self.warm_lock = threading.Lock()
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
        if (verdict["intent"] == "offtopic" and (about_problem(text, problem) or glossary.terms(text))) or \
                (verdict["intent"] == "siguiente" and len(text.split()) > 4 and "problem" not in text.lower()):
            # "per on començo?" has no maths word in it, but it is a question about this problem; and
            # "i si perd el bus, quan passa el següent?" is not a request for the next problem
            verdict = {"ok": True, "intent": "math", "locked": False, "reply": "", "state": {"streak": 0}}
        self.state = verdict["state"]
        debug = {"input": text, "intent": verdict["intent"], "locked": verdict.get("locked", False)}
        if not verdict["ok"]:
            return {"kind": "rail", "text": verdict["reply"], "locked": verdict.get("locked", False),
                    "debug": debug, "events": [{"event": "letter", "value": "?"}]}
        intent = verdict["intent"]
        if intent == "eleccion":
            letter = topics.choice_letter(text)
            return {"kind": "answer", **self.tutor.answer(letter), "debug": debug}
        if intent in ("pista", "repetir", "math"):  # written help that fits the question comes first
            found = syllabus(text, problem)  # "què és un nombre primer?": a written definition, not the model
            if found:
                return {"kind": "reply", "text": found["text"], "status": found["status"], "tone": "help",
                        "debug": {**debug, "matched": found["source"]}, "events": []}
            reply = self._written(match.pick(text, self.tutor), debug)
            if reply:
                return reply
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
        if match.kind(text) != "word":
            # Nothing written fits, and it isn't a question about what a word means: the model states
            # false things about steps and numbers, so the student gets the next step of the guide.
            step = self.tutor.help()
            return {"kind": "help", "step": step, "debug": {**debug, "matched": "next step"}, "events": step["events"]}
        return {"kind": "job", "job": self.model_hint(text, debug), "debug": debug,
                "events": [{"event": "thinking"}]}

    def _written(self, found, debug):
        """Turn what match.pick found into a reply for the page, or None if there is nothing to show."""
        if not found:
            return None
        debug = {**debug, "matched": found.get("take") or found.get("source"), "kind_of_question": match.kind(debug["input"])}
        if "take" in found:
            step = self.tutor.take(found["take"])
            if not step:
                return None
            return {"kind": "help", "step": step, "before": found.get("before"), "debug": debug,
                    "events": step["events"]}
        session = self.tutor._session()
        if found.get("say"):
            session["said"].add(found["say"])
        if found.get("drop"):  # the student has just done this checkpoint: don't ask it again
            self.tutor.take(found["drop"])
        right = found.get("tone") == "ok"
        return {"kind": "reply", "text": found["text"], "status": found["status"], "tone": found.get("tone", "help"),
                "debug": debug, "events": [{"event": "tick"}] if right else []}

    # --- The model, in the background ---------------------------------------------

    def warm(self):
        """Let the model read the current problem while the student reads it. Once per problem.

        Call it after any action that may have changed the problem. Returns True if it started.
        """
        problem = self._problem()
        if problem["key"] == self.warmed:
            return False
        self.warmed = problem["key"]
        threading.Thread(target=self._warm, args=(problem,), daemon=True).start()
        return True

    def _warm(self, problem):
        with self.warm_lock:  # one at a time, and skip a problem the student has already left
            current = self.tutor.current
            if current and current["problem"]["key"] == problem["key"]:
                self.warmer(problem)

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
        explains = match.kind(student_text) == "word"  # the only questions that reach the model today
        ok, reason = guardrails.check(reply["text"], problem, explains=explains) if not reply["error"] \
            else (False, "model_error")
        if ok and leaks_answer(reply["text"], problem):
            ok, reason = False, "tutor_leak_check"
        if ok and restates_question(reply["text"], problem):
            ok, reason = False, "restates_question"
        if ok and echoes_student(reply["text"], student_text):
            ok, reason = False, "echoes_student"
        debug.update(model_text=reply["text"], model_error=reply["error"], rail=reason, accepted=ok,
                     seconds=reply["seconds"], prompt_tokens=reply["prompt_tokens"],
                     cached_tokens=reply.get("cached_tokens"), generated_tokens=reply.get("generated_tokens"))
        if ok:
            result = {"done": True, "kind": "model_hint", "text": reply["text"].strip(), "status": "generado:qwen",
                      "debug": debug, "events": [{"event": "help_step", "value": 1, "of": 1}]}
        else:  # the written help is chosen when the page asks, with the tutor's lock held: see job()
            result = {"done": True, "kind": "fallback", "problem": problem["key"], "debug": debug}
        with self.lock:
            self.jobs[job] = result

    def _fallback(self, problem):
        """When there is no step of the guide left: a curated line for this problem, else the template."""
        card = self.tutor.types.get(problem.get("topic")) or {}
        if card.get("method") and base_status(card.get("status")) in self.tutor.show:
            return card["method"], card["status"]
        return guardrails.TEMPLATES.get(problem.get("language"), guardrails.TEMPLATES["eng"]), "plantilla"

    def job(self, job):
        """The result of a model job. A rejected answer becomes the next step of the guide, once."""
        with self.lock:
            result = self.jobs.get(int(job), {"done": True, "error": "unknown job"})
        if result.get("kind") != "fallback":
            return result
        problem = self._problem()
        if problem["key"] != result["problem"]:  # the student has moved on: nothing to add
            final = {"done": True, "kind": "model_hint", "text": "", "status": None, "debug": result["debug"],
                     "events": []}
        else:
            step = self.tutor.help()
            if step["kind"] == "none":
                text, status = self._fallback(problem)
                final = {"done": True, "kind": "model_hint", "text": text, "status": status,
                         "debug": result["debug"], "events": [{"event": "letter", "value": "?"}]}
            else:
                final = {"done": True, "kind": "help", "step": step, "debug": result["debug"],
                         "events": step["events"]}
        with self.lock:
            self.jobs[int(job)] = final
        return final

