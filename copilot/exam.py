"""Exam mode: a timed Cangur paper from the catalogue, scored like the competition.

A paper takes the same number of problems from each of the three blocks of a level
(the easy third, the middle third, the hard third of the real papers). While it runs
the student gets no feedback: an answer can be changed or left blank until the paper
is handed in or the time runs out. The result says what each wrong answer cost and
which questions to go over with the tutor. It never contains a right letter: the
student finds it with the tutor.

It keeps its own state, apart from the tutor's session, and uses no model.
Standard library only.
"""
import math
import random
import time
from fractions import Fraction

# The scoring, in one place. The points per block, the quarter lost per wrong answer and
# the free blank are the rules the owner gave. NEEDS CHECKING against the real rules of
# the Cangur for primary school: "start_per_question" (points every student starts with,
# so that a score cannot go below zero) and the minutes of the full paper.
SETTINGS = {
    "points": (3, 4, 5),            # what a question of block 0, 1, 2 is worth
    "wrong_fraction": (1, 4),       # share of the question's points lost by a wrong answer
    "blank": 0,                     # a question left blank
    "start_per_question": 1,        # NEEDS CHECKING
    "papers": {                     # name -> questions per block, minutes
        "tast": {"per_block": 1, "minutes": 3},
        "curt": {"per_block": 3, "minutes": 15},
        "complet": {"per_block": 8, "minutes": 60},   # minutes NEED CHECKING
    },
}
SHOWN = ("key", "id", "grade", "options")  # all of a problem that a paper sends to the page
CLEAR = "-"                                # the "letter" that leaves a question blank


def _num(value):
    """A score as JSON: whole numbers as int, quarters as an exact float."""
    value = Fraction(value)
    return int(value) if value.denominator == 1 else float(value)


class Exam:
    def __init__(self, problems, settings=None, clock=time.monotonic, seed=None):
        self.settings = settings or SETTINGS
        self.clock = clock
        self.rng = random.Random(seed)
        blocks = range(len(self.settings["points"]))
        self.pool = {}  # level -> block -> problems
        for p in problems:
            if p.get("block") in blocks and p.get("options") and p.get("label"):
                self.pool.setdefault(p["level"], {b: [] for b in blocks})[p["block"]].append(p)
        self.used = set()   # keys already put in a paper: a second paper takes new ones first
        self.paper = None   # the paper being sat, or the last one handed in

    # --- What can be sat -------------------------------------------------------------

    def info(self):
        """The papers on offer and the scoring rules, for the page to show before starting."""
        s = self.settings
        levels = []
        for level in sorted(self.pool):
            least = min(len(v) for v in self.pool[level].values())
            names = [name for name, paper in s["papers"].items() if paper["per_block"] <= least]
            grade = next((p.get("grade") for v in self.pool[level].values() for p in v), None)
            if names:
                levels.append({"level": level, "grade": grade, "papers": names})
        blocks = len(s["points"])
        papers = {name: {"questions": paper["per_block"] * blocks, "minutes": paper["minutes"]}
                  for name, paper in s["papers"].items()}
        return {"levels": levels, "papers": papers, "status": self.status(),
                "rules": {"points": list(s["points"]), "wrong_fraction": list(s["wrong_fraction"]),
                          "blank": s["blank"], "start_per_question": s["start_per_question"]}}

    def status(self):
        if self.paper is None:
            return "none"
        self._check_time()
        return "finished" if self.paper["finished"] else "running"

    # --- Sitting a paper -------------------------------------------------------------

    def start(self, level, paper="curt"):
        try:
            level = int(level)
        except (TypeError, ValueError):
            raise ValueError("unknown level") from None
        if level not in self.pool:
            raise ValueError("unknown level")
        if paper not in self.settings["papers"]:
            raise ValueError("unknown paper")
        shape = self.settings["papers"][paper]
        questions = []
        for block, points in enumerate(self.settings["points"]):
            have = self.pool[level][block]
            if len(have) < shape["per_block"]:
                raise ValueError("not enough problems for this paper")
            fresh = [p for p in have if p["key"] not in self.used]
            if len(fresh) < shape["per_block"]:  # all seen: start the rotation again
                self.used -= {p["key"] for p in have}
                fresh = have
            chosen = self.rng.sample(fresh, shape["per_block"])
            chosen.sort(key=lambda p: (p.get("question_number", 0), p["key"]))
            questions += [{"problem": p, "points": points, "block": block} for p in chosen]
        self.used |= {q["problem"]["key"] for q in questions}
        seconds = shape["minutes"] * 60
        self.paper = {"level": level, "name": paper, "questions": questions, "answers": {},
                      "seconds": seconds, "deadline": self.clock() + seconds,
                      "finished": False, "timed_out": False}
        return self.state()

    def _running(self):
        if self.paper is None:
            raise RuntimeError("no exam yet")
        self._check_time()
        return self.paper

    def _left(self):
        return max(0, math.ceil(self.paper["deadline"] - self.clock()))

    def _check_time(self):
        """The server owns the clock: once the time is over the paper is handed in as it is."""
        if not self.paper["finished"] and self.clock() >= self.paper["deadline"]:
            self.paper["finished"] = self.paper["timed_out"] = True

    def _clock_event(self):
        return {"event": "clock", "value": self._left(), "of": self.paper["seconds"]}

    def state(self):
        """The paper as the page may see it. While it runs: no right letter, no right or wrong."""
        if self.paper is None:
            return {"status": "none", "events": []}
        paper = self._running()
        if paper["finished"]:
            return self.results()
        return {"status": "running", "level": paper["level"], "paper": paper["name"],
                "questions": [{"n": i + 1, "points": q["points"],
                               **{k: q["problem"].get(k) for k in SHOWN}}
                              for i, q in enumerate(paper["questions"])],
                "answers": {str(n): letter for n, letter in sorted(paper["answers"].items())},
                "left": self._left(), "seconds": paper["seconds"], "events": [self._clock_event()]}

    def answer(self, n, letter):
        """Mark a letter for question n, or CLEAR to leave it blank again. Says nothing about it."""
        paper = self._running()
        if paper["finished"]:  # too late: the time ran out before this answer
            return self.results()
        try:
            n = int(n)
        except (TypeError, ValueError):
            raise ValueError("unknown question") from None
        if not 1 <= n <= len(paper["questions"]):
            raise ValueError("unknown question")
        letter = str(letter).strip().upper()
        if letter == CLEAR:
            paper["answers"].pop(n, None)
        elif len(letter) == 1 and letter in "ABCDE":
            paper["answers"][n] = letter
        else:
            raise ValueError("answer with one letter, A to E")
        return {"status": "running", "n": n, "letter": paper["answers"].get(n),
                "answered": len(paper["answers"]), "left": self._left(), "events": [self._clock_event()]}

    def tick(self):
        """The time left, and the countdown for the LED matrix. The page asks; the board draws."""
        paper = self._running()
        if paper["finished"]:
            return self.results()
        return {"status": "running", "left": self._left(), "seconds": paper["seconds"],
                "events": [self._clock_event()]}

    def finish(self):
        self._running()["finished"] = True
        return self.results()

    def close(self):
        """Forget the paper: back to the tutor, or ready for another one."""
        self.paper = None
        return {"status": "none", "events": [{"event": "clear"}]}

    # --- The result ------------------------------------------------------------------

    def results(self):
        paper = self._running()
        if not paper["finished"]:
            raise RuntimeError("the exam is still running")
        s = self.settings
        fraction = Fraction(*s["wrong_fraction"])
        start = Fraction(s["start_per_question"]) * len(paper["questions"])
        gained = lost = Fraction(0)
        counts = {"right": 0, "wrong": 0, "blank": 0}
        rows = []
        for i, q in enumerate(paper["questions"]):
            given = paper["answers"].get(i + 1)
            if given is None:
                outcome, delta = "blank", Fraction(s["blank"])
            elif given == q["problem"]["label"]:
                outcome, delta = "right", Fraction(q["points"])
            else:
                outcome, delta = "wrong", -fraction * q["points"]
            counts[outcome] += 1
            gained += max(delta, 0)
            lost += max(-delta, 0)
            # No right letter here, ever: the student finds it with the tutor
            rows.append({"n": i + 1, "key": q["problem"]["key"], "id": q["problem"].get("id"),
                         "points": q["points"], "given": given, "outcome": outcome, "delta": _num(delta)})
        score = start + gained - lost
        return {"status": "finished", "timed_out": paper["timed_out"], "level": paper["level"],
                "paper": paper["name"], "questions": rows, **counts,
                "start": _num(start), "gained": _num(gained), "lost": _num(lost), "score": _num(score),
                "if_blank": _num(score + lost + Fraction(s["blank"]) * counts["wrong"]),
                "maximum": _num(start + sum(q["points"] for q in paper["questions"])),
                "guess": self.guess(),
                "events": [{"event": "number", "value": counts["right"]}]}

    def guess(self, options=5):
        """Is a guess worth it? The mean gain of a random pick among the options not yet ruled out,
        as a share of the question's points, for 0, 1, 2... options ruled out."""
        fraction = Fraction(*self.settings["wrong_fraction"])
        mean = [Fraction(1, k) - Fraction(k - 1, k) * fraction for k in range(options, 1, -1)]
        pays = [i for i, m in enumerate(mean) if m > 0]
        return {"mean": [_num(m) if m.denominator in (1, 2, 4) else round(float(m), 3) for m in mean],
                "sign_with_none_out": (mean[0] > 0) - (mean[0] < 0),
                "pays_from": pays[0] if pays else None}
