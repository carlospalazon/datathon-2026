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
SYSTEM = {
    "cat": ("Ets un tutor de matemàtiques per a nens de 10 a 12 anys. Escriu UNA sola frase curta "
            "(màxim 25 paraules) en català que ajudi l'alumne a començar el problema. "
            "No diguis mai la resposta, cap resultat ni cap lletra d'opció. No facis càlculs. "
            "Fes-li una pregunta o digues-li en què s'ha de fixar."),
    "eng": ("You are a maths tutor for children aged 10 to 12. Write ONE short sentence (at most "
            "25 words) in English that helps the student start the problem. Never say the answer, "
            "any result or any option letter. Don't calculate. Ask a question or say what to look at."),
}


def build_messages(problem, student_text=""):
    language = problem.get("language") if problem.get("language") in SYSTEM else "eng"
    parts = [problem.get("question") or problem.get("text", "")]
    figure = (problem.get("figure") or {}).get(language)
    if figure:
        parts.append(("Figura: " if language == "cat" else "Figure: ") + figure)
    if student_text:
        parts.append(("L'alumne diu: " if language == "cat" else "The student says: ") + student_text)
    return [{"role": "system", "content": SYSTEM[language]}, {"role": "user", "content": "\n".join(parts)}]


def ask_hint(problem, student_text="", timeout=50, url=LLM_URL):
    """Return {"text", "seconds", "prompt_tokens", "error"}. Never raises."""
    start = time.perf_counter()
    payload = {"messages": build_messages(problem, student_text), "max_tokens": 60, "temperature": 0,
               "seed": 42, "cache_prompt": True}
    try:
        request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            reply = json.loads(response.read())
        text = reply["choices"][0]["message"]["content"].strip()
        timings = reply.get("timings", {})
        return {"text": text, "seconds": round(time.perf_counter() - start, 1),
                "prompt_tokens": timings.get("prompt_n"), "generated_tokens": timings.get("predicted_n"),
                "error": None}
    except Exception as error:  # noqa: BLE001 - the lesson goes on without the model
        return {"text": "", "seconds": round(time.perf_counter() - start, 1), "prompt_tokens": None,
                "generated_tokens": None, "error": f"{type(error).__name__}: {error}"}
