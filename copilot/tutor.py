"""The teaching side of the copilot: check answers, guide the student step by step, pick the next problem.

No language model in here. Answers are checked against the verified label of a
catalogue problem, and help comes from content in the catalogue, written ahead of
time. Every piece of help says where it came from and its status ("revisado",
"preparado", "generado"), so the page can show it honestly.

Kept apart from predict.py and copilot/pipeline.py: the official run never imports it.

    tutor = Tutor(problems, types)          # records from data/catalog/problems.jsonl, method cards
    view = tutor.start("lvl-0_2015_13_cat") # the problem, without its answer
    tutor.answer("B")                       # {"correct": False, "feedback": ..., "events": [...]}
                                            # feedback: a reviewed distractor note, else a rule diagnosis
    step = tutor.help()                     # next step of the guide
    tutor.respond(step["qid"], 12)          # the student answers a guide question
    tutor.solution()                        # only when the student asks for it
    tutor.next_problem()                    # adaptive: up a level after a right answer

What the tutor remembers about the student, and the rules that use it:
  skill[topic]         right answers in a row. MASTERED in a row: the next problem is from the
                       topic that goes worst, or from one not tried yet.
  errors[topic, code]  problems where a rule diagnosed that mistake. The second time, the next
                       help step is the method of the topic, not one more detail of the problem.
  review               problems that went wrong come back REVIEW_AFTER problems later.
A slip named on a practice problem counts in errors too (practice_slip), under a code of its own.
An exam handed in counts too (exam_checked): its questions by topic in skill, the wrong ones in review.

The guide, in order, skipping steps that have no content or aren't safe to show.
Help about the problem on screen comes first, the general method after it:
  1. hint        graded hints written for this problem (where to look, how to start, the key step)
  2. checkpoint  intermediate results the student computes and the tutor checks (problem)
  3. method      how this type of problem is approached (type card)
  4. guide       reflection and choice questions about the method (type card)
  5. similar     an easier solved problem of the same type
  6. compare     "what do the two problems have in common?" (choice, from the type card)
The solution is never a step: the student asks for it on purpose.
"""
import hashlib
import math
import re
import sqlite3
import time
from datetime import datetime, timezone

STATUSES = ("revisado", "preparado", "generado")
MASTERED = 3      # first-try right answers in a row before the tutor moves to another topic
REVIEW_AFTER = 3  # a problem that went wrong comes back after this many other problems


def _rank(key):
    """A stable pseudo-random order, the same on every run."""
    return hashlib.sha256(key.encode()).hexdigest()


def _difficulty(problem):
    """The fine scale (level * 3 + block); problems without it count as the start of their level."""
    return problem.get("difficulty", problem["level"] * 3)


def _now():
    return datetime.now(timezone.utc).isoformat()


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


def base_status(status):
    """'generado:claude-opus' -> 'generado': the part after the colon only says who made it."""
    return str(status or "").split(":", 1)[0]


def correct_value(problem):
    """The correct option as a number, if it is one."""
    options = problem.get("options") or {}
    return _number(options.get(problem.get("label"), "")) if options else None


class Tutor:
    def __init__(self, problems, types=None, show=STATUSES, neighbours=None, profile_path=None):
        """problems: catalogue records. types: method cards per topic.

        show: which content statuses the student may see. For a demo, ("revisado",).
        neighbours(problem) -> catalogue keys, most similar first (for example from
        the embedding index). Without it, similar problems come from topic and difficulty.
        profile_path: a SQLite file that keeps what the student has seen and solved across
        restarts (no name, no personal data). None: kept in memory only.
        """
        self.problems = {p["key"]: p for p in problems}
        self.types = types or {}
        self.show = set(show)
        self.neighbours = neighbours
        self.seen = set()
        self.history = []  # (key, solved_first_try)
        self.skill = {}    # topic -> {"streak", "done", "right"}
        self.errors = {}   # (topic, code) -> problems where it was diagnosed
        self.review = []   # [key, problems left before it comes back]; in memory only
        self.current = None
        self.observer = None  # observer(kind, problem, detail): told of answers, solutions and slips
        self.planner = None   # planner(problem) -> {"solid", "topics"}: the skill map's advice, if there is one
        self.clock = time.monotonic  # for the think-first time; a test can put its own
        self.profile_path = profile_path
        if profile_path:
            self._load_profile()

    # --- What the student sees -------------------------------------------------

    def public(self, problem):
        hidden = {"label", "solution", "hints", "distractors", "checkpoints", "anatomy"}
        return {k: v for k, v in problem.items() if k not in hidden}

    def start(self, key):
        problem = self.problems[key]
        self.current = {"problem": problem, "attempts": [], "rejected": [], "errors": [], "solution_shown": False,
                        "queue": self._plan(problem), "done": 0, "questions": {}, "said": set(),
                        "started": self.clock(), "think_skipped": False, "think_over": False}
        self.seen.add(key)
        self.review = [item for item in self.review if item[0] != key]  # on screen now: no need to come back
        self._save("INSERT OR IGNORE INTO history (key, seen_at) VALUES (?, ?)", (key, _now()))
        return {"problem": self.public(problem),
                "events": [{"event": "level", "value": problem["level"]}]}

    def think(self, seconds, skip=False):
        """The think-first time left for the problem on screen: for its first seconds the page shows
        a calm ring where the hint button is, and the board the same ring on the matrix.

        It is over when the seconds have gone, at the first answer, help step or solution, or when
        the student skips it after an attempt (skip=True). It only tells the page: help() is never
        locked. Events: the ring while it runs; once, when it ends untouched, the problem's level
        again so the ring leaves the matrix; nothing after an answer (its tick or cross stays).
        """
        s = self._session()
        if skip:
            s["think_skipped"] = True
        touched = bool(s["attempts"] or s["done"] or s["solution_shown"])
        seconds = max(0, int(seconds))
        left = 0 if touched or s["think_skipped"] else max(0, math.ceil(seconds - (self.clock() - s["started"])))
        events = []
        if left:
            events = [{"event": "think", "value": left, "of": seconds}]
        elif seconds and not touched and not s["think_over"]:
            events = [{"event": "level", "value": s["problem"]["level"]}]
        if not left:
            s["think_over"] = True
        return {"left": left, "of": seconds, "events": events}

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
                                     source=f"distractor {letter}") or self._diagnosis(problem, letter)
        if correct or s["solution_shown"]:
            self._remember(problem, correct and len(s["attempts"]) == 1)
        self._tell("answer", problem, {"correct": correct})
        return {"correct": correct, "attempts": len(s["attempts"]), "feedback": feedback,
                "events": [{"event": "tick" if correct else "cross"}]}

    def _tell(self, kind, problem, detail=None):
        if self.observer:
            self.observer(kind, problem, detail)

    def _diagnosis(self, problem, letter):
        """Feedback worked out by rules from the wrong option (copilot/diagnose.py), or None."""
        from . import diagnose  # here: diagnose imports this module
        card = self.types.get(problem.get("topic")) or {}
        card = card if base_status(card.get("status")) in self.show else None
        for found in diagnose.diagnose(problem, letter, show=self.show):
            text, status = diagnose.message(found["code"], problem.get("language"), card)
            if leaks_answer(text, problem):
                continue
            s, pair = self._session(), (problem.get("topic"), found["code"])
            if found["code"] not in s["errors"]:  # once per problem
                s["errors"].append(found["code"])
                self._tell("slip", problem, {"code": found["code"]})
                self.errors[pair] = self.errors.get(pair, 0) + 1
                self._save("INSERT INTO errors (topic, code, n) VALUES (?, ?, 1)"
                           " ON CONFLICT (topic, code) DO UPDATE SET n = n + 1", pair)
            repeated = self.errors[pair] >= 2
            if repeated:  # the same mistake again: the method of the topic is the next help step
                s["queue"].sort(key=lambda step: step["kind"] != "method")
            return {"kind": "diagnosis", "text": text, "status": status, "source": f"rule {found['code']}",
                    "code": found["code"], "repeated": repeated}
        return None

    # --- The guide -----------------------------------------------------------------

    def _plan(self, problem):
        """Every step this problem can offer, in order. Built once, when the problem starts."""
        card = self.types.get(problem["topic"]) or {}
        card_ok = base_status(card.get("status")) in self.show
        steps = [{"kind": "hint", "item": h, "source": f"hint {i}"}
                 for i, h in enumerate(problem.get("hints") or [], 1)]
        final = correct_value(problem)
        for i, c in enumerate(problem.get("checkpoints") or [], 1):
            if base_status(c.get("status")) not in self.show or _number(c.get("answer")) is None:
                continue
            if final is not None and _number(c["answer"]) == final:  # a checkpoint must be a step, not the answer
                continue
            if leaks_answer(c["question"], problem):
                continue
            steps.append(self._question(f"checkpoint {i}", "number", c, c["status"], f"checkpoint {i}"))
        method = self._method(problem)
        if method:
            steps.append(method)
        if card_ok:
            for i, q in enumerate(card.get("guide", []), 1):
                steps.append(self._question(f"guide {i}", q["kind"], q, card["status"], f"type {problem['topic']}"))
        similar = self._similar(problem)
        if similar:
            steps.append(similar)
            if card_ok and card.get("compare"):
                steps.append(self._question("compare", "choice", card["compare"], card["status"],
                                            f"type {problem['topic']}"))
        return steps

    def _question(self, qid, kind, q, status, source):
        return {"kind": "question", "qid": qid, "type": kind, "text": q["question"],
                "choices": q.get("choices"), "status": status, "source": source, "_q": q}

    def help(self):
        """The next step of the guide that has something to show."""
        s = self._session()
        while s["queue"]:
            shown = self._show(s["queue"].pop(0))
            if shown:
                return shown
        return {"kind": "none", "text": None, "step": s["done"],
                "events": [{"event": "letter", "value": "?"}]}

    def take(self, source):
        """Show one step of the guide out of order: the one that fits what the student typed.

        source: "hint 2", "checkpoint 1"... It leaves the queue, so the hint button never repeats it.
        Returns None if that step isn't waiting, or can't be shown.
        """
        s = self._session()
        for i, step in enumerate(s["queue"]):
            if step.get("source") == source:
                return self._show(s["queue"].pop(i))
        return None

    def waiting(self):
        """The steps still in the guide, in order, as (source, text): for whoever picks one."""
        return [(step["source"], step["item"]["text"] if step["kind"] == "hint" else step.get("text"))
                for step in self._session()["queue"] if step.get("source")]

    def _show(self, step):
        """Count a step as given and return what the page needs, or None for a hint that leaks."""
        s = self._session()
        problem = s["problem"]
        if step["kind"] == "hint":  # checked against leaks when it's about to be shown
            step = self._visible(step["item"], problem, source=step["source"])
            if step is None:
                return None
        s["done"] += 1
        total = s["done"] + len(s["queue"])
        shown = {k: v for k, v in step.items() if not k.startswith("_")}
        if step["kind"] == "question":
            s["questions"][step["qid"]] = step
        shown["step"] = s["done"]
        shown["events"] = [{"event": "help_step", "value": s["done"], "of": total}]
        return shown

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
        self._tell("solution", problem)
        item = problem.get("solution")
        if item and base_status(item.get("status")) in self.show:
            text, status = item["text"], item["status"]
        else:
            text, status = None, None
        return {"kind": "solution", "label": problem["label"], "text": text, "status": status,
                "events": [{"event": "letter", "value": problem["label"]}]}

    def _visible(self, item, problem, source):
        """A content item the student may see, or None. Never shows a hint that leaks."""
        if not item or base_status(item.get("status")) not in self.show or not item.get("text"):
            return None
        if leaks_answer(item["text"], problem):
            self._session()["rejected"].append(source)
            return None
        return {"kind": source.split()[0], "text": item["text"], "status": item["status"], "source": source}

    def _similar(self, problem):
        """An easier solved problem of the same type, in the student's language.

        Strictly easier first (the closest below), then equal difficulty, then the rest.
        """
        d = _difficulty(problem)
        pool = [p for p in self.problems.values()
                if p["id"] != problem["id"] and p["language"] == problem["language"]
                and p["topic"] == problem["topic"] and p["level"] <= problem["level"]]
        if not pool:
            return None
        order = {k: i for i, k in enumerate(self.neighbours(problem))} if self.neighbours else None

        def key(p):
            q = _difficulty(p)
            tier = (0, d - q) if q < d else (1, 0) if q == d else (2, q - d)
            if order is not None:
                return (tier[0], order.get(p["key"], len(order)), _rank(p["key"]))
            return (*tier, not p.get("options"), _rank(problem["key"] + p["key"]))
        pool.sort(key=key)
        best = pool[0]
        solution = best.get("solution") if base_status((best.get("solution") or {}).get("status")) in self.show else None
        return {"kind": "similar", "text": None, "status": "dataset", "source": "M3Kang",
                "problem": self.public(best), "label": best["label"], "solution": solution}

    def _method(self, problem):
        card = self.types.get(problem["topic"]) or {}
        if base_status(card.get("status")) not in self.show or not card.get("method"):
            return None
        if leaks_answer(card["method"], problem):
            return None
        return {"kind": "method", "text": card["method"], "steps": card.get("steps", []),
                "status": card["status"], "source": f"type {problem['topic']}"}

    # --- Adaptive practice -----------------------------------------------------------

    def next_problem(self):
        """The next problem, by rules, in this order:

        1. a problem that went wrong REVIEW_AFTER problems ago comes back;
        2. after MASTERED first-try right answers in a row, another topic: the one that goes worst,
           an untried one before one that goes well, and before both a topic where a slip came
           back (twice or more, with the tutor or on practice problems). With a skill map (self.planner) the topic is
           the first one the map says to try, and a topic the map calls solid is left after a
           first-try right answer even before the streak;
        3. else the same topic, one step up the difficulty scale after a first-try right answer,
           one down otherwise.
        """
        s = self._session()
        problem = s["problem"]
        for item in self.review:
            item[1] -= 1
        due = next((item for item in self.review if item[1] <= 0 and item[0] != problem["key"]), None)
        if due:
            self.review.remove(due)
            return {**self.start(due[0]), "review": True}
        first_try = s["attempts"][:1] == [problem["label"]] and not s["solution_shown"]
        step = 1 if "difficulty" in problem else 3  # without the fine scale, move a whole level
        target = _difficulty(problem) + (step if first_try else -step)
        pool = [p for p in self.problems.values()
                if p["key"] not in self.seen and p["language"] == problem["language"]]
        if not pool:
            return None
        topic = problem["topic"]
        skill = self.skill.get(topic)
        others = {p["topic"] for p in pool} - {topic}
        advice = self.planner(problem) if self.planner else None
        wanted = [t for t in (advice or {}).get("topics", []) if t in others]
        leave = bool(skill and skill["streak"] >= MASTERED)
        if first_try and wanted and advice.get("solid"):
            leave = True
        if leave and others:
            if skill:
                skill["streak"] = 0
                self._save_skill(topic)
            topic = min(others, key=lambda t: (not self._slipped(t), wanted.index(t) if t in wanted else len(wanted),
                                               self._mastery(t)))
            target = _difficulty(problem)
        pool.sort(key=lambda p: (p["topic"] != topic, abs(_difficulty(p) - target),
                                 not p.get("options"), _rank(problem["key"] + p["key"])))
        return self.start(pool[0]["key"])

    def practice_slip(self, topic, generator, code):
        """A slip named on a practice problem counts in the memory, like one the tutor's rules name:
        the topic's streak ends (the tutor does not leave the topic right after a slip), and the
        second time the method of the topic becomes the next help step of the problem on screen.
        Returns {"repeated", "method"}: has it come back, and is the method card now next."""
        pair = (topic, f"practice:{generator}:{code}")
        self.errors[pair] = self.errors.get(pair, 0) + 1
        self._save("INSERT INTO errors (topic, code, n) VALUES (?, ?, 1)"
                   " ON CONFLICT (topic, code) DO UPDATE SET n = n + 1", pair)
        if topic in self.skill and self.skill[topic]["streak"]:
            self.skill[topic]["streak"] = 0
            self._save_skill(topic)
        repeated, method = self.errors[pair] >= 2, False
        if repeated and self.current and self.current["problem"]["topic"] == topic:
            queue = self.current["queue"]
            queue.sort(key=lambda step: step["kind"] != "method")
            method = bool(queue) and queue[0]["kind"] == "method"
        return {"repeated": repeated, "method": method}

    def _slipped(self, topic):
        """Has a slip come back in this topic (twice or more)?"""
        return any(n >= 2 for (t, _), n in self.errors.items() if t == topic)

    def exam_checked(self, paper):
        """An exam handed in feeds the memory, once per paper: each question answered counts in its
        topic like a problem met here (right the first time, or not), a wrong one also comes back
        later unless the student goes over it before, and a blank ends the topic's streak. A problem
        already settled with the tutor is not counted again, and going over a miss afterwards does
        not count it twice."""
        if not paper or not paper.get("finished") or paper.get("remembered"):
            return
        paper["remembered"] = True
        for n, q in enumerate(paper["questions"], 1):
            problem, given = q["problem"], paper["answers"].get(n)
            if given is None:
                skill = self.skill.setdefault(problem["topic"], {"streak": 0, "done": 0, "right": 0})
                skill["streak"] = 0
                self._save_skill(problem["topic"])
            else:
                self.seen.add(problem["key"])
                self._remember(problem, given == problem["label"])

    def _mastery(self, topic):
        """Sort key: the topic with the lowest share of first-try right answers first; untried ones at 0.5."""
        skill = self.skill.get(topic)
        return (skill["right"] / skill["done"] if skill and skill["done"] else 0.5, topic)

    def _remember(self, problem, solved_first_try):
        if not any(k == problem["key"] for k, _ in self.history):
            self.history.append((problem["key"], solved_first_try))
            skill = self.skill.setdefault(problem["topic"], {"streak": 0, "done": 0, "right": 0})
            skill["done"] += 1
            skill["right"] += int(solved_first_try)
            skill["streak"] = skill["streak"] + 1 if solved_first_try else 0
            self._save_skill(problem["topic"])
            if not solved_first_try:
                self.review.append([problem["key"], REVIEW_AFTER + 1])  # next_problem counts down first
            self._save("INSERT OR IGNORE INTO history (key, seen_at) VALUES (?, ?)", (problem["key"], _now()))
            self._save("UPDATE history SET solved_first_try = ?, done_at = ? WHERE key = ?",
                       (int(solved_first_try), _now(), problem["key"]))

    # --- Profile on disk ---------------------------------------------------------------

    def _connect(self):
        db = sqlite3.connect(self.profile_path)
        db.execute("CREATE TABLE IF NOT EXISTS history (key TEXT PRIMARY KEY, solved_first_try INTEGER,"
                   " seen_at TEXT, done_at TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS skill (topic TEXT PRIMARY KEY, streak INTEGER, done INTEGER,"
                   " right INTEGER)")
        db.execute("CREATE TABLE IF NOT EXISTS errors (topic TEXT, code TEXT, n INTEGER, PRIMARY KEY (topic, code))")
        return db

    def _load_profile(self):
        with self._connect() as db:
            rows = db.execute("SELECT key, solved_first_try FROM history ORDER BY done_at, key").fetchall()
            self.skill = {t: {"streak": a, "done": b, "right": c}
                          for t, a, b, c in db.execute("SELECT topic, streak, done, right FROM skill")}
            self.errors = {(t, c): n for t, c, n in db.execute("SELECT topic, code, n FROM errors")}
        self.seen = {k for k, _ in rows}
        self.history = [(k, bool(v)) for k, v in rows if v is not None]

    def _save_skill(self, topic):
        skill = self.skill[topic]
        self._save("INSERT OR REPLACE INTO skill (topic, streak, done, right) VALUES (?, ?, ?, ?)",
                   (topic, skill["streak"], skill["done"], skill["right"]))

    def _save(self, sql, args):
        if self.profile_path:
            db = self._connect()
            try:
                with db:
                    db.execute(sql, args)
            finally:
                db.close()

    def _session(self):
        if self.current is None:
            raise RuntimeError("start a problem first")
        return self.current
