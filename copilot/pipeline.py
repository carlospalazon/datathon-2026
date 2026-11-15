"""The baseline copilot: one problem in, one letter out.

This is the file to change first. predict.py and eval.py both call solve(),
so whatever you build here is exactly what the official run measures.
"""
import json
import math
import os
import socket
import time
import urllib.error

from . import presolve as presolver
from . import prior as letter_prior
from .config import CONFIG, ROOT
from .llm import (URL, answer_letter, answer_reasoned, answer_scores, answer_thinking, force_letter,
                  render_prompt, stated_letter, working_messages, write_working)

TIME_LIMIT = float(CONFIG["TIME_LIMIT_SECONDS"])
FALLBACK = CONFIG["FALLBACK_ANSWER"]
MARGIN = 3.0  # seconds kept free for Python and for writing the answer
FIXED_WORKING_TOKENS = 160  # the cap on the working when the server cannot count the prompt
_PRESOLVE_INDEX = {}  # path -> index, or the name of the error that stopped it being built
_PRIOR_TABLE = {}  # path -> table, or the name of the error that stopped it being loaded


def _speed(name, default):
    try:
        value = float(str(CONFIG.get(name, "")).strip())
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


def token_budget(prompt_tokens, time_limit=TIME_LIMIT):
    """Tokens the model may write for this prompt inside the limit, at the board's speeds.

    Computed, never timed: the same prompt gets the same budget on any machine.
    """
    read, write = _speed("BOARD_READ_TPS", 11.0), _speed("BOARD_WRITE_TPS", 6.0)
    return max(int((time_limit - MARGIN - prompt_tokens / read) * write), 0)


def _token_cap():
    try:
        return max(int(str(CONFIG.get("REASON_MAX_TOKENS", "")).strip() or 0), 0)
    except ValueError:
        return 0


def _twin_solutions():
    """{(id, language): checked worked solution} from the PRESOLVE_SOLUTIONS files, or {} if there are none."""
    table = {}
    for path in str(CONFIG.get("PRESOLVE_SOLUTIONS", "") or "").split(","):
        path = path.strip()
        if not path:
            continue
        try:
            with open(path if os.path.isabs(path) else os.path.join(ROOT, path), encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        row = json.loads(line)
                        table[(row["id"], row.get("language"))] = row["rationale"]
        except Exception:  # noqa: BLE001  a missing or broken file means no solutions, never a failed run
            continue
    return table


def _presolved(problem, exclude_id, result):
    """A copied answer from copilot.presolve, or None. Never raises: no index means no answer."""
    path = str(CONFIG.get("PRESOLVE_DATA", "") or "data/train.jsonl")
    path = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if path not in _PRESOLVE_INDEX:
        try:
            with open(path, encoding="utf-8") as f:
                problems = [json.loads(line) for line in f if line.strip()]
            _PRESOLVE_INDEX[path] = presolver.build(problems, _twin_solutions())
        except Exception as error:  # noqa: BLE001
            _PRESOLVE_INDEX[path] = type(error).__name__
    index = _PRESOLVE_INDEX[path]
    if isinstance(index, str):
        result["presolve_error"] = index
        return None
    try:
        return presolver.presolve(problem, index, exclude_id=exclude_id)
    except Exception as error:  # noqa: BLE001
        result["presolve_error"] = type(error).__name__
        return None


def _prior_letter(problem, result):
    """The letter of copilot.prior (counts from the training split, no model), or None. Never raises."""
    path = str(CONFIG.get("PRIOR_TABLE", "") or "copilot/prior_table.json")
    path = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if path not in _PRIOR_TABLE:
        try:
            _PRIOR_TABLE[path] = letter_prior.load(path)
        except Exception as error:  # noqa: BLE001
            _PRIOR_TABLE[path] = type(error).__name__
    table = _PRIOR_TABLE[path]
    if isinstance(table, str):
        result["prior_error"] = table
        return None
    try:
        letter, _scores = letter_prior.choose(problem, table)
    except Exception as error:  # noqa: BLE001
        result["prior_error"] = type(error).__name__
        return None
    return letter if letter in tuple("ABCDE") else None


def save_text(problem, result, text, mode):
    """Append the written working to the SAVE_TEXTS file. It quotes the problem: results/ only."""
    path = str(CONFIG.get("SAVE_TEXTS", "") or "").strip()
    if not path:
        return
    try:
        path = os.path.realpath(path if os.path.isabs(path) else os.path.join(ROOT, path))
        root, results = os.path.realpath(ROOT), os.path.realpath(os.path.join(ROOT, "results"))
        if path.startswith(root + os.sep) and not path.startswith(results + os.sep):
            raise ValueError("inside the repository only results/ may hold texts")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        row = {"id": problem.get("id"), "language": problem.get("language"), "mode": mode,
               "answer": result["answer"],
               **{k: result.get(k) for k in ("letter_from", "finished", "prompt_tokens", "budget_tokens",
                                             "written_tokens", "working")},
               "text": text}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as error:  # noqa: BLE001
        result["save_error"] = f"{type(error).__name__}: {error}"[:100]


def _work(problem, examples, image_b64, llm_url, mode, time_limit, left, result):
    """Working first, then the letter. Return (letter or "", text); never raises.

    The size of the working is a token budget from the prompt's size, not elapsed time. If the working
    ends without an answer, the letter is asked as its continuation (one token). "" means every step
    here failed and the caller asks the plain one-letter question.
    """
    letter, text, prompt, cap = "", "", None, _token_cap()
    result["passes"] = 1
    if image_b64:
        result["budget_error"] = "image"  # a rendered text prompt cannot carry the picture
    else:
        try:
            prompt, prompt_tokens = render_prompt(working_messages(problem, examples, None, mode),
                                                  timeout=max(left(), 1.0), url=llm_url)
        except Exception as error:  # noqa: BLE001
            result["budget_error"] = type(error).__name__
    try:
        if prompt is None:
            # The server cannot count the prompt: a fixed number of tokens, still no clock.
            allowed = cap or FIXED_WORKING_TOKENS
            result.update(working="fixed", budget_tokens=allowed)
            ask = answer_reasoned if mode == "reason" else answer_thinking
            letter, timings, text = ask(problem, examples, timeout=max(left(), 1.0), image_b64=image_b64,
                                        url=llm_url, max_tokens=allowed)
            result["prompt_tokens"] = timings.get("prompt_n", 0)
            result["written_tokens"] = timings.get("predicted_n", 0)
            result["finished"] = bool(letter)
        else:
            allowed = token_budget(prompt_tokens, time_limit)
            allowed = min(allowed, cap) if cap else allowed
            result.update(working="budget", budget_tokens=allowed, prompt_tokens=prompt_tokens,
                          written_tokens=0, finished=False)
            if allowed > 1:
                text, result["written_tokens"] = write_working(prompt, allowed - 1, mode,
                                                               timeout=max(left(), 1.0), url=llm_url)
                letter = stated_letter(text, mode)
                result["finished"] = bool(letter)
            if not letter:
                letter = force_letter(prompt, text, timeout=max(left(), 1.0), url=llm_url)
                result["written_tokens"] += 1
                result["letter_from"] = "forced"
        if letter and "letter_from" not in result:
            result["letter_from"] = "working"
    except Exception as error:  # noqa: BLE001
        result["pass_error"] = f"{mode}: {type(error).__name__}"
        letter = ""
    result["answer_tokens"] = result.get("written_tokens", 0)
    result["reasoned"] = bool(letter)
    return letter, text


def load_bias(path):
    """{"A": x, ..., "E": x} from a JSON file, or None if unset, missing or malformed."""
    if not path:
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        bias = {c: float(data[c]) for c in "ABCDE"}
        return bias if all(math.isfinite(v) for v in bias.values()) else None
    except Exception:  # noqa: BLE001
        return None


def parse_orders(value):
    try:
        return min(max(int(str(value).strip()), 1), 5)
    except ValueError:
        return 1


def shifted(problem, s):
    """The problem with the option shown at position j being the original one at (j+s) % 5."""
    if s == 0:
        return problem
    options = problem["options"]
    return {**problem, "options": {"ABCDE"[j]: options["ABCDE"[(j + s) % 5]] for j in range(5)}}


def _ask_orders(problem, examples, image_b64, llm_url, bias, orders, start, time_limit, remaining, result):
    """Ask with logprobs, once per option order while time allows; answer from the summed scores."""
    offsets = bias or {c: 0.0 for c in "ABCDE"}
    parts = {c: [] for c in "ABCDE"}  # original letter -> corrected logprob of each pass
    slowest = 0.0
    for s in range(orders):
        began = time.perf_counter()
        if s:
            left = time_limit - MARGIN - (began - start)
            if left < 1.3 * slowest:
                break
            remaining = left
        result["passes"] += 1
        try:
            letter, lps, timings = answer_scores(shifted(problem, s), examples,
                                                 timeout=max(remaining, 1.0),
                                                 image_b64=image_b64, url=llm_url)
            if len(letter) != 1 or letter not in "ABCDE":
                raise ValueError(f"not a letter A to E: {letter[:20]!r}")
        except Exception as error:  # noqa: BLE001
            if s == 0:
                raise
            result["pass_error"] = f"{type(error).__name__}: {error}"[:100]
            break
        slowest = max(slowest, time.perf_counter() - began)
        if s == 0:
            result["prompt_tokens"] = result["prompt_tokens"] or timings.get("prompt_n", 0)
        for o, c in enumerate("ABCDE"):
            p = "ABCDE"[(o - s) % 5]
            parts[c].append(lps[p] - offsets[p])
    totals = {c: math.fsum(v) for c, v in parts.items()}
    result["logprobs"] = totals
    result["answer"] = max("ABCDE", key=lambda c: totals[c])


def solve(problem, index=None, k=0, exclude_id=None, image_b64=None, llm_url=URL,
          time_limit=TIME_LIMIT):
    """Return {"answer", "seconds", "status", ...} for one problem.

    index and k turn on retrieval: the k most similar solved problems are
    added to the prompt as examples. Each example costs reading time.
    image_b64 and llm_url send the problem image to a vision server.
    """
    start = time.perf_counter()
    result = {"answer": FALLBACK, "status": "ok", "prompt_tokens": 0, "retrieved": "", "examples": [],
              "logprobs": {}, "passes": 0, "retrieval_error": ""}
    text, mode = "", ""
    try:
        prior = str(CONFIG.get("NO_OPTIONS_PRIOR", "")).strip().upper()
        prior_answers = prior in tuple("ABCDE") and not problem.get("options") and not image_b64
        # ANSWER_PRIOR=1: every problem is answered from the table of copilot.prior, no model call.
        table_answers = str(CONFIG.get("ANSWER_PRIOR", "")).strip() == "1"
        if str(CONFIG.get("PRESOLVE", "")).strip() == "1":
            hit = _presolved(problem, exclude_id, result)
            if hit:
                result["answer"] = hit["answer"]
                result["status"] = "presolve"
                result["presolve"] = f"{hit['kind']}:{hit['source']}:{hit['similarity']}"
                if hit.get("solution"):  # the twin's checked solution: how it is solved, not only the letter
                    result["twin_solution"] = hit["solution"]
                result["seconds"] = round(time.perf_counter() - start, 2)
                return result
        if table_answers:
            letter = _prior_letter(problem, result)
            if letter:  # no table, or a broken one: the model answers as if the setting were off
                result["answer"] = letter
                result["status"] = "prior"
                result["seconds"] = round(time.perf_counter() - start, 2)
                return result
        if prior_answers:
            result["answer"] = prior
            result["status"] = "prior"
            result["seconds"] = round(time.perf_counter() - start, 2)
            return result
        bias = load_bias(CONFIG.get("LETTER_BIAS_FILE", ""))
        orders = parse_orders(CONFIG.get("OPTION_ORDERS", "1"))
        if len(problem.get("options") or {}) != 5 or set(problem["options"]) != set("ABCDE"):
            orders = 1
        examples = []
        if index is not None and k > 0:
            try:
                hits = index.search(problem, k=k, exclude_id=exclude_id)
                examples = [p for _score, p in hits]
                result["examples"] = hits
                result["retrieved"] = ";".join(f"{p['id']}:{s:.2f}" for s, p in hits)
            except Exception as error:  # noqa: BLE001
                # No examples is a weaker prompt, not a reason to skip the model.
                result["retrieval_error"] = type(error).__name__

        def left():
            return time_limit - (time.perf_counter() - start) - MARGIN

        reasoned = ""
        mode = str(CONFIG.get("ANSWER_MODE", "")).strip().lower()
        if mode in ("reason", "think") and problem.get("options"):
            reasoned, text = _work(problem, examples, image_b64, llm_url, mode, time_limit, left, result)
            if not reasoned:
                result["letter_from"] = "direct"
        remaining = left()
        if reasoned:
            result["answer"] = reasoned
        elif bias is None and orders == 1:
            result["passes"] = 1
            letter, timings = answer_letter(problem, examples, timeout=max(remaining, 1.0),
                                            image_b64=image_b64, url=llm_url)
            result["prompt_tokens"] = result["prompt_tokens"] or timings.get("prompt_n", 0)
            if len(letter) == 1 and letter in "ABCDE":
                result["answer"] = letter
            else:
                result["status"] = f"error: not a letter A to E: {letter[:20]!r}"
        else:
            _ask_orders(problem, examples, image_b64, llm_url, bias, orders, start, time_limit, remaining, result)
    except (socket.timeout, TimeoutError):
        result["status"] = "timeout"
    except urllib.error.URLError as error:
        if isinstance(error.reason, (socket.timeout, TimeoutError)):
            result["status"] = "timeout"
        else:
            result["status"] = f"error: {error.reason}"
    except Exception as error:  # noqa: BLE001
        # A server killed mid-request, a malformed reply, a bug: the official run
        # must still write one letter for this problem and go on to the next one.
        result["status"] = f"error: {type(error).__name__}: {error}"[:200]
    if text:
        save_text(problem, result, text, mode)
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result
