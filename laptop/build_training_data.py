#!/usr/bin/env python3
"""Build the fine-tuning data for the small maths model (standard library only).

Sources: the M3Kang training split (research use only: output stays in data/training/,
which is never committed), AQuA-RAT (Apache-2.0) and synthetic problems with computed
answers. Writes data/training/master.jsonl plus four chat-format exports
(letter / reasoning, each with a small dev file) and STATS.md.

Usage:
    .venv/bin/python laptop/build_training_data.py
    .venv/bin/python laptop/build_training_data.py --aqua 8000 --synthetic 6000 \
        --m3kang-copies 3 --seed 42 --rationales path/to/rationales.jsonl
"""
import argparse
import hashlib
import json
import math
import random
import re
import sys
import urllib.request
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from copilot.llm import SYSTEM, build_messages, format_problem  # noqa: E402
from laptop import synthetic_problems  # noqa: E402

AQUA_URL = "https://raw.githubusercontent.com/google-deepmind/AQuA/master/train.json"
MAX_PROMPT = 1100
MAX_RATIONALE = 350
MIN_AQUA_RATIONALE = 40
CHARS_PER_TOKEN = 3.5
BOARD_TOK_PER_S = 6
BOARD_WRITE_BUDGET_S = 40
LETTERS = "ABCDE"


# --------------------------------------------------------------------------- text helpers

def clean_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def norm(text):
    return "".join(ch for ch in text.lower() if ch.isalnum())


def norm_variants(text):
    """Normalised text, and the same without a leading question number ("13. ")."""
    out = [norm(text)]
    stripped = norm(re.sub(r"^\s*\d+\s*[.)]\s*", "", text))
    if stripped not in out:
        out.append(stripped)
    return [v for v in out if v]


def rng_for(seed, *parts):
    return random.Random(f"{seed}|" + "|".join(str(p) for p in parts))


# --------------------------------------------------------------------------- rationale cleaning

_END_PATTERNS = [
    re.compile(r"(?i)[\s,.;:\-\u2013]*\b(?:so|hence|thus|therefore)?[\s,]*(?:the\s+)?(?:correct\s+)?"
               r"(?:answer|ans|option|choice)\b\s*(?:is|=|:|-|\u2013)?\s*[\(\[]?(?-i:[A-E])[\)\]]?\s*\.?\s*$"),
    re.compile(r"(?i)[\s,.;:\-\u2013]*\b(?:hence|so|thus|therefore)\b\s*[\(\[]?(?-i:[A-E])[\)\]]\s*\.?\s*$"),
    re.compile(r"(?i)[\s,.;:\-\u2013]*\b(?:hence|so|thus|therefore)\b\s+(?-i:[A-E])\s*\.?\s*$"),
    re.compile(r"[\s,.;:\-\u2013]*\((?-i:[A-E])\)\s*\.?\s*$"),
    re.compile(r"^\s*\(?(?-i:[A-E])\)?\s*\.?\s*$"),
]

_REF_PATTERNS = [
    re.compile(r"(?-i:\([A-E]\))"),
    re.compile(r"(?-i:\b[A-E]\))"),
    re.compile(r"(?i:\b(?:option|options|choice|choices|answer|answers|ans|opci[oó]n?|opcions|opciones|"
               r"resposta|respuesta)\b)\s*[:=\-]?\s*\(?(?-i:[A-E])\b"),
    re.compile(r"[.\s)=:](?-i:[A-E])\.?$"),  # a letter left at the very end, e.g. "= 75.E"
    re.compile(r"(?-i:\b[A-E]\b)\s*(?i:is|are|es|son|\u00e9s)\s+(?i:wrong|incorrect|correct|right|false|true|"
               r"the\s+(?:answer|correct))"),
]


_ANSWER_WORD = re.compile(r"(?i)\b(?:answer|ans)\b")


def clean_rationale(raw):
    """One line, whitespace collapsed, trailing statements that declare the answer removed."""
    lines = [clean_ws(x) for x in (raw or "").splitlines() if x.strip()]
    while lines and re.fullmatch(r"\(?[A-E]\)?\.?", lines[-1]):
        lines.pop()  # a last line that is only a letter
    text = clean_ws(" ".join(lines))
    changed = True
    while changed and text:
        changed = False
        for pat in _END_PATTERNS:
            new = pat.sub("", text).strip()
            if new != text:
                text, changed = new, True
    return text


def refers_to_option(text):
    """True if the text names an option by its letter, e.g. "option C", "(B)", "A is wrong"."""
    return any(p.search(text) for p in _REF_PATTERNS)


def validate_rationale(raw):
    """(clean rationale or None, reason it was dropped or None)."""
    text = clean_rationale(raw)
    if len(text) < 10:
        return None, "empty_after_cleaning"
    if len(text) > MAX_RATIONALE:
        return None, "too_long"
    if refers_to_option(text):
        return None, "letter_reference"
    return text, None


# --------------------------------------------------------------------------- shuffle exceptions

_REFERENCE_PHRASES = [
    r"\b(both|neither)\b",
    r"\b(none|all) of (the )?(above|these|previous|preceding|answers|options|choices)\b",
    r"\b(none|all) the above\b",
    r"\bthe (first|second|third|fourth|fifth|last|previous|preceding) (option|answer|choice)s?\b",
    r"\b(options?|answers?|choices?) [a-e]\b(?= and | or |,|\.|\?|$)",
    r"cap de les anteriors", r"totes les anteriors", r"cap de les (respostes|opcions)", r"cap dels anteriors",
    r"cap d'aquest", r"\bamb[dp]?[óo]s\b", r"\bambdues\b", r"\bambd[óo]s\b",
    r"\b(primera|segona|tercera|quarta|cinquena|[úu]ltima|darrera) (opci[óo]|resposta)\b",
    r"la resposta anterior", r"l'anterior",
    r"ninguna de las anteriores", r"ninguno de los anteriores", r"todas las anteriores",
    r"todos los anteriores", r"ninguna de las (opciones|respuestas)", r"ninguno de estos", r"ninguna de estas",
    r"\bambos\b", r"\bambas\b", r"\b(primera|segunda|tercera|cuarta|quinta|[úu]ltima) (opci[óo]n|respuesta)\b",
    r"la respuesta anterior",
]
_REFERENCE_RE = re.compile("|".join(f"(?:{p})" for p in _REFERENCE_PHRASES), re.IGNORECASE)
_LETTER_PAIR_RE = re.compile(r"\b[A-E]\s+(?:and|or|i|o|y|&)\s+[A-E]\b")
_OPTION_LETTERS_RE = re.compile(
    r"^\s*(?i:(?:only|just|solament|nom\u00e9s|solo|s\u00f3lo)\s+)?\(?(?-i:[A-E])\)?"
    r"(?:\s*(?i:,|and|or|i|o|y|&|\+)\s*\(?(?-i:[A-E])\)?)*\s*$")


def no_shuffle_reason(text, values):
    """A reason string if the problem refers to other options or positions, else None."""
    blob = text + "\n" + "\n".join(values)
    if _REFERENCE_RE.search(blob):
        return "refers_to_options"
    if _LETTER_PAIR_RE.search(blob):
        return "letter_pair"
    for v in values:
        # option "A", "B and D", "only C": a label or a combination of options, not a value
        if _OPTION_LETTERS_RE.match(v):
            return "option_is_letter"
    return None


# --------------------------------------------------------------------------- shuffling

class Deck:
    """Draws target letters in shuffled blocks of five, so the correct letter is balanced."""

    def __init__(self, rng):
        self.rng, self.cards = rng, []

    def draw(self):
        if not self.cards:
            self.cards = list(LETTERS)
            self.rng.shuffle(self.cards)
        return self.cards.pop()


def make_variants(values, label, uid, copies, seed, deck, shuffle_ok):
    """[(option values in order, label)]: differently shuffled copies, or the original order once."""
    li = LETTERS.index(label)
    if not shuffle_ok:
        return [(list(values), label)]
    out, seen = [], set()
    for k in range(copies):
        rng = rng_for(seed, "shuffle", uid, k)
        for attempt in range(30):
            target = deck.draw() if attempt == 0 else LETTERS[rng.randrange(5)]
            others = [v for i, v in enumerate(values) if i != li]
            rng.shuffle(others)
            slot = LETTERS.index(target)
            perm = others[:slot] + [values[li]] + others[slot:]
            if tuple(perm) not in seen:
                seen.add(tuple(perm))
                out.append((perm, target))
                break
    return out


# --------------------------------------------------------------------------- leak guards

def assert_no_leaks(records, val_ids, val_norms):
    """Abort the build if a validation id or a validation question text is in the output."""
    for rec in records:
        mid = rec.get("meta", {}).get("m3k_id")
        if mid is not None and mid in val_ids:
            raise AssertionError(f"leak: validation id {mid} in output ({rec['uid']})")
        for v in norm_variants(rec["text"]):
            if v in val_norms:
                raise AssertionError(f"leak: validation question text in output ({rec['uid']})")


# --------------------------------------------------------------------------- chat export

def problem_of(rec):
    return {"text": rec["text"], "options": rec["options"]}


def to_chat(rec, reasoning):
    messages = build_messages(problem_of(rec))  # system + user, exactly as at inference
    assert messages[0] == {"role": "system", "content": SYSTEM}
    user = messages[1]
    assert user["content"] == format_problem(problem_of(rec)) + "\nAnswer:"
    content = f"{rec['rationale']}\nAnswer: {rec['label']}" if reasoning else rec["label"]
    return {"messages": [messages[0], user, {"role": "assistant", "content": content}]}


def is_dev(rec):
    h = int(hashlib.sha256(rec["uid"].encode("utf-8")).hexdigest()[:8], 16)
    return rec["source"] != "m3kang" and h % 1000 < 50


# --------------------------------------------------------------------------- loading

def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_val(path):
    ids, norms = set(), set()
    for row in read_jsonl(path):
        ids.add(row["id"])
        for v in norm_variants(row.get("text", "")):
            norms.add(v)
    return ids, norms


def load_rationales(paths):
    """One path or several: later files win for the same (id, language)."""
    table = {}
    for path in ([paths] if isinstance(paths, str) else paths or []):
        for row in read_jsonl(path):
            table[(row["id"], row.get("language"))] = row
    return table


def load_options(path):
    """{(id, language): {"A".."E": text}}: options read from the problem image where OCR found none."""
    table = {}
    if path:
        for row in read_jsonl(path):
            opts = row.get("options") or {}
            if set(opts) == set(LETTERS) and all(str(opts[c]).strip() for c in LETTERS):
                table[(row["id"], row["language"])] = {c: str(opts[c]) for c in LETTERS}
    return table


def prompt_len(text, options):
    return len(format_problem({"text": text, "options": options}) + "\nAnswer:")


def base_m3kang(args, val_ids, val_norms, rationales, drops):
    """Base problems (before copies) from the M3Kang training split."""
    bases = []
    used = set()
    recovered = load_options(getattr(args, "options", None))
    for row in read_jsonl(args.train):
        if row["id"] in val_ids:
            drops["m3kang:id_in_validation"] += 1
            continue
        text = (row.get("text") or "").strip()
        opts = row.get("options") or {}
        from_image = False
        if not opts and (row["id"], row["language"]) in recovered:
            opts, from_image = recovered[(row["id"], row["language"])], True
            drops["m3kang:options_recovered_from_image"] += 1
        label = (row.get("label") or "").strip().upper()
        if label not in LETTERS:
            drops["m3kang:bad_label"] += 1
            continue
        if any(v in val_norms for v in norm_variants(text)):
            drops["m3kang:text_equals_validation"] += 1
            continue
        if not opts:
            if not args.include_no_options:
                drops["m3kang:no_options"] += 1
                continue
            values, no_opts = [], True
        else:
            if set(opts) != set(LETTERS) or any(not str(opts[c]).strip() for c in LETTERS):
                drops["m3kang:not_five_options"] += 1
                continue
            values, no_opts = [clean_ws(str(opts[c])) for c in LETTERS], False
            if values.count(values[LETTERS.index(label)]) > 1:
                drops["m3kang:ambiguous_label"] += 1
                continue
        options = {} if no_opts else dict(zip(LETTERS, values))
        if prompt_len(text, options) > MAX_PROMPT:
            drops["m3kang:prompt_too_long"] += 1
            continue
        rationale = None
        sup = rationales.get((row["id"], row["language"])) or rationales.get((row["id"], None))
        if sup is not None:
            used.add(id(sup))
            ans = str(sup.get("answer") or "").strip().upper()
            if ans and ans != label:
                drops["m3kang:rationale_answer_mismatch"] += 1
            elif no_opts:
                drops["m3kang:rationale_for_no_options"] += 1
            else:
                rationale, why = validate_rationale(sup.get("rationale"))
                if why:
                    drops[f"m3kang:rationale_{why}"] += 1
        bases.append(dict(uid=f"m3k:{row['id']}:{row['language']}", source="m3kang", language=row["language"],
                          text=text, values=values, label=label, rationale=rationale, no_options=no_opts,
                          meta={"m3k_id": row["id"], "level": row.get("level"), "year": row.get("year"),
                                "text_only": row.get("text_only"), "options_from_image": from_image}))
    drops["m3kang:rationales_unmatched"] += sum(1 for v in rationales.values() if id(v) not in used)
    return bases


_AQ_PREFIX = re.compile(r"^\s*([A-E])\s*\)\s*(.*)$", re.DOTALL)


def ensure_aqua(path):
    if Path(path).exists():
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(AQUA_URL, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(path, "wb") as f:
        f.write(resp.read())


def base_aqua(args, val_norms, drops, seen_norms):
    pool_r, pool_l = [], []
    for idx, row in enumerate(read_jsonl(args.aqua_file)):
        q = clean_ws(row.get("question", ""))
        raw_opts = row.get("options") or []
        correct = str(row.get("correct", "")).strip().upper()
        if len(raw_opts) != 5:
            drops["aqua:not_five_options"] += 1
            continue
        values, ok = [], True
        for pos, o in enumerate(raw_opts):
            m = _AQ_PREFIX.match(o)
            if not m or m.group(1) != LETTERS[pos]:
                ok = False
                break
            values.append(clean_ws(m.group(2)))
        if not ok:
            drops["aqua:bad_option_prefix"] += 1
            continue
        if any(not v for v in values) or len(set(values)) != 5:
            drops["aqua:empty_or_repeated_option"] += 1
            continue
        if correct not in LETTERS:
            drops["aqua:bad_label"] += 1
            continue
        if not 40 <= len(q) <= 600:
            drops["aqua:question_length"] += 1
            continue
        rationale = clean_rationale(row.get("rationale", ""))
        if not MIN_AQUA_RATIONALE <= len(rationale) <= MAX_RATIONALE:
            drops["aqua:rationale_length"] += 1
            continue
        if refers_to_option(rationale) or _ANSWER_WORD.search(rationale) or re.search(r"[\u00e2\u00c3\ufffd]", rationale):
            drops["aqua:rationale_letter_reference_kept_letter_only"] += 1
            rationale = None
        if any(v in val_norms for v in norm_variants(q)):
            drops["aqua:text_equals_validation"] += 1
            continue
        if prompt_len(q, dict(zip(LETTERS, values))) > MAX_PROMPT:
            drops["aqua:prompt_too_long"] += 1
            continue
        n = norm(q)
        if n in seen_norms:
            drops["aqua:duplicate_question"] += 1
            continue
        seen_norms.add(n)
        base = dict(uid=f"aqua:{idx}", source="aqua_rat", language="eng", text=q, values=values, label=correct,
                    rationale=rationale, no_options=False, meta={"aqua_index": idx})
        (pool_r if rationale else pool_l).append(base)
    rng = rng_for(args.seed, "aqua")
    rng.shuffle(pool_r)
    rng.shuffle(pool_l)
    chosen = (pool_r + pool_l)[:args.aqua]
    drops["aqua:eligible_with_rationale"] = len(pool_r)
    drops["aqua:eligible_letter_only"] = len(pool_l)
    drops["aqua:not_sampled"] = len(pool_r) + len(pool_l) - len(chosen)
    return chosen


def base_synthetic(args, val_norms, drops, seen_norms):
    cells = [(g, l) for g in synthetic_problems.GENERATOR_NAMES for l in synthetic_problems.LANGS]
    want = {c: args.synthetic // len(cells) + (1 if i < args.synthetic % len(cells) else 0)
            for i, c in enumerate(cells)}
    made = {c: [] for c in cells}
    tries = {c: 0 for c in cells}
    stuck = set()

    def produce(cell, how_many):
        g, l = cell
        misses = 0
        while how_many > 0 and misses < 60:
            rng = rng_for(args.seed, "syn", g, l, tries[cell])
            tries[cell] += 1
            ex = synthetic_problems.generate(g, rng, l)
            n = norm(ex["text"])
            if n in seen_norms:
                misses += 1
                drops["synthetic:duplicate_question"] += 1
                continue
            if any(v in val_norms for v in norm_variants(ex["text"])):
                drops["synthetic:text_equals_validation"] += 1
                continue
            options = ex["options"]
            if prompt_len(ex["text"], options) > MAX_PROMPT:
                drops["synthetic:prompt_too_long"] += 1
                continue
            misses = 0
            seen_norms.add(n)
            made[cell].append(dict(
                uid=f"syn:{g}:{l}:{tries[cell] - 1}", source="synthetic", language=l, text=ex["text"],
                values=[options[c] for c in LETTERS], label=ex["label"], rationale=ex["rationale"],
                no_options=False, meta={"generator": g}))
            how_many -= 1
        if how_many > 0:
            stuck.add(cell)
        return how_many

    deficit = 0
    for c in cells:
        deficit += produce(c, want[c])
    while deficit > 0 and len(stuck) < len(cells):
        progressed = False
        for c in cells:
            if deficit <= 0:
                break
            if c in stuck:
                continue
            left = produce(c, 1)
            if left == 0:
                deficit -= 1
                progressed = True
        if not progressed:
            break
    drops["synthetic:shortfall_cells_exhausted"] = len(stuck)
    drops["synthetic:shortfall_total"] = max(deficit, 0)
    return [b for c in cells for b in made[c]]


# --------------------------------------------------------------------------- build

def expand(bases, copies, seed, deck, drops):
    records = []
    for b in bases:
        values = b["values"]
        if b["no_options"]:
            variants, reason = [([], b["label"])], "no_options"
        else:
            reason = no_shuffle_reason(b["text"], values)
            if b["source"] == "m3kang":
                n_copies = copies
            else:
                n_copies = 1
            variants = make_variants(values, b["label"], b["uid"], n_copies, seed, deck, reason is None)
        if reason:
            drops[f"{b['source']}:kept_original_order_{reason}"] += 1
        for k, (vals, label) in enumerate(variants):
            meta = dict(b["meta"], copy=k, shuffled=reason is None)
            records.append({"uid": f"{b['uid']}#{k}", "source": b["source"], "language": b["language"],
                            "text": b["text"], "options": dict(zip(LETTERS, vals)) if vals else {},
                            "label": label, "rationale": b["rationale"], "meta": meta})
    return records


def pct(values, p):
    s = sorted(values)
    return s[min(len(s) - 1, max(0, math.ceil(p * len(s)) - 1))] if s else 0


def summary(values):
    if not values:
        return dict(mean=0, p50=0, p90=0, max=0)
    return dict(mean=sum(values) / len(values), p50=pct(values, 0.5), p90=pct(values, 0.9), max=max(values))


def build(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    drops = Counter()
    val_ids, val_norms = load_val(args.val)
    rationales = load_rationales(args.rationales)
    seen_norms = set()

    bases = base_m3kang(args, val_ids, val_norms, rationales, drops)
    if args.aqua > 0:
        ensure_aqua(args.aqua_file)
        bases += base_aqua(args, val_norms, drops, seen_norms)
    if args.synthetic > 0:
        bases += base_synthetic(args, val_norms, drops, seen_norms)

    deck = Deck(rng_for(args.seed, "deck"))
    records = expand(bases, args.m3kang_copies, args.seed, deck, drops)

    for r in records:  # sanity: format, rationale form
        assert r["label"] in LETTERS
        if r["options"]:
            assert r["options"][r["label"]]
        if r["rationale"]:
            assert len(r["rationale"]) <= MAX_RATIONALE and not refers_to_option(r["rationale"])
    assert_no_leaks(records, val_ids, val_norms)

    write_jsonl(out / "master.jsonl", records)

    exports = OrderedDict()
    for name, reasoning, dev in (("letter", False, False), ("reasoning", True, False),
                                 ("dev_letter", False, True), ("dev_reasoning", True, True)):
        chosen = [r for r in records if is_dev(r) == dev and (r["rationale"] or not reasoning)]
        rng = rng_for(args.seed, "order", name)
        chosen = chosen[:]
        rng.shuffle(chosen)
        rows = [to_chat(r, reasoning) for r in chosen]
        write_jsonl(out / f"{name}.jsonl", rows)
        exports[name] = (chosen, rows)

    stats = render_stats(args, records, exports, drops, len(val_ids), len(val_norms))
    (out / "STATS.md").write_text(stats, encoding="utf-8")
    return stats


def table(rows, header):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def render_stats(args, records, exports, drops, n_val_ids, n_val_norms):
    L = ["# Training data statistics", "",
         f"Seed {args.seed}; aqua {args.aqua}; synthetic {args.synthetic}; m3kang copies {args.m3kang_copies}; "
         f"include-no-options {args.include_no_options}; rationales file {'yes' if args.rationales else 'no'}.", "",
         "No problem text is in this report. Token estimate: 3.5 characters per token; "
         f"board writing speed {BOARD_TOK_PER_S} tokens/s, budget {BOARD_WRITE_BUDGET_S} s.", ""]
    sources = sorted({r["source"] for r in records})
    langs = sorted({r["language"] for r in records})

    L += ["## Master file", "", f"Examples: {len(records)}", ""]
    rows = []
    for s in sources:
        for lg in langs:
            sel = [r for r in records if r["source"] == s and r["language"] == lg]
            if sel:
                rows.append((s, lg, len(sel), sum(1 for r in sel if r["rationale"]),
                             sum(1 for r in sel if not r["meta"].get("shuffled"))))
    L += [table(rows, ["source", "language", "examples", "with rationale", "original order kept"]), ""]
    dist = Counter(r["label"] for r in records)
    L += ["Correct letter in master: " + ", ".join(f"{c}={dist[c]}" for c in LETTERS), ""]

    for name, (chosen, rows_) in exports.items():
        L += [f"## {name}.jsonl", "", f"Examples: {len(chosen)}", ""]
        trows = []
        for s in sources:
            for lg in langs:
                n = sum(1 for r in chosen if r["source"] == s and r["language"] == lg)
                if n:
                    trows.append((s, lg, n))
        L += [table(trows, ["source", "language", "examples"]), ""]
        d = Counter(r["label"] for r in chosen)
        L += ["Correct letter: " + ", ".join(f"{c}={d[c]}" for c in LETTERS), ""]
        users = [len(m["messages"][1]["content"]) for m in rows_]
        asst = [len(m["messages"][2]["content"]) for m in rows_]
        lrows = []
        for label, vals in (("user prompt", users), ("assistant turn", asst)):
            s = summary(vals)
            lrows.append((label, f"{s['mean']:.1f}", s["p50"], s["p90"], s["max"],
                          f"{s['mean'] / CHARS_PER_TOKEN:.1f}", f"{s['p90'] / CHARS_PER_TOKEN:.1f}"))
        L += [table(lrows, ["length (chars)", "mean", "p50", "p90", "max", "mean tokens", "p90 tokens"]), ""]
        if name.endswith("reasoning") and asst:
            secs = [a / CHARS_PER_TOKEN / BOARD_TOK_PER_S for a in asst]
            s = summary(secs)
            flag = "  **FLAG: p90 exceeds the 40 s budget**" if s["p90"] > BOARD_WRITE_BUDGET_S else ""
            L += [f"Estimated board writing time of the answer: mean {s['mean']:.1f} s, p90 {s['p90']:.1f} s, "
                  f"max {s['max']:.1f} s.{flag}", ""]

    L += ["## Drops and skips", ""]
    L += [table([(k, drops[k]) for k in sorted(drops)], ["reason", "count"]) if drops else "none", ""]
    L += ["## Leak guards", "",
          f"Validation ids loaded: {n_val_ids}; validation normalised texts: {n_val_norms}. Both assertions passed "
          "on the final output.", ""]
    return "\n".join(L)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--train", default=str(ROOT / "data" / "train.jsonl"))
    p.add_argument("--val", default=str(ROOT / "data" / "val.jsonl"))
    p.add_argument("--aqua", type=int, default=8000, help="AQuA-RAT examples to sample (default 8000)")
    p.add_argument("--aqua-file", default=str(ROOT / "data" / "external" / "aqua_train.json"))
    p.add_argument("--synthetic", type=int, default=6000, help="synthetic examples in total (default 6000)")
    p.add_argument("--m3kang-copies", type=int, default=3, help="shuffled copies of each M3Kang problem")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rationales", nargs="*", default=None,
                   help="JSON Lines files: id, [language], rationale, [answer]")
    p.add_argument("--options", default=None,
                   help="JSON Lines: id, language, options {A..E}, for M3Kang problems whose options OCR missed")
    p.add_argument("--include-no-options", action="store_true",
                   help="also add M3Kang training problems whose options are pictures, as letter-only")
    p.add_argument("--out", default=str(ROOT / "data" / "training"))
    return p.parse_args(argv)


def main(argv=None):
    stats = build(parse_args(argv))
    print(stats)


if __name__ == "__main__":
    main()
