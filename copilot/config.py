"""Read config.env, the settings file shared with the board scripts."""
import os
import shlex

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Settings the settings file may not define. All are off. The file overrides
# these, the environment overrides both.
DEFAULTS = {
    "NO_OPTIONS_PRIOR": "",   # a letter: answer problems without options with it, no model call
    "LETTER_BIAS_FILE": "",   # JSON {"A": x, ..., "E": x}: per-letter log-probability offsets
    "OPTION_ORDERS": "1",     # 1..5 cyclic option orders to ask, time permitting
    "ANSWER_MODE": "",        # "reason": one line of working, then the letter (a model tuned for it);
                              # "think": free step-by-step working, then the letter (an untuned model)
    "REASON_MAX_TOKENS": "",  # an extra cap on the working, in tokens; empty means the token budget alone
                              # (and 160 when the server cannot count the prompt)
    # The board's speeds for the model in use, in tokens per second. In the two modes above the working
    # may use (TIME_LIMIT_SECONDS - 3 - prompt_tokens / READ) * WRITE tokens: tokens, not a clock.
    "BOARD_READ_TPS": "11",
    "BOARD_WRITE_TPS": "6",
    "SAVE_TEXTS": "",         # a file under results/: append each problem's written working (JSON Lines).
                              # It quotes problems: never commit it.
    "PRESOLVE": "",           # "1": copy the answer value of a near-identical training problem, no model
    "PRESOLVE_DATA": "data/train.jsonl",  # training problems only, never data/demo or data/val.jsonl
}


def load(path=os.path.join(ROOT, "config.env")):
    values = dict(DEFAULTS)
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw = line.split("=", 1)
            parts = shlex.split(raw, comments=True)
            values[key.strip()] = os.path.expanduser(parts[0]) if parts else ""
    # Environment variables win, so you can try a setting without editing the file
    for key in values:
        if key in os.environ:
            values[key] = os.environ[key]
    return values


CONFIG = load()
