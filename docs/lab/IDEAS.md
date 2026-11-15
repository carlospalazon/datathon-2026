# Ideas backlog for the model lab

Owned by the **Ideas** role; the **Engineer** takes the top open idea each round and marks it.
Status: `open`, `running`, `done: <result>`, `dropped: <why>`. Keep it ranked: best expected gain per
hour of work first. Every idea says how to test it cheaply and what result would kill it.

Merged on 15 November (round 2) from the round-1 backlog and two brainstorms: **A** (data and training)
and **B** (decoding and system). Ids: plain numbers are round-1 ideas, `M` measurement, `A`/`B` the
brainstorms, `T`/`G`/`P` round 3. Under the owner's rules only the Qwen3.5 0.8B counts.

**Estimate after round 3 (15 Nov 10:30, notebook entry of that time):** demo-like problems, 0.8B:
**20–25%** by any route measured so far (letter, free working, two tunes: 16–23 of 100, all chance).
More generators can add about 3.5 points per 10% of test problems that fall in a learned family, and
only if T1 passes; a week of that gives 22–30%. 45% needs 71% of the test in learned families at the
55% the model reaches inside a family (58% at 63%): the training problems say that is several hundred
families, and the test is new problems. **No evidence supports 45% for this model.**

## Measurement first (not bets: without these no number can be shown to the owner)

| # | What | Why | Test that it is done | Who | Status |
|---|---|---|---|---|---|
| M1 | **The reported number comes from the `predict.py` path**: `eval.py` / `compare_models.py` with the final `config.env` and model file. `bench_exam.py` is a development tool only. | `bench_exam.py` builds its own prompts and never calls `pipeline.solve()`, so its "main number" is not what the board will run (owner's rule: same code path). | The demo number in the notebook names the `eval.py` run, commit and `config.env` values | Engineer | done on the laptop (09:12): demo 20/100, validation 103/562, all rows `working = budget`, no `direct` row, worst board time 57.0 s. Still to do: the same run on the board |
| M2 | **Deterministic time handling in the pipeline** (B6): budget each step in tokens from the board's measured speeds, not in elapsed seconds. | Reason mode keeps "remaining − 12 s" and `_ask_orders` stops on "1.3 × slowest pass": on a slower or busier machine the same problem can take another branch and get another letter. | Two runs of the predict path on the 100 demo problems give 100 identical letters; and the same under an artificial 2× slowdown | Engineer | code done for the working modes, mocked test passes (notebook 15 Nov 02:45); the two real runs are still to do; `OPTION_ORDERS` > 1 still uses the clock |
| M3 | **A Cangur-like development set cut from the training split** (A1): hold out whole years 2022–2024 (about 95 ids) and 8 generators; select checkpoints, prompts and thresholds on it, never on demo or validation. | Today every choice is made blind or on the sets that may only measure. Whole years, because twins of one problem sit at neighbouring levels of the same year (B1 found 64, all same-year): holding out single ids would leak. | Builder refuses a held-out id; the dev score is in every training entry | Engineer | open. The mix run already started is not selected on it: say so in its entry |
| 11 | **Keep every written text, read the answer properly.** | Round 1: two runs could not be explained without texts. | Texts under `~/unoq-local/`, scored with `laptop/find_letter.py` | Engineer | running (saving added to `bench_exam.py`); `find_letter` ready, 10 tests |

## Ranked ideas

| # | Idea | Why it might work | Cheapest test | Kills it if | Who | Status |
|---|---|---|---|---|---|---|
| T1 | **Transfer test: the same maths in other words** (`laptop/reworded_problems.py`, 9 families, eng + cat, with the trained wording as a paired control). | Decides the whole data route. The tuned model is right 46 of 50 on these 9 families in their trained wording; every fresh problem it solved shares at least 73% of its words with a training row, and inside the fresh set a sentence pattern never seen in training scores 17/42 against 147/258. Nobody has measured whether it solves a problem it has not seen the wording of. | One run of the tuned file on 360 problems (`--n 10`: 180 reworded, 180 control), about 4 minutes, no training | Reworded at or under 40% while the control is over 80%: the model learned templates, and G1, A5, 8 and A8 die with it. Reworded at or over 70%: the maths is learned, go to G1 | Ideas built it (4 tests); Engineer runs it | **open: run next** |
| B3 | **Score the option values, not the letters**: grammar restricted to the five option strings, minus the score of the same options with the statement removed. | Not a variation of anything tried. Letters carry nothing (true letter's rank flat), and the written working is no better: when its value is one of the options it is the right one 33 of 158 times. This reads the model without asking it to derive. Two short calls, about 25 board seconds. | 100 training-split problems with numeric options, tuned and untuned model | Top-1 under 28% | Engineer (short model job) | open: second |
| 12 = B4 | **Code tests the five options**: the model writes one condition on `x`, code puts each option in, answers only if exactly one passes. | Uses the options as candidates; 248 of 339 validation problems with options are five distinct numbers. Weakened this round: the model's set-up is what fails, and a condition is a set-up. | `measure_setup.py` with a comparison grammar, 60 training-split problems | Exactly one option passes in under 20%, or under 40% of those are right | Engineer (short model job) | open |
| G1 | **Many more generator families, modelled on the types of the training problems.** | The one recipe that moved a number: 57 families at a median 111 rows each (16–132) took fresh problems of those families from about 19% to 55% (19 families at 80% or more, 14 at 25% or less). | Only after T1 passes: 30 new families from the commonest topic and strategy cells of the training split, retrain, score on a development set of whole held-out years (M3) | T1 fails; or the 30 families do not lift held-out-year Cangur problems by 3 points | Ideas writes generators, Engineer trains | waits for T1. Size of the job, from the 497 text-only training problems with options: 80 topic × strategy cells (20 cells hold 73%), but a cell is not a family: 483 of the 497 method descriptions are unique and 35% of problems sit in a four-label cell seen once. 45% needs about 71% of the test inside learned families: several hundred families, and the 57 existing ones cover at most 13% of validation problems (point estimate 0) |
| P1 | **Settings that are free on an M3Kang-style test:** `NO_OPTIONS_PRIOR` on, and presolve value copies on. | The tuned model's own letter on the 223 validation problems without options is right 36 times (A 107, E 96); always D is right 58 times: +22 problems, 18.3% → 22.2%. Presolve value copies: 10 answered, 10 right. | Count with no model (done) | — | Engineer (settings) | open: worth about +5 points on validation, **nothing on the demo set** (no problem without options, no twin). It is not progress on the owner's number |
| A6 | **Option-testing targets** in training ("try each option") for numeric options. | Same lever as B4, taught instead of decoded. | After B4/B5: 500 steps | B4 and B5 both killed, or T1 fails | Engineer | open, waits for B4 and T1 |
| 3 = B5 | **Per-option yes/no check with the statement cached first** (about 19 board seconds, not 50). | Verifying is easier than deriving. | 50 training-split problems | Not above 30%, or over 40 board seconds | Engineer | open, after B4 |
| A5 | **Givens-first targets**: first line restates the quantities and what is asked, then `a op b = c` lines. | Set-up is the wall. But it is one more change of the training target, and two tunes have not moved Cangur. | 500 steps, development set | T1 fails; or not better on the development set | Engineer | open, demoted under T1 |
| A7 + 9 | **Catalan repair.** | The gap closed by itself in the mix tune: validation eng 31/167, cat 36/172; demo 11/50 and 9/50. What remains is that Catalan loops more on the demo set (forced 15/50 against 2/50). | — | — | — | dropped: no Catalan deficit left to repair at chance level |
| 7 | **Stop loops** (repetition stop in the decoder). | Loops are real: a 25-character piece repeated three times in 59 of 339 validation workings and 15 of 100 demo; 46 of the 63 forced letters follow a loop. But a finished working is right 20% of the time and a forced letter 19%. | — | — | — | dropped as a way to score: stopping every loop is worth 0 points. Keep only as a time saver (a loop burns the full 57 s) |
| 1 = B8 | **Python does the sums.** | — | Post-hoc on 339 saved validation workings (checker: 0 false alarms on 6,947 code-computed sums) | Under 1 in 10 wrong answers contains a wrong sum | Ideas | **dropped, measured:** 76 of 332 written sums are wrong (23%), in 32 of 272 wrong answers (12%) and in 10 of 67 right ones (15%). Redoing the sums changes the final value in 21 workings, lands on an option in 1, and that one flips right → wrong. Net −1. Demo: 0 changes |
| — | **Match the working's value to the options by code** (value matching in `find_letter`, nearest option when the value is not there). | — | Post-hoc on the same texts | — | Ideas | **dropped, measured:** the model already names the option that holds its value 156 of 158 times; re-matching changes 2 answers, +1. When the value is on no option (118 of 276 finished) the nearest option is right 8 of 83 against 16 as written. Do not wire it |
| 2 + A2 | **Train the 0.8B on the mix, showing the value-to-letter step.** | — | Done | — | Engineer | done (09:12): demo 20/100, validation 103/562, fresh generated 164/300. The A habit is gone (A 19 of 100) and the value-to-letter line works; Cangur did not move |
| A3, A4 | **Teacher-written problems and paraphrases.** | — | — | — | — | dropped: closed by the coordinator (02:00), the model's safeguards stop it; do not relaunch |
| B1 | **Copy the answer value of a near-identical training problem** (`copilot/presolve.py`). | — | Done | — | — | done: validation 10 answered, 10 right (value); 22 letter copies, 11 right; demo 0. See P1 |
| 8 | **Curriculum.** | — | — | T1 fails | Engineer | open, low |
| A8 | **Capacity last** (rank, layers, open grade-school sets). | Only matters once T1 passes. | — | T1 fails | Engineer | open, last |
| B7 | **Fixed terse worked examples as a cached prefix.** | — | Untuned model, 50 problems | No gain | Engineer | open, low |
| 4 | **Solved neighbours as worked examples.** | Weak. | `--rag 1` with rationale | No gain | Engineer | open, demoted |
| 13 | **Middle-value prior.** | — | Done | — | — | done, not shipped: +6 points on M3Kang-style numeric options, nothing on the demo set |
| B2 | **Pure-code solvers with abstention.** | — | Done | — | Ideas | dropped: answers 25 of 1,863, 7 right |
| — | **Letter calibration, option rotation, letter votes, two-language agreement.** | — | — | — | — | dropped: true letter's rank is flat; the two languages agree on 7 of 50 demo problems and 55 of 158 validation pairs (13 right) |
| 5 | **Maths 1.5B model.** | — | — | — | — | dropped by the owner's rule |
| 10 | **Per-level label prior without options.** | — | — | — | — | dropped: equals always-D (see P1) |

## Questions only the organisers or the user can answer

- Is the hidden test drawn from M3Kang (2007–2024) or new problems like the 2026 demo set? (Decides
  whether B1 and 13 are worth anything.)
- Which languages? Does it come with images, or text plus OCR options only?
- Answered by the owner, 15 November: only the Qwen3.5 0.8B may run on the board.
