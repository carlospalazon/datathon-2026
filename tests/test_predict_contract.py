"""predict.py must answer every problem with one letter, A to E, whatever the model server does.

Runs on a laptop, without models: a fake server plays a broken llama-server.

    python3 -m unittest discover -s tests -v
"""
import csv
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "data", "sample_problems.jsonl")
sys.path.insert(0, ROOT)

from copilot.pipeline import solve  # noqa: E402


def reply(letter):
    return {"choices": [{"message": {"content": letter}}], "timings": {"prompt_n": 42}}


class FakeServer:
    """A fake llama-server on a free port. `mode` decides how it answers."""

    def __init__(self, mode):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if server.mode == "drop":            # crashes mid-request, e.g. killed for memory
                    self.close_connection = True
                    return
                if server.mode == "slow":            # slower than the time limit
                    time.sleep(4)
                if server.mode == "http500":
                    body, code = b'{"error": "boom"}', 500
                elif server.mode == "badjson":
                    body, code = b"not json", 200
                elif server.mode == "noletter":      # valid JSON, but no letter A to E
                    body, code = json.dumps(reply("Z")).encode(), 200
                elif server.mode == "noshape":       # valid JSON, unexpected shape
                    body, code = b'{"unexpected": true}', 200
                else:
                    body, code = json.dumps(reply("B")).encode(), 200
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.mode = mode
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}/v1/chat/completions"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PROBLEM = {"id": "synthetic-1", "language": "eng", "text": "What is 1 + 1?",
           "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"}}


class SolveAlwaysAnswers(unittest.TestCase):
    def check(self, mode, status_start, answer="D", time_limit=60.0):
        server = FakeServer(mode)
        try:
            result = solve(PROBLEM, llm_url=server.url, time_limit=time_limit)
        finally:
            server.close()
        self.assertEqual(result["answer"], answer)
        self.assertTrue(result["status"].startswith(status_start), result["status"])
        return result

    def test_ok(self):
        result = self.check("ok", "ok", answer="B")
        self.assertEqual(result["prompt_tokens"], 42)

    def test_connection_refused(self):
        url = f"http://127.0.0.1:{free_port()}/v1/chat/completions"
        result = solve(PROBLEM, llm_url=url)
        self.assertEqual(result["answer"], "D")
        self.assertTrue(result["status"].startswith("error"), result["status"])

    def test_dropped_connection(self):
        self.check("drop", "error")

    def test_bad_json(self):
        self.check("badjson", "error")

    def test_unexpected_shape(self):
        self.check("noshape", "error")

    def test_not_a_letter(self):
        self.check("noletter", "error")

    def test_http_500(self):
        self.check("http500", "error")

    def test_timeout(self):
        # time_limit 5 minus the 3-second margin: the client gives up after 2 s
        result = self.check("slow", "timeout", time_limit=5.0)
        self.assertLess(result["seconds"], 5.0)


class PredictWritesEveryRow(unittest.TestCase):
    """End to end: run predict.py as the organizers do, against a broken server."""

    def run_predict(self, port):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "predictions.csv")
            env = {**os.environ, "LLM_PORT": str(port)}
            done = subprocess.run([sys.executable, "predict.py", "--input", SAMPLES, "--output", out],
                                  cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stderr)
            with open(out, newline="") as f:
                return list(csv.DictReader(f))

    def assert_contract(self, rows):
        with open(SAMPLES) as f:
            ids = [json.loads(line)["id"] for line in f if line.strip()]
        self.assertEqual([r["id"] for r in rows], ids)
        for r in rows:
            self.assertIn(r["answer"], list("ABCDE"))
            self.assertLess(float(r["seconds"]), 60)
            self.assertTrue(r["status"])

    def test_every_failure_mode(self):
        for mode in ("ok", "drop", "badjson", "noletter", "http500"):
            with self.subTest(mode=mode):
                server = FakeServer(mode)
                try:
                    self.assert_contract(self.run_predict(server.port))
                finally:
                    server.close()

    def test_no_server(self):
        self.assert_contract(self.run_predict(free_port()))


if __name__ == "__main__":
    unittest.main()
