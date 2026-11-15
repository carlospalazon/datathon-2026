# Ideas backlog for the model lab

Owned by the **Ideas** role; the **Engineer** takes the top open idea each round and marks it.
Status: `open`, `running`, `done: <result>`, `dropped: <why>`. Keep it ranked: best expected gain per
hour of work first. Every idea says how to test it cheaply and what result would kill it.

| # | Idea | Why it might work | Cheapest test | Kills it if | Status |
|---|---|---|---|---|---|
| 1 | **Python does the sums.** While the model writes, stop at each `=`, compute the left side in Python, insert the result, continue. | The tuned model sets up `15 × 14 ÷ 2` and then writes 112. Arithmetic slips were the commonest error in the outputs read. | Post-hoc first: in saved outputs, recompute every `a op b = c` and count how many answers would change to the right option. No model run needed. | Fewer than 1 in 10 wrong answers contain a wrong sum | open |
| 2 | **Train on the mix, with sums in a checkable form.** `v2_mix_reason` (Cangur + easy and hard synthetic + a little AQuA); write every calculation as `a × b = c` so idea 1 can check it. | The Cangur-only tune never practised basic procedure; synthetic answers are computed, so the working is always right. | 500 steps on `v2_mix_reason`, score on demo + 300 held-out synthetic | No gain on easy synthetic problems either | open |
| 3 | **Check each option instead of solving.** For "which number…" problems, ask five short yes/no questions (does option X satisfy the statement?) and pick the best-scoring option. | Verifying is easier than deriving, and it uses the options, which are information the model now ignores. | 50 text-only problems, untuned 0.8B, compare with direct letter | Not above 30% on text-only problems | open |
| 4 | **Solved neighbours as worked examples.** Retrieval already finds similar training problems; show their short checked solution, not just their letter. | A worked example of the same type gives the method; 708 checked solutions exist. | `--rag 1` with the rationale in the example turn, tuned model, demo set; watch the token budget | Reading the example leaves under 80 tokens to write | open |
| 5 | **A maths-specialised 1.5B model.** Qwen2.5-Math-1.5B, untuned first, then tuned on our data. | Trained for step-by-step maths; published scores far above general models of its size. | `bench_exam.py` on demo (running); then time it on the real board | It cannot finish inside the board's 60 s, or Catalan collapses | running |
| 6 | **Two or three short attempts and a vote.** The tuned model answers in about 20 s on the board: run it with two option orders and take the agreed letter. | Cheap ensemble; also removes the letter-position habit. | Tuned model, demo set, orders 0 and 2 | No gain over a single pass | open |
| 7 | **Stop loops.** Detect a repeated phrase while generating and cut to the forced letter; or a repetition penalty. | Some outputs repeat one sentence until the budget ends. | Count looping outputs in saved texts first | Under 5% of outputs loop | open |
| 8 | **Curriculum:** easy synthetic first, then hard synthetic, then Cangur. | Small models learn procedure before puzzles. | Same steps as idea 2, ordered data | No better than the shuffled mix | open |
| 9 | **Use the English version when both exist.** If a problem arrives in Catalan and its English twin is known, solve in English. | Models are stronger in English; the test may give both languages of one id. | Compare cat vs eng accuracy on the same ids in every run | Catalan is not worse | open |
| 10 | **Problems without options:** answer from the training label frequency for that level instead of calling the model. | The model cannot know; a prior is free and deterministic. | `NO_OPTIONS_PRIOR` already exists: measure D vs per-level prior on validation | Within noise of always-D | open |

## Questions only the organisers or the user can answer

- Is the hidden test drawn from M3Kang (2007–2024) or new problems like the 2026 demo set?
- Which languages? Does it come with images, or text plus OCR options only?
- May a team run a different model than Qwen3.5 0.8B on the board?
