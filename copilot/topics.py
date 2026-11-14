"""Input guardrails: decide what a student's text is about before anything reaches the model.

Pure rules, standard library only. Order: injection -> intent -> math/current problem ->
small talk -> off topic. Anything unclear is redirected. Text that is not on topic
never reaches the language model.
"""
import re

from .guardrails import numbers_in, strip_accents

MAX_INPUT = 200
LOCK_AFTER = 3  # consecutive redirects before free text is turned off (buttons only)

INJECTION = [
    "ignore previous", "ignore all", "ignore the instructions", "ignora las instrucciones",
    "ignora les instruccions", "olvida las instrucciones", "system prompt", "prompt del sistema",
    "actua como", "actua com", "eres ahora", "ets ara", "pretend", "you are now", "jailbreak",
    "developer mode", "modo desarrollador", "http://", "https://", "www.", "```", "import os",
    "<script", "def ", "print(",
]

# Intents work with or without explicit maths words. (eng / cat / esp)
INTENTS = {
    "pista": ["hint", "help", "pista", "ajuda", "ayuda", "no se", "no entiendo", "no ho entenc",
              "i dont know", "i don't know", "stuck", "no entenc", "atascado", "encallat"],
    "repetir": ["repeat", "again", "repite", "repeteix", "otra vez", "una altra vegada"],
    "siguiente": ["next", "skip", "siguiente", "seguent", "otro problema", "un altre problema", "pasa"],
    # Only a request to be given the answer: "the answer is 12" is an attempt, not a request.
    "solucion": ["solution", "give up", "solucion", "me rindo", "em rendeixo", "dime la respuesta",
                 "dona'm la resposta", "tell me the answer", "quina es la resposta",
                 "cual es la respuesta", "what is the answer"],
    "progreso": ["how am i doing", "my level", "mi nivel", "el meu nivell", "como voy", "com vaig", "progress"],
    "ayuda_app": ["how do i use", "como se usa", "com es fa servir", "how does this work", "como funciona"],
}

MATH_WORDS = {
    "suma", "sumar", "resta", "restar", "multiplic", "divis", "fraccio", "fraction", "decimal",
    "area", "perimetro", "perimetre", "perimeter", "angulo", "angle", "triangulo", "triangle",
    "cuadrado", "quadrat", "square", "circulo", "cercle", "circle", "rectangulo", "rectangle",
    "primo", "primer", "prime", "par", "impar", "odd", "even", "multiplo", "multiple", "divisor",
    "ecuacion", "equacio", "equation", "porcentaje", "percentatge", "percent", "numero", "nombre",
    "number", "digito", "xifra", "digit", "promedio", "mitjana", "average", "mean", "mayor",
    "menor", "larger", "smaller", "bigger", "total", "cuantos", "quants", "how many", "cubo",
    "cube", "volumen", "volume", "raiz", "arrel", "root", "potencia", "power", "hora", "clock",
    "minutos", "minuts", "minutes", "dias", "dies", "days", "grafico", "patron", "patro",
    "pattern", "secuencia", "sequence", "probabilidad", "probability", "problema", "problem",
    "opcion", "opcio", "option", "respuesta", "resposta", "answer", "calculo", "calcul",
}

SOCIAL = ["hola", "hello", "hi", "hey", "gracias", "gracies", "thanks", "thank you", "merci",
          "adeu", "adios", "bye", "bon dia", "buenos dias", "good morning"]

# Asking the copilot to solve some other sum or to do homework
HOMEWORK = ["resuelve", "resol", "solve", "calcula", "calculate", "cuanto es", "quant es",
            "how much is", "what is", "cuanto son", "quant son", "hazme", "fes-me", "do my"]

REDIRECT = {
    "eng": "That's outside what I can help with. Let's go back to your problem: what is it asking you to find?",
    "cat": "Això queda fora del que et puc ajudar. Tornem al problema: què et demana exactament?",
    "esp": "Eso queda fuera de lo que puedo ayudarte. Volvamos al problema: ¿qué te pide exactamente?",
}
SOCIAL_REPLY = {
    "eng": "Hi! Ready? Tell me what you need for this problem, or ask for a hint.",
    "cat": "Hola! Preparat? Digues què necessites per a aquest problema, o demana una pista.",
    "esp": "¡Hola! ¿Listo? Dime qué necesitas para este problema, o pide una pista.",
}
LOCKED = {
    "eng": "Let's use the buttons: hint or next problem.",
    "cat": "Fem servir els botons: pista o següent problema.",
    "esp": "Usemos los botones: pista o siguiente problema.",
}


def clean(text):
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text))[:MAX_INPUT]
    return re.sub(r"\s+", " ", strip_accents(text.lower())).strip()


# "B", "(b)", "option b", "crec que és la B", "la resposta és b", "creo que es la c": a choice.
# Anchored to the whole text, so "a la granja" is never read as the letter A.
CHOICE = re.compile(r"^(?:(?:jo )?(?:crec|penso|diria|creo|pienso|i think)(?: que| it)?\s+)?"
                    r"(?:(?:es|seria|is|sera)\s+)?(?:(?:la|el|l'|the)\s*)?"
                    r"(?:(?:opcio|opcion|resposta|respuesta|lletra|letra|option|answer|letter)\s+)?"
                    r"(?:(?:es|is|:)\s*)?(?:(?:la|el|the)\s+)?"
                    r"\(?([a-e])\)?[.!]?$")


def choice_letter(text):
    """The letter A-E the student chose, or None if the text is not a choice."""
    match = CHOICE.match(clean(text))
    return match.group(1).upper() if match else None


def _has(text, phrases):
    return any(re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", text) for p in phrases)


def _starts(text, phrases):
    return any(re.search(r"(?<!\w)" + re.escape(p), text) for p in phrases)


def _problem_words(problem):
    base = problem.get("text", "") + " " + " ".join(str(v) for v in (problem.get("options") or {}).values())
    return {w for w in re.findall(r"[^\W\d_]{4,}", strip_accents(base.lower()))}


def classify(text, problem):
    """Return an intent name, 'math', 'social' or 'offtopic' (no state, no reply)."""
    t = clean(text)
    if not t:
        return "offtopic"
    if _has(t, INJECTION) or "http" in t:
        return "injection"
    if choice_letter(t):
        return "eleccion"
    for intent, phrases in INTENTS.items():
        if _has(t, phrases):
            return intent
    words = set(re.findall(r"[^\W\d_]{4,}", t))
    shares_problem = bool(words & _problem_words(problem))
    has_lexicon = any(w.startswith(m) for w in words for m in MATH_WORDS if len(m) >= 4) \
        or any(m in t for m in ("how many",)) or bool(words & {"par", "mitjana"})
    nums = numbers_in(t)
    foreign = nums - numbers_in(problem.get("text", "") + " " + " ".join(str(v) for v in (problem.get("options") or {}).values()))
    foreign -= {"1", "2", "3", "4", "5", "10"}
    if foreign and _starts(t, HOMEWORK) and not shares_problem:
        return "offtopic"  # maths, but not the student's current problem
    if shares_problem or has_lexicon:
        return "math"
    if nums and len(t.split()) <= 6 and not _starts(t, HOMEWORK):
        return "math"  # a short attempt such as "6+6", "12" or "creo que es 6+6"
    if _has(t, SOCIAL):
        return "social"
    return "offtopic"


def check_input(text, problem, state=None):
    """Return {"ok", "intent", "reply", "state"}.

    state = {"streak": int}: consecutive redirects. After LOCK_AFTER the app should
    stop accepting free text and show only buttons (reply is the locked message).
    """
    state = dict(state or {})
    streak = int(state.get("streak", 0))
    language = problem.get("language") if problem.get("language") in REDIRECT else "eng"
    try:
        intent = classify(text, problem)
    except Exception:  # noqa: BLE001 - fail closed: redirect
        intent = "offtopic"
    if intent in ("offtopic", "injection"):
        streak += 1
        locked = streak >= LOCK_AFTER
        return {"ok": False, "intent": intent, "locked": locked,
                "reply": (LOCKED if locked else REDIRECT)[language], "state": {"streak": streak}}
    if intent == "social":
        return {"ok": False, "intent": "social", "locked": False,
                "reply": SOCIAL_REPLY[language], "state": {"streak": 0}}
    return {"ok": True, "intent": intent, "locked": False, "reply": "", "state": {"streak": 0}}
