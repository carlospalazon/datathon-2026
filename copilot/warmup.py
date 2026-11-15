"""Warm-up of three: before the first Cangur problem of a sitting, three short practice problems.

One problem per topic that went worst for this student so far (the skill map says which;
a new student gets three varied topics), each made on the spot by the practice generators
with the smallest numbers drawn, so the sitting starts with something that works out.
The student can skip it at any time, and it is offered once: it is over when the three
are solved, when it is skipped, or as soon as the student touches a Cangur problem.

It owns no problems of its own: each one is the practice card's current problem
(copilot/practice.py), so answers, named slips and the skill map work as they do there.

    warm = Warmup(practice, topics=lambda: skills.warmup_topics(practice.available))
    warm.state()          # {"pending": True, "active": False, "n": 0, "total": 3, "topics": [...]}
    view = warm.next(0)   # the first problem (never its answer); again after it is solved: the next
    warm.close()          # skipped, or the student went on to something else

Standard library only, no model.
"""


class Warmup:
    def __init__(self, practice, topics):
        """practice: the student's Practice. topics() -> [{"topic", "from_map"}], hardest first."""
        self.practice = practice
        self.pick = topics
        self.topics = None   # fixed when the warm-up starts
        self.n = 0           # problems made so far
        self.view = None     # the problem on screen, as the page saw it
        self.closed = False

    def _topics(self):
        return self.topics if self.topics is not None else self.pick()

    def _solved(self):
        current = self.practice.current
        return bool(self.view and current and current["n"] == self.view["n"]
                    and current["problem"]["label"] in current["attempts"])

    def state(self):
        """Where the warm-up is, for the page. pending: on offer; active: begun and not over."""
        topics = [] if self.closed else self._topics()
        started = self.topics is not None
        return {"pending": bool(topics) and not started and not self.closed,
                "active": started and not self.closed,
                "n": self.n, "total": len(topics), "topics": [t["topic"] for t in topics],
                "from_map": any(t["from_map"] for t in topics)}

    def next(self, level=None):
        """The problem to show: the first one, the same one until it is solved (a page reload), then
        the next; {"finished": True} after the last. level: the level of the Cangur problem on
        screen, so the skill map can file the practice."""
        if not self.closed and self.topics is None:
            self.topics = self.pick()
        current = self.practice.current
        if not self.closed and self.view and current and current["n"] == self.view["n"] and not self._solved():
            return self.view
        while not self.closed and self.n < len(self.topics):
            made = self.practice.new(self.topics[self.n]["topic"])
            if made is None:           # no problem can be made for this topic after all: one fewer
                del self.topics[self.n]
                continue
            self.n += 1
            if level is not None:
                self.practice.current["level"] = level
            self.view = {**made, "warmup": {"n": self.n, "total": len(self.topics)}}
            return self.view
        done = bool(self.topics) and not self.closed
        self.close()
        return {"finished": True, "done": done, "events": []}

    def close(self):
        """Over for this sitting: solved, skipped, or the student is already on a Cangur problem."""
        self.closed, self.view = True, None
