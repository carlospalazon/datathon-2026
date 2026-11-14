"""The opt-in settings of copilot.pipeline: no model call without options, letter bias,
several option orders, and retrieval that fails soft. Everything is mocked: no server.

    python3 -m unittest tests.test_pipeline_options
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copilot import pipeline, rag  # noqa: E402
from copilot.config import CONFIG  # noqa: E402

PROBLEM = {"id": "synthetic-1", "language": "eng", "text": "Pick the odd one.",
           "options": {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta", "E": "epsilon"}}


def response(letter, lps=None, with_logprobs=True):
    body = {"choices": [{"message": {"content": letter}}], "timings": {"prompt_n": 7}}
    if lps is not None and with_logprobs:
        top = [{"token": " " + c, "logprob": v} for c, v in lps.items()] + [{"token": "To", "logprob": -9.0}]
        body["choices"][0]["logprobs"] = {"content": [{"top_logprobs": top}]}
    return body


def shown(payload):
    """{letter: option text} of the problem in the request."""
    lines = payload["messages"][-1]["content"].split("\n")
    return {line[0]: line[3:] for line in lines if len(line) > 3 and line[1:3] == ") "}


class Fake:
    """A fake post(): `favour` maps a request's shown options to {letter: logprob}."""

    def __init__(self, favour):
        self.favour = favour
        self.payloads = []

    def __call__(self, url, payload, timeout):
        self.payloads.append(payload)
        lps = self.favour(shown(payload), len(self.payloads))
        return response(max(lps, key=lps.get), lps)


def favour_text(text, high=-0.1, low=-3.0):
    def f(options, _n):
        return {c: (high if options[c] == text else low) for c in "ABCDE"}
    return f


def run(post, settings=None, problem=PROBLEM, **kw):
    with mock.patch("copilot.llm.post", post), mock.patch.dict(CONFIG, settings or {}):
        return pipeline.solve(problem, llm_url="http://127.0.0.1:9/x", **kw)


class Defaults(unittest.TestCase):
    def test_default_request_has_no_logprobs_and_one_pass(self):
        fake = Fake(favour_text("gamma"))
        result = run(fake, {"NO_OPTIONS_PRIOR": "", "LETTER_BIAS_FILE": "", "OPTION_ORDERS": "1"})
        self.assertEqual(len(fake.payloads), 1)
        self.assertNotIn("logprobs", fake.payloads[0])
        self.assertNotIn("top_logprobs", fake.payloads[0])
        self.assertEqual(result["answer"], "C")
        self.assertEqual((result["passes"], result["logprobs"], result["retrieval_error"]), (1, {}, ""))
        self.assertEqual(result["prompt_tokens"], 7)

    def test_config_has_defaults(self):
        self.assertEqual(CONFIG["OPTION_ORDERS"], "1")
        self.assertEqual(CONFIG["NO_OPTIONS_PRIOR"], "")
        self.assertEqual(CONFIG["LETTER_BIAS_FILE"], "")


class NoOptionsPrior(unittest.TestCase):
    def test_skips_model(self):
        fake = Fake(favour_text("gamma"))
        for options in ({}, None):
            problem = {k: v for k, v in PROBLEM.items() if k != "options"}
            if options is not None:
                problem["options"] = options
            result = run(fake, {"NO_OPTIONS_PRIOR": "D"}, problem=problem)
            self.assertEqual((result["answer"], result["status"], result["passes"]), ("D", "prior", 0))
        self.assertEqual(fake.payloads, [])

    def test_problem_with_options_still_asks(self):
        fake = Fake(favour_text("gamma"))
        self.assertEqual(run(fake, {"NO_OPTIONS_PRIOR": "D"})["answer"], "C")
        self.assertEqual(len(fake.payloads), 1)


class LetterBias(unittest.TestCase):
    def bias_file(self, content):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        f.write(content)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_bias_changes_argmax(self):
        # Model says A (-0.5) over B (-1.0), but A is over-chosen by 1.0 on average.
        def favour(_options, _n):
            return {"A": -0.5, "B": -1.0, "C": -3.0, "D": -3.0, "E": -3.0}
        path = self.bias_file(json.dumps({"A": 1.0, "B": 0, "C": 0, "D": 0, "E": 0}))
        fake = Fake(favour)
        result = run(fake, {"LETTER_BIAS_FILE": path})
        self.assertEqual(result["answer"], "B")
        self.assertTrue(fake.payloads[0]["logprobs"])
        self.assertEqual(fake.payloads[0]["top_logprobs"], 60)
        self.assertAlmostEqual(result["logprobs"]["A"], -1.5)
        self.assertEqual(result["passes"], 1)

    def test_bad_files_are_ignored(self):
        for content in ("not json", '{"A": 1}', '{"A":"x","B":0,"C":0,"D":0,"E":0}', "[1,2]"):
            fake = Fake(favour_text("gamma"))
            result = run(fake, {"LETTER_BIAS_FILE": self.bias_file(content)})
            self.assertNotIn("logprobs", fake.payloads[0], content)
            self.assertEqual(result["answer"], "C")
        fake = Fake(favour_text("gamma"))
        run(fake, {"LETTER_BIAS_FILE": "/nonexistent/bias.json"})
        self.assertNotIn("logprobs", fake.payloads[0])


class OptionOrders(unittest.TestCase):
    def test_five_orders_map_back_to_original_letters(self):
        for target, letter in (("alpha", "A"), ("beta", "B"), ("gamma", "C"), ("delta", "D"), ("epsilon", "E")):
            fake = Fake(favour_text(target))
            result = run(fake, {"OPTION_ORDERS": "5"})
            self.assertEqual(result["answer"], letter, target)
            self.assertEqual(result["passes"], 5)
            self.assertEqual(len(fake.payloads), 5)
            self.assertEqual(max(result["logprobs"], key=result["logprobs"].get), letter)

    def test_shift_definition(self):
        fake = Fake(favour_text("alpha"))
        run(fake, {"OPTION_ORDERS": "3"})
        self.assertEqual(shown(fake.payloads[0])["A"], "alpha")
        self.assertEqual(shown(fake.payloads[1]), {"A": "beta", "B": "gamma", "C": "delta", "D": "epsilon", "E": "alpha"})
        self.assertEqual(shown(fake.payloads[2])["A"], "gamma")

    def test_always_position_a_ties_to_a(self):
        fake = Fake(lambda _o, _n: {"A": -0.1, "B": -2.0, "C": -2.0, "D": -2.0, "E": -2.0})
        result = run(fake, {"OPTION_ORDERS": "5"})
        self.assertEqual(result["answer"], "A")
        self.assertEqual(len(set(result["logprobs"].values())), 1)

    def test_fewer_than_five_options_is_one_plain_pass(self):
        problem = {**PROBLEM, "options": {"A": "x", "B": "y", "C": "z"}}
        fake = Fake(lambda o, _n: {c: (-0.1 if o.get(c) == "y" else -3.0) for c in "ABCDE"})
        result = run(fake, {"OPTION_ORDERS": "5"}, problem=problem)
        self.assertEqual((result["passes"], len(fake.payloads), result["answer"]), (1, 1, "B"))
        self.assertNotIn("logprobs", fake.payloads[0])

    def test_budget_stops_extra_passes(self):
        clock = {"t": 0.0}

        def slow(options, n):
            clock["t"] += 10.0  # each pass takes 10 s
            return favour_text("beta")(options, n)

        fake = Fake(slow)
        # limit 30 - margin 3 = 27 s of room: after 1 pass 17 left (>=13), after 2 pass 7 left (<13)
        with mock.patch("copilot.pipeline.time.perf_counter", lambda: clock["t"]):
            result = run(fake, {"OPTION_ORDERS": "5"}, time_limit=30.0)
        self.assertEqual((result["passes"], len(fake.payloads)), (2, 2))
        self.assertEqual(result["answer"], "B")
        self.assertEqual(result["status"], "ok")

    def test_failing_extra_pass_keeps_earlier_answer(self):
        calls = []

        def post(url, payload, timeout):
            calls.append(payload)
            if len(calls) == 2:
                raise TimeoutError("slow")
            return response("C", {"A": -3, "B": -3, "C": -0.1, "D": -3, "E": -3})

        result = run(post, {"OPTION_ORDERS": "3"})
        self.assertEqual((result["answer"], result["status"], result["passes"]), ("C", "ok", 2))
        self.assertIn("pass_error", result)

    def test_first_pass_failure_is_the_usual_fallback(self):
        def post(url, payload, timeout):
            raise TimeoutError("slow")
        result = run(post, {"OPTION_ORDERS": "3"})
        self.assertEqual((result["answer"], result["status"]), (pipeline.FALLBACK, "timeout"))

    def test_missing_logprobs_fall_back_to_the_grammar_letter(self):
        def post(url, payload, timeout):
            return response("B", with_logprobs=False)
        result = run(post, {"OPTION_ORDERS": "2"})
        self.assertEqual(result["answer"], "B")
        self.assertEqual(result["logprobs"]["B"], -20.0)
        self.assertEqual(result["logprobs"]["A"], -40.0)
        self.assertEqual(result["passes"], 2)

    def test_missing_letter_gets_floor_below_lowest(self):
        from copilot.llm import letter_logprobs
        body = response("A", {"A": -1.0, "B": -2.0})
        scores = letter_logprobs(body)
        self.assertEqual(scores["A"], -1.0)
        self.assertEqual(scores["E"], -9.0 - 1.0)  # "To" at -9.0 is the lowest listed


class FakeIndex:
    def __init__(self, error=None):
        self.error = error

    def search(self, problem, k=1, exclude_id=None):
        if self.error:
            raise self.error
        return [(0.9, {"id": "x1", "label": "A", "text": "t", "options": {}})]


class Retrieval(unittest.TestCase):
    def test_failure_still_asks_the_model(self):
        fake = Fake(favour_text("gamma"))
        result = run(fake, index=FakeIndex(ConnectionRefusedError("embed down")), k=2)
        self.assertEqual((result["answer"], result["status"]), ("C", "ok"))
        self.assertEqual(result["retrieval_error"], "ConnectionRefusedError")
        self.assertEqual(len(fake.payloads), 1)
        self.assertEqual(len(fake.payloads[0]["messages"]), 2)  # system + problem, no examples

    def test_success_adds_examples(self):
        fake = Fake(favour_text("gamma"))
        result = run(fake, index=FakeIndex(), k=1)
        self.assertEqual(result["retrieval_error"], "")
        self.assertEqual(len(fake.payloads[0]["messages"]), 4)


class SearchDedup(unittest.TestCase):
    def index(self, rows):
        idx = rag.Index.__new__(rag.Index)
        idx.rows = [(f"{p['id']}|{p['language']}", p, vec) for p, vec in rows]
        return idx

    def search(self, idx, problem, **kw):
        with mock.patch("copilot.rag.embed", lambda texts, query=False: [[1.0, 0.0]]):
            return idx.search(problem, **kw)

    def test_one_row_per_id_best_score(self):
        rows = [({"id": "a", "language": "eng"}, [0.9, 0.0]), ({"id": "a", "language": "cat"}, [0.5, 0.0]),
                ({"id": "b", "language": "eng"}, [0.4, 0.0]), ({"id": "b", "language": "cat"}, [0.3, 0.0])]
        hits = self.search(self.index(rows), {"text": "q", "language": "spa"}, k=2)
        self.assertEqual([(round(s, 1), p["id"], p["language"]) for s, p in hits],
                         [(0.9, "a", "eng"), (0.4, "b", "eng")])

    def test_prefers_query_language_when_close(self):
        rows = [({"id": "a", "language": "eng"}, [0.90, 0.0]), ({"id": "a", "language": "cat"}, [0.88, 0.0]),
                ({"id": "b", "language": "eng"}, [0.80, 0.0]), ({"id": "b", "language": "cat"}, [0.40, 0.0])]
        hits = self.search(self.index(rows), {"text": "q", "language": "cat"}, k=5)
        self.assertEqual([(p["id"], p["language"]) for _s, p in hits], [("a", "cat"), ("b", "eng")])

    def test_exclude_id(self):
        rows = [({"id": "a", "language": "eng"}, [0.9, 0.0]), ({"id": "b", "language": "eng"}, [0.4, 0.0])]
        hits = self.search(self.index(rows), {"text": "q", "language": "eng"}, k=5, exclude_id="a")
        self.assertEqual([p["id"] for _s, p in hits], ["b"])


if __name__ == "__main__":
    unittest.main()


class ReasonMode(unittest.TestCase):
    """ANSWER_MODE=reason: one line of working, then the letter; a plain letter if that fails."""

    def post(self, replies):
        calls = []

        def f(url, payload, timeout):
            calls.append(payload)
            reply = replies[len(calls) - 1]
            if isinstance(reply, Exception):
                raise reply
            return {"choices": [{"message": {"content": reply}}], "timings": {"prompt_n": 7, "predicted_n": 9}}
        return f, calls

    def test_letter_comes_from_the_answer_line(self):
        post, calls = self.post(["Two and two make four, so B is not it.\nAnswer: C"])
        out = run(post, {"ANSWER_MODE": "reason"})
        self.assertEqual((out["answer"], out["status"], len(calls)), ("C", "ok", 1))
        self.assertGreater(calls[0]["max_tokens"], 1)
        self.assertIn("Answer: ", calls[0]["grammar"])

    def test_no_answer_line_asks_for_a_plain_letter(self):
        post, calls = self.post(["working that never ends", "E"])
        out = run(post, {"ANSWER_MODE": "reason"})
        self.assertEqual((out["answer"], out["status"], len(calls)), ("E", "ok", 2))
        self.assertEqual(calls[1]["max_tokens"], 1)

    def test_timeout_while_reasoning_asks_for_a_plain_letter(self):
        post, calls = self.post([TimeoutError(), "A"])
        out = run(post, {"ANSWER_MODE": "reason"})
        self.assertEqual((out["answer"], out["status"]), ("A", "ok"))

    def test_without_options_it_asks_for_a_plain_letter(self):
        post, calls = self.post(["D"])
        out = run(post, {"ANSWER_MODE": "reason"}, problem={**PROBLEM, "options": {}})
        self.assertEqual((out["answer"], len(calls), calls[0]["max_tokens"]), ("D", 1, 1))

    def test_off_by_default(self):
        post, calls = self.post(["B"])
        out = run(post)
        self.assertEqual((out["answer"], calls[0]["max_tokens"]), ("B", 1))
