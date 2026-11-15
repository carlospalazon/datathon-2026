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

## What is known (14–15 November 2026)

| Fact | Evidence |
|---|---|
| Asking for one letter with no working is guessing, for every model size | 0.8B 22.8%, 2B 21.4%, 4B 24.0% on 562 validation problems; always-D is 23.1% |
| Letter-only fine-tuning teaches nothing | validation loss flat after 200 steps; the model just guesses more evenly |
| The untuned 0.8B can reason on easy problems but is too wordy to finish | 26 of 40 easy problems cut off at 300 tokens; 11 of the 14 that finished were right |
| Free working, 250 tokens, untuned: still chance on validation | 0.8B 22.1%, 2B 21.2% (562 problems) |
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
