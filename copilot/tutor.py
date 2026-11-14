"""The teaching side of the copilot: check answers, climb a help ladder, pick the next problem.

No language model in here. Answers are checked against the verified label of a
catalogue problem, and help comes from content in the catalogue, written ahead of
time. Every piece of help says where it came from and its status ("revisado",
"preparado", "generado"), so the page can show it honestly.

Kept apart from predict.py and copilot/pipeline.py: the official run never imports it.

    tutor = Tutor(problems, types)          # records from data/catalog/problems.jsonl, types.json
    view = tutor.start("lvl-0_2015_13_eng") # the problem, without its answer
    tutor.answer("B")                       # {"correct": False, "feedback": ..., "events": [...]}
    tutor.help()                            # next rung of the ladder
    tutor.solution()                        # only when the student asks for it
    tutor.next_problem()                    # adaptive: up a level after a right answer
"""
import hashlib
import re

STATUSES = ("revisado", "preparado", "generado")
LADDER = ("similar", "method", "hint")  # the solution is never a rung: the student asks for it


def _rank(key):
    """A stable pseudo-random order, the same on every run."""
    return hashlib.sha256(key.encode()).hexdigest()


def _norm(value):
    return re.sub(r"\s+", " ", str(value).strip().lower().replace("−", "-"))


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


class Tutor:
    def __init__(self, problems, types=None, show=STATUSES, neighbours=None):
        """problems: catalogue records. types: teaching cards per topic.

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
        hidden = {"label", "solution", "hints", "distractors"}
        return {k: v for k, v in problem.items() if k not in hidden}

    def start(self, key):
        problem = self.problems[key]
        self.current = {"problem": problem, "attempts": [], "rung": 0, "hint": 0,
                        "rejected": [], "solution_shown": False}
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
            if not any(k == problem["key"] for k, _ in self.history):
                self.history.append((problem["key"], correct and len(s["attempts"]) == 1))
        return {"correct": correct, "attempts": len(s["attempts"]), "feedback": feedback,
                "events": [{"event": "tick" if correct else "cross"}]}

    # --- The help ladder -----------------------------------------------------------

    def help(self):
        """The next rung that has something to show, skipping empty or unsafe ones."""
        s = self._session()
        problem = s["problem"]
        while s["rung"] < len(LADDER):
            kind = LADDER[s["rung"]]
            item = None
            if kind == "similar":
                item = self._similar(problem)
                s["rung"] += 1
            elif kind == "method":
                item = self._method(problem)
                s["rung"] += 1
            elif kind == "hint":
                hints = problem.get("hints") or []
                while s["hint"] < len(hints) and item is None:
                    item = self._visible(hints[s["hint"]], problem, source=f"hint {s['hint'] + 1}")
                    s["hint"] += 1
                if item is None:
                    s["rung"] += 1
            if item:
                item["step"] = s["rung"] if kind != "hint" else len(LADDER)
                item["events"] = [{"event": "help_step", "value": item["step"], "of": len(LADDER) + 1}]
                return item
        return {"kind": "none", "text": None, "step": len(LADDER),
                "events": [{"event": "letter", "value": "?"}]}

    def solution(self):
        s = self._session()
        problem = s["problem"]
        s["solution_shown"] = True
        if not any(k == problem["key"] for k, _ in self.history):
            self.history.append((problem["key"], False))
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
        return {"kind": "similar", "text": None, "status": "dataset", "source": "M3Kang",
                "problem": self.public(best), "label": best["label"],
                "solution": best.get("solution") if (best.get("solution") or {}).get("status") in self.show else None}

    def _method(self, problem):
        card = self.types.get(problem["topic"]) or {}
        if card.get("status") not in self.show or not card.get("method"):
            return None
        text = card["method"]
        if leaks_answer(text, problem):
            self._session()["rejected"].append("method")
            return None
        return {"kind": "method", "text": text, "steps": card.get("steps", []),
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

    def _session(self):
        if self.current is None:
            raise RuntimeError("start a problem first")
        return self.current
