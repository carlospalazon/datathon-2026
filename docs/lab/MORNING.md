# Morning summary (15 November, 09:15)

Branch `lab/overnight-model-and-product`. Nothing was pushed, nothing was installed on the board.

## The model: no gain on Cangur. The target of 45% was not reached.

Everything below is the Qwen3.5 0.8B, measured through the same path `predict.py` runs
(`ANSWER_MODE=reason`, token budget for the board's speeds), never on a hand-picked subset.

| Model | 100 sample problems (2026) | 562 validation problems | 300 fresh generated problems |
|---|---|---|---|
| Untuned, one letter (yesterday) | 21% | 22.8% | about 19% |
| Tuned on the mix, step 2250 (tonight) | **20/100 = 20%** | **103/562 = 18.3%** | **164/300 = 55%** |

Chance is 20%. What this says:

- **The training method works where the data matches.** On new problems of the kinds our generators
  produce, the model went from about 19% to 55% (63% on the easy kinds, 48% on the hard ones), with
  short, correct working.
- **None of it carries over to real Cangur problems.** Two honest sets, both at chance. The model
  writes plausible working and reaches a wrong value.
- **Two independent estimates made last night said 22–30% by morning and 30–38% in a week**, with no
  evidence for 45% from this model. The night's result is at the bottom of that range.

## Found and fixed: the tuned model would not have loaded on the board

A model file converted on the Mac loads on the Mac but is refused by the board's server
(`tensor 'blk.0.ssm_beta.weight' not found`): the Mac's converter is newer and merges layers.
`laptop/adapter_to_gguf.py` now uses the board's own converter. The board-layout file is
`~/unoq-local/models/ft-v3-mix-s2250-board-Q8_0.gguf`. Whether it loads and how fast it really runs
on the board is being measured now (see the notebook for the result).

## Also fixed along the way

- **Yesterday's fine-tune scores (17.3%, 20.1%) were measured on a corrupted file.** Fixed and re-measured.
- **`predict.py` can now reason with a fixed token budget instead of a clock** (off by default), so
  a run gives the same letters every time and the score comes from the code the board runs.
- **The training data is guarded against both held-out sets** (validation and the 2026 samples).

## Product: two new features, in commits

1. **"One like this, but yours"** (`3595d99`, `5b7fd90`): after a wrong answer, a fresh problem of
   the same topic with a computed answer; each wrong option names the slip behind it.
2. **Cangur exam mode** (`fd90572`): a timed paper by level, countdown on the LED matrix, review
   that leads back into the tutor.

See both: `python3 teach/server.py --port 8650`, open http://127.0.0.1:8650.
- Practice: answer a problem wrong, then press "Prova'n un de semblant, però teu".
- Exam: press "Mode examen", choose "Tast", "Comença l'examen", answer, "Lliura l'examen".

Not verified: neither was clicked through in a real browser or run on the board; the tests and the
endpoints pass (249 tests). The exam's scoring rules are assumptions kept as settings. Catalan
wording needs a native read. A third feature (the skill map) is being built.

## What went wrong overnight

- **Three agents stalled for up to 80 minutes** waiting for a command approval nobody could give.
  They were stopped and their work finished by hand; later agents were limited to commands that
  need no approval.
- **Writing new problems with agents was stopped by the model's safeguards** (two of eight agents
  flagged, the rest cancelled). No data came from that route and it was not retried.
- **The session itself was suspended from about 04:00 to 09:00**, so the finished training waited
  five hours to be scored.

## Decisions waiting for you

1. **Is the test drawn from M3Kang or new problems like the 2026 samples?** If M3Kang, copying the
   answer value from a near-identical training problem (built, off) is worth about 2 points and is
   your call; on new problems it gives nothing.
2. **The honest options for a better score** are few: a larger model on the board (you ruled this
   out for now), or many more code generators modelled on the kinds of problems in the training
   set, which is days of work with an uncertain return.
3. **What to show.** The strongest thing we have is the tutor, not the solver: the catalogue of
   checked solutions, the practice generator, the exam mode.
4. **Merge** `lab/overnight-model-and-product` into the team branch, or parts of it.

Details and every number: `docs/lab/NOTEBOOK.md`. Ideas and their status: `docs/lab/IDEAS.md`.
Product log: `docs/lab/PRODUCT.md`.
