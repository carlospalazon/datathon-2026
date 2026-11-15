"""A statistical prior over answer letters and option shapes. No model, and no maths: it solves nothing.

Kangaroo answer keys are not uniform (D is the most frequent letter, A the rarest), and the right
option has a slightly different "shape" from the wrong ones (its rank among five numbers, whether it
is the round one, whether its value is already written in the statement...). This module counts those
things on the TRAINING split and picks the option with the best summed log-odds: naive Bayes over the
five candidates. It is a guess that is a little better than a fixed letter, nothing more.

    table = fit(training_problems, features)   # counts only, no problem text
    letter, scores = choose(problem, table)    # deterministic; ties go to the table's letter order

    table = load("copilot/prior_table.json")   # the committed table, built by laptop/build_prior.py

Rules it keeps: everything is learned from data/train.jsonl; nothing is keyed on a problem id or on a
problem's or option's text (every key is a category made here: a letter, a level band, a rank...).
Standard library only; one problem takes well under a millisecond.

The level is read from the "level" field, or from an id shaped "lvl-N_YYYY_Q" when the field is
missing; the question number only from the start of the text. A feature whose input is missing adds
nothing, so a problem with only a text still gets the plain letter prior.
"""
import json
import math
import re

LETTERS = "ABCDE"
BASE = 1.0 / len(LETTERS)
SMOOTHING = 20.0  # pseudo-candidates at the base rate added to every cell

_ID = re.compile(r"lvl-(\d+)_(\d{4})_")
_QUESTION = re.compile(r"\s*(\d{1,2})\s*[.)]")
_STRICT = re.compile(r"^(-?\d+(?:\.\d+)?)(?:/(\d+))?(?:\s*[^\d\s][^\d]{0,11})?$")
_LEADING = re.compile(r"^(-?\d+(?:\.\d+)?)")
_NUMBERS = re.compile(r"\d+(?:\.\d+)?")
_FIGURE = re.compile(r"\b(figur\w*|pictur\w*|diagram\w*|drawing\w*|image\w*|shown|dibuix\w*|imatge\w*|"
                     r"mostra\w*|il·lustra\w*|gràfic\w*|graph\w*)\b", re.I)
_NONE = re.compile(r"\b(none|neither|cannot|can't|impossible|not possible|no other|another|"
                   r"cap\b|no es pot|no és possible|un altre|una altra|depèn|depends)", re.I)


def level_of(problem):
    level = problem.get("level")
    if isinstance(level, int) and not isinstance(level, bool):
        return level
    match = _ID.match(str(problem.get("id", "")))
    return int(match.group(1)) if match else None


def year_of(problem):
    year = problem.get("year")
    if isinstance(year, int) and not isinstance(year, bool):
        return year
    match = _ID.match(str(problem.get("id", "")))
    return int(match.group(2)) if match else None


def question_number(text):
    """The number a Kangaroo problem starts with ("17. A square..."), or None."""
    match = _QUESTION.match(text or "")
    number = int(match.group(1)) if match else 0
    return number if 1 <= number <= 30 else None


def section(problem, last_question):
    """0, 1 or 2: the 3-, 4- or 5-point third of the paper, from the question number in the text."""
    number = question_number(problem.get("text"))
    level = level_of(problem)
    if number is None or level is None:
        return None
    last = int(last_question.get(str(level), 0)) or 30
    return min(3 * (number - 1) // last, 2)


def _clean(option):
    return re.sub(r"[\s$*_\\{}]", "", str(option).lower()).replace(",", ".")


def _plain(option):
    """An option as written, without mark-up, decimal comma as a point. Spaces stay: "12 3" is not 123."""
    return re.sub(r"[$*_\\{}]", "", str(option).lower()).replace(",", ".").strip()


def number(option):
    """The value of an option like "12", "3,5", "3/4", "14 km"; None when it is not one number."""
    match = _STRICT.match(_plain(option))
    if not match:
        return None
    value = float(match.group(1))
    if match.group(2):
        if not int(match.group(2)):
            return None
        value /= int(match.group(2))
    return value


def numbers(options):
    """Five values when the options are numbers, else None.

    The text comes from OCR and often has stray characters after the last option, so one option of
    the five may contribute only the number it starts with.
    """
    values = [number(options[c]) for c in LETTERS]
    missing = [i for i, v in enumerate(values) if v is None]
    if len(missing) > 1:
        return None
    for i in missing:
        match = _LEADING.match(_plain(options[LETTERS[i]]))
        if not match:
            return None
        values[i] = float(match.group(1))
    return values


def shape(values):
    """How five numeric options are laid out: asc, desc or mixed."""
    if all(a < b for a, b in zip(values, values[1:])):
        return "asc"
    if all(a > b for a, b in zip(values, values[1:])):
        return "desc"
    return "mixed"


def has_options(problem):
    options = problem.get("options")
    return isinstance(options, dict) and set(options) == set(LETTERS)


# --- Features. Each returns {letter: key} (or None when it does not apply). A key never holds text.

def f_letter(problem, ctx):
    kind = "none" if ctx["kind"] == "none" else "options"
    return {c: f"{kind}|{c}" for c in LETTERS}


def f_layout(problem, ctx):
    """The letter again, but counted apart for each layout of the options (asc, desc, mixed, text)."""
    kind = ctx["kind"]
    return None if kind == "none" else {c: f"{kind}|{c}" for c in LETTERS}


def f_level(problem, ctx):
    level = level_of(problem)
    return None if level is None else {c: f"{level}|{c}" for c in LETTERS}


def f_levelband(problem, ctx):
    level = level_of(problem)
    return None if level is None else {c: f"{level // 2}|{c}" for c in LETTERS}


def f_section(problem, ctx):
    part = section(problem, ctx["last_question"])
    return None if part is None else {c: f"{part}|{c}" for c in LETTERS}


def f_levelband_section(problem, ctx):
    part, level = section(problem, ctx["last_question"]), level_of(problem)
    return None if part is None else {c: f"{level // 2}|{part}|{c}" for c in LETTERS}


def f_figure(problem, ctx):
    mentioned = bool(_FIGURE.search(problem.get("text") or ""))
    return {c: f"{int(mentioned)}|{c}" for c in LETTERS}


def f_year(problem, ctx):
    year = year_of(problem)
    return None if year is None else {c: f"{year}|{c}" for c in LETTERS}


def f_length(problem, ctx):
    words = len((problem.get("text") or "").split())
    bucket = 0 if words < 20 else 1 if words < 45 else 2
    return {c: f"{bucket}|{c}" for c in LETTERS}


def f_language(problem, ctx):
    language = problem.get("language")
    return None if not language else {c: f"{language}|{c}" for c in LETTERS}


def f_rank(problem, ctx):
    """Rank of the value among the five (r0 the smallest), whatever the order they are written in."""
    values = ctx["values"]
    if values is None:
        return None
    out = {}
    for i, c in enumerate(LETTERS):
        below, same = sum(v < values[i] for v in values), sum(v == values[i] for v in values)
        out[c] = "tie" if same > 1 else f"r{below}"
    return out


def f_rank_mixed(problem, ctx):
    """The rank, only when the options are not written in order.

    In an ordered list the rank is the position, which the letter counts already cover; counting it
    twice would overstate it.
    """
    return f_rank(problem, ctx) if ctx["kind"] == "mixed" else None


def f_extreme(problem, ctx):
    """Smallest, largest or in between, whatever the order of the options."""
    values = ctx["values"]
    if values is None:
        return None
    low, high = min(values), max(values)
    return {c: "min" if v == low else "max" if v == high else "mid" for c, v in zip(LETTERS, values)}


def f_round(problem, ctx):
    values = ctx["values"]
    if values is None:
        return None
    flags = [v == int(v) and int(v) % 10 == 0 for v in values]
    if sum(flags) in (0, 5):
        return None
    return {c: f"{int(flag)}|{min(sum(flags), 3)}" for c, flag in zip(LETTERS, flags)}


def f_in_text(problem, ctx):
    """Is the option's number written in the statement? (text options: are all of its words?)"""
    text = (problem.get("text") or "").lower().replace(",", ".")
    values = ctx["values"]
    if values is not None:
        seen = {float(t) for t in _NUMBERS.findall(text)}
        flags = [v in seen for v in values]
    else:
        words = set(re.findall(r"\w+", text))
        flags = []
        for c in LETTERS:
            own = re.findall(r"\w+", str(problem["options"][c]).lower())
            flags.append(bool(own) and all(w in words for w in own))
    kind = "num" if values is not None else "text"
    return {c: f"{kind}|{int(flag)}|{min(sum(flags), 3)}" for c, flag in zip(LETTERS, flags)}


def f_outlier(problem, ctx):
    """The one value furthest from its nearest neighbour, if there is exactly one."""
    values = ctx["values"]
    if values is None:
        return None
    gaps = [min(abs(v - w) for j, w in enumerate(values) if j != i) for i, v in enumerate(values)]
    top = max(gaps)
    if gaps.count(top) != 1 or top == 0:
        return None
    return {c: "out" if gap == top else "in" for c, gap in zip(LETTERS, gaps)}


def f_digits(problem, ctx):
    """How many of the other four values are written with the same number of characters."""
    values = ctx["values"]
    if values is None:
        return None
    sizes = [len(f"{v:g}") for v in values]
    if len(set(sizes)) == 1:
        return None
    return {c: f"same{sizes.count(size) - 1}" for c, size in zip(LETTERS, sizes)}


def f_lastdigit(problem, ctx):
    """How many of the other four values end with the same digit."""
    values = ctx["values"]
    if values is None:
        return None
    ends = [f"{v:g}"[-1] for v in values]
    if len(set(ends)) in (1, 5):
        return None
    return {c: f"same{min(ends.count(end) - 1, 2)}" for c, end in zip(LETTERS, ends)}


def f_textlength(problem, ctx):
    """Text options: the shortest, the longest, or neither."""
    if ctx["values"] is not None:
        return None
    sizes = [len(str(problem["options"][c]).strip()) for c in LETTERS]
    low, high = min(sizes), max(sizes)
    if low == high:
        return None
    return {c: ("short" if size == low else "long" if size == high else "mid")
            + ("1" if sizes.count(size) == 1 else "n") for c, size in zip(LETTERS, sizes)}


def f_none(problem, ctx):
    """Options of the "none of these" / "it cannot be known" kind."""
    flags = [bool(_NONE.search(str(problem["options"][c]))) for c in LETTERS]
    if sum(flags) in (0, 5):
        return None
    return {c: f"{int(flag)}|{min(sum(flags), 2)}" for c, flag in zip(LETTERS, flags)}


def f_similar(problem, ctx):
    """Text options: the one that shares most (or least) characters pairs with the other four."""
    if ctx["values"] is not None:
        return None
    grams = []
    for c in LETTERS:
        s = _clean(problem["options"][c])
        grams.append(set(zip(s, s[1:])) or {s})
    totals = [sum(len(g & h) for j, h in enumerate(grams) if j != i) for i, g in enumerate(grams)]
    low, high = min(totals), max(totals)
    if low == high:
        return None
    return {c: "most" if t == high else "least" if t == low else "mid" for c, t in zip(LETTERS, totals)}


def f_duplicate(problem, ctx):
    cleaned = [_clean(problem["options"][c]) for c in LETTERS]
    if len(set(cleaned)) == 5:
        return None
    return {c: f"dup{int(cleaned.count(s) > 1)}" for c, s in zip(LETTERS, cleaned)}


FEATURES = {
    "letter": f_letter, "layout": f_layout, "level": f_level, "levelband": f_levelband, "section": f_section,
    "levelband_section": f_levelband_section, "figure": f_figure, "year": f_year, "length": f_length,
    "language": f_language, "rank": f_rank, "rank_mixed": f_rank_mixed, "extreme": f_extreme, "round": f_round, "in_text": f_in_text,
    "outlier": f_outlier, "digits": f_digits, "lastdigit": f_lastdigit, "textlength": f_textlength,
    "none": f_none, "similar": f_similar, "duplicate": f_duplicate,
}
# Candidates in the order they are tried by laptop/build_prior.py. "letter" is always the first.
NO_OPTIONS_CANDIDATES = ("levelband", "level", "section", "levelband_section", "figure", "length", "year",
                         "language")
OPTIONS_CANDIDATES = ("rank_mixed", "extreme", "rank", "layout", "round", "in_text", "outlier", "digits", "lastdigit", "textlength",
                      "none", "similar", "duplicate", "levelband", "section", "figure")


def context(problem, last_question):
    """What the features share: the numeric values and the kind of problem."""
    if not has_options(problem):
        return {"kind": "none", "values": None, "last_question": last_question}
    values = numbers(problem["options"])
    return {"kind": shape(values) if values is not None else "text", "values": values,
            "last_question": last_question}


def keys(problem, features, last_question):
    """{feature: {letter: key}} for the features that apply to this problem."""
    ctx = context(problem, last_question)
    out = {}
    for name in features:
        try:
            found = FEATURES[name](problem, ctx)
        except Exception:  # noqa: BLE001  a strange option must not stop the answer
            found = None
        if found:
            out[name] = found
    return out


def last_questions(problems):
    """{level: the highest question number seen}, to cut a paper into its three sections."""
    last = {}
    for p in problems:
        number, level = question_number(p.get("text")), level_of(p)
        if number is not None and level is not None:
            last[str(level)] = max(last.get(str(level), 0), number)
    return last


def weight(right, total, smoothing=SMOOTHING):
    """Log-odds of a cell against the base rate of one in five, pulled towards 0 when it is small."""
    return math.log((right + smoothing * BASE) / (total + smoothing) / BASE)


def fit_part(problems, features, last_question):
    """Counts for one kind of problem: {feature: {key: [right, total]}}."""
    counts = {name: {} for name in features}
    for p in problems:
        if p.get("label") not in tuple(LETTERS):
            continue
        for name, by_letter in keys(p, features, last_question).items():
            for c, key in by_letter.items():
                cell = counts[name].setdefault(key, [0, 0])
                cell[0] += c == p["label"]
                cell[1] += 1
    return counts


def fit(problems, no_options_features=("letter",), options_features=("letter",)):
    """The table: counts and weights per feature, for problems without and with options."""
    problems = list(problems)
    last_question = last_questions(problems)
    order = sorted(LETTERS, key=lambda c: (-sum(p.get("label") == c for p in problems), c))
    table = {"version": 1, "rows": len(problems), "smoothing": SMOOTHING, "last_question": last_question,
             "letter_order": "".join(order), "parts": {}}
    for part, features, rows in (
            ("no_options", no_options_features, [p for p in problems if not has_options(p)]),
            ("options", options_features, [p for p in problems if has_options(p)])):
        counts = fit_part(rows, features, last_question)
        table["parts"][part] = {
            "rows": len(rows), "features": list(features),
            "cells": {name: {key: [right, total, round(weight(right, total), 4)]
                             for key, (right, total) in sorted(cells.items())}
                      for name, cells in counts.items()}}
    return table


def scores(problem, table):
    """{letter: summed log-odds}. Higher is more likely under the prior."""
    part = table["parts"]["options" if has_options(problem) else "no_options"]
    total = {c: 0.0 for c in LETTERS}
    for name, by_letter in keys(problem, part["features"], table.get("last_question", {})).items():
        cells = part["cells"].get(name, {})
        for c, key in by_letter.items():
            cell = cells.get(key)
            if cell:
                total[c] += cell[2]
    return total


def choose(problem, table):
    """(letter, scores). Ties go to the letter that is most frequent in training."""
    total = scores(problem, table)
    order = table.get("letter_order", "DCBEA")
    return max(order, key=lambda c: (round(total[c], 9), -order.index(c))), total


def load(path):
    """The table from a JSON file. Raises on a missing or malformed file: the caller decides."""
    with open(path, encoding="utf-8") as f:
        table = json.load(f)
    for part in ("no_options", "options"):
        for name in table["parts"][part]["features"]:
            if name not in FEATURES:
                raise ValueError(f"unknown feature {name!r}")
    return table
