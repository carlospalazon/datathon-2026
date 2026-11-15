"""Answer before the model: copy the answer VALUE of a near-identical training problem. No model.

Cangur papers reuse a problem at neighbouring levels of the same year, often with the options in
another order. If the problem asked is almost word for word a training problem (another id, same
language), the value of that problem's correct option is looked for among the options asked; it is the
answer only if exactly one option has it. Otherwise this module abstains and the model answers.

    index = build(training_problems)                 # once; training problems only
    hit = presolve(problem, index, exclude_id=None)  # None, or {"answer", "kind", "source", "similarity"}

    python3 -m copilot.presolve data/train.jsonl     # leave-one-id-out coverage and precision

Rules it keeps: the index holds training problems only (never data/demo or data/val.jsonl); a problem
never matches its own id, so not its translation either (and `exclude_id` removes one more id).
Deterministic: no clock, no randomness, ties broken by id. Standard library only.

Measured on the training split, leave one id out, threshold 0.5 (15 Nov 2026): with options it answers
64 of 1,863 (3.4%) and 52 are right (81%); the misses are twins whose numbers were changed while the old
value stayed among the options. Without readable options, copying the neighbour's letter is right 48 of
97 times (49%): better than a fixed letter, far from safe, so it comes back as kind "letter" for the
caller to use or ignore. Every match found is a problem of the same year, so a test made of new problems
(like the 2026 demo set) has no neighbour here: expect no answers and no gain there.
"""
import json
import re
import sys

THRESHOLD = 0.5


def _grams(text):
    words = re.findall(r"\w+", (text or "").lower())
    return frozenset(words) | frozenset(zip(words, words[1:]))


def _norm(value):
    return re.sub(r"[\s$*_\\{}()]", "", str(value).lower().replace(",", ".")).rstrip(".")


def build(problems):
    """The index: one entry per training problem that has text and a label."""
    index = []
    for p in problems:
        grams = _grams(p.get("text"))
        label = p.get("label")
        if not grams or label not in tuple("ABCDE"):
            continue
        options = p.get("options") or {}
        value = _norm(options[label]) if label in options else None
        index.append({"id": p["id"], "language": p.get("language"), "grams": grams, "label": label,
                      "value": value})
    index.sort(key=lambda e: (e["id"], str(e["language"])))
    return index


def nearest(problem, index, exclude_id=None):
    """(similarity, entry) of the most similar other problem in the same language, or (0.0, None)."""
    grams = _grams(problem.get("text"))
    best = (0.0, None)
    if not grams:
        return best
    for entry in index:
        if entry["language"] != problem.get("language") or entry["id"] in (problem.get("id"), exclude_id):
            continue
        shared = len(grams & entry["grams"])
        if not shared:
            continue
        similarity = shared / (len(grams) + len(entry["grams"]) - shared)
        if similarity > best[0]:
            best = (similarity, entry)
    return best


def presolve(problem, index, exclude_id=None, threshold=THRESHOLD):
    """The copied answer, or None to let the model answer."""
    similarity, entry = nearest(problem, index, exclude_id)
    if entry is None or similarity < threshold:
        return None
    found = {"source": entry["id"], "similarity": round(similarity, 3)}
    options = problem.get("options") or {}
    if not options:
        return {**found, "answer": entry["label"], "kind": "letter"}
    if entry["value"] is None:
        return None
    letters = [letter for letter, value in sorted(options.items()) if _norm(value) == entry["value"]]
    if len(letters) != 1:
        return None
    return {**found, "answer": letters[0], "kind": "value"}


def main(path):
    problems = [json.loads(line) for line in open(path, encoding="utf-8")]
    index = build(problems)
    with_options = sum(1 for p in problems if p.get("options"))
    print(f"{path}: {len(problems)} problems, {with_options} with options; leave one id out")
    for threshold in (0.6, 0.5, 0.4, 0.3):
        count = {"value": [0, 0], "letter": [0, 0]}
        for p in problems:
            hit = presolve(p, index, threshold=threshold)
            if hit:
                count[hit["kind"]][0] += 1
                count[hit["kind"]][1] += hit["answer"] == p["label"]
        (va, vr), (la, lr) = count["value"], count["letter"]
        print(f"threshold {threshold}: value copied {va}/{with_options} ({100 * va / max(with_options, 1):.1f}%), "
              f"right {vr}/{va}; letter copied (no options) {la}/{len(problems) - with_options}, right {lr}/{la}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/train.jsonl")
