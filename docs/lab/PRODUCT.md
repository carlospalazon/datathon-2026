# Product lab: original features for Tutor Cangur

Memory of the **Product** role. Newest "Built" entry at the bottom. No problem text here.

## Backlog (best first)

| # | Feature | Why a student or teacher wants it | Uses | Status |
|---|---|---|---|---|
| 1 | **"One like this, but yours."** After a wrong answer (or on request), generate a fresh problem of the same kind with smaller numbers, solvable in a minute, then return to the original. | Practice on the exact skill that failed, never the same problem twice, nothing to memorise. | synthetic generators (computed answers, worked solutions, 3 languages), topic of the current problem | **built** (2026-11-15; smallest of 8 draws rather than purpose-made small numbers) |
| 2 | **Mistake names on generated problems.** Each wrong option of a generated problem is the result of a known slip: say which ("you added the prices but forgot the quantities"), without giving the answer. | Feedback that is specific, instant and needs no model. | generators' wrong-option formulas, `copilot/diagnose.py` | **built** (2026-11-15; 16 generators, slips worked out again from `params`) |
| 3 | **Cangur exam mode.** A timed paper built from the catalogue by level, with the real scoring (3/4/5 points, a quarter of the points lost per wrong answer, blank is free), a countdown on the LED matrix, and a review at the end that leads into the tutor. | The real competition experience; shows when leaving a blank is the right call. | catalogue levels, LED matrix, student memory | open |
| 4 | **Skill map.** One screen (and a matrix view) of the student's topics by level: tried, mastered, shaky, with "what to try next". A teacher view of the class as a heat map, by pseudonym. | Students see progress; teachers see where the class is stuck. | SQLite student memory, topics | open |
| 5 | **Think-first timer.** The page hides the hint button for the first seconds of a new problem and shows a calm progress ring; the board uses that time to get the help ready. | Encourages a real attempt, and makes the wait invisible. | read-ahead of the problem (already in the app), LED matrix | open |
| 6 | **Explain it back.** After a right answer, one tap picks which of three explanations matches how the student solved it (the checked solution and two wrong methods that also give that number). | Checks understanding, not luck. | checked solutions, generators' typical mistakes | open |
| 7 | **Reading modes.** One idea per line, larger spacing, key data highlighted, a "numbers only" strip; chosen by the student, remembered, never labelled. | Dyslexia- and dyscalculia-friendly without a separate product. | key data and key condition already in the catalogue | open |
| 9 | **Practice feeds the memory.** A slip named on a practice problem counts in the student memory (topic, slip), so the second time the tutor goes to the method card, and the skill map (4) can show it. | The tutor learns from practice too, not only from Cangur problems. | `copilot/practice.py` codes, SQLite `errors` table | open |
| 10 | **Practice for the picture topics.** Generators with a figure drawn by the page (grids to count, folded paper, cube nets) so `visual` and `geometria_espacial` get a practice problem too. | 28 of the 154 primary problems have no practice today. | new generators of our own, SVG drawn by the page | open |
| 11 | **Warm-up of three.** Before the first Cangur problem, three one-minute generated problems, one per topic the student found hardest last time. | A start that always succeeds, and it uses the memory. | `copilot/practice.py`, student memory | open |
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
- **Commit:** see `git log -1 -- copilot/practice.py`

