---
description: One round of the model lab with two subagents (Engineer and Ideas) that talk through the lab notebook
---
Run ONE round of the model lab, then stop (the loop calls you again). You are the coordinator: you
do not run experiments or write ideas yourself.

1. Read `docs/lab/NOTEBOOK.md` and `docs/lab/IDEAS.md`. Check `pgrep -fl "llama-server|mlx_lm"`.
2. Start the **Ideas** subagent with the full text of `.claude/commands/cangur-ideas.md` as its
   brief. It only reads results and writes, so it can run while a training job is alive.
3. When it reports, start the **Engineer** subagent with the full text of
   `.claude/commands/cangur-model.md`, plus Ideas' "For the Engineer" line. Skip this step if a model
   job from an earlier round is still running: one model job at a time on this machine.
4. When the Engineer reports, send its result to Ideas (SendMessage to the same agent, so it keeps
   its context) and ask for a two-paragraph critique: is the number believable, and what next. If
   Ideas raises a concrete doubt, pass it back to the Engineer once for an answer or a quick check.
   One exchange each way per round is enough; the notebook carries the rest to the next round.
5. Make sure both wrote their notebook entries and committed by file name. Nothing is pushed.
6. Tell the user in five lines or fewer: what was tried, the number (with n), whether Ideas believes
   it, what runs next, and anything waiting on the user's decision.

Stop the loop and ask the user when: the top of the backlog needs a decision that is theirs (push,
board deployment, a different model on the board, test-set rules), or three rounds bring no gain.
