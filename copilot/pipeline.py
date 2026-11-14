"""The baseline copilot: one problem in, one letter out.

This is the file to change first. predict.py and eval.py both call solve(),
so whatever you build here is exactly what the official run measures.
"""
import json
import math
import socket
import time
import urllib.error

from .config import CONFIG
from .llm import URL, answer_letter, answer_scores

TIME_LIMIT = float(CONFIG["TIME_LIMIT_SECONDS"])
FALLBACK = CONFIG["FALLBACK_ANSWER"]
MARGIN = 3.0  # seconds kept free for Python and for writing the answer


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
            result["prompt_tokens"] = timings.get("prompt_n", 0)
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
    try:
        prior = str(CONFIG.get("NO_OPTIONS_PRIOR", "")).strip().upper()
        if prior in tuple("ABCDE") and not problem.get("options") and not image_b64:
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
        remaining = time_limit - (time.perf_counter() - start) - MARGIN
        if bias is None and orders == 1:
            result["passes"] = 1
            letter, timings = answer_letter(problem, examples, timeout=max(remaining, 1.0),
                                            image_b64=image_b64, url=llm_url)
            result["prompt_tokens"] = timings.get("prompt_n", 0)
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
    result["seconds"] = round(time.perf_counter() - start, 2)
    return result
