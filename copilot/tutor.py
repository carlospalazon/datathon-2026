"""The teaching side of the copilot: check answers, guide the student step by step, pick the next problem.

No language model in here. Answers are checked against the verified label of a
catalogue problem, and help comes from content in the catalogue, written ahead of
time. Every piece of help says where it came from and its status ("revisado",
"preparado", "generado"), so the page can show it honestly.

Kept apart from predict.py and copilot/pipeline.py: the official run never imports it.

    tutor = Tutor(problems, types)          # records from data/catalog/problems.jsonl, method cards
    view = tutor.start("lvl-0_2015_13_cat") # the problem, without its answer
    tutor.answer("B")                       # {"correct": False, "feedback": ..., "events": [...]}
    step = tutor.help()                     # next step of the guide
    tutor.respond(step["qid"], 12)          # the student answers a guide question
    tutor.solution()                        # only when the student asks for it
    tutor.next_problem()                    # adaptive: up a level after a right answer

The guide, in order, skipping steps that have no content or aren't safe to show:
  1. similar     an easier solved problem of the same type
  2. compare     "what do the two problems have in common?" (choice, from the type card)
  3. method      how this type of problem is approached (type card)
  4. guide       reflection and choice questions about the method (type card)
  5. checkpoint  intermediate results the student computes and the tutor checks (problem)
  6. hint        hints written for this problem
The solution is never a step: the student asks for it on purpose.
"""
import hashlib
import re

STATUSES = ("revisado", "preparado", "generado")


def _rank(key):
    """A stable pseudo-random order, the same on every run."""
    return hashlib.sha256(key.encode()).hexdigest()


def _norm(value):
    return re.sub(r"\s+", " ", str(value).strip().lower().replace("−", "-"))


def _number(value):
    """A number from what the student typed ("12", "12,5", " 12 pomes"), or None."""
    match = re.search(r"-?\d+(?:[.,]\d+)?", str(value).replace("−", "-"))
    return float(match.group().replace(",", ".")) if match else None


def leaks_answer(text, problem):
    """True if text gives away the correct option, False if not, None if we can't tell.

    We can only tell when the options are known as text (OCR or checked by hand).
    """
    options = problem.get("options") or {}
    label = problem.get("label")
    if not options or label not in options:
        return None
    said = _norm(text)
    value = _norm(options[label])
    if re.search(rf"\b(answer|option|opci[oó]|resposta|respuesta)\s*(is|es|és|:)?\s*\(?{label.lower()}\b", said):
        return True
    if not value:
        return None
    if re.fullmatch(r"-?\d+([.,]\d+)?", value):
        number = re.escape(value).replace(r"\.", "[.,]").replace(",", "[.,]")
        return re.search(rf"(?<![\d.,]){number}(?![\d]|[.,]\d)", said) is not None
    if len(value) >= 3:
        return value in said
    return None


def correct_value(problem):
    """The correct option as a number, if it is one."""
    options = problem.get("options") or {}
    return _number(options.get(problem.get("label"), "")) if options else None


class Tutor:
    def __init__(self, problems, types=None, show=STATUSES, neighbours=None):
        """problems: catalogue records. types: method cards per topic.

        show: which content statuses the student may see. For a demo, ("revisado",).
        neighbours(problem) -> catalogue keys, most similar first (for example from
        the embedding index). Without it, similar problems come from topic and level.
        """
        self.problems = {p["key"]: p for p in problems}
        self.types = types or {}
        self.show = set(show)
        self.neighbours = neighbours
        self.seen = set()
        self.history = []  # (key, solved_first_try)
        self.current = None

    # --- What the student sees -------------------------------------------------

    def public(self, problem):
        hidden = {"label", "solution", "hints", "distractors", "checkpoints"}
        return {k: v for k, v in problem.items() if k not in hidden}

    def start(self, key):
        problem = self.problems[key]
        self.current = {"problem": problem, "attempts": [], "rejected": [], "solution_shown": False,
                        "queue": self._plan(problem), "done": 0, "questions": {}}
        self.seen.add(key)
        return {"problem": self.public(problem),
                "events": [{"event": "level", "value": problem["level"]}]}

    # --- Answers -----------------------------------------------------------------

    def answer(self, letter):
        letter = str(letter).strip().upper()
        if len(letter) != 1 or letter not in "ABCDE":
            raise ValueError("answer with one letter, A to E")
        s = self._session()
        problem = s["problem"]
        correct = letter == problem["label"]
        s["attempts"].append(letter)
        feedback = None
        if not correct:
            feedback = self._visible(problem.get("distractors", {}).get(letter), problem,
                                     source=f"distractor {letter}")
        if correct or s["solution_shown"]:
            self._remember(problem, correct and len(s["attempts"]) == 1)
        return {"correct": correct, "attempts": len(s["attempts"]), "feedback": feedback,
                "events": [{"event": "tick" if correct else "cross"}]}

    # --- The guide -----------------------------------------------------------------

    def _plan(self, problem):
        """Every step this problem can offer, in order. Built once, when the problem starts."""
        card = self.types.get(problem["topic"]) or {}
        card_ok = card.get("status") in self.show
        steps = []
        similar = self._similar(problem)
        if similar:
            steps.append(similar)
            if card_ok and card.get("compare"):
                steps.append(self._question("compare", "choice", card["compare"], card["status"],
                                            f"type {problem['topic']}"))
        method = self._method(problem)
        if method:
            steps.append(method)
        if card_ok:
            for i, q in enumerate(card.get("guide", []), 1):
                steps.append(self._question(f"guide {i}", q["kind"], q, card["status"], f"type {problem['topic']}"))
        final = correct_value(problem)
        for i, c in enumerate(problem.get("checkpoints") or [], 1):
            if c.get("status") not in self.show or _number(c.get("answer")) is None:
                continue
            if final is not None and _number(c["answer"]) == final:  # a checkpoint must be a step, not the answer
                continue
            if leaks_answer(c["question"], problem):
                continue
            steps.append(self._question(f"checkpoint {i}", "number", c, c["status"], f"checkpoint {i}"))
        for i, h in enumerate(problem.get("hints") or [], 1):
            steps.append({"kind": "hint", "item": h, "source": f"hint {i}"})
        return steps

    def _question(self, qid, kind, q, status, source):
        return {"kind": "question", "qid": qid, "type": kind, "text": q["question"],
                "choices": q.get("choices"), "status": status, "source": source, "_q": q}

    def help(self):
        """The next step of the guide that has something to show."""
        s = self._session()
        problem = s["problem"]
        while s["queue"]:
            step = s["queue"].pop(0)
            if step["kind"] == "hint":  # checked against leaks when it's about to be shown
                step = self._visible(step["item"], problem, source=step["source"])
                if step is None:
                    continue
            s["done"] += 1
            total = s["done"] + len(s["queue"])
            shown = {k: v for k, v in step.items() if not k.startswith("_")}
            if step["kind"] == "question":
                s["questions"][step["qid"]] = step
            shown["step"] = s["done"]
            shown["events"] = [{"event": "help_step", "value": s["done"], "of": total}]
            return shown
        return {"kind": "none", "text": None, "step": s["done"],
                "events": [{"event": "letter", "value": "?"}]}

    def respond(self, qid, value):
        """Check the student's answer to a guide question. Reflection questions have no wrong answer."""
        s = self._session()
        step = s["questions"].get(qid)
        if step is None:
            raise ValueError(f"no open question {qid!r}")
        q = step["_q"]
        if step["type"] == "reflect":
            return {"qid": qid, "correct": None, "feedback": None, "events": []}
        if step["type"] == "choice":
            correct = str(value).strip() == str(q["answer"])
            feedback = q.get("explain")
        else:  # number
            given = _number(value)
            if given is None:
                raise ValueError("write a number")
            correct = abs(given - _number(q["answer"])) < 1e-9
            feedback = None if correct else q.get("error_hint")
        return {"qid": qid, "correct": correct, "feedback": feedback,
                "events": [{"event": "tick" if correct else "cross"}]}

    def solution(self):
        s = self._session()
        problem = s["problem"]
        s["solution_shown"] = True
        self._remember(problem, False)
        item = problem.get("solution")
        if item and item.get("status") in self.show:
            text, status = item["text"], item["status"]
        else:
            text, status = None, None
        return {"kind": "solution", "label": problem["label"], "text": text, "status": status,
                "events": [{"event": "letter", "value": problem["label"]}]}

    def _visible(self, item, problem, source):
        """A content item the student may see, or None. Never shows a hint that leaks."""
        if not item or item.get("status") not in self.show or not item.get("text"):
            return None
        if leaks_answer(item["text"], problem):
            self._session()["rejected"].append(source)
            return None
        return {"kind": source.split()[0], "text": item["text"], "status": item["status"], "source": source}

    def _similar(self, problem):
        """An easier solved problem of the same type, in the student's language."""
        pool = [p for p in self.problems.values()
                if p["id"] != problem["id"] and p["language"] == problem["language"]
                and p["topic"] == problem["topic"] and p["level"] <= problem["level"]]
        if not pool:
            return None
        if self.neighbours:
            order = {k: i for i, k in enumerate(self.neighbours(problem))}
            pool.sort(key=lambda p: (order.get(p["key"], len(order)), _rank(p["key"])))
        else:
            # Prefer one level below, then the same level; then problems with readable options
            pool.sort(key=lambda p: (abs(problem["level"] - 1 - p["level"]), not p.get("options"),
                                     _rank(problem["key"] + p["key"])))
        best = pool[0]
        solution = best.get("solution") if (best.get("solution") or {}).get("status") in self.show else None
        return {"kind": "similar", "text": None, "status": "dataset", "source": "M3Kang",
                "problem": self.public(best), "label": best["label"], "solution": solution}

    def _method(self, problem):
        card = self.types.get(problem["topic"]) or {}
        if card.get("status") not in self.show or not card.get("method"):
            return None
        if leaks_answer(card["method"], problem):
            return None
        return {"kind": "method", "text": card["method"], "steps": card.get("steps", []),
                "status": card["status"], "source": f"type {problem['topic']}"}

    # --- Adaptive practice -----------------------------------------------------------

    def next_problem(self):
        """Same type; one level up after a first-try right answer, one down otherwise."""
        s = self._session()
        problem = s["problem"]
        first_try = s["attempts"][:1] == [problem["label"]] and not s["solution_shown"]
        target = problem["level"] + (1 if first_try else -1)
        pool = [p for p in self.problems.values()
                if p["key"] not in self.seen and p["language"] == problem["language"]]
        if not pool:
            return None
        pool.sort(key=lambda p: (p["topic"] != problem["topic"], abs(p["level"] - target),
                                 not p.get("options"), _rank(problem["key"] + p["key"])))
        return self.start(pool[0]["key"])

    def _remember(self, problem, solved_first_try):
        if not any(k == problem["key"] for k, _ in self.history):
            self.history.append((problem["key"], solved_first_try))

    def _session(self):
        if self.current is None:
            raise RuntimeError("start a problem first")
        return self.current
