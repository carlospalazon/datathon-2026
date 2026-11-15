# Lab notebook: getting a model on the UNO Q to solve Cangur problems

Shared memory of the model lab. Two roles write here: **Engineer** (runs experiments) and **Ideas**
(reads results, proposes and criticises). Newest entry at the bottom. Numbers, ids and letters only:
never problem text (M3Kang is research-use only).

## The goal and how it is measured

- **Goal:** the highest share of correct answers on test-like Cangur problems, inside 60 s per problem on
  the board, offline, one letter A–E per problem (the `predict.py` contract in `README.md`).
- **Main number:** `python3 laptop/bench_exam.py` on `data/demo/train.jsonl` (100 problems: 50 from 2026,
  in English and Catalan, all with options, none in any training set), column "with working, in time".
  100 problems means roughly ±9 points of noise: a difference under 10 points is not a result.
- **Second check:** `ANSWER_MODE=... python3 laptop/compare_models.py ... --languages eng,cat --limit 0`
  on the 562 validation problems. A gain on the demo set that does not show here is probably noise.
- **Never train on, or tune prompts by reading, `data/demo` or `data/val.jsonl`.** They only measure.

## The owner's rules (15 November, 01:50)

- **Only the Qwen3.5 0.8B model.** Larger or different models are out of scope for now. Everything else
  is allowed: tuning it, how it is prompted and decoded, code that does part of the work, retrieval.
- **Target: 45% correct on a base of at least 50 problems**, inside the board's limits. Report the
  number on all 100 demo problems, and never on a subset chosen after seeing results.
- **No cheating. It must work the same in tomorrow's test.** That means:
  - the score comes from exactly what `predict.py` will run on the board (same code path, same model
    file, same settings in `config.env`), within 60 s per problem at the board's real speed;
  - no answers looked up: nothing from `data/demo` or `data/val.jsonl` in any index, training set,
    prompt, example or rule, and retrieval never returns the problem being asked or its translation;
  - no tuning of prompts or rules by reading the demo problems one by one; use training problems to
    develop, the demo set only to measure;
  - a gain counts only if it also shows on the 562 validation problems and on the real board.

## What is known (14–15 November 2026)

| Fact | Evidence |
|---|---|
| Asking for one letter with no working is guessing, for every model size | 0.8B 22.8%, 2B 21.4%, 4B 24.0% on 562 validation problems; always-D is 23.1% |
| Letter-only fine-tuning teaches nothing | validation loss flat after 200 steps; the model just guesses more evenly |
| The untuned 0.8B can reason on easy problems but is too wordy to finish | 26 of 40 easy problems cut off at 300 tokens; 11 of the 14 that finished were right |
| Free working, 250 tokens, untuned 0.8B: still chance on validation. **The 2B was not measured** (see Ideas, 15 Nov 01:50) | 0.8B 22.1% (562 problems); only 86 of 339 problems with options reached an answer, 22 of them right. 2B: 338 of 339 fell back to the direct letter |
| Fine-tune on 3,883 Cangur worked solutions (reasoning): format learned, maths not | 18.3% (step 1000), 20.1% (step 500) on 562; arithmetic and set-up errors in the raw outputs |
| Validation loss of that fine-tune was lowest at step 500 and rose after | 1.26 → 1.33 → 1.41 |
| 40% of validation problems have no readable options; only 178 of 562 are solvable from text alone | `data/val.jsonl` counts |

## Traps already paid for

- **Look at raw outputs before believing a score.** Two fine-tune scores were measured on a corrupted
  GGUF that wrote noise; the one-letter grammar hid it. After any conversion, print 5 full answers.
- **Converting a tuned model:** only `laptop/adapter_to_gguf.py` (it patches the original weight file).
  `mlx_lm.fuse` + `convert_hf_to_gguf.py` produces a broken file for Qwen3.5.
- **Memory (16 GB Mac):** one model job at a time. Training crashed four times when anything else ran,
  and a reasoning batch of 4 does not fit: use `--batch-size 2 --grad-accumulation-steps 2
  --grad-checkpoint --max-seq-length 448`, with `--save-every 100`.
- **Board speed is simulated,** not measured, in `bench_exam.py`: 0.8B reads 11 and writes 6 tokens/s
  (measured, README); 1.5B at 5.5 and 3 is an assumption until someone times it on the board.
- **Another session may be working in this folder.** Check `git status` and `git log -3` before editing,
  commit your own files by name, never `git add -A`.

## Where things are

- Data: `data/training_v2/master.jsonl` (26,357 examples: 708 Cangur problems with checked solutions,
  12,000 synthetic from 57 generators, 8,000 AQuA). Builder: `laptop/build_training_data.py`.
- Sets: `laptop/make_ft_sets.py` → `~/unoq-local/ft/<name>`; ready: `v2_m3k_reason`, `v2_mix_reason`.
- Models: `~/unoq-local/models/*.gguf`; training env `~/unoq-local/train-venv`; server
  `~/unoq-local/llama.cpp/b12383/llama-b12383/llama-server`.
- Answer modes in `copilot/pipeline.py`: `ANSWER_MODE=reason` (tuned model, short working) and
  `ANSWER_MODE=think` (untuned model, free working). Default is the single letter.

## Log

<!-- One entry per experiment or review. Template:

### YYYY-MM-DD HH:MM · Engineer|Ideas · short title
- **Tried / claim:**
- **Result:** numbers with n and interval; commit; files
- **Raw outputs checked:** yes (what they showed) / no
- **Conclusion and next:**
- **For the other role:** question or request, if any
-->

### 2026-11-15 01:50 · Ideas · First review: every run so far is a guess, and two of them measured less than they claim
- **Read:** `results/exam_bench_demo.csv` (complete, 3 models × 100), the `base-`, `think250-`, `think600-`
  and `ft3reason-` CSVs, `results/setup/*.jsonl`, the catalogue. Ignored: `ft1-`, `ft2-` and the
  `sanity-reason-ftreason-*` runs (same commit and half-hour as the corrupted file; unverified).
- **Latest result (exam benchmark, demo set, "with working, in time"):** untuned 0.8B 23/100 (16–32),
  maths 1.5B 21/100 (14–30), tuned 0.8B step 500 16/100 (10–24). Chance is exactly 20: the demo labels are
  20 per letter. No model is above chance; the three are not distinguishable from each other.
- **Artefacts found:**
  1. **`think250-q2` did not measure working.** In `pipeline.py`, `passes == 2` means "no answer found in
     the working, asked for a direct letter instead". That happened on 338 of 339 problems with options, and
     561 of 562 letters equal `base-q2b`. The 21.2% is the direct-letter score a second time. Cause unknown
     without the texts: either 250 tokens never reach an answer, or the answer is written in a form the
     pattern rejects. The pattern `Answer:\s*\**\(?([A-E])` rejects `**Answer:** B`, `The answer is B`,
     `Resposta: B`, `answer: B` and `Answer: $B$` (checked on CPU).
  2. **The maths 1.5B was given 114 tokens** (median budget, from the assumed 3 tokens/s) and finished
     0 of 100. Its 21% is a forced letter (E 75 times). The run says "does not fit at the assumed speed";
     it says nothing about whether the model can do the maths.
     Checked per row: in all three models every unfinished answer (63, 100 and 26) used its whole budget;
     none stopped early with an answer the pattern missed. So on this benchmark the cause is the budget.
  3. `results/setup/*.jsonl`: the `direct` column is identical in all 466 rows of both models and
     `direct_read` is 0 everywhere, so it is not a per-model measurement. Do not quote it.
  4. `think600-q08` stopped at 447 rows and is not in `ablations.csv`.
- **Error patterns, counted:**
  - *Finishing is not the wall, wrong working is.* Untuned 0.8B on validation problems with options: 250
    tokens → 86/339 finished, 22 right (26%); 600 tokens → 131/260 finished, 28 right (21%). Demo: 37/100
    finished, 10 right (27%, 15–43); forced letters 13/63 (21%). More tokens bought more finished answers,
    not more right ones. The earlier "11 of 14 finished easy problems right" does not carry to Cangur.
  - *Tuned 0.8B:* finishes 74/100 in a median 24 board seconds, 14 of those right (19%). It answers A 57
    times of 100 (validation: A in 126 of 273 finished). Catalan 4/50 against English 12/50. When forced,
    2/26. On the demo set it is 7 points under the untuned model (inside the noise, but not a gain).
  - *The answers behave like noise.* The same problem in English and Catalan gets the same letter in
    16/50 (untuned) and 23/50 (tuned); steps 500 and 1000 of the same tune agree on 98 of 339 option
    problems (29%). When the two languages agree they are right 5/16 and 3/23: agreement is not a signal.
  - *Set-up, not arithmetic* (set-up measurement, 0.8B writes one expression, Python computes it): on
    synthetic problems the value lands on an option 113/294 times and is right in 72 of them (64%); on
    Cangur it lands 15/172 times and is right 0 times; with the options shown, 78/172 and 18 right (23%,
    chance). Python doing the sums cannot help while the expression itself is wrong.
  - Levels and topics: the two cells with n ≥ 50 (algebra 54, numbers 52) swing between 8% and 40% from
    run to run; nothing there is a pattern.
- **A prior that is real on M3Kang and absent on the demo set.** Fixed on the training split only
  (1,181 problems whose five options are distinct numbers): the correct value is the middle one 31%, an
  extreme 9% and 11%. Validation: middle value 57/200 (28.5%, 23–35); replacing a model's extreme pick by
  the middle value moves `base-q2b` from 49 to 63 of 200. Demo set: middle value 14/80, and the correct
  rank is flat (18, 20, 14, 12, 16). So the 2026 problems are built differently from M3Kang, and a gain
  on one set says little about the other. This makes the organisers' question (which kind is the test?)
  worth more than any run tonight.
- **What is reachable.** Score = f·a + (1−f)·20%, f the share finished, a the share right when finished.
  Today: 0.37·27% + 0.63·21% ≈ 23%. No slice with n ≥ 100 in any run is above 29%. On a demo-like test,
  45% needs about f = 0.9 and a = 48%: finished accuracy has to almost double. On a validation-like test
  40% of problems (223/562) have no readable options and another 135 need the figure; if the 204
  text-with-options problems went to 60%, the total would be about 36%. **The evidence does not support
  45–50% by morning.** Honest range for tonight: 22–28% overall. A real first result would be one slice,
  n ≥ 100, text-only with options, whose interval starts above 25%.
- **Prototype (no model):** `laptop/find_letter.py` + `tests/test_find_letter.py` (10 tests pass, on
  invented strings only: read ten real texts by eye before trusting it; a letter needs a colon or "is"
  before it, so "Answer B is too big" is not an answer). Reads
  the forms above, takes the last stated answer, and maps a stated value (`\boxed{12}`) to the one option
  with that value. Not yet wired into `bench_exam.py` or `answer_thinking`: one import each.
- **Backlog changes:** see `IDEAS.md`. Dropped 6 (vote) and 10 (per-level prior: D is the commonest label
  at 7 of 8 levels, so it equals always-D). Demoted 1 and 4. New: 11 (keep the texts), 12 (code tests the
  five options), 13 (middle-value prior, measured).
- **For the Engineer:** run the maths 1.5B once more on the 80 text-only demo problems with a fixed 600
  tokens, `boxed` style, **saving every text** to `~/unoq-local/` (not git) and scoring with `find_letter`.
  Decided beforehand: right in ≥ 32/80 (40%) → the model can do the maths and the night goes to making it
  fit (board timing, short working); ≤ 24/80 (30%) → drop the 1.5B and start idea 2. In between: 100 more
  validation problems. From the same run report: right and finished within 114 and within 200 written
  tokens (does it fit?), and how many texts had no letter found (read ten of those). The same saved texts
  settle ideas 1 and 7 on CPU. Until the user confirms another model may run on the board, start idea 2's
  training for the rest of the night whatever this run says.
- **For the user / organisers:** is a model other than Qwen3.5 0.8B allowed on the board, and is the
  hidden test M3Kang-style or 2026-style? Both answers change the ranking.

### 2026-11-15 03:00 · Ideas · Round 2: one backlog from three sources; value copy clears its line, code solvers do not
- **Tried / claim:** merged round 1 with brainstorms A (data, training) and B (decoding, system) into
  `IDEAS.md`; closed the maths 1.5B (owner's rule); prototyped B1 and B2 on CPU, on `data/train.jsonl`
  only. Nothing here read `data/val.jsonl` or `data/demo`.
- **Result, B1 (copy the answer value of a near-identical training problem), leave one id out:**
  similarity = shared words and word pairs over all of them, same language, another id. At 0.5: answers
  64 of 1,863 problems with options (3.4%), 52 right (81%, about 70–89). At 0.6: 50, 42 right; at 0.4:
  80, 62 right. Without options, the neighbour's letter is right 48 of 97 (49%) against about 23% for a
  fixed letter. Kill line was coverage under 3% or precision under 70%: **cleared, narrowly.** Module
  `copilot/presolve.py`, 8 tests (`tests/test_presolve.py`); `python3 -m copilot.presolve data/train.jsonl`
  reprints the numbers.
- **What it is worth, honestly:** every one of the 64 matches is a problem of the same year (the same
  problem at a neighbouring level). On an M3Kang-style test: about 3.4% × (81 − 22) ≈ +2 points on problems
  with options and about 9% × (49 − 23) ≈ +2 on those without. On a 2026-style test (the demo set): no
  neighbour, no answers, **zero gain**. It will not move the number the owner asked for. It also cannot
  hurt it. The threshold was read off the same training split, so expect a little less on validation.
- **Result, B2 (pure-code solvers with abstention), 1,863 training problems with options:** arithmetic
  written in the statement: answers 10 (0.5%), 4 right. Divisibility, multiple, remainder, prime, square,
  parity and digit-sum conditions tried on integer options: a condition is found in 66 problems, exactly
  one option passes in 15 (0.8%), 3 right; refusing statements with "not", "how many", "smallest" and
  the like leaves 1. Kill line was coverage under 4% or precision under 85%: **dropped.** The statements
  mention these words while asking something else.
- **Raw outputs checked:** not applicable (no model). Wrong B1 copies are twins whose numbers changed
  while the old value stayed among the options (seen by id, not listed here).
- **Two things from brainstorm B that change how results are read:**
  1. `bench_exam.py` builds its own prompts and never calls `pipeline.solve()`. Every "main number" so
     far, including round 1's 23/21/16, is a development number. The number for the owner has to come
     from `eval.py` / `compare_models.py` on the predict path (M1).
  2. The pipeline decides by elapsed seconds in two places, so letters can change between runs and
     between laptop and board (M2). Fix before the final measurement, not after.
- **A leak to guard against (M3):** because twins are same-year, a development set must hold out whole
  years; a held-out id whose twin stays in training is not held out. Same for A4's paraphrases.
- **Conclusion and next:** nothing found tonight moves the demo number except training (running) and,
  untested, B3 and B4. Estimates from all three sources agree: 22–30% by morning; no evidence for 45%.
- **For the Engineer** (the GPU is training, so in this order, no model needed):
  1. M1 + M2: make the pipeline's time handling token-budgeted, and prepare the `eval.py` run that will
     produce the reported number.
  2. Wire `presolve` in `pipeline.solve()` before any model call, behind `PRESOLVE=1`: build the index
     once from `data/train.jsonl` (`build(rows)`); `hit = presolve(problem, index, exclude_id)`; if
     `hit["kind"] == "value"` answer it with `status = "presolve"`; if `"letter"` use it only where
     `NO_OPTIONS_PRIOR` would have answered. Then count it on validation with no model (answered, right):
     keep it if at least 12 of 562 are answered and at least 65% of them are right.
  3. M3: cut the development set (whole years 2022–2024) and add the guard to the builder.
  4. Wire `find_letter` where the saved texts are scored.
  When the GPU is free: first the new model through the predict path on the 100 demo problems with texts
  saved (read 5, print letter counts: A under 35), then B3 (two short constrained calls per problem, 100
  dev problems, kill under 28%), then B4.
- **For the user / organisers:** is the hidden test M3Kang-style or 2026-style? B1 is worth about 2 points
  or nothing depending on the answer.

