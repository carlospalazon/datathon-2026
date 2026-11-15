# Ideas backlog for the model lab

Owned by the **Ideas** role; the **Engineer** takes the top open idea each round and marks it.
Status: `open`, `running`, `done: <result>`, `dropped: <why>`. Keep it ranked: best expected gain per
hour of work first. Every idea says how to test it cheaply and what result would kill it.

Merged on 15 November (round 2) from the round-1 backlog and two brainstorms: **A** (data and training)
and **B** (decoding and system). Ids: plain numbers are round-1 ideas, `M` measurement, `A`/`B` the
brainstorms. All three estimates agree: 22–30% by morning, 30–38% on text-only problems in a week, and
no evidence yet for 45%. Under the owner's rules only the Qwen3.5 0.8B counts.

## Measurement first (not bets: without these no number can be shown to the owner)

| # | What | Why | Test that it is done | Who | Status |
|---|---|---|---|---|---|
| M1 | **The reported number comes from the `predict.py` path**: `eval.py` / `compare_models.py` with the final `config.env` and model file. `bench_exam.py` is a development tool only. | `bench_exam.py` builds its own prompts and never calls `pipeline.solve()`, so its "main number" is not what the board will run (owner's rule: same code path). | The demo number in the notebook names the `eval.py` run, commit and `config.env` values | Engineer | open |
| M2 | **Deterministic time handling in the pipeline** (B6): budget each step in tokens from the board's measured speeds, not in elapsed seconds. | Reason mode keeps "remaining − 12 s" and `_ask_orders` stops on "1.3 × slowest pass": on a slower or busier machine the same problem can take another branch and get another letter. | Two runs of the predict path on the 100 demo problems give 100 identical letters; and the same under an artificial 2× slowdown | Engineer | open |
| M3 | **A Cangur-like development set cut from the training split** (A1): hold out whole years 2022–2024 (about 95 ids) and 8 generators; select checkpoints, prompts and thresholds on it, never on demo or validation. | Today every choice is made blind or on the sets that may only measure. Whole years, because twins of one problem sit at neighbouring levels of the same year (B1 found 64, all same-year): holding out single ids would leak. | Builder refuses a held-out id; the dev score is in every training entry | Engineer | open. The mix run already started is not selected on it: say so in its entry |
| 11 | **Keep every written text, read the answer properly.** | Round 1: two runs could not be explained without texts. | Texts under `~/unoq-local/`, scored with `laptop/find_letter.py` | Engineer | running (saving added to `bench_exam.py`); `find_letter` ready, 10 tests |

## Ranked ideas

| # | Idea | Why it might work | Cheapest test | Kills it if | Who | Status |
|---|---|---|---|---|---|---|
| 2 + A2 | **Train the 0.8B on the mix, showing the value-to-letter step** ("<value> is option X." before "Answer: X"). Cangur + about 6,000 synthetic + about 1,000 AQuA, about 2,500 steps. | Only thing that changes ability. Cangur-only tune: 16/100, A 57 times, set-up wrong. The value-to-letter line attacks the A habit: the letter must follow from a value. | Running. Read 5 raw answers; letter counts; dev set (M3); then demo through the predict path | No gain on held-out easy synthetic, or A still above 40 of 100 | Engineer | running |
| A3 | **Many more original verified problems from a teacher** (target 5,000; first about 1,000 from eight agents, English + Catalan, each with a `solve()` that proves the answer). | 708 solved Cangur problems are too few to teach set-up; computed answers mean the working is never wrong. | Second training run with them added, against the mix-only run on the dev set | No gain on the dev set over mix-only; or more than 2% of a 100-problem sample has a wrong answer or copies a public paper | Teacher agents, then Engineer | running (writing to `data/training/teacher/out/`) |
| A5 | **Givens-first targets**: first line restates the quantities and what is asked, then `a op b = c` lines, under 60 tokens. | The wall is set-up, not sums: 0.8B expression + Python is right 0 of 15 on Cangur, 72 of 113 on synthetic. A forced restatement is practice at exactly that step, and short targets finish in time. | Rewrite the targets of the mix (code only), 500 steps, dev set against the current format | Not better than the current format on the dev set | Ideas writes the rewriter, Engineer trains | open: next training run |
| B1 | **Copy the answer value of a near-identical training problem** (`copilot/presolve.py`). | Cangur reuses problems at neighbouring levels of a year with options reordered. | Done on train, leave one id out | Coverage under 3% or precision under 70% | Ideas built it; Engineer wires it | done: answers 64 of 1,863 (3.4%), 52 right (81%); without options the neighbour's letter is right 48 of 97. Clears the line, narrowly. Worth about +2 points on an M3Kang-style test and nothing on a 2026-style one (every match is same-year). Wire behind `PRESOLVE=1`; count on validation with no model |
| B3 | **Score the option values, not the letters**: grammar restricted to the five option strings, minus the score of the same options with the statement removed. | Letters carry nothing: on 339 validation problems the true letter's rank among the five letter scores is flat (67/68/70/67/67). A value has meaning to the model; subtracting the no-question score removes "likes round numbers". Two short calls, about 25 board seconds. | 100 dev problems with numeric options, untuned and tuned model | Top-1 under 28% | Engineer (short model job) | open: first model test when the GPU is free |
| 12 = B4 | **Code tests the five options**: the model writes one condition on `x`, code puts each option in, answers only if exactly one passes. | Uses the options as candidates; 200 of 339 validation problems with options are five distinct numbers. | `measure_setup.py` with a comparison grammar, 60 dev problems | Exactly one option passes in under 20%, or under 40% of those are right | Engineer (short model job) | open |
| A6 | **Option-testing targets** in training ("try each option") for numeric options. | Same lever as B4, taught instead of decoded; only worth it if B4 or B5 shows the model can check one option. | After B4/B5: 500 steps on dev | B4 and B5 both killed | Engineer | open, waits for B4 |
| 3 = B5 | **Per-option yes/no check with the statement cached first** (about 19 board seconds, not 50). | Verifying is easier than deriving. | 50 dev problems | Not above 30%, or over 40 board seconds | Engineer | open, after B4 |
| A7 + 9 | **Catalan repair**: Catalan problem with English working against Catalan working. | Tuning made Catalan worse (4/50 against 12/50) although 673 of 708 Catalan rows have Catalan working. | Two 500-step tunes, Catalan rows of the dev set | English working not better on Catalan dev rows | Engineer | open: needs M3 |
| A4 | **Squeeze the real problems**: teacher solutions for the 399 ids with options and no rationale; 3 short paraphrases of each solved problem. | More of the true distribution. Risk: paraphrases of training problems inflate any score measured on their twins. | Add to the next run; dev set only | No gain on dev over A3 alone | Teacher agents | open, after A3 |
| 8 | **Curriculum**: easy synthetic, hard synthetic, then Cangur. | Procedure before puzzles. | Same steps, ordered | No better than shuffled | Engineer | open, low |
| A8 | **Capacity last**: LoRA rank 16–32 on all layers, lr 5e-5 with decay, dropout 0.05; grade-school sets instead of AQuA; no public Kangaroo papers (they may be the test). | Only matters once the data teaches something. | After a run beats chance on dev | — | Engineer | open, last |
| B7 | **Fixed terse worked examples as a cached prefix, plus a structure grammar.** | Shows the format without training. Costs reading time on every problem unless the prefix cache survives; a tuned model should not need it. | Untuned model, 50 dev problems | Under 100 tokens left to write, or no gain | Engineer | open, low |
| 1 = B8 | **Python does the sums** (stop at `=`). | Counter-evidence stands: the expression is wrong before the sum is (0 of 15). | Post-hoc on saved texts | Under 1 in 10 wrong answers contains a wrong sum | Ideas, on texts | open, demoted |
| 7 | **Stop loops.** | 63 of 100 untuned answers hit the budget. | Count loops in saved texts | Under 5% loop | Ideas, on texts | open, waiting for texts |
| 4 | **Solved neighbours as worked examples.** | Weak: strategy retrieval 11–26%; reading cost. | `--rag 1` with rationale | No gain | Engineer | open, demoted |
| 13 | **Middle-value prior.** | — | Done | — | — | done, not shipped: +6 points on M3Kang-style numeric options, nothing on the demo set, so it fails the owner's "must show on both" rule |
| B2 | **Pure-code solvers with abstention.** | — | Done on train (1,863 problems with options) | Coverage under 4% or precision under 85% | Ideas | dropped: arithmetic written in the statement answers 10 (0.5%), 4 right; divisibility, remainder, prime, square and digit-sum conditions answer 15 (0.8%), 3 right. Cangur statements are not that literal |
| — | **Letter calibration, option rotation, letter votes** (6 and B's finding ii). | — | — | — | — | dropped: true letter's rank is flat; same problem in two languages agrees 16/50 |
| 5 | **Maths 1.5B model.** | — | — | — | — | dropped by the owner's rule: only the Qwen3.5 0.8B |
| 10 | **Per-level label prior without options.** | — | — | — | — | dropped: equals always-D. B1's letter copy (48 of 97) replaces it where a twin exists |

## Questions only the organisers or the user can answer

- Is the hidden test drawn from M3Kang (2007–2024) or new problems like the 2026 demo set? (Decides
  whether B1 and 13 are worth anything.)
- Which languages? Does it come with images, or text plus OCR options only?
- Answered by the owner, 15 November: only the Qwen3.5 0.8B may run on the board.
