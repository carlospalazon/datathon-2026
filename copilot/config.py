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
    "ANSWER_MODE": "",        # "reason": one line of working before the letter (needs a model tuned for it)
    "REASON_MAX_TOKENS": "160",
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
