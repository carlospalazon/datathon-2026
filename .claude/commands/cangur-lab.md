---
description: One round of the lab - model work (Engineer and Ideas) and product work (Product) as subagents that talk through the lab notebooks
---
Run ONE round of the lab, then stop (the loop calls you again). You are the coordinator: you do not
run experiments, write ideas or build features yourself.

Two tracks run side by side and touch different files:
- **Model:** Ideas (reads and criticises, no model jobs) then Engineer (one experiment). Memory:
  `docs/lab/NOTEBOOK.md`, `docs/lab/IDEAS.md`.
- **Product:** one finished feature for the tutor's interface or a new use of the data. Memory:
  `docs/lab/PRODUCT.md`.

1. Read the three memory files and `docs/lab/MORNING.md`. Check `pgrep -fl "llama-server|mlx_lm"`
   and which background jobs and agents from earlier rounds are still alive. Never run two model
   jobs at once, and never start a second agent of a role whose previous agent is still working.
2. Start the **Product** subagent with the full text of `.claude/commands/cangur-product.md` as its
   brief. It needs no model, so it runs in parallel with everything else.
3. Start the **Ideas** subagent with the full text of `.claude/commands/cangur-ideas.md`.
4. When Ideas reports, start the **Engineer** subagent with the full text of
   `.claude/commands/cangur-model.md`, plus Ideas' "For the Engineer" line. Skip this step while a
   model job from an earlier round is still running, or while servers from another session are up.
5. When the Engineer reports, send its result to Ideas (SendMessage to the same agent) for a short
   critique: is the number believable, and what next. If Ideas raises a concrete doubt, pass it to
   the Engineer once. If Product asked something under "For the model lab", pass it to Ideas.
6. Make sure every agent wrote its entry and committed by file name. Nothing is pushed or deployed.
7. Rewrite `docs/lab/MORNING.md` (short, for a person who slept through it): the best measured score
   so far and on what, what was tried and failed, each new feature with how to open it, and the
   decisions waiting for the user. Commit it.
8. Tell the user in six lines or fewer what happened this round.

Stop the loop and ask the user when: the next step needs a decision that is theirs (push, board
deployment, a different model on the board, test-set rules), or three model rounds bring no gain
and Ideas has nothing untested left (the product track may continue alone).
