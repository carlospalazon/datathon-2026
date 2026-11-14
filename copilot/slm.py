"""Ask the small language model (Qwen, llama-server on port 8081) for a one-sentence hint.

Standard library only, and no import of config.env, so the App Lab app can use it
as is. The caller must check the text with copilot.guardrails before a student
sees it: this module only asks and measures.
"""
import json
import os
import time
import urllib.request

LLM_URL = os.environ.get("LLM_URL", "http://127.0.0.1:8081") + "/v1/chat/completions"

# Keep the system prompt fixed: llama-server keeps the start of the prompt in its
# cache, so this part is read once and later hints only pay for the new tokens.
# Measured on the board (6 demo problems): with examples and the grammar below, 5/6
# hints passed the guardrails against 3/6 with plain instructions, and none gave
# a number away. Many still just restate the question: the assistant checks that.
SYSTEM = {
    "cat": ("Ets un tutor de matemàtiques per a nens de 10 a 12 anys. No resols mai el problema: "
            "fas UNA pregunta curta que ajuda l'alumne a fer el primer pas. Sense números.\n\n"
            "Exemples:\n"
            "Problema: La Laia té 3 capses amb 5 llapis a cada una i en regala 4. Quants llapis li queden?\n"
            "Pregunta: Quants llapis té en total abans de regalar-ne cap?\n"
            "Problema: Un tren surt a les 9 i arriba a les 11 i quart. Quant dura el viatge?\n"
            "Pregunta: Quantes hores completes passen entre la sortida i l'arribada?\n"
            "Problema: Quants números de dues xifres tenen les xifres que sumen 6?\n"
            "Pregunta: Si la primera xifra és la més petita possible, quina ha de ser la segona?"),
    "eng": ("You are a maths tutor for children aged 10 to 12. You never solve the problem: you ask "
            "ONE short question that helps the student take the first step. No numbers.\n\n"
            "Examples:\n"
            "Problem: Laia has 3 boxes with 5 pencils in each and gives 4 away. How many pencils are left?\n"
            "Question: How many pencils does she have before giving any away?\n"
            "Problem: A train leaves at 9 and arrives at a quarter past 11. How long is the journey?\n"
            "Question: How many whole hours pass between leaving and arriving?"),
}
LABEL = {"cat": ("Problema: ", "Pregunta:"), "eng": ("Problem: ", "Question:")}
# One question, no digits (so no result or calculation), ending with "?"
GRAMMAR = 'root ::= [A-ZÀ-Ú¿] [^0-9?\\n]{15,150} "?"'


READ = {"cat": "Llegit.", "eng": "Read."}


def build_messages(problem, student_text=""):
    """The request for a hint: the statement as a first turn, what the student wrote as a second one.

    The statement is a turn of its own on purpose. llama-server can only go back to what it had read
    at the end of a message, so with the statement and the student's words in one message it read the
    statement again for every question. Measured on the board: 36 new tokens instead of 101, and
    6 seconds instead of 12.
    """
    language = problem.get("language") if problem.get("language") in SYSTEM else "eng"
    problem_label, question_label = LABEL[language]
    statement = problem_label + (problem.get("question") or problem.get("text", ""))
    figure = (problem.get("figure") or {}).get(language)
    if figure:
        statement += ("\nFigura: " if language == "cat" else "\nFigure: ") + figure
    ask = question_label
    if student_text:
        ask = ("L'alumne diu: " if language == "cat" else "The student says: ") + student_text + "\n" + ask
    return [{"role": "system", "content": SYSTEM[language]}, {"role": "user", "content": statement},
            {"role": "assistant", "content": READ[language]}, {"role": "user", "content": ask}]


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
               "seed": 42, "cache_prompt": True, "grammar": GRAMMAR}
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
