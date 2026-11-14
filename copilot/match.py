"""Pick the written help that fits what the student typed. Pure rules: no model, no embeddings.

    found = match.pick(text, tutor)      # {"take": "hint 2"} | {"text": ..., "status": ...} | None

Two questions, in order:
  1. What kind of question is it? ("what does it ask", "how do I start", "what now", "why", a number)
  2. Which written item of this problem answers that kind, and hasn't been shown yet?

If the kind is unknown, the item that shares the most words with the question wins, when it shares
enough. Nothing fits: None, and the caller may ask the model.

A number the student typed is compared with the checkpoint answers: the tutor can say "that step
is right" because a person or a checked solution wrote that number, never because a model said so.
It never says whether a number is the final answer.
"""
import re

from .guardrails import strip_accents
from .tutor import _number, base_status, leaks_answer

# Phrases without accents, lower case (cat / esp / eng). Order matters: the first kind that matches.
KINDS = [
    ("word", ["vol dir", "volen dir", "significa", "quiere decir", "quieren decir", "que es un", "que es una",
              "que son", "what does", "what is a", "means"]),
    ("why", ["per que", "perque", "por que", "why"]),
    ("next", ["i ara", "ara que", "i despres", "que faig ara", "que mes", "seguent pas", "y ahora", "ahora que",
              "y luego", "y despues", "what next", "what now", "ja he", "ja tinc", "ya he", "ya tengo"]),
    ("start", ["comenc", "empiez", "empez", "per on comenc", "com comenc", "com es comenca", "com ho faig", "com es fa", "que he de fer",
               "que haig de fer", "que faig primer", "primer pas", "no se que fer", "no se com", "no se per on",
               "por donde empiezo", "como empiezo", "como se hace", "que hago", "que tengo que hacer",
               "how do i start", "where do i start"]),
    ("look", ["no entenc", "no ho entenc", "no entiendo", "que em demanen", "que demana", "que demanen",
              "que pregunta", "que pregunten", "que he de trobar", "que he de buscar", "que he de mirar",
              "on he de mirar", "on miro", "que me piden", "que pide", "que hay que encontrar", "what does it ask"]),
]
OPERATION = re.compile(r"(?:he de|haig de|tinc que|tengo que|hay que|cal|s'ha de|se ha de|debo|do i)\s+"
                       r"(?:sumar|restar|multiplicar|dividir|comptar|contar|add|subtract|multiply|divide)")
ATTEMPT = re.compile(r"m'ha donat|em dona|em surt|m'ha sortit|me da|me sale|me ha dado|i got|=|\bno\?$"
                     r"|crec que|creo que|i think|resposta es|respuesta es|answer is")
MIN_SHARED = 2   # words in common before an item "fits" a question of unknown kind

LEAD = {
    "key_condition": {"cat": "Fixa't en això: ", "eng": "Look at this: "},
    "key_data": {"cat": "Les dades que compten: ", "eng": "The data that matter: "},
    "step_right": {"cat": "Sí, aquest pas és correcte. ", "eng": "Yes, that step is right. "},
    "option": {"cat": "Si creus que aquest és el resultat, tria la lletra que el té.",
               "eng": "If you think that is the result, choose the letter that has it."},
    "unknown_number": {"cat": "Aquest número no et puc dir si va bé. Prova aquest pas:",
                       "eng": "I can't tell you whether that number is right. Try this step:"},
}


def clean(text):
    return re.sub(r"\s+", " ", strip_accents(str(text).lower())).strip()


def words(text):
    return set(re.findall(r"[^\W\d_]{4,}", clean(text)))


def kind(text):
    """'word', 'why', 'next', 'start', 'look' or None."""
    t = clean(text)
    if OPERATION.search(t):
        return "next"
    for name, phrases in KINDS:
        if any(re.search(r"(?<!\w)" + re.escape(p), t) for p in phrases):
            return name
    return None


def attempt(text, problem):
    """The number the student is trying out, or None. A number already in the statement isn't an attempt."""
    t = clean(text)
    if not re.search(r"\d", t):
        return None
    if not (ATTEMPT.search(t) or len(t.split()) <= 4):
        return None
    after = t.rsplit("=", 1)[-1] if "=" in t else t
    numbers = re.findall(r"-?\d+(?:[.,]\d+)?", after)
    if not numbers:
        return None
    value = _number(numbers[-1])
    statement = {_number(n) for n in re.findall(r"-?\d+(?:[.,]\d+)?", problem.get("question") or problem.get("text", ""))}
    return None if value in statement and "=" not in t and not ATTEMPT.search(t) else value


def _language(problem):
    return "cat" if problem.get("language") == "cat" else "eng"


def _extra(tutor, name, said):
    """A piece of the problem's anatomy the student may see, with its lead-in, or None."""
    problem = tutor._session()["problem"]
    item = problem.get("anatomy") or {}
    text = item.get(name)
    if not text or name in said or base_status(item.get("status")) not in tutor.show or leaks_answer(text, problem):
        return None
    return {"text": LEAD[name][_language(problem)] + text, "status": item["status"], "source": name, "say": name}


def _first(waiting, prefix):
    return next((source for source, _ in waiting if source.startswith(prefix)), None)


def pick(text, tutor):
    """The written help that fits the text, or None.

    {"take": source}: a step of the guide (the caller shows it with tutor.take).
    {"text", "status", "source", "say"}: a piece outside the guide ("say" marks it as used).
    Either may carry "tone": "ok" for a step the student got right.
    """
    session = tutor._session()
    problem, said = session["problem"], session["said"]
    language = _language(problem)
    waiting = tutor.waiting()

    number = attempt(text, problem)
    if number is not None:
        for i, c in enumerate(problem.get("checkpoints") or [], 1):
            if base_status(c.get("status")) in tutor.show and _number(c.get("answer")) == number \
                    and f"checkpoint {i}" in dict(waiting):
                unit = f" ({c['unit']})" if c.get("unit") else ""
                return {"text": LEAD["step_right"][language] + c["question"] + f" {c['answer']}{unit}.",
                        "status": c["status"], "source": f"checkpoint {i}", "drop": f"checkpoint {i}", "tone": "ok"}
        if any(_number(v) == number for v in (problem.get("options") or {}).values()):
            return {"text": LEAD["option"][language], "status": "regla", "source": "option"}
        step = _first(waiting, "checkpoint")
        if step:
            return {"take": step, "before": LEAD["unknown_number"][language]}
        return None

    k = kind(text)
    if k == "why":  # "why can't it be 8?": the note written for that wrong option, if there is one
        mentioned = {_number(n) for n in re.findall(r"-?\d+(?:[.,]\d+)?", clean(text))}
        for letter, note in (problem.get("distractors") or {}).items():
            value = _number((problem.get("options") or {}).get(letter, ""))
            if value is not None and value in mentioned and f"note {letter}" not in said \
                    and base_status(note.get("status")) in tutor.show and not leaks_answer(note.get("text", ""), problem):
                return {"text": note["text"], "status": note["status"], "source": f"distractor {letter}",
                        "say": f"note {letter}"}
    order = {"look": [("extra", "key_condition"), ("take", "hint 1"), ("extra", "key_data")],
             "start": [("take", "hint 2"), ("take", "hint 1"), ("extra", "key_data")],
             "next": [("take", "checkpoint"), ("take", "hint 3"), ("take", "hint")],
             "why": [("extra", "key_condition"), ("take", "checkpoint"), ("take", "hint")],
             "word": []}.get(k)
    if order is not None:
        for how, name in order:
            if how == "extra":
                found = _extra(tutor, name, said)
                if found:
                    return found
            else:
                source = name if " " in name and name in dict(waiting) else _first(waiting, name) if " " not in name else None
                if source:
                    return {"take": source}
        return None

    # Unknown kind: the waiting hint or checkpoint that shares the most words with the question
    asked = words(text)
    best, shared = None, 0
    for source, item_text in waiting:
        if source.startswith(("hint", "checkpoint")) and item_text:
            n = len(asked & words(item_text))
            if n > shared:
                best, shared = source, n
    return {"take": best} if shared >= MIN_SHARED else None
