import contextlib
import csv
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import analyze_errors as ae
import calibrate
import eval as ev

OLD_HEADER = "id,language,level,has_options,label,answer,correct,seconds,status,prompt_tokens,retrieved"


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


def old_csv(path, rows):
    write(path, OLD_HEADER + "\n" + "".join(
        f"{i},{lang},{lvl},{ho},{lab},{ans},{int(lab == ans)},{sec},{st},10,\n"
        for i, lang, lvl, ho, lab, ans, sec, st in rows))


class Stats(unittest.TestCase):
    def test_wilson_known_values(self):
        lo, hi = ae.wilson(50, 100)
        self.assertAlmostEqual(lo, 0.4038, places=3)
        self.assertAlmostEqual(hi, 0.5962, places=3)
        lo, hi = ae.wilson(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.2775, places=3)
        self.assertEqual(ae.wilson(0, 0), (0.0, 1.0))

    def test_mcnemar_exact(self):
        self.assertAlmostEqual(ae.mcnemar_exact(0, 10), 2 / 1024)
        self.assertEqual(ae.mcnemar_exact(5, 5), 1.0)
        self.assertEqual(ae.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(ae.mcnemar_exact(2, 8), 0.109375)


class Analyze(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def p(self, name):
        return os.path.join(self.dir, name)

    def tables(self, tables):
        return {t[0]: t for t in tables}

    def test_old_format_without_catalogue(self):
        old_csv(self.p("a.csv"), [("q1", "eng", 0, "True", "A", "A", 1.0, "ok"),
                                  ("q2", "eng", 1, "False", "B", "C", 70.0, "timeout"),
                                  ("q3", "cat", 1, "True", "C", "C", 2.0, "error: x")])
        tables, notes = ae.analyze(self.p("a.csv"), self.p("none.jsonl"))
        t = self.tables(tables)
        self.assertEqual(t["By language"][2], [["cat", "1/1", "100.0%", ae.fmt_ci(1, 1)],
                                               ["eng", "1/2", "50.0%", ae.fmt_ci(1, 2)]])
        self.assertNotIn("By topic", t)
        self.assertNotIn("By needs_figure", t)
        self.assertTrue(any("No topic" in n for n in notes))
        self.assertEqual(t["Latency (seconds)"][2][0][-1], "1")
        self.assertIn(["timeout", "1"], t["Status"][2])
        self.assertIn(["error", "1"], t["Status"][2])
        self.assertEqual(t["Letter confusion (rows: true, columns: predicted)"][2][1][3], "1")

    def test_catalogue_join_and_answerable(self):
        old_csv(self.p("a.csv"), [("q1", "eng", 0, "True", "A", "A", 1.0, "ok"),
                                  ("q1", "cat", 0, "True", "A", "B", 1.0, "ok"),
                                  ("q2", "eng", 1, "True", "B", "B", 1.0, "ok")])
        write(self.p("cat.jsonl"),
              json.dumps({"id": "q1", "language": "eng", "topic": "algebra", "needs_figure": False}) + "\n"
              + json.dumps({"id": "q1", "language": "cat", "topic": "algebra", "needs_figure": True}) + "\n")
        cat = ae.load_catalog(self.p("cat.jsonl"))
        self.assertEqual(cat[("q1", "eng")]["topic"], "algebra")
        tables, _ = ae.analyze(self.p("a.csv"), self.p("cat.jsonl"))
        t = self.tables(tables)
        self.assertEqual(t["By topic"][2], [["algebra", "1/2", "50.0%", ae.fmt_ci(1, 2)]])
        ans = [x for k, x in t.items() if k.startswith("Answerable")][0]
        self.assertEqual(ans[2], [["False", "0/1", "0.0%", ae.fmt_ci(0, 1)],
                                  ["True", "1/1", "100.0%", ae.fmt_ci(1, 1)]])

    def test_new_format_and_markdown(self):
        write(self.p("n.csv"), OLD_HEADER + ",topic,needs_figure,passes,lp_A,lp_B,lp_C,lp_D,lp_E\n"
              "q1,eng,0,True,A,A,1,1.0,ok,10,,conteo,False,1,,,,,\n"
              "q2,eng,0,True,B,A,0,1.0,ok,10,,conteo,True,1,,,,,\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ae.main([self.p("n.csv"), "--catalog", self.p("none"), "--markdown", self.p("o.md")])
        self.assertIn("By topic", out.getvalue())
        md = open(self.p("o.md")).read()
        self.assertIn("| conteo | 1/2 | 50.0% |", md)
        self.assertIn("|---|", md)

    def test_compare(self):
        a = [(f"q{i}", "eng", 0, "True", "A", "A" if i < 8 else "B", 1.0, "ok") for i in range(10)]
        b = [(f"q{i}", "eng", 0, "True", "A", "B" if i < 8 else "A", 1.0, "ok") for i in range(10)]
        old_csv(self.p("a.csv"), a)
        old_csv(self.p("b.csv"), b)
        tables, notes = ae.analyze(self.p("a.csv"), self.p("none"), self.p("b.csv"))
        t = [x for x in tables if x[0].startswith("Paired")][0]
        self.assertEqual(t[2][0][:4], ["0", "8", "2", "0"])
        self.assertEqual(t[2][0][4], "0.1094")
        self.assertTrue(any("NOT significant" in n for n in notes))

    def test_compare_ignores_unshared(self):
        old_csv(self.p("a.csv"), [("q1", "eng", 0, "True", "A", "A", 1.0, "ok")])
        old_csv(self.p("b.csv"), [("q1", "cat", 0, "True", "A", "A", 1.0, "ok")])
        _, notes = ae.analyze(self.p("a.csv"), self.p("none"), self.p("b.csv"))
        self.assertTrue(any("No shared" in n for n in notes))


class Calibrate(unittest.TestCase):
    def rows(self):
        # the model over-favours C by 2 nats; the true letter is slightly ahead of C otherwise
        data = []
        for i in range(10):
            label = "AB"[i % 2]
            lps = {l: -3.0 for l in "ABCDE"}
            lps["C"] = -1.0
            lps[label] = -0.5 if i < 5 else -1.5  # clearly right on half; on the rest C wins
            data.append((label, lps))
        return data

    def test_correction_changes_argmax(self):
        data = [(lab, [lp[l] for l in "ABCDE"]) for lab, lp in self.rows()]
        off, before, after, loo = calibrate.evaluate(data)
        self.assertEqual(before, 5)
        self.assertGreater(off[2], off[0])
        self.assertEqual(calibrate.argmax_letter(data[9][1]), "C")
        self.assertEqual(calibrate.argmax_letter([x - o for x, o in zip(data[9][1], off)]) in "AB", True)
        self.assertGreater(after, before)
        self.assertGreaterEqual(loo, before)

    def test_cli_and_errors(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.csv")
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["id", "language", "has_options", "label", "lp_A", "lp_B", "lp_C", "lp_D", "lp_E"])
                for lab, lp in self.rows():
                    w.writerow(["q", "eng", "True", lab] + [lp[l] for l in "ABCDE"])
                w.writerow(["q", "eng", "False", "A", -1, -1, -1, -1, -1])
                w.writerow(["q", "eng", "True", "A", "", "", "", "", ""])
            out_json = os.path.join(d, "b.json")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                calibrate.main([path, "--output", out_json])
            self.assertIn("Rows used: 10", out.getvalue())
            self.assertIn("WARNING", out.getvalue())
            self.assertEqual(sorted(json.load(open(out_json))), list("ABCDE"))
            old = os.path.join(d, "old.csv")
            write(old, OLD_HEADER + "\n")
            with self.assertRaises(SystemExit) as cm:
                calibrate.main([old, "--output", out_json])
            self.assertIn("no lp_A", str(cm.exception))


class EvalMain(unittest.TestCase):
    def test_ablation_header_migration(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ablations.csv")
            old = ["time", "name", "commit", "input", "languages", "n", "rag_k", "accuracy",
                   "mean_s", "worst_s", "over_limit"]
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(old)
                w.writerow(["t0", "base", "abc", "data/val.jsonl", "all", "50", "0", "40.0", "5", "9", "0"])
            new_row = ["t1", "x", "def", "i", "all", "10", "0", "50.0", "1", "2", "0", "30.0", "70.0", "K=V"]
            ev.append_ablation(path, new_row)
            ev.append_ablation(path, new_row)
            rows = list(csv.reader(open(path)))
            self.assertEqual(rows[0], ev.ABLATION_COLUMNS)
            self.assertEqual(rows[0][:11], old)
            self.assertEqual(rows[1][:2], ["t0", "base"])
            self.assertEqual(rows[1][11:], ["", "", ""])
            self.assertEqual(rows[2], new_row)
            self.assertEqual(len(rows), 4)

    def test_main_with_mock_solve(self):
        def fake(problem, index=None, k=0, exclude_id=None):
            has_lp = problem["id"] == "q1"
            r = {"answer": "A", "seconds": 1.5, "status": "ok", "prompt_tokens": 7, "retrieved": ""}
            if has_lp:
                r.update(logprobs={"A": -0.1, "B": -2, "C": -3, "D": -4, "E": -5}, passes=2)
            return r

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            self.addCleanup(os.chdir, cwd)
            probs = [{"id": "q1", "language": "eng", "level": 0, "label": "A", "options": {"A": "x"}},
                     {"id": "q1", "language": "cat", "level": 0, "label": "A", "options": {"A": "x"}},
                     {"id": "q2", "language": "eng", "level": 1, "label": "B", "options": None}]
            write("val.jsonl", "".join(json.dumps(x) + "\n" for x in probs))
            write("cat.jsonl", json.dumps({"id": "q1", "language": "eng", "topic": "conteo",
                                           "needs_figure": False, "topic_confidence": "high"}) + "\n")
            out = io.StringIO()
            with mock.patch.object(ev, "solve", fake), mock.patch.dict(
                    os.environ, {"NO_OPTIONS_PRIOR": "1", "LETTER_BIAS_FILE": "b.json"}), \
                    contextlib.redirect_stdout(out):
                ev.main(["--input", "val.jsonl", "--limit", "0", "--catalog", "cat.jsonl", "--name", "t"])
            text = out.getvalue()
            self.assertIn("95% CI", text)
            self.assertIn("noise", text)
            self.assertIn("By topic", text)
            detail = [f for f in os.listdir("results") if f.startswith("eval-")][0]
            rows = list(csv.DictReader(open(os.path.join("results", detail))))
            self.assertEqual(len(rows), 3)
            self.assertEqual(list(rows[0])[:11], OLD_HEADER.split(","))
            self.assertEqual(list(rows[0])[11:], ["topic", "needs_figure", "passes"] +
                             [f"lp_{l}" for l in "ABCDE"])
            by_id = {(r["id"], r["language"]): r for r in rows}
            self.assertEqual(by_id[("q1", "eng")]["topic"], "conteo")
            self.assertEqual(by_id[("q1", "eng")]["lp_A"], "-0.1")
            self.assertEqual(by_id[("q1", "eng")]["passes"], "2")
            self.assertEqual(by_id[("q2", "eng")]["lp_A"], "")
            self.assertEqual(by_id[("q2", "eng")]["topic"], "")
            ab = list(csv.DictReader(open("results/ablations.csv")))[0]
            self.assertEqual(ab["env"], "NO_OPTIONS_PRIOR=1;LETTER_BIAS_FILE=b.json")
            self.assertLess(float(ab["ci_low"]), float(ab["ci_high"]))

    def test_one_per_id_and_missing_catalogue(self):
        calls = []

        def fake(problem, **kw):
            calls.append(problem["id"])
            return {"answer": "A", "seconds": 1.0, "status": "ok", "prompt_tokens": 0, "retrieved": ""}

        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            self.addCleanup(os.chdir, cwd)
            probs = [{"id": f"q{i}", "language": lang, "level": 0, "label": "A", "options": {"A": "x"}}
                     for i in range(4) for lang in ("eng", "cat", "spa")]
            write("val.jsonl", "".join(json.dumps(x) + "\n" for x in probs))
            with mock.patch.object(ev, "solve", fake), contextlib.redirect_stdout(io.StringIO()):
                ev.main(["--input", "val.jsonl", "--limit", "0", "--one-per-id", "--catalog", "nope"])
            self.assertEqual(sorted(calls), ["q0", "q1", "q2", "q3"])


if __name__ == "__main__":
    unittest.main()
