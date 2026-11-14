"""Output guardrails: check any text the language model writes for a student.

Pure rules, standard library only, a few milliseconds. The model writes, these rules
decide. If a text fails, the caller shows a fixed template instead (see TEMPLATES).
check() never raises: on any internal error it rejects (fail-closed).
"""
import re
import unicodedata

MAX_CHARS = 220
MAX_SENTENCES = 2
ALLOWED_NUMBERS = {"1", "2", "10", "100"}

# Fixed fallback hints, one per language. Used when a check fails or the model is late.
TEMPLATES = {
    "eng": "Read it again: what exactly is the problem asking you to find?",
    "cat": "Torna a llegir-ho: què et demana exactament el problema?",
    "esp": "Léelo otra vez: ¿qué te pide exactamente el problema?",
}

STOPWORDS = {
    "eng": {"the", "is", "are", "of", "and", "to", "what", "how", "you", "it", "this", "that", "with", "for", "in", "a"},
    "cat": {"el", "la", "els", "les", "de", "del", "que", "és", "es", "per", "amb", "un", "una", "i", "quants", "quin"},
    "esp": {"el", "la", "los", "las", "de", "del", "que", "es", "por", "con", "un", "una", "y", "cuántos", "cual", "qué"},
}

META_PHRASES = [
    "the answer is", "the correct answer", "the solution is", "te doy la respuesta",
    "la respuesta es", "la respuesta correcta", "la solucion es", "la solucion correcta",
    "la resposta es", "la resposta correcta", "la solucio es", "correct option",
    "opcion correcta", "opcio correcta", "you should pick", "debes elegir", "has de triar",
]

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
LETTER_LEAKS = [
    re.compile(r"\b(?i:answer|respuesta|resposta|option|opcion|opcio|solution|solucion|solucio|letter|letra|lletra|correct\w*)\b[^.!?]{0,20}?\b([A-E])\b"),
    re.compile(r"\(([A-E])\)"),
    re.compile(r"\b([A-E])\)"),
    re.compile(r"\b(?i:la|l'|el|option|opcion|opcio|letter|letra|lletra)\s*([A-E])\b"),
]
LIST_OR_MARKDOWN = re.compile(r"(?m)^\s*(?:[-*•]|\d+[.)])\s|\*\*|```|^#|<think|</think")
CALC_RESULT = re.compile(r"=\s*-?\d")


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def norm_number(token):
    """'0,50' -> '0.5', '12' -> '12', '3.0' -> '3'."""
    token = token.replace(",", ".")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token or "0"


def numbers_in(text):
    return {norm_number(t) for t in NUMBER.findall(text)}


def detect_language(text):
    words = re.findall(r"[\wàèéíòóúçïü·']+", text.lower())
    scores = {lang: sum(w in sw for w in words) for lang, sw in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    return best, scores


def _problem_numbers(problem):
    text = problem.get("text", "")
    for value in (problem.get("options") or {}).values():
        text += " " + str(value)
    return numbers_in(text)


def _correct_value(problem):
    return str((problem.get("options") or {}).get(problem.get("label", ""), "")).strip()


def _check(text, problem, max_chars):
    if not isinstance(text, str) or not text.strip():
        return False, "empty"
    if len(text) > max_chars:
        return False, "too_long"
    if len([s for s in re.split(r"[.!?]+(?:\s|$)", text) if s.strip()]) > MAX_SENTENCES:
        return False, "too_many_sentences"
    if LIST_OR_MARKDOWN.search(text) or "\n\n" in text:
        return False, "format"
    for pattern in LETTER_LEAKS:
        if pattern.search(text):
            return False, "letter_leak"
    plain = strip_accents(text.lower())
    if any(phrase in plain for phrase in META_PHRASES):
        return False, "meta_leak"

    statement = problem.get("text", "")
    # Value of the correct option, unless it already appears in the statement
    correct = _correct_value(problem)
    if correct:
        correct_numbers = numbers_in(correct)
        statement_numbers = numbers_in(statement)
        if correct_numbers and (correct_numbers - statement_numbers) & numbers_in(text):
            return False, "value_leak"
        if not correct_numbers and len(correct) >= 3 and strip_accents(correct.lower()) in plain \
                and strip_accents(correct.lower()) not in strip_accents(statement.lower()):
            return False, "value_leak"

    if CALC_RESULT.search(text):
        return False, "calculation"
    unknown = numbers_in(text) - _problem_numbers(problem) - ALLOWED_NUMBERS
    if unknown:
        return False, "invented_number"

    language = problem.get("language")
    if language in STOPWORDS:
        best, scores = detect_language(text)
        if best != language and scores[best] >= 3 and scores[best] > scores[language] + 1:
            return False, "language"

    words = [w for w in re.findall(r"\w+", plain) if len(w) > 3]
    statement_words = set(re.findall(r"\w+", strip_accents(statement.lower())))
    if len(words) >= 6 and sum(w in statement_words for w in words) / len(words) > 0.8:
        return False, "copies_problem"
    sentences = [s.strip() for s in re.split(r"[.!?]+", plain) if s.strip()]
    if len(sentences) != len(set(sentences)):
        return False, "repetition"
    return True, "ok"


def check(text, problem, max_chars=MAX_CHARS):
    """Return (ok, reason). Fail-closed: any error counts as a rejection."""
    try:
        return _check(text, problem, max_chars)
    except Exception as error:  # noqa: BLE001 - a guardrail must never break the app
        return False, f"error: {error.__class__.__name__}"


def safe_hint(text, problem, template=None):
    """The model text if it passes every rule, otherwise the fixed template."""
    ok, _reason = check(text, problem)
    if ok:
        return text.strip()
    return template or TEMPLATES.get(problem.get("language"), TEMPLATES["eng"])
