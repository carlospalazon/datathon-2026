import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyze_errors import load_catalog, load_results, main, option_evidence, report, review_candidates


class ErrorAnalysisTests(unittest.TestCase):
    def test_join_groups_and_review_sample(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            catalog_path = base / "catalog.jsonl"
            eval_path = base / "eval.csv"
            problems = [
                {"id": "madeup_1", "language": "eng", "level": 1, "difficulty": 4,
                 "topic": "algebra", "label": "B", "options": {"A": "1"},
                 "options_status": "ocr", "ocr_flags": []},
                {"id": "madeup_2", "language": "cat", "level": 2, "difficulty": 8,
                 "topic": "conteo", "label": "C", "options": {}, "options_status": "none",
                 "needs_figure": True},
                {"id": "madeup_3", "language": "eng", "level": 1, "difficulty": 5,
                 "topic": "algebra", "label": "D", "options": {"A": "2"},
                 "options_status": "revisado", "ocr_flags": []},
            ]
            catalog_path.write_text("\n".join(json.dumps(p) for p in problems) + "\n")
            with eval_path.open("w", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(["id", "language", "level", "label", "answer", "correct", "seconds", "status"])
                writer.writerows([("madeup_1", "eng", 1, "B", "A", 0, 9.0, "ok"),
                                  ("madeup_2", "cat", 2, "C", "D", 0, 11.0, "timeout"),
                                  ("madeup_3", "eng", 1, "D", "D", 1, 7.0, "ok")])
            catalog = load_catalog(catalog_path)
            rows = load_results(eval_path, catalog)
            self.assertEqual(len(rows), 3)
            self.assertEqual([r["id"] for r in review_candidates(rows, 2)], ["madeup_1", "madeup_2"])
            markdown = report(rows, eval_path)
            for expected in ("1/3", "By topic", "By language", "By estimated difficulty",
                             "By answer-option evidence", "OCR/unreviewed", "no options"):
                self.assertIn(expected, markdown)
            self.assertNotIn("question text", markdown)
            report_path = base / "report.md"
            review_path = base / "review.csv"
            with patch("sys.argv", ["analyze_errors.py", "--eval", str(eval_path),
                                    "--catalog", str(catalog_path), "--out", str(report_path),
                                    "--review-out", str(review_path), "--review-limit", "2"]):
                main()
            self.assertIn("By topic", report_path.read_text())
            with review_path.open(newline="") as source:
                review_rows = list(csv.DictReader(source))
            self.assertEqual(len(review_rows), 2)
            self.assertEqual(review_rows[0]["suspected_cause"], "")

    def test_option_evidence_is_cautious(self):
        self.assertEqual(option_evidence({"options": {}}), "no options")
        self.assertEqual(option_evidence({"options": {"A": "1"}, "ocr_flags": ["duplicate"]}), "OCR flagged")
        self.assertEqual(option_evidence({"options": {"A": "1"}, "options_status": "revisado"}), "human reviewed")

    def test_missing_catalog_row_is_an_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "eval.csv"
            path.write_text("id,language,level,label,answer,correct,seconds,status\n"
                            "madeup_1,eng,1,B,A,0,9,ok\n")
            with self.assertRaisesRegex(ValueError, "no catalogue metadata"):
                load_results(path, {})
