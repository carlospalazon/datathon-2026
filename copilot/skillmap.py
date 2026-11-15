"""The skill map: what a student has tried, by topic and level, and what to try next.

One record per problem, written by three sources: the tutor (every answer and every
solution shown), the practice problems made on the spot (the first click on each one)
and the exam (each question of a paper handed in). A Cangur problem met twice, for
example missed in an exam and then solved with the tutor, stays one record that improves.

The words describe a topic, never a student: "new", "tried", "shaky", "solid". A topic
is solid only on Cangur problems answered right the first time; practice problems show
that the topic was worked on and which slips came back, but never make it solid.

The map also plans: "today's session" is up to three problems, one of a topic that
resists, one of a topic just begun and one of a new topic, with a practice problem offered
between two of them when a slip came back; and advice() tells the tutor which topic to
take next.

Several students can share one board. Each gets the name of an animal, never a real
name, and the class view is one row per animal with no marks and no ranking.

Kept in memory, and in a table of its own in the profile file when there is one.
No model, standard library only. Nothing here holds a problem's text or right letter.
"""
import json
import random
import sqlite3

TOPICS = ("aritmetica", "algebra", "conteo", "numeros", "patrones", "logica", "geometria_plana",
          "geometria_espacial", "medida", "visual", "otros")
WINDOW = 5   # a topic is judged on the last Cangur problems answered, so it can change
SOLID = 3    # right the first time on this many of them (the tutor's own MASTERED), with one other at most
SESSION = 3  # problems in "today's session": a shaky topic, one just begun, a new one
WARMUP = 3   # problems in the warm-up before the first Cangur problem, one per topic
# Warm-up topics for a student with nothing on the map yet, or to fill up: varied, friendly ones first
WARMUP_DEFAULTS = ("aritmetica", "patrones", "geometria_plana", "conteo", "medida", "numeros", "algebra", "logica")
BAR = 6      # tallest column of the LED view; the top row marks what to try next
# Pseudonyms in the order students sit down. Animals of Catalonia, none of them a person's name.
ANIMALS = ("Guineu", "Mussol", "Dofí", "Esquirol", "Llúdriga", "Falcó", "Eriçó", "Isard", "Granota", "Teixó",
           "Oreneta", "Linx", "Cigonya", "Salamandra", "Pop", "Cabirol", "Geneta", "Tortuga", "Papallona",
           "Voltor", "Sargantana", "Cavallet de mar", "Ratpenat", "Flamenc")


def state(clean, tries, other=0):
    """The word for a topic: clean of the last tries were right the first time.

    other: practice problems and exam blanks, which only show the topic was met.
    """
    if tries == 0:
        return "tried" if other else "new"
    if clean >= SOLID and clean * 4 >= tries * 3:
        return "solid"
    if tries >= 2 and clean * 2 < tries:
        return "shaky"
    return "tried"


def _merge(old, event):
    """The outcome of a Cangur problem after one more event (right, wrong, shown, blank)."""
    if old in ("first", "later", "shown"):  # settled: a second visit does not rewrite it
        return old
    if old == "open":
        return {"right": "later", "shown": "shown"}.get(event, "open")
    return {"right": "first", "wrong": "open", "shown": "shown", "blank": "blank"}[event]


class SkillMap:
    def __init__(self, problems, path=None, language="cat"):
        self.language = language
        self.problems = {p["key"]: p for p in problems}
        self.catalogue = {}  # (level, topic) -> keys, easiest first
        self.grades = {}     # level -> school grade
        for p in sorted(problems, key=lambda p: (p.get("difficulty", 0), p["key"])):
            self.catalogue.setdefault((p["level"], p["topic"]), []).append(p["key"])
            self.grades.setdefault(p["level"], p.get("grade"))
        found = {topic for _, topic in self.catalogue}
        self.topics = [t for t in TOPICS if t in found] + sorted(found - set(TOPICS))
        self.students = []   # pseudonyms, in the order they sat down
        self.items = {}      # student -> {item id: record}, oldest first
        self.student = None  # who is at the board now
        self.plans = {}      # student -> today's session; in memory only
        self.path = path
        self.seq = 0
        if path:
            self._load()
        if self.students:
            self.student = self.students[0]
        else:
            self.new_student()

    # --- Who is at the board -----------------------------------------------------------

    def new_student(self):
        n = len(self.students)
        name = ANIMALS[n % len(ANIMALS)] + (f" {n // len(ANIMALS) + 1}" if n >= len(ANIMALS) else "")
        self.students.append(name)
        self.items[name] = {}
        self.student = name
        self._save("INSERT OR REPLACE INTO skillmap_students (n, name) VALUES (?, ?)", (n, name))
        return name

    def switch(self, n):
        try:
            self.student = self.students[int(n)]
        except (TypeError, ValueError, IndexError):
            raise ValueError("unknown student") from None
        return self.student

    # --- The three sources ---------------------------------------------------------------

    def _record(self, student, item_id, record):
        items = self.items[student]
        items.pop(item_id, None)  # back to the end: the newest evidence
        items[item_id] = record
        self.seq += 1
        self._save("INSERT OR REPLACE INTO skillmap (student, item, seq, data) VALUES (?, ?, ?, ?)",
                   (student, item_id, self.seq, json.dumps(record)))

    def _cangur(self, student, problem, event, slip=None):
        item_id = "cangur:" + problem["key"]
        old = self.items[student].get(item_id) or {"kind": "cangur", "topic": problem["topic"],
                                                   "level": problem["level"], "outcome": None, "slips": []}
        record = {**old, "outcome": _merge(old["outcome"], event),
                  "slips": old["slips"] + ([slip] if slip and slip not in old["slips"] else [])}
        self._record(student, item_id, record)

    def tutor_event(self, kind, problem, detail=None, student=None):
        """What the tutor reports: an answer, a solution shown, a slip its rules named."""
        student = student or self.student
        if kind == "answer":
            self._cangur(student, problem, "right" if detail["correct"] else "wrong")
        elif kind == "solution":
            self._cangur(student, problem, "shown")
        elif kind == "slip":  # named while the wrong answer is being checked, before the answer is reported
            self._cangur(student, problem, "wrong", slip="tutor:" + detail["code"])

    def practice_answered(self, current, result, student=None):
        """A practice problem counts once, on the first click: later clicks are the student reading
        the slip behind each option."""
        if not current or result.get("attempts") != 1 or "level" not in current:
            return
        student = student or self.student
        code = (result.get("mistake") or {}).get("code")
        topic, level = current["topic"], current["level"]
        if (level, topic) not in self.catalogue:  # a warm-up topic the level on screen does not have: the nearest level's tile
            level = min((lv for lv, t in self.catalogue if t == topic), key=lambda lv: abs(lv - level), default=level)
        self.seq += 1
        self._record(student, f"practice:{self.seq}", {
            "kind": "practice", "topic": topic, "level": level,
            "outcome": "first" if result["correct"] else "open",
            "slips": [f"practice:{current['problem']['generator']}:{code}"] if code else []})

    def exam_checked(self, paper, student=None):
        """Each question of a paper handed in, once per paper. A blank is not a miss."""
        if not paper or not paper.get("finished") or paper.get("mapped"):
            return
        paper["mapped"] = True
        student = student or self.student
        for n, q in enumerate(paper["questions"], 1):
            given = paper["answers"].get(n)
            event = "blank" if given is None else "right" if given == q["problem"]["label"] else "wrong"
            self._cangur(student, q["problem"], event)

    def after(self, action, tutor, practice, exam, result):
        """Called by the server after an action of the practice card or the exam."""
        if action == "practice" and practice.current and tutor.current:
            practice.current.setdefault("level", tutor.current["problem"]["level"])
        elif action == "practiceanswer":
            self.practice_answered(practice.current, result)
            code = (result.get("mistake") or {}).get("code")
            if practice.current and result.get("attempts") == 1 and code:  # the first click, as on the map
                told = tutor.practice_slip(practice.current["topic"], practice.current["problem"]["generator"], code)
                result["again"], result["method_next"] = told["repeated"], told["method"]
        elif action.startswith("exam"):
            self.exam_checked(exam.paper)
            tutor.exam_checked(exam.paper)  # the tutor's own memory: by topic, and the misses come back

    # --- The map ---------------------------------------------------------------------------

    def _summary(self, student):
        """(level, topic) and (None, topic) -> what was done there."""
        cells = {}
        for item in self.items[student].values():
            for where in ((item["level"], item["topic"]), (None, item["topic"])):
                c = cells.setdefault(where, {"marks": [], "blank": 0, "practice": 0, "slips": {}})
                if item["kind"] == "practice":
                    c["practice"] += 1
                elif item["outcome"] == "blank":
                    c["blank"] += 1
                else:
                    c["marks"].append(item["outcome"] == "first")
                for slip in item["slips"]:
                    c["slips"][slip] = c["slips"].get(slip, 0) + 1
        return cells

    def _cell(self, topic, c, problems=0):
        c = c or {"marks": [], "blank": 0, "practice": 0, "slips": {}}
        marks = c["marks"][-WINDOW:]
        again = [s for s, n in sorted(c["slips"].items(), key=lambda kv: -kv[1]) if n >= 2]
        return {"topic": topic, "state": state(sum(marks), len(marks), c["blank"] + c["practice"]),
                "clean": sum(marks), "tries": len(marks), "done": len(c["marks"]), "blank": c["blank"],
                "practice": c["practice"], "problems": problems,
                "slip": self._slip_text(again[0]) if again else None}

    def _slip_text(self, slip):
        """The sentence for a slip that came back. They hold no digits, so none can hold an answer."""
        parts = slip.split(":")
        try:
            if parts[0] == "tutor":
                from . import diagnose
                return diagnose.MESSAGES[parts[1]].get(self.language) or diagnose.MESSAGES[parts[1]]["eng"]
            from . import practice
            return practice.MESSAGES[parts[1]][parts[2]][self.language == "eng"]
        except (KeyError, IndexError):
            return None

    @staticmethod
    def _height(cell):
        if cell["state"] == "new":
            return 0
        return 1 + round((BAR - 1) * cell["clean"] / cell["tries"]) if cell["tries"] else 1

    def view(self, seen=(), home=None, student=None):
        """The student's own map. seen: keys the tutor has already shown; home: the level of the
        problem on screen, where untried topics are offered."""
        student = student or self.student
        done = self._summary(student)
        levels = self._levels(student)
        nexts = self._next(student, levels, set(seen), self._home(home))
        totals = [self._cell(t, done.get((None, t))) for t in self.topics]
        return {"student": student, "students": list(self.students), "levels": levels, "next": nexts,
                "started": bool(self.items[student]),
                "events": [{"event": "skills", "value": [self._height(c) for c in totals],
                            "next": self.topics.index(nexts[0]["topic"]) if nexts else None}]}

    def _candidates(self, levels, home):
        """Every (level, topic) worth trying, the one that goes worst first (as the tutor's own rule
        does): shaky ones, then the ones just begun, then untried ones of the level on screen."""
        order = {"shaky": 0, "tried": 1, "new": 2}
        found = []
        for row in levels:
            for c in row["cells"]:
                if c["state"] == "solid" or (c["state"] == "new" and row["level"] != home):
                    continue
                share = c["clean"] / c["tries"] if c["tries"] else 0.5
                found.append((order[c["state"]], share, -c["problems"], row["level"], c))
        found.sort(key=lambda f: f[:4])
        return [(level, c) for _, _, _, level, c in found]

    def _next(self, student, levels, seen, home, limit=3):
        """Up to three topics to try, each with a problem to start on."""
        nexts, topics = [], set()
        for level, c in self._candidates(levels, home):
            if c["topic"] in topics:
                continue
            key = self._pick(student, level, c["topic"], seen)
            if key is None:
                continue
            topics.add(c["topic"])
            nexts.append({"topic": c["topic"], "level": level, "grade": self.grades[level],
                          "state": c["state"], "key": key})
            if len(nexts) == limit:
                break
        return nexts

    def _pickable(self, student, level, topic, seen):
        """Problems of this topic and level: the ones not yet shown, else the ones not yet solved; easiest first."""
        keys = self.catalogue.get((level, topic), [])
        items = self.items[student]
        fresh = [k for k in keys if k not in seen and "cangur:" + k not in items]
        unsolved = [k for k in keys if (items.get("cangur:" + k) or {}).get("outcome") in ("open", "blank")]
        return fresh or unsolved

    def _pick(self, student, level, topic, seen):
        return (self._pickable(student, level, topic, seen) or [None])[0]

    def _levels(self, student):
        done = self._summary(student)
        return [{"level": level, "grade": self.grades[level],
                 "cells": [self._cell(t, done.get((level, t)), len(self.catalogue[(level, t)]))
                           for t in self.topics if (level, t) in self.catalogue]}
                for level in sorted(self.grades)]

    def _home(self, home):
        return home if home in self.grades else min(self.grades) if self.grades else None

    # --- The map as a plan -------------------------------------------------------------------

    def advice(self, problem, seen=(), student=None):
        """For the tutor's choice of the next problem: is the topic of this problem solid at its
        level, and which topics does the map say to try, the one that goes worst first."""
        student = student or self.student
        levels = self._levels(student)
        here = next((c for row in levels if row["level"] == problem["level"]
                     for c in row["cells"] if c["topic"] == problem["topic"]), None)
        nexts = self._next(student, levels, set(seen), self._home(problem["level"]), limit=len(self.topics))
        return {"solid": bool(here and here["state"] == "solid"), "topics": [n["topic"] for n in nexts]}

    def warmup_topics(self, can=lambda topic: True, student=None):
        """The topics of the warm-up, one short practice problem each: the ones that went worst so
        far (a topic to reinforce first, then the most slips, then the lowest share of first-time
        answers), filled up with WARMUP_DEFAULTS, which is all a new student gets, and where the
        catalogue has fewer topics than that, with the same topics again (another kind of problem).
        can(topic): can a practice problem be made for it? Only topics of the catalogue, so each
        one has a tile on the map. Returns [{"topic", "from_map"}]."""
        student = student or self.student
        done = self._summary(student)
        hard = []
        for (level, topic), c in done.items():
            if level is not None or topic not in self.topics or not can(topic):
                continue
            cell = self._cell(topic, c)
            missed, slips = cell["tries"] - cell["clean"], sum(c["slips"].values())
            if missed or slips or cell["blank"]:
                share = cell["clean"] / cell["tries"] if cell["tries"] else 0.5
                hard.append((cell["state"] != "shaky", -slips, share, topic))
        picked = [{"topic": topic, "from_map": True} for *_, topic in sorted(hard)[:WARMUP]]
        for topic in WARMUP_DEFAULTS:
            if len(picked) < WARMUP and topic in self.topics and can(topic) and topic not in [p["topic"] for p in picked]:
                picked.append({"topic": topic, "from_map": False})
        for i in range(WARMUP - len(picked) if picked else 0):  # a catalogue of few topics: another kind of the same ones
            picked.append(dict(picked[i]))
        return picked

    def plan_start(self, seen=(), home=None, student=None):
        """Today's session: a topic that resists, one just begun and a new one, in that order. Where
        the map has fewer kinds, the next topics in line fill the session, then second problems.
        The problem of each step is picked when the step starts."""
        student = student or self.student
        seen = set(seen)
        found = self._candidates(self._levels(student), self._home(home))
        room = {}  # (level, topic) -> problems that can still be picked there

        def take(level, c):
            where = (level, c["topic"])
            if where not in room:
                room[where] = len(self._pickable(student, level, c["topic"], seen))
            if not room[where]:
                return None
            room[where] -= 1
            return {"topic": c["topic"], "level": level, "grade": self.grades[level], "state": c["state"],
                    "key": None}

        steps = []
        for want in ("shaky", "tried", "new"):   # one of each kind, each of a different topic
            for level, c in found:
                if c["state"] == want and c["topic"] not in {s["topic"] for s in steps}:
                    step = take(level, c)
                    if step:
                        steps.append(step)
                        break
        for level, c in found:                   # then the topics that come next on the map
            if len(steps) < SESSION and c["topic"] not in {s["topic"] for s in steps}:
                steps += [step for step in [take(level, c)] if step]
        more = True
        while more and len(steps) < SESSION:     # then second problems of the same topics
            more = False
            for level, c in found:
                step = take(level, c) if len(steps) < SESSION else None
                if step:
                    steps.append(step)
                    more = True
        steps.sort(key=lambda s: ("shaky", "tried", "new").index(s["state"]))
        self.plans[student] = {"steps": steps[:SESSION], "at": -1, "offered": False}
        return self.plan_state(student)

    def plan_state(self, student=None):
        """The session as the page may see it, or None when there is none."""
        student = student or self.student
        plan = self.plans.get(student)
        if plan is None:
            return None
        steps = []
        for i, step in enumerate(plan["steps"]):
            record = self.items[student].get("cangur:" + step["key"]) if step["key"] else None
            steps.append({"topic": step["topic"], "level": step["level"], "grade": step["grade"],
                          "state": step["state"], "outcome": (record or {}).get("outcome"),
                          "status": "done" if i < plan["at"] else "now" if i == plan["at"] else "todo"})
        total = len(steps)
        return {"steps": steps, "at": plan["at"], "total": total, "active": 0 <= plan["at"] < total,
                "finished": total > 0 and plan["at"] >= total}

    def plan_advance(self, seen=(), on_screen=None, student=None):
        """On to the next step. Returns {"key": the problem to start}, {"finished": True}, or once
        per step {"offer": ...}: a slip named on the step's problem has come back in its topic, so
        a practice problem is offered before moving on.

        on_screen: the key of the problem on screen when a practice problem can be made for it.
        """
        student = student or self.student
        plan = self.plans.get(student)
        if plan is None:
            raise ValueError("no session")
        steps, at = plan["steps"], plan["at"]
        if 0 <= at < len(steps) and not plan["offered"] and on_screen and on_screen == steps[at]["key"]:
            slip = self._came_back(student, steps[at])
            if slip:
                plan["offered"] = True
                return {"offer": {"topic": steps[at]["topic"], "slip": slip}}
        while at + 1 < len(steps):
            at += 1
            key = self._pick(student, steps[at]["level"], steps[at]["topic"], set(seen))
            if key is None:   # nothing left there since the plan was made: the step is dropped
                del steps[at]
                at -= 1
                continue
            steps[at]["key"] = key
            plan["at"], plan["offered"] = at, False
            return {"key": key}
        plan["at"] = len(steps)
        return {"finished": True}

    def plan_stop(self, student=None):
        self.plans.pop(student or self.student, None)

    def _came_back(self, student, step):
        """The sentence for a slip named on this step's problem that the topic has seen twice or more."""
        record = self.items[student].get("cangur:" + str(step["key"])) or {}
        counts = (self._summary(student).get((None, step["topic"])) or {"slips": {}})["slips"]
        for slip in record.get("slips", []):
            if counts.get(slip, 0) >= 2:
                text = self._slip_text(slip)
                if text:
                    return text
        return None

    def classroom(self):
        """The class, one row per pseudonym, in the order they sat down: no marks, no ranking."""
        rows, tried, shaky, solid = [], {}, {}, {}
        for student in self.students:
            done = self._summary(student)
            cells = {t: self._cell(t, done.get((None, t))) for t in self.topics}
            for t, c in cells.items():
                if c["state"] != "new":
                    tried[t] = tried.get(t, 0) + 1
                    shaky[t] = shaky.get(t, 0) + (c["state"] == "shaky")
                    solid[t] = solid.get(t, 0) + (c["state"] == "solid")
            rows.append({"name": student, "current": student == self.student,
                         "cells": [{k: c[k] for k in ("topic", "state", "clean", "tries", "practice", "blank")}
                                   for c in cells.values()]})
        stuck = sorted(({"topic": t, "shaky": shaky[t], "tried": tried[t]} for t in self.topics if shaky.get(t)),
                       key=lambda s: (-s["shaky"] / s["tried"], -s["shaky"], self.topics.index(s["topic"])))
        heights = [1 + round((BAR - 1) * solid[t] / tried[t]) if tried.get(t) else 0 for t in self.topics]
        return {"topics": list(self.topics), "students": rows, "stuck": stuck, "sample": False,
                "events": [{"event": "skills", "value": heights,
                            "next": self.topics.index(stuck[0]["topic"]) if stuck else None}]}

    # --- On disk -----------------------------------------------------------------------------

    def _connect(self):
        db = sqlite3.connect(self.path)
        db.execute("CREATE TABLE IF NOT EXISTS skillmap_students (n INTEGER PRIMARY KEY, name TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS skillmap (student TEXT, item TEXT, seq INTEGER, data TEXT,"
                   " PRIMARY KEY (student, item))")
        return db

    def _load(self):
        db = self._connect()
        try:
            self.students = [name for _, name in db.execute("SELECT n, name FROM skillmap_students ORDER BY n")]
            self.items = {name: {} for name in self.students}
            for student, item, seq, data in db.execute("SELECT student, item, seq, data FROM skillmap ORDER BY seq"):
                if student in self.items:
                    self.items[student][item] = json.loads(data)
                    self.seq = max(self.seq, seq)
        finally:
            db.close()

    def _save(self, sql, args):
        if self.path:
            db = self._connect()
            try:
                with db:
                    db.execute(sql, args)
            finally:
                db.close()


def sample_class(problems, language="cat", seed=7, size=8):
    """A made-up class, to see the class view before a real class has used the board.
    Marked as a sample; nothing of it is kept."""
    rng = random.Random(seed)
    skills = SkillMap(problems, language=language)
    hard = set(rng.sample(skills.topics, min(2, len(skills.topics))))  # where this class is stuck
    ease = {topic: rng.uniform(0.2, 0.35) if topic in hard else rng.uniform(0.75, 0.97) for topic in skills.topics}
    for i in range(size):
        student = skills.new_student() if i else skills.student
        own = rng.uniform(-0.1, 0.1)
        for (_, topic), keys in sorted(skills.catalogue.items()):
            for key in rng.sample(keys, min(len(keys), rng.randint(1, 3))):
                right = rng.random() < ease[topic] + own
                skills._cangur(student, skills.problems[key], "right" if right else "wrong")
    skills.student = None  # nobody of a sample class is at the board
    return {**skills.classroom(), "sample": True}
