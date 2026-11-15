# Product lab: original features for Tutor Cangur

Memory of the **Product** role. Newest "Built" entry at the bottom. No problem text here.

## Backlog (best first)

| # | Feature | Why a student or teacher wants it | Uses | Status |
|---|---|---|---|---|
| 1 | **"One like this, but yours."** After a wrong answer (or on request), generate a fresh problem of the same kind with smaller numbers, solvable in a minute, then return to the original. | Practice on the exact skill that failed, never the same problem twice, nothing to memorise. | synthetic generators (computed answers, worked solutions, 3 languages), topic of the current problem | **built** (2026-11-15; smallest of 8 draws rather than purpose-made small numbers) |
| 2 | **Mistake names on generated problems.** Each wrong option of a generated problem is the result of a known slip: say which ("you added the prices but forgot the quantities"), without giving the answer. | Feedback that is specific, instant and needs no model. | generators' wrong-option formulas, `copilot/diagnose.py` | **built** (2026-11-15; 16 generators, slips worked out again from `params`) |
| 3 | **Cangur exam mode.** A timed paper built from the catalogue by level, with the real scoring (3/4/5 points, a quarter of the points lost per wrong answer, blank is free), a countdown on the LED matrix, and a review at the end that leads into the tutor. | The real competition experience; shows when leaving a blank is the right call. | catalogue levels, LED matrix, student memory | **built** (2026-11-15; scoring settings need checking; the student memory is not fed) |
| 4 | **Skill map.** One screen (and a matrix view) of the student's topics by level: tried, mastered, shaky, with "what to try next". A teacher view of the class as a heat map, by pseudonym. | Students see progress; teachers see where the class is stuck. | SQLite student memory, topics | open |
| 5 | **Think-first timer.** The page hides the hint button for the first seconds of a new problem and shows a calm progress ring; the board uses that time to get the help ready. | Encourages a real attempt, and makes the wait invisible. | read-ahead of the problem (already in the app), LED matrix | open |
| 6 | **Explain it back.** After a right answer, one tap picks which of three explanations matches how the student solved it (the checked solution and two wrong methods that also give that number). | Checks understanding, not luck. | checked solutions, generators' typical mistakes | open |
| 7 | **Reading modes.** One idea per line, larger spacing, key data highlighted, a "numbers only" strip; chosen by the student, remembered, never labelled. | Dyslexia- and dyscalculia-friendly without a separate product. | key data and key condition already in the catalogue | open |
| 9 | **Practice feeds the memory.** A slip named on a practice problem counts in the student memory (topic, slip), so the second time the tutor goes to the method card, and the skill map (4) can show it. | The tutor learns from practice too, not only from Cangur problems. | `copilot/practice.py` codes, SQLite `errors` table | open |
| 10 | **Practice for the picture topics.** Generators with a figure drawn by the page (grids to count, folded paper, cube nets) so `visual` and `geometria_espacial` get a practice problem too. | 28 of the 154 primary problems have no practice today. | new generators of our own, SVG drawn by the page | open |
| 11 | **Warm-up of three.** Before the first Cangur problem, three one-minute generated problems, one per topic the student found hardest last time. | A start that always succeeds, and it uses the memory. | `copilot/practice.py`, student memory | open |
| 12 | **The exam feeds the memory and the tutor.** Wrong and blank exam questions go to the student memory by topic, and the result offers "repassa les que has fallat" as one queue instead of one button per question. | The exam becomes the tutor's plan for the next session. | `copilot/exam.py` results, SQLite student memory | open |
| 13 | **Printable paper and answer sheet for the class.** The teacher starts one paper, every device gets the same questions, and the board shows the shared countdown. | A whole class sits the same mock exam with one board. | `copilot/exam.py` (seeded papers), LED matrix | open |
| 8 | **Class duel.** Two students (or two halves of the class) answer the same problem on two devices; the matrix shows the vote split before the answer is revealed. | Makes the board the centre of a classroom debate. | LED matrix, web page | open |

## For the model lab

(Requests from Product to the model lab, and answers.)

- **2026-11-15, from Product (`laptop/synthetic_problems.py`, not edited by us):**
  1. `make()` could return which entry of `wrong` each option came from (for example
     `sources: {"A": 2, "C": None}`, the index in `wrong` or `None` for a filler). Today
     `copilot/practice.py` works every slip out again from `params`, which only holds while your
     formulas stay as they are (a test of ours fails when they change, and the page then says nothing
     rather than something wrong).
  2. `color_pattern` could put its colour list in `params`, and `race_logic` its clues: without
     them no wrong option of theirs can be explained.
  3. Text glitches seen in Catalan while testing: "a 1 euros la unitat" (singular) in `shopping`,
     and "just després de Anna" (should be "d'Anna") in `race_logic`.
  4. A `small=True` draw (numbers a 10-year-old does in the head) would beat our "smallest of 8 draws".

## Built

<!-- Template:
### YYYY-MM-DD HH:MM · short name
- **What:**
- **Why:**
- **See it:** command, URL, what to click
- **Tests / checks run:**
- **Not done:**
- **Commit:**
-->

### 2026-11-15 01:55 · One like this, but yours (backlog 1 and 2)
- **What:** a practice problem made on the spot, of the same topic as the Cangur problem on screen,
  with the answer computed and the slip behind a wrong option named in a sentence. New module
  `copilot/practice.py` (wraps the generators, never edits them), four endpoints (`practiceok`,
  `practice`, `practiceanswer/<letter>`, `practicesolution`), a card in the page, and the same
  endpoints in the App Lab app. Tick, cross and "?" go to the LED matrix with the existing events.
  Covered topics (126 of the 154 primary problems): arithmetic, hidden number, counting, number
  properties, patterns, plane geometry, measure, logic. 17 generators; 16 have named slips
  (52 sentences, Catalan and English). No model is used at all.
- **Why:** the student practises the exact skill that just failed on a problem nobody has seen
  before, and the feedback says what went wrong ("this is what everything costs; the question is
  how much comes back") the instant they click, without giving the answer. A teacher gets unlimited
  problems with honest feedback, offline.
- **See it:** `python3 teach/server.py --port 8650`, open http://127.0.0.1:8650. The first problem
  is a measure problem: click a wrong letter, then the green button **"Prova'n un de semblant, però
  teu"** in the red message (or **"Un de semblant"** next to "Següent problema" at any time). On the
  card, click wrong options to read the slip behind each one, the right one to get the worked
  solution, "Un altre" for a different kind, "Com es resol" (after one try) for the solution, and
  "Torna al meu problema" to close it. The Cangur problem stays where it was.
- **Tests / checks run:** `python3 -m pytest -q`: 198 passed (16 new in `tests/test_practice.py`,
  among them: over 200 seeds in 2 languages the answer we work out equals the generator's; a named
  option is never the right one; no message contains a digit, so none can contain the answer; the
  view sent to the page has no answer). Server on port 8643 with curl: page served with the
  button, practice made, each letter answered, slip named, solution on request, bad letter
  refused, original problem's `answer`, `help` and `state` still working; server stopped.
  `node --check` on the page script: OK. `applab/package.py` built into a scratch folder and
  `copilot.practice` imported from the build: OK.
- **Not done:** not clicked through in a browser (only curl and the syntax check), and not run on
  the board. Share of wrong options with a named slip: about two thirds overall, from 100% (L-shaped
  floor, film time) to about 30% (ribbon, hidden number, sharing); the rest are the generators' "one
  more, one less" fillers and get a neutral line; `race_logic` gets a way to check instead of a
  name. No practice for `visual`, `geometria_espacial` and `otros` (button hidden). Of 8 draws the page shows the one
  with most named options and then the smallest numbers; they are not purpose-made small numbers. Practice does not feed the student memory. The
  page stays Catalan-only; Spanish messages not written. Catalan sentences need a native read.
- **Commit:** 3595d99, and a follow-up that makes the sentences fit every wording of a generator
  (see `git log -2 -- copilot/practice.py`)


### 2026-11-15 04:30 · Cangur exam mode (backlog 3)
- **What:** a timed paper in the tutor's place. New module `copilot/exam.py` (no model, its own
  state apart from the tutor's session), seven endpoints (`examinfo`, `examstart/<level>/<paper>`,
  `examstate`, `examanswer/<n>/<letter>`, `examtick`, `examfinish`, `examclose`) in
  `teach/server.py` and in the App Lab app, a pane in the page, and a `clock` event for the LED
  matrix (minutes left as a number, seconds in the last minute, the share of time left as a bar on
  the bottom row; RGB LED blue). A paper takes the same number of problems from each of the three
  blocks of the level chosen (5th or 6th of primary): "Tast" 3 questions in 3 minutes, "Curt" 9 in
  15, "Complet" 24 in 60. While it runs there is no feedback at all: a letter can be changed or
  left blank again, and the server owns the clock (when the time is over the paper is handed in as
  it is, and a page reload goes back to the running paper). The result gives the score, what the
  wrong answers cost, the score there would have been leaving them blank, a line on when a guess
  pays, and a review list where each question opens in the tutor with hints. The right letter is
  never sent, neither during the paper nor in the result. A second paper takes problems not yet
  used first.
- **Why:** the real competition experience, offline, in three minutes or in an hour; and the
  result shows with the student's own numbers when a blank beats a guess. The review turns every
  miss into a tutor session instead of a red cross with the answer next to it.
- **See it:** `python3 teach/server.py --port 8650`, open http://127.0.0.1:8650, click **"Mode
  examen"** (top right). Pick "5è de primària" and "Tast · 3 preguntes · 3 minuts", then **"Comença
  l'examen"**. Mark letters (the matrix under the page shows the countdown), try "Deixa-la en
  blanc" and the numbered chips, then **"Lliura l'examen"** and "Sí, lliura'l". On the result click
  **"Repassa-la amb el tutor"** on a question; **"Resultats de l'examen"** in the header leads back.
  To see the time run out, start a "Tast" and wait 3 minutes.
- **Scoring: needs checking.** All of it is the `SETTINGS` dictionary at the top of
  `copilot/exam.py`. From the owner: 3, 4 and 5 points, a quarter lost per wrong answer, blank
  free. Assumed by us and NOT checked against the real rules for primary: `start_per_question`
  = 1 (points every student starts with, so no score is below zero; the page states it as a rule:
  "Comences amb 1 punt per pregunta"; set it to 0 and the line disappears), 8 questions per block
  in the full paper, and its 60 minutes. The short papers are our invention.
- **Tests / checks run:** `python3 -m pytest -q`: 249 passed (16 in `tests/test_exam.py` on a
  made-up catalogue with a fake clock: blocks and order, scoring with exact quarters, rules as
  settings, the timeout, no right letter in anything sent, every exam event draws on the matrix;
  1 in `tests/test_page.py`, which runs the page's own script against a small stand-in for the DOM
  (`tests/page_harness.mjs`) and a live server on a made-up catalogue: 7 steps through tutor,
  practice card and exam, including a double click and the way back from the review; it needs
  node and is skipped without it). Real catalogue, server started from a Python script on a free
  port: page served with the button; every paper of both levels started, no label, text or
  solution in what is sent, an image served for each question; answer, change, blank, bad
  question and bad letter refused, tick, hand in, score 2.25 for one wrong 3-point answer and two
  blanks, review question opened in the tutor, tutor `state` and `practiceok` still working,
  close; server stopped. `applab/package.py` built into a scratch folder: `copilot.exam` imports
  from the build and offers both levels, the app's `main.py` parses, the built page has the pane.
- **Not done:** not clicked through in a real browser (the harness sees no CSS, layout or
  images), and not run on the board, so the countdown has only been drawn on the page's copy of
  the matrix. The page's handling of a timeout is not in the harness (the server side is tested).
  The student memory is not fed by the exam (new backlog 12). While a paper runs the tutor's
  endpoints still answer if called by hand: the page hides them, the server does not lock them.
  One paper at a time for the whole server, as with the tutor's session. No Spanish; the Catalan
  needs a native read.
- **Commit:** see `git log -1 -- copilot/exam.py`
