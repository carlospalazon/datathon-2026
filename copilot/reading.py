"""Reading modes: the same statement, laid out the way the student chooses to read it.

Four switches, each on or off, in any mix:
  lines    one idea per line (a sentence, or the part of one before a semicolon or a colon)
  space    larger type and more room between letters, words and lines (the page does it)
  key      the key data marked in the statement, and the key data and key condition the
           catalogue carries for the problem, listed under it
  numbers  a strip with only the numbers of the statement, each with the word that follows

Nothing is rewritten: the lines put together again are the statement. The key data and the
key condition come from the catalogue (`anatomy`), are shown only when their status may be
shown and they do not give the answer away, and never include the first step or the strategy,
which are help. The numbers of the strip are read from the statement only.

The choice is kept per pseudonym as a list of switches (Choices). It is a display setting:
it says nothing about the student, and no map, class view or report reads it.

    reading.of_problem(problem, show)   # {"lines", "numbers", "key_data", "key_condition", ...}
    reading.of_text("Some text. More.") # the same for any text, for example a practice problem

Standard library only, no model.
"""
import re
import sqlite3

from .tutor import STATUSES, base_status, leaks_answer

MODES = ("lines", "space", "key", "numbers")
# 12, 3,5, 17:45, 23/4/2031: one number each; not the 5 of "5è"
NUMBER = re.compile(r"(?<![^\W_])\d+(?:[.,:/]\d+)*(?![^\W\d_])")
UNITS = {"%", "€", "cm", "mm", "m", "km", "kg", "g", "l", "h", "s"}
# Words that follow a number without saying what it counts (Catalan, English)
STOP = {"que", "per", "amb", "més", "menys", "són", "com", "als", "del", "dels", "des", "les", "els", "una", "uns", "unes",
        "fins", "cada", "quants", "quantes", "quin", "quina", "the", "and", "are", "more", "less", "than",
        "from", "how", "what", "which", "for", "with", "has", "have", "was", "were", "but", "then"}


def _clean(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def lines(text):
    """The statement as ideas, one per line. Joined with spaces they are the statement again."""
    text = _clean(text)
    if not text:
        return []
    # After . ? ! … when a new sentence starts, and after ; and : (a list of data, a condition)
    parts = re.split(r"(?<=[.?!…])\s+(?=[A-ZÀ-ÝØ«¿¡\d(])|(?<=[;:])\s+", text)
    return [p for p in parts if p]


def _segments(line, key):
    """A line as pieces: plain text, and numbers ({"n": True}; "key" when it is key data)."""
    out, at = [], 0
    for m in NUMBER.finditer(line):
        if m.start() > at:
            out.append({"t": line[at:m.start()]})
        out.append({"t": m.group(), "n": True, "key": key is None or m.group() in key})
        at = m.end()
    if at < len(line):
        out.append({"t": line[at:]})
    return out


def numbers(text):
    """The numbers of a statement in order, each with the word after it when that word says what it counts."""
    text = _clean(text)
    found = []
    for m in NUMBER.finditer(text):
        after = re.match(r"\s*(%|€|[^\W\d_]+\b(?!['’]))", text[m.end():])  # not the s of "s'han"
        word = after.group(1) if after else ""
        keep = word in UNITS or (len(word) >= 3 and word.lower() not in STOP and word == word.lower())
        found.append({"n": m.group(), "what": word if keep else ""})
    return found


def of_text(text, key=None):
    """Any statement for the reading modes. key: the numbers that are key data (None: all of them)."""
    return {"lines": [_segments(line, key) for line in lines(text)], "numbers": numbers(text)}


def _shown(text, anatomy, problem, show):
    """A catalogue sentence the student may read in a reading mode, or None."""
    text = _clean(text)
    if not text or base_status(anatomy.get("status")) not in show or leaks_answer(text, problem):
        return None
    return text


def of_problem(problem, show=STATUSES):
    """A catalogue problem for the reading modes: its statement, its numbers, and the key data and
    key condition of the catalogue when they may be shown. Never the answer, a hint or the strategy."""
    anatomy = problem.get("anatomy") or {}
    statement = problem.get("question") or problem.get("text") or ""
    key_data = _shown(anatomy.get("key_data"), anatomy, problem, show)
    key_condition = _shown(anatomy.get("key_condition"), anatomy, problem, show)
    in_text = {m.group() for m in NUMBER.finditer(_clean(statement))}
    key = {m.group() for m in NUMBER.finditer(key_data or "")} & in_text
    view = of_text(statement, key or None)  # no key data to go by: every number of the statement is a datum
    view.update({
        "key_data": [part.strip().rstrip(".") for part in key_data.split(";") if part.strip()] if key_data else [],
        "key_condition": key_condition,
        "status": anatomy.get("status") if key_data or key_condition else None,
        "figure": bool(problem.get("needs_figure")),
    })
    return view


def parse(modes):
    """'lines-key' or ['lines', 'key'] -> the switches that exist, in the order of MODES."""
    wanted = modes if isinstance(modes, (list, tuple, set)) else re.split(r"[-+, ]+", str(modes or ""))
    return [m for m in MODES if m in wanted]


class Choices:
    """The reading switches each pseudonym chose. In memory, and in a table of its own in the
    profile file when there is one. A new student starts with none."""

    def __init__(self, path=None):
        self.path = path
        self.chosen = {}
        if path:
            db = self._connect()
            try:
                self.chosen = {student: parse(modes) for student, modes in db.execute("SELECT student, modes FROM display")}
            finally:
                db.close()

    def _connect(self):
        db = sqlite3.connect(self.path)
        db.execute("CREATE TABLE IF NOT EXISTS display (student TEXT PRIMARY KEY, modes TEXT)")
        return db

    def get(self, student):
        return list(self.chosen.get(student, []))

    def set(self, student, modes):
        self.chosen[student] = parse(modes)
        if self.path:
            db = self._connect()
            try:
                with db:
                    db.execute("INSERT OR REPLACE INTO display (student, modes) VALUES (?, ?)",
                               (student, "-".join(self.chosen[student])))
            finally:
                db.close()
        return self.get(student)
