"""Guess what went wrong from the wrong option the student chose. Pure rules, no model.

    diagnose(problem, "D")  ->  [{"code": "sum_all", "evidence": "3+4+2"}, ...]   most specific first
    message("sum_all", "cat", card)  ->  a question for the student, never a number

A message must stay a fair question when the rule guessed wrong, and must not say how far
the choice is from the answer: "you're one away" would leave a single option standing.

Only numbers are compared: the chosen option, the correct one, the numbers in the
question and the checkpoints. A rule that can't tell stays silent, so an empty list
is the normal result for figure problems and options without text.

Codes:
  intermediate    the option is a checkpoint value, or one operation between two of the data
  left_to_right   the option is an expression of the question computed without operator priority
  sum_all         the option is the sum of every number in the question
  wrong_op        the last step went the other way (added instead of subtracting, times instead of divided)
  off_by_one      one more or one less than the answer, in counting, pattern and measure problems
  perimeter_area  the question is about area and perimeter and the option is one of its data
  copied_datum    the option is a number that is written in the question
"""
import re
from itertools import permutations

from .tutor import _number, base_status, correct_value

CODES = ("intermediate", "left_to_right", "sum_all", "wrong_op", "off_by_one", "perimeter_area", "copied_datum")

# Generic questions, used when the topic card has no hint for the code. No digits: they can't leak.
MESSAGES = {
    "intermediate": {
        "cat": "Torna a llegir la pregunta: has arribat al que et demanen, o et falta algun pas?",
        "eng": "Read the question again: have you reached what is asked, or is a step still missing?"},
    "left_to_right": {
        "cat": "Recorda l'ordre: primer multiplicacions i divisions, després sumes i restes.",
        "eng": "Remember the order: multiplications and divisions first, then additions and subtractions."},
    "sum_all": {
        "cat": "Què representa cada número? Cal sumar-los tots, o només alguns?",
        "eng": "What does each number stand for? Do you need to add them all, or only some?"},
    "wrong_op": {
        "cat": "Mira l'últim pas: la quantitat creix o es fa més petita? Has fet servir l'operació que toca?",
        "eng": "Look at the last step: does the amount grow or shrink? Did you use the right operation?"},
    "off_by_one": {
        "cat": "Què comptes exactament: les coses o els espais entre elles? Comptes també els extrems?",
        "eng": "What exactly are you counting: the things or the gaps between them? Do the ends count?"},
    "perimeter_area": {
        "cat": "Compte: el perímetre és la vora i l'àrea és el que hi ha a dins. Quina de les dues et demanen?",
        "eng": "Careful: the perimeter is the border and the area is what's inside. Which one are you asked for?"},
    "copied_datum": {
        "cat": "Què has de fer amb les dades de l'enunciat per arribar al que et demanen?",
        "eng": "What do you have to do with the data in the problem to reach what is asked?"},
}

COUNTING = ("conteo", "patrones", "medida")
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w]|[.,]\d)")
EXPRESSION = re.compile(r"\d+(?:[.,]\d+)?(?:\s*[-+−×x*·:÷/]\s*\d+(?:[.,]\d+)?){2,}")
AREA = re.compile(r"\b(area|àrea|área)\b", re.I)
PERIMETER = re.compile(r"\bper[ií]met", re.I)


def _same(a, b):
    return abs(a - b) < 1e-9


def _question(problem):
    return str(problem.get("question") or problem.get("text") or "")


def text_numbers(problem):
    """The numbers written in the question, in order, as floats."""
    return [float(t.replace(",", ".")) for t in NUMBER.findall(_question(problem).replace("−", "-"))]


def option_values(problem):
    """{"A": 12.0, ...} for the options that are one number (with or without a unit)."""
    values = {}
    for letter, text in (problem.get("options") or {}).items():
        if len(re.findall(r"\d+(?:[.,]\d+)?", str(text))) == 1:  # "36 cm²" yes, "3 and 4" no
            values[letter] = _number(re.sub(r"[²³]", "", str(text)))
    return values


def _left_to_right(expression):
    tokens = re.findall(r"\d+(?:[.,]\d+)?|[-+−×x*·:÷/]", expression)
    total = float(tokens[0].replace(",", "."))
    for op, raw in zip(tokens[1::2], tokens[2::2]):
        n = float(raw.replace(",", "."))
        if op == "+":
            total += n
        elif op in "-−":
            total -= n
        elif op in "×x*·":
            total *= n
        elif n == 0:
            return None
        else:
            total /= n
    return total


def _pair_results(numbers):
    """Every a+b, a-b, a×b and exact a÷b for two of the data: what one single step can give."""
    out = {}
    for a, b in permutations(numbers[:8], 2):
        out.setdefault(a + b, f"{a:g}+{b:g}")
        out.setdefault(a * b, f"{a:g}×{b:g}")
        if a > b:
            out.setdefault(a - b, f"{a:g}-{b:g}")
        if b and a % b == 0:
            out.setdefault(a / b, f"{a:g}÷{b:g}")
    return out


def diagnose(problem, letter, show=None):
    """Hypotheses about a wrong choice, most specific first. [] when the rules can't tell.

    show: content statuses that count for checkpoints (None: all but rejected ones).
    """
    values = option_values(problem)
    chosen, correct = values.get(letter), correct_value(problem)
    if chosen is None or correct is None or letter == problem.get("label") or _same(chosen, correct):
        return []
    numbers = text_numbers(problem)
    found = []

    def add(code, evidence):
        if all(f["code"] != code for f in found):
            found.append({"code": code, "evidence": evidence})

    for i, c in enumerate(problem.get("checkpoints") or [], 1):
        status = base_status(c.get("status"))
        if (status in show if show is not None else status != "rebutjat") \
                and _number(c.get("answer")) is not None and _same(_number(c["answer"]), chosen):
            add("intermediate", f"checkpoint {i}")
    for match in EXPRESSION.finditer(_question(problem)):
        value = _left_to_right(match.group())
        if value is not None and _same(value, chosen):
            add("left_to_right", match.group())
    if len(numbers) >= 3 and _same(sum(numbers), chosen):
        add("sum_all", "+".join(f"{n:g}" for n in numbers))
    pairs = _pair_results(numbers)
    before = set(pairs) | set(numbers)  # what the student can have just before the last step
    for n in numbers:
        if n > 0 and _same(abs(chosen - correct), 2 * n) and (chosen + correct) / 2 in before:
            add("wrong_op", f"±{n:g}")
        elif n > 1 and correct and (_same(chosen, correct * n * n) and correct * n in before
                                    or _same(chosen * n * n, correct) and chosen * n in before):
            add("wrong_op", f"×÷{n:g}")
    if chosen in pairs and correct not in pairs and correct not in numbers:
        add("intermediate", pairs[chosen])
    spread = sorted(values.values())
    consecutive = len(spread) == 5 and all(_same(b - a, 1) for a, b in zip(spread, spread[1:]))
    # Only where counting ends or gaps is a real mistake, and never with five numbers in a row
    if _same(abs(chosen - correct), 1) and not consecutive and problem.get("topic") in COUNTING:
        add("off_by_one", f"{chosen:g} vs answer")
    if chosen in numbers and correct not in numbers:
        both = AREA.search(_question(problem)) and PERIMETER.search(_question(problem))
        add("perimeter_area" if both else "copied_datum", f"{chosen:g} in the question")
    return found


def message(code, language, card=None):
    """(text, status) for a code: the topic card's own hint when it has one, else the generic question."""
    if language == "cat":  # the cards are written in Catalan
        for error in (card or {}).get("typical_errors", []):
            if error.get("code") == code and error.get("hint"):
                return error["hint"], card.get("status", "generado")
    return MESSAGES[code].get(language, MESSAGES[code]["eng"]), "regla"
