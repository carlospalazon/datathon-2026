"""The page clicked through without a browser, on a made-up catalogue: no model, no M3Kang data.

Starts teach/server.py's app on a free port and runs tests/page_harness.mjs (the page's own
script against a small stand-in for the DOM). Skipped where node is not installed.

    python3 -m unittest tests.test_page -v
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "teach"))

import server  # noqa: E402


def catalogue():
    rows = []
    for block in range(3):
        for i in range(6):   # enough for the tutor, an exam, its review and a session without running out
            n = block * 8 + i + 1
            rows.append({"key": f"lvl-0_2020_{n}_cat", "id": f"lvl-0_2020_{n}", "language": "cat", "stage": "primaria",
                         "level": 0, "grade": 5, "block": block, "question_number": n, "difficulty": block,
                         "topic": ("visual", "geometria_espacial")[n % 2] if block == 2 else "aritmetica", "text": f"{n}. Made-up problem {n}", "label": "C",
                         "question": f"A made-up shelf has 12 boxes with 7 pens each. Box {n + 20} is empty; how many pens?",
                         "needs_figure": bool(n % 2),
                         "anatomy": {"key_data": "12 boxes; 7 pens in each box.", "key_condition": "One box is empty.",
                                     "first_step": "SECRET STEP", "strategy": "made_up", "status": "generado:test"},
                         "options": {"A": "1", "B": "2", "C": "3", "D": "4", "E": "5"},
                         "solution": {"text": "Made-up solution.", "status": "revisado"},
                         "hints": [{"text": "Made-up hint.", "status": "revisado"}], "distractors": {}})
    return rows


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Page(unittest.TestCase):
    def test_the_click_path_through_tutor_practice_and_exam(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "catalog.jsonl")
            with open(path, "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in catalogue())
            args = argparse.Namespace(catalog=path, types="content/types_primaria.json", images=tmp, stage="primaria",
                                      language="cat", show="revisado,preparado,generado", profile="",
                                      think=1)  # one second of think-first time: the harness waits for it
            app = server.App(args)
            handler = server.make_handler(app)
            handler.log_message = lambda *a: None
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                run = subprocess.run(["node", os.path.join(ROOT, "tests", "page_harness.mjs"),
                                      f"http://127.0.0.1:{httpd.server_port}"],
                                     capture_output=True, text=True, timeout=120)
            finally:
                httpd.shutdown()
                httpd.server_close()
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("OK: 17 steps", run.stdout)


if __name__ == "__main__":
    unittest.main()
