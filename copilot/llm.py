"""Ask the small language model for one letter, A to E."""
from urllib.parse import urlsplit

from .config import CONFIG
from .client import post
from .find_letter import find_letter

URL = f"http://127.0.0.1:{CONFIG['LLM_PORT']}/v1/chat/completions"

# Keep the system prompt stable: llama-server caches the start of the prompt,
# so text that never changes is only read once.
SYSTEM = ("You solve multiple-choice math competition problems for school students. "
          "Read the problem and the options, then reply with the letter of the correct option.")


def format_problem(problem, sees_image=False):
    lines = [problem["text"].strip()]
    options = problem.get("options") or {}
    for letter in "ABCDE":
        if letter in options:
            lines.append(f"{letter}) {options[letter]}")
    if not options:
        lines.append("(The options are in the picture.)" if sees_image else
                     "(The options are in a picture that you can't see. Pick the most likely letter.)")
    return "\n".join(lines)


def build_messages(problem, examples=(), image_b64=None):
    """image_b64 is a PNG as base64 text. Only a server started with --mmproj can see it."""
    messages = [{"role": "system", "content": SYSTEM}]
    for ex in examples:  # solved problems retrieved with RAG, if any
        messages.append({"role": "user", "content": format_problem(ex) + "\nAnswer:"})
        messages.append({"role": "assistant", "content": ex["label"]})
    text = format_problem(problem, sees_image=bool(image_b64)) + "\nAnswer:"
    if image_b64:
        content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
                   {"type": "text", "text": text}]
    else:
        content = text
    messages.append({"role": "user", "content": content})
    return messages


def _payload(problem, examples, image_b64, logprobs=False):
    payload = {
        "messages": build_messages(problem, examples, image_b64),
        "grammar": "root ::= [A-E]",
        "max_tokens": 1,
        "temperature": 0,
        "seed": int(CONFIG["SEED"]),
        "cache_prompt": True,
    }
    if logprobs:
        payload["logprobs"] = True
        payload["top_logprobs"] = 60
    return payload


def answer_letter(problem, examples=(), timeout=60, image_b64=None, url=URL):
    """Return (letter, timings). The grammar makes any other output impossible."""
    response = post(url, _payload(problem, examples, image_b64), timeout=timeout)
    letter = response["choices"][0]["message"]["content"].strip()
    return letter, response.get("timings", {})


def letter_logprobs(response):
    """{"A": lp, ..., "E": lp} from a response asked with logprobs, or None if it has none.

    These are the model's probabilities before the grammar, so a letter can be
    missing from the top list: it gets (lowest logprob listed) - 1.
    """
    try:
        top = response["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
        found, lowest = {}, None
        for entry in top:
            lp = float(entry["logprob"])
            lowest = lp if lowest is None else min(lowest, lp)
            token = str(entry["token"]).strip()
            if len(token) == 1 and token in "ABCDE" and token not in found:
                found[token] = lp
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    if not found:
        return None
    floor = lowest - 1.0
    return {c: found.get(c, floor) for c in "ABCDE"}


def answer_scores(problem, examples=(), timeout=60, image_b64=None, url=URL):
    """Return (letter, {"A": logprob, ..., "E": logprob}, timings), asking for logprobs.

    Without usable logprobs the grammar's letter gets 0 and the others -20.
    """
    response = post(url, _payload(problem, examples, image_b64, logprobs=True), timeout=timeout)
    letter = response["choices"][0]["message"]["content"].strip()
    scores = letter_logprobs(response)
    if scores is None:
        scores = {c: (0.0 if c == letter else -20.0) for c in "ABCDE"}
    return letter, scores, response.get("timings", {})


REASON_GRAMMAR = 'root ::= line ("\\n" line)* "\\nAnswer: " [A-E]\nline ::= [^\\n]+'


def answer_reasoned(problem, examples=(), timeout=60, image_b64=None, url=URL, max_tokens=160):
    """Return (letter or "", timings, text): one line of working, then "Answer: <letter>".

    For a model fine-tuned to write its working first. The letter is "" when the
    model ran out of tokens before the answer line: the caller decides what to do.
    """
    payload = _payload(problem, examples, image_b64)
    payload["grammar"] = REASON_GRAMMAR
    payload["max_tokens"] = int(max_tokens)
    response = post(url, payload, timeout=timeout)
    text = response["choices"][0]["message"]["content"]
    tail = text.rsplit("\nAnswer: ", 1)
    letter = tail[1].strip() if len(tail) == 2 else ""
    return (letter if len(letter) == 1 and letter in "ABCDE" else ""), response.get("timings", {}), text


THINK_SYSTEM = ("You solve multiple-choice math competition problems for school students. "
                "Work it out step by step, briefly and in plain text, then finish with a line "
                "'Answer: <letter>'.")


def working_messages(problem, examples=(), image_b64=None, mode="reason"):
    """The messages that ask for working: the tuned model's prompt ("reason") or THINK_SYSTEM ("think")."""
    messages = build_messages(problem, examples, image_b64)
    if mode == "think":
        messages[0] = {"role": "system", "content": THINK_SYSTEM}
        last = messages[-1]
        if isinstance(last["content"], str) and last["content"].endswith("\nAnswer:"):
            last["content"] = last["content"][: -len("\nAnswer:")]
    return messages


def answer_thinking(problem, examples=(), timeout=60, image_b64=None, url=URL, max_tokens=250):
    """Return (letter or "", timings, text): free working by an untuned model, then "Answer: <letter>".

    No grammar: the model may use several lines. The letter is the last answer it stated
    (copilot.find_letter), or "" if it ran out of tokens first.
    """
    payload = {"messages": working_messages(problem, examples, image_b64, "think"),
               "max_tokens": int(max_tokens), "temperature": 0,
               "seed": int(CONFIG["SEED"]), "cache_prompt": True}
    response = post(url, payload, timeout=timeout)
    text = response["choices"][0]["message"]["content"]
    return find_letter(text), response.get("timings", {}), text


# Working under a token budget. The prompt is rendered once by the server, so that its size is known
# before anything is written and the letter can be asked as a continuation of the working.

def server_base(url):
    """"http://host:port" of a chat completions URL."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def render_prompt(messages, timeout=10, url=URL):
    """Return (prompt, prompt_tokens): the chat template applied by the server, and its size in tokens."""
    base = server_base(url)
    prompt = post(base + "/apply-template", {"messages": messages}, timeout=timeout)["prompt"]
    tokens = post(base + "/tokenize", {"content": prompt}, timeout=timeout)["tokens"]
    if not isinstance(prompt, str) or not prompt or not isinstance(tokens, list) or not tokens:
        raise ValueError("the server did not render or count the prompt")
    return prompt, len(tokens)


def _completion(prompt, tokens, grammar, timeout, url):
    payload = {"prompt": prompt, "n_predict": int(tokens), "temperature": 0, "seed": int(CONFIG["SEED"]),
               "cache_prompt": True}
    if grammar:
        payload["grammar"] = grammar
    return post(server_base(url) + "/completion", payload, timeout=timeout)


def stated_letter(text, mode="reason"):
    """The letter the working ends with, or "" when it did not get there.

    "reason": the grammar's last line, "Answer: X", and nothing else: a letter mentioned earlier in
    cut-off working is not an answer. "think": no grammar, so the last answer stated in any usual form.
    """
    if mode == "think":
        return find_letter(text)
    tail = (text or "").rsplit("\nAnswer: ", 1)
    letter = tail[1].strip() if len(tail) == 2 else ""
    return letter if len(letter) == 1 and letter in "ABCDE" else ""


def write_working(prompt, max_tokens, mode="reason", timeout=60, url=URL):
    """Return (text, tokens_written): the working, stopped after at most max_tokens tokens."""
    response = _completion(prompt, max_tokens, REASON_GRAMMAR if mode == "reason" else None, timeout, url)
    text = response.get("content", "")
    if not isinstance(text, str):
        raise ValueError("no text in the reply")
    return text, int(response.get("tokens_predicted", 0) or 0)


def open_working(text):
    """The working without trailing blanks and without a cut-off start of the answer line."""
    text = (text or "").rstrip()
    marker = "\nAnswer:"
    for n in range(len(marker), 1, -1):
        if text.endswith(marker[:n]):
            return text[:-n].rstrip()
    return text


def force_letter(prompt, text, timeout=60, url=URL):
    """The letter the model gives right after its unfinished working: one token, grammar [A-E]."""
    response = _completion(prompt + open_working(text) + "\nAnswer: ", 1, "root ::= [A-E]", timeout, url)
    letter = str(response.get("content", "")).strip()[:1]
    if len(letter) != 1 or letter not in "ABCDE":
        raise ValueError(f"not a letter A to E: {letter!r}")
    return letter
