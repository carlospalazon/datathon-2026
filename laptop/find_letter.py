#!/usr/bin/env python3
"""Find the letter a model chose in its written working. No model needed: text in, letter out.

Why: `copilot.llm.answer_thinking` and `laptop/bench_exam.py` only accept "Answer: B". A model that
writes "**Answer:** B", "The answer is B", "Resposta: B" or "\\boxed{12}" (12 being option B) is counted
as not finished and its working is thrown away for a forced letter.

    from laptop.find_letter import find_letter
    find_letter(text)                      # "" when no answer is stated
    find_letter(text, problem["options"])  # also accepts a stated value that equals exactly one option

The last statement in the text wins. Standard library only.
"""
import re

_WORD = r"(?:final answer|answer|resposta final|resposta|respuesta|correct option|opci[oó] correcta)"
_GLUE = r"(?:\s+(?:is|és|es))?[\s:*_$(\[]*"
# "Answer: A number of ..." is a sentence, not the letter A.
_LETTER = r"(?:\\boxed\{)?(?:\\text\{)?([B-E]|A(?!\s+[a-zà-ú]))(?![A-Za-zÀ-ú0-9])"
_STATED = re.compile(r"(?i:" + _WORD + r")" + _GLUE + _LETTER)
_BOXED = re.compile(r"boxed\{\s*\\?(?:text\{)?\s*\(?([A-E])\)?\s*\}")
_VALUE = re.compile(r"(?:boxed\{\s*(?:\\text\{)?|(?i:" + _WORD + r")" + _GLUE + r")([^{}\n]{1,40})")


def _norm(value):
    """A value as written, reduced so that "12 cm", "$12$" and "12." compare equal to "12"."""
    s = str(value).lower().replace(",", ".")
    s = re.sub(r"[\s$*_\\{}()]", "", s)
    number = re.match(r"-?\d+(?:\.\d+)?(?:/\d+)?", s)
    return number.group().rstrip(".") if number else s.rstrip(".")


def find_letter(text, options=None):
    """The letter A to E stated last in the text, or ""."""
    text = text or ""
    hits = [(m.end(), m.group(1)) for m in _STATED.finditer(text)]
    hits += [(m.end(), m.group(1)) for m in _BOXED.finditer(text)]
    if hits:
        return max(hits)[1]
    if options:
        by_value = {}
        for letter, value in options.items():
            by_value.setdefault(_norm(value), []).append(letter)
        for m in reversed(list(_VALUE.finditer(text))):
            letters = by_value.get(_norm(m.group(1)), [])
            if len(letters) == 1:
                return letters[0]
    return ""
