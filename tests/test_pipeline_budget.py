"""copilot.pipeline with working (ANSWER_MODE=reason or think): the token budget, the letter forced as a
continuation of unfinished working, the saved texts, and the optional presolve. No server: post is faked.

    python3 -m unittest tests.test_pipeline_budget
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from copilot import llm, pipeline  # noqa: E402
from copilot.config import CONFIG  # noqa: E402

PROBLEM = {"id": "synthetic-1", "language": "eng", "text": "Pick the odd one.",
           "options": {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta", "E": "epsilon"}}
BASE = "http://127.0.0.1:9"
CHAT = BASE + "/v1/chat/completions"
REASON = {"ANSWER_MODE": "reason", "BOARD_READ_TPS": "11", "BOARD_WRITE_TPS": "6", "REASON_MAX_TOKENS": "",
          "SAVE_TEXTS": "", "PRESOLVE": "", "NO_OPTIONS_PRIOR": "", "LETTER_BIAS_FILE": "", "OPTION_ORDERS": "1"}
# 110 prompt tokens: (60 - 3 - 110 / 11) * 6 = 282 tokens, one of them kept for a forced letter.
PROMPT_TOKENS, BUDGET = 110, 282


class Server:
    """A fake llama-server. `working` is what /completion writes; `forced` the letter under the grammar;
    `fail` holds the endpoints that raise."""

    def __init__(self, working="It is the third.\nAnswer: C", forced="E", direct="D", fail=(), written=9,
                 prompt_tokens=PROMPT_TOKENS):
        self.working, self.forced, self.direct, self.fail = working, forced, direct, set(fail)
        self.written, self.prompt_tokens = written, prompt_tokens
        self.calls = []

    def __call__(self, url, payload, timeout):
        assert url.startswith(BASE), url
        kind = url[len(BASE):]
        if kind == "/completion":
            kind = "/force" if payload.get("grammar") == "root ::= [A-E]" else "/working"
        self.calls.append((kind, payload))
        if kind in self.fail:
            raise TimeoutError(kind)
        if kind == "/apply-template":
            return {"prompt": "<prompt>" + payload["messages"][-1]["content"] + "<assistant>"}
        if kind == "/tokenize":
            return {"tokens": list(range(self.prompt_tokens))}
        if kind == "/working":
            return {"content": self.working, "tokens_predicted": self.written}
        if kind == "/force":
            return {"content": self.forced, "tokens_predicted": 1}
        return {"choices": [{"message": {"content": self.direct}}], "timings": {"prompt_n": 7, "predicted_n": 1}}

    def kinds(self):
        return [k for k, _ in self.calls]

    def payload(self, kind):
        return [p for k, p in self.calls if k == kind][0]


def run(server, settings=None, problem=PROBLEM, **kw):
    with mock.patch("copilot.llm.post", server), mock.patch.dict(CONFIG, {**REASON, **(settings or {})}):
        return pipeline.solve(problem, llm_url=CHAT, **kw)


class Budget(unittest.TestCase):
    def test_formula_is_the_benchmarks(self):
        with mock.patch.dict(CONFIG, REASON):
            self.assertEqual(pipeline.token_budget(110, 60.0), 282)
            self.assertEqual(pipeline.token_budget(0, 60.0), 342)
            self.assertEqual(pipeline.token_budget(5000, 60.0), 0)
        with mock.patch.dict(CONFIG, {"BOARD_READ_TPS": "5.5", "BOARD_WRITE_TPS": "3"}):
            self.assertEqual(pipeline.token_budget(110, 60.0), 111)
        sys.path.insert(0, os.path.join(ROOT, "laptop"))
        from laptop import bench_exam
        for tokens in (0, 87, 110, 400, 5000):
            with mock.patch.dict(CONFIG, REASON):
                self.assertEqual(pipeline.token_budget(tokens, 60.0), bench_exam.budget(tokens, 11, 6, 60.0, 3.0))

    def test_bad_speeds_fall_back_to_the_defaults(self):
        for bad in ("", "fast", "0", "-3", "nan", "inf"):
            with mock.patch.dict(CONFIG, {"BOARD_READ_TPS": bad, "BOARD_WRITE_TPS": bad}):
                self.assertEqual(pipeline.token_budget(110, 60.0), 282, bad)

    def test_new_settings_exist_and_are_off(self):
        from copilot.config import DEFAULTS
        self.assertEqual((DEFAULTS["BOARD_READ_TPS"], DEFAULTS["BOARD_WRITE_TPS"]), ("11", "6"))
        self.assertEqual((DEFAULTS["ANSWER_MODE"], DEFAULTS["SAVE_TEXTS"]), ("", ""))
        self.assertEqual(DEFAULTS["PRESOLVE"], "1")  # the twin copy is part of what predict.py delivers

    def test_finished_working_gives_its_letter(self):
        server = Server()
        out = run(server)
        self.assertEqual(server.kinds(), ["/apply-template", "/tokenize", "/working"])
        working = server.payload("/working")
        self.assertEqual(working["n_predict"], BUDGET - 1)
        self.assertEqual(working["grammar"], llm.REASON_GRAMMAR)
        self.assertEqual((working["temperature"], working["cache_prompt"]), (0, True))
        self.assertEqual(working["prompt"], server.payload("/tokenize")["content"])
        self.assertTrue(working["prompt"].endswith("E) epsilon\nAnswer:<assistant>"))
        self.assertEqual((out["answer"], out["status"], out["passes"]), ("C", "ok", 1))
        self.assertEqual((out["prompt_tokens"], out["budget_tokens"], out["written_tokens"]), (110, BUDGET, 9))
        self.assertEqual((out["finished"], out["letter_from"], out["working"]), (True, "working", "budget"))

    def test_unfinished_working_is_continued_for_one_letter(self):
        server = Server(working="First, count the sides. Then\nAnsw", forced="B", written=BUDGET - 1)
        out = run(server)
        self.assertEqual(server.kinds(), ["/apply-template", "/tokenize", "/working", "/force"])
        force = server.payload("/force")
        self.assertEqual(force["prompt"],
                         server.payload("/working")["prompt"] + "First, count the sides. Then\nAnswer: ")
        self.assertEqual((force["n_predict"], force["grammar"], force["temperature"]), (1, "root ::= [A-E]", 0))
        self.assertEqual((out["answer"], out["status"]), ("B", "ok"))
        self.assertEqual((out["finished"], out["letter_from"], out["written_tokens"]), (False, "forced", BUDGET))

    def test_a_letter_inside_cut_off_working_is_not_the_answer(self):
        server = Server(working="The answer is A if we forget the last one, but", forced="D")
        out = run(server)
        self.assertEqual((out["answer"], out["finished"], out["letter_from"]), ("D", False, "forced"))

    def test_think_mode_reads_the_letter_in_any_usual_form_and_has_no_grammar(self):
        server = Server(working="3 x 4 = 12.\n**Answer:** B")
        out = run(server, {"ANSWER_MODE": "think"})
        self.assertNotIn("grammar", server.payload("/working"))
        self.assertEqual(server.payload("/apply-template")["messages"][0]["content"], llm.THINK_SYSTEM)
        self.assertFalse(server.payload("/apply-template")["messages"][-1]["content"].endswith("Answer:"))
        self.assertEqual((out["answer"], out["finished"], out["letter_from"]), ("B", True, "working"))
        server = Server(working="so the result is 12", forced="E")
        out = run(server, {"ANSWER_MODE": "think"})
        self.assertEqual((out["answer"], out["finished"], out["letter_from"]), ("E", False, "forced"))

    def test_extra_cap_and_no_room(self):
        server = Server()
        out = run(server, {"REASON_MAX_TOKENS": "100"})
        self.assertEqual((server.payload("/working")["n_predict"], out["budget_tokens"]), (99, 100))
        # A prompt too long to leave room for working: the letter is asked right after the prompt.
        server = Server(prompt_tokens=700, forced="A")
        out = run(server)
        self.assertEqual(server.kinds(), ["/apply-template", "/tokenize", "/force"])
        self.assertEqual(server.payload("/force")["prompt"], server.payload("/tokenize")["content"] + "\nAnswer: ")
        self.assertEqual((out["answer"], out["budget_tokens"], out["written_tokens"], out["finished"]),
                         ("A", 0, 1, False))

    def test_the_answer_does_not_depend_on_the_clock(self):
        def letters(step):
            clock = {"t": 0.0}

            def tick():
                clock["t"] += step
                return clock["t"]
            server = Server(working="Still counting", forced="B")
            with mock.patch("copilot.pipeline.time.perf_counter", tick):
                out = run(server)
            return out["answer"], out["letter_from"], out["budget_tokens"], [(k, p) for k, p in server.calls]
        self.assertEqual(letters(0.0), letters(20.0))  # 20 s per look at the clock: far slower than the board
        self.assertEqual(letters(0.0)[:3], ("B", "forced", BUDGET))


class LastResorts(unittest.TestCase):
    def test_failed_forced_letter_asks_the_plain_question(self):
        server = Server(working="Still counting", fail={"/force"}, direct="D")
        out = run(server)
        self.assertEqual(server.kinds()[-1], "/v1/chat/completions")
        self.assertEqual(server.calls[-1][1]["max_tokens"], 1)
        self.assertEqual((out["answer"], out["status"], out["letter_from"], out["finished"]),
                         ("D", "ok", "direct", False))
        self.assertEqual((out["pass_error"], out["prompt_tokens"]), ("reason: TimeoutError", 110))

    def test_bad_forced_letter_asks_the_plain_question(self):
        out = run(Server(working="Still counting", forced="?", direct="A"))
        self.assertEqual((out["answer"], out["letter_from"]), ("A", "direct"))

    def test_failed_working_asks_the_plain_question(self):
        server = Server(fail={"/working"}, direct="E")
        out = run(server)
        self.assertEqual(server.kinds(), ["/apply-template", "/tokenize", "/working", "/v1/chat/completions"])
        self.assertEqual((out["answer"], out["status"], out["letter_from"]), ("E", "ok", "direct"))

    def test_server_that_cannot_count_uses_a_fixed_number_of_tokens(self):
        for fail in ({"/apply-template"}, {"/tokenize"}):
            server = Server(fail=fail)
            server.direct = "Short working.\nAnswer: B"
            out = run(server)
            self.assertEqual(server.kinds()[-1], "/v1/chat/completions")
            self.assertEqual(server.calls[-1][1]["max_tokens"], pipeline.FIXED_WORKING_TOKENS)
            self.assertEqual((out["answer"], out["working"], out["budget_error"], out["letter_from"]),
                             ("B", "fixed", "TimeoutError", "working"))

    def test_a_picture_uses_the_chat_path(self):
        server = Server()
        server.direct = "Short working.\nAnswer: B"
        out = run(server, image_b64="aGk=")
        self.assertEqual(server.kinds(), ["/v1/chat/completions"])
        self.assertEqual((out["answer"], out["working"], out["budget_error"]), ("B", "fixed", "image"))

    def test_default_mode_is_one_plain_letter_and_nothing_else(self):
        server = Server(direct="C")
        out = run(server, {"ANSWER_MODE": ""})
        self.assertEqual(server.kinds(), ["/v1/chat/completions"])
        self.assertEqual(server.calls[0][1], llm._payload(PROBLEM, (), None))
        self.assertEqual(out, {"answer": "C", "status": "ok", "prompt_tokens": 7, "retrieved": "", "examples": [],
                               "logprobs": {}, "passes": 1, "retrieval_error": "", "seconds": out["seconds"]})


class SaveTexts(unittest.TestCase):
    def test_appends_one_line_per_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "texts.jsonl")
            run(Server(), {"SAVE_TEXTS": path})
            run(Server(working="Still counting", forced="B"), {"SAVE_TEXTS": path})
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f]
        self.assertEqual([(r["id"], r["answer"], r["finished"], r["letter_from"]) for r in rows],
                         [("synthetic-1", "C", True, "working"), ("synthetic-1", "B", False, "forced")])
        self.assertEqual(rows[0]["text"], "It is the third.\nAnswer: C")
        self.assertEqual((rows[0]["budget_tokens"], rows[0]["written_tokens"], rows[0]["mode"]), (BUDGET, 9, "reason"))

    def test_refuses_a_file_git_would_see(self):
        path = os.path.join(ROOT, "docs", "texts-test-should-not-exist.jsonl")
        out = run(Server(), {"SAVE_TEXTS": "docs/texts-test-should-not-exist.jsonl"})
        self.assertFalse(os.path.exists(path))
        self.assertIn("results/", out["save_error"])
        self.assertEqual((out["answer"], out["status"]), ("C", "ok"))

    def test_off_by_default_and_nothing_to_save_without_working(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "texts.jsonl")
            run(Server())
            run(Server(direct="C"), {"ANSWER_MODE": "", "SAVE_TEXTS": path})
            self.assertFalse(os.path.exists(path))


TRAIN = [{"id": "t1", "language": "eng", "label": "B",
          "text": "A farmer has twelve sheep and buys three times as many. How many sheep does the farmer have now?",
          "options": {"A": "15", "B": "48", "C": "24", "D": "36", "E": "39"}}]
TWIN = {"id": "q1", "language": "eng",
        "text": "A farmer has twelve sheep and buys three times as many. How many sheep does the farmer have now?",
        "options": {"A": "48", "B": "15", "C": "24", "D": "36", "E": "39"}}


class Presolve(unittest.TestCase):
    def setUp(self):
        pipeline._PRESOLVE_INDEX.clear()
        self.addCleanup(pipeline._PRESOLVE_INDEX.clear)
        f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        f.write("\n".join(json.dumps(p) for p in TRAIN) + "\n")
        f.close()
        self.addCleanup(os.unlink, f.name)
        self.on = {"PRESOLVE": "1", "PRESOLVE_DATA": f.name}

    def test_a_twin_is_answered_without_the_model(self):
        server = Server()
        out = run(server, self.on, problem=TWIN)
        self.assertEqual(server.calls, [])
        self.assertEqual((out["answer"], out["status"], out["passes"]), ("A", "presolve", 0))
        self.assertEqual(out["presolve"], "value:t1:1.0")

    def test_no_twin_goes_to_the_model(self):
        server = Server()
        out = run(server, self.on)
        self.assertEqual((out["answer"], out["status"], out["letter_from"]), ("C", "ok", "working"))
        self.assertNotIn("presolve", out)

    def test_exclude_id_and_own_id_are_never_copied(self):
        for problem, kw in (({**TWIN, "id": "t1"}, {}), (TWIN, {"exclude_id": "t1"})):
            out = run(Server(), self.on, problem=problem, **kw)
            self.assertEqual((out["status"], out["answer"]), ("ok", "C"))

    def test_a_copied_letter_answers_a_close_twin_without_options(self):
        # On the training split a letter copied from a close twin is right about half the time, against
        # about a fifth for the model, so it answers with or without a fixed prior.
        no_options = {**TWIN, "options": {}}
        server = Server(direct="D")
        out = run(server, self.on, problem=no_options)
        self.assertEqual((out["answer"], out["status"], len(server.calls)), ("B", "presolve", 0))
        out = run(Server(), {**self.on, "NO_OPTIONS_PRIOR": "E"}, problem=no_options)
        self.assertEqual((out["answer"], out["status"], out["presolve"]), ("B", "presolve", "letter:t1:1.0"))
        out = run(Server(), {**self.on, "NO_OPTIONS_PRIOR": "E"}, problem={**PROBLEM, "options": {}})
        self.assertEqual((out["answer"], out["status"]), ("E", "prior"))

    def test_missing_training_file_is_not_an_error(self):
        out = run(Server(), {"PRESOLVE": "1", "PRESOLVE_DATA": "/nonexistent/train.jsonl"}, problem=TWIN)
        self.assertEqual((out["answer"], out["status"], out["presolve_error"]), ("C", "ok", "FileNotFoundError"))

    def test_off_by_default_never_opens_the_file(self):
        with mock.patch("copilot.pipeline.open", side_effect=AssertionError("opened"), create=True):
            out = run(Server(), {"PRESOLVE_DATA": self.on["PRESOLVE_DATA"]}, problem=TWIN)
        self.assertEqual((out["status"], out["answer"]), ("ok", "C"))
        self.assertEqual(pipeline._PRESOLVE_INDEX, {})


if __name__ == "__main__":
    unittest.main()
