"""Ask the small language model (Qwen, llama-server on port 8081) for a one-sentence answer.

Standard library only, and no import of config.env, so the App Lab app can use it
as is. The caller must check the text with copilot.guardrails before a student
sees it: this module only asks and measures.
"""
import json
import os
import time
import urllib.request

LLM_URL = os.environ.get("LLM_URL", "http://127.0.0.1:8081") + "/v1/chat/completions"

# What the model is asked to do, and why only that. Measured with the model on 48 questions that
# children would type about 6 problems (data/newproblem/chat):
#  - Asked to invent a hint, it restated the question or wrote nonsense.
#  - Given the teacher's notes on the problem, it explains what a word or a phrase of the statement
#    means well enough: 6 of 6 answers passed the guardrails and read as sensible.
#  - On "what do I do now?", "is 8 right?" or "why not?" it states false things with confidence
#    ("No, Berta isn't the 8th"), and the guardrails can check leaks and format, not truth.
# So the assistant sends it questions about meaning only, and answers the rest with written help.
SYSTEM = {
    "cat": ("Ets un tutor de matemàtiques per a nens de 10 a 12 anys. Respon la pregunta de l'alumne amb UNA "
            "frase curta i clara, en català. Fes servir les notes del professor. No diguis mai el resultat "
            "del problema."),
    "eng": ("You are a maths tutor for children aged 10 to 12. Answer the student's question in ONE short, "
            "clear sentence. Use the teacher's notes. Never say the result of the problem."),
}
LABEL = {"cat": ("Problema: ", "Notes del professor: ", "L'alumne pregunta: ", "Què vol dir l'enunciat?"),
         "eng": ("Problem: ", "Teacher's notes: ", "The student asks: ", "What does the problem say?")}
READ = {"cat": "Llegit.", "eng": "Read."}
NOTES = ("key_data", "key_condition")  # from the problem's anatomy: never the first step or the solution


def build_messages(problem, student_text=""):
    """The request: the statement and the teacher's notes as a first turn, the student's words as a second.

    The statement is a turn of its own on purpose. llama-server can only go back to what it had read
    at the end of a message, so with the statement and the student's words in one message it read the
    statement again for every question. Measured on the board: 36 new tokens instead of 101, and
    6 seconds instead of 12.
    """
    language = problem.get("language") if problem.get("language") in SYSTEM else "eng"
    problem_label, notes_label, ask_label, default = LABEL[language]
    statement = problem_label + (problem.get("question") or problem.get("text", ""))
    figure = (problem.get("figure") or {}).get(language)
    if figure:
        statement += ("\nFigura: " if language == "cat" else "\nFigure: ") + figure
    anatomy = problem.get("anatomy") or {}
    notes = " ".join(str(anatomy[k]) for k in NOTES if anatomy.get(k))
    if notes:
        statement += "\n" + notes_label + notes
    return [{"role": "system", "content": SYSTEM[language]}, {"role": "user", "content": statement},
            {"role": "assistant", "content": READ[language]},
            {"role": "user", "content": ask_label + (student_text or default)}]


def warm(problem, timeout=60, url=LLM_URL):
    """Have the model read the statement now, so a later question only pays for the student's words.

    llama-server keeps what it has just read (cache_prompt) and a later request reuses it up to
    the end of the statement's turn. Reading is most of the wait: about 11 tokens per second.
    Returns {"seconds", "prompt_tokens", "error"}. Never raises.
    """
    start = time.perf_counter()
    payload = {"messages": build_messages(problem), "max_tokens": 1, "temperature": 0,
               "seed": 42, "cache_prompt": True}
    try:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            timings = json.loads(response.read()).get("timings", {})
        return {"seconds": round(time.perf_counter() - start, 1), "prompt_tokens": timings.get("prompt_n"),
                "error": None}
    except Exception as error:  # noqa: BLE001 - warming is a convenience, the lesson goes on without it
        return {"seconds": round(time.perf_counter() - start, 1), "prompt_tokens": None,
                "error": f"{type(error).__name__}: {error}"}


def ask_hint(problem, student_text="", timeout=50, url=LLM_URL):
    """Return {"text", "seconds", "prompt_tokens", "error"}. Never raises."""
    start = time.perf_counter()
    payload = {"messages": build_messages(problem, student_text), "max_tokens": 60, "temperature": 0,
               "seed": 42, "cache_prompt": True, "stop": ["\n"]}
    try:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            reply = json.loads(response.read())
        text = reply["choices"][0]["message"]["content"].strip()
        timings = reply.get("timings", {})
        return {"text": text, "seconds": round(time.perf_counter() - start, 1),
                "prompt_tokens": timings.get("prompt_n"), "cached_tokens": timings.get("cache_n"),
                "generated_tokens": timings.get("predicted_n"), "error": None}
    except Exception as error:  # noqa: BLE001 - the lesson goes on without the model
        return {"text": "", "seconds": round(time.perf_counter() - start, 1), "prompt_tokens": None,
                "generated_tokens": None, "error": f"{type(error).__name__}: {error}"}
