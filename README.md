# Tutor Cangur: a Kangaroo maths tutor that runs on the Arduino UNO Q

Tutor Cangur helps primary school students (10 to 12 years old) practise Kangaroo competition problems without being given the answer. The student works on a web page served by the board. When they ask for help, the tutor gives graded hints about that problem, checks intermediate results, and explains typical mistakes. The board's LED matrix and RGB LED show what is happening: a tick, a cross, the hint step, or a colour.

Everything runs on an Arduino UNO Q 4 GB, with no internet connection. Built at the Datathon FME 2026 for the Qualcomm challenge, [Math on the Edge](DATATHON.md).

The organizers' setup guide, steps 0 to 15, is in [DATATHON.md](DATATHON.md). This README describes what our team built on top of it.

## What it does

| The student | The tutor | The board shows |
|---|---|---|
| Opens a problem | Shows the original image and the options A to E | Blue |
| Asks for a hint | Hint 1: where to look. Hint 2: how to start. Hint 3: the key step | Purple, and the step number on the matrix |
| Keeps asking | Asks for an intermediate result and checks the number | Tick or cross |
| Asks again | Shows the method for this type of problem, then an easier solved problem | Step number |
| Answers wrong | Explains the likely mistake behind that option | Red, and a cross |
| Answers right | Picks the next problem: harder, or another topic after three in a row | Green, and a tick |
| Types a question | Routes it: a hint, an answer, off topic, or a question for the model | Yellow while the model works |
| Opens "El meu mapa" | Shows each topic by level (new, tried, shaky, solid) from the tutor, the practice problems and the exams, and what to try next; a class view by animal pseudonym for the teacher | A column per topic, taller the more solid, and a dot over what to try next |

The solution is shown only when the student asks for it.

## Architecture

```text
Laptop browser  ── USB (adb forward) or Wi-Fi ──►  port 7000
                                                      │
Arduino UNO Q, Linux side (Qualcomm QRB2210)          ▼
  App Lab app "Tutor Cangur" (Docker container)
    assets/index.html      the student's page (teach/index.html)
    python/main.py         the API for the page
    copilot/tutor.py       answers, help ladder, next problem      no model
    copilot/diagnose.py    the mistake behind a wrong option       no model
    copilot/assistant.py   routes free text, checks model output
    copilot/guardrails.py  blocks answers, invented numbers, copies
          │                               │
          │ Bridge.call("draw", frame)    │ HTTP, through board/llm_bridge.py
          ▼                               ▼
  STM32 microcontroller             llama-server, 127.0.0.1:8081
    sketch.ino draws the frame        Qwen3.5 0.8B Q8_0 (optional hints)
    on the 8x13 LED matrix          llama-server, 127.0.0.1:8082
  RGB LED 1 (set from Linux)          bge-small-en-v1.5 (similar problems)
```

- **Linux side:** the tutor is plain Python with no model. It reads a catalogue of problems prepared ahead of time, so help appears at once.
- **Microcontroller:** the sketch only draws the frame it receives. Python decides every pixel.
- **Language model:** used only when the student asks for a model hint or types a free question. Its output is shown only if it passes the guardrails; otherwise the student gets a written hint.
- **`predict.py`:** the entry point the jury runs. It is independent of the tutor, the page and the LEDs.

### How we use M3Kang

- **A catalogue for teaching.** Each of the 1,747 problems gets a topic from an 11-topic taxonomy, a school grade and a difficulty from its position in the exam.
- **Written help for the 154 primary-school problems in Catalan.** Three graded hints, a solution, up to three checkpoints with a numeric answer, and notes on wrong options. Written by Claude while looking at each problem's image. Every item carries a status: `generado` (by a model), `preparado` (by a person) or `revisado` (checked by a person).
- **The anatomy of 804 solved problems.** For each one: the data that matters, the condition that is easy to miss, the solving strategy from a closed list of 15, and the first step.
- **Similar problems.** The embedding model finds an easier problem of the same type to show as a worked example.
- **Training data.** Problems with short worked solutions, to fine-tune the small model (in progress).

M3Kang is licensed for research use only. Nothing derived from its problems is in this repository: the catalogue, the hints and the images stay in `data/`, which Git ignores. See the [dataset card](https://huggingface.co/datasets/qualcomm/M3Kang) and Torres-Camps et al., 2026, [arXiv:2601.16218](https://arxiv.org/abs/2601.16218).

## How to replicate it

Start from a board set up with steps 0 to 12 of [DATATHON.md](DATATHON.md): both model services running, and the M3Kang files prepared on the laptop with `laptop/prepare_m3kang.py --save-images`.

**1. Build the teaching catalogue (laptop).** You need topic labels in `data/catalog/content/labels/` and, for the help, the content files in `data/catalog/content/` (`hints.jsonl`, `checkpoints.jsonl`, `figures.jsonl`). These hold M3Kang text, so they are not in the repository: generate them following the `FORMAT_*.md` briefs, or ask the team.

```bash
python3 laptop/merge_hints.py        # checks the hints: right letter, no leaked answer
python3 laptop/build_catalog.py --labels "data/catalog/content/labels/*.jsonl"
```

You should see `Wrote data/catalog/problems.jsonl: 3494 rows, 1747 problem ids`.

**2. Try it on the laptop, without the board.**

```bash
python3 teach/server.py              # then open http://127.0.0.1:8010
```

**3. Package the App Lab app and copy it to the board (laptop).**

```bash
python3 applab/package.py            # -> applab/build/math-tutor: 154 problems, 154 images
adb push applab/build/math-tutor /home/arduino/ArduinoApps/
```

**4. Let the app reach the language model (board).** App Lab runs the app in a container, where `127.0.0.1` is not the board. `board/llm_bridge.py` forwards the model's port on the Docker interface only. To start it at boot, install `board/systemd/math-llm-bridge.service` as described in [applab/README.md](applab/README.md).

**5. Start the app (board).**

```bash
export TMPDIR=/tmp                   # only needed inside `adb shell`
arduino-app-cli app start user:math-tutor
```

The sketch compiles on the first start, which takes about a minute. You should see `App "Tutor Cangur" started successfully`.

**6. Open the page (laptop).**

```bash
adb forward tcp:7000 tcp:7000        # then open http://127.0.0.1:7000
```

Ask for a hint: RGB LED 1 turns purple and the matrix shows the step. Answer wrong: red and a cross. Answer right: green and a tick.

**Tests** (laptop or board, standard library only): `python3 -m unittest discover -s tests`. 154 tests.

## Results

### Reason: answering problems (`predict.py`)

What `predict.py` runs: the Qwen3.5 0.8B answers with one letter, and before it, code copies the answer of a twin problem when the training set holds one (`copilot/presolve.py`, on by default). Kangaroo papers reuse a problem at neighbouring levels of the same year; when the problem asked is almost word for word a training problem, the value of that problem's answer is looked for among the options. It never matches the problem's own id or its translation, and it only knows the training split.

| Run | Where | Problems | Accuracy (95% interval) |
|---|---|---|---|
| **0.8B, one letter, with the twin copy (what we deliver)** | laptop, `eval.py` | 562 English and Catalan validation | **26.2% (22.7–29.9), 147/562** |
| 0.8B, one letter (baseline) | laptop | 562 | 22.8% (19.5–26.4), 128/562 |
| 0.8B, one letter (baseline) | board | 281 English validation | 22.4% (17.9–27.6), 8.8 s mean, 19.2 s worst |
| Always answer D (no model) | – | 562 | 23.1% |

The twin copy answers 50 of the 562 problems without the model and is right on 27; two runs gave the same 562 letters. Chance is 20% with five options, and 223 of the 562 problems arrive without readable options.

**The model itself does not solve Kangaroo problems, and we measured why.** Everything below is the 0.8B unless it says otherwise, on the same 562 problems.

| What we tried | Result |
|---|---|
| Free step-by-step working, 250 tokens | 22.1% (2B: 21.2%) |
| Fine-tuned to answer the letter | 17.3% measured on a broken file; the idea was dropped, the model only learned to guess evenly |
| Fine-tuned on 3,883 checked Kangaroo solutions, writing its working | 18.3% |
| Fine-tuned on a mix: Kangaroo solutions, 6,000 generated problems, 1,000 AQuA | 18.3% (20/100 on 100 unseen 2026-style problems) |
| The same model on 300 fresh generated problems | 54.7%, up from about 19% before tuning |
| The same generated problems told as another story (same numbers) | 35% reworded against 88% in the trained wording |
| One similar solved problem shown as a worked example | 20% → 17%; but 2/13 → 8/13 when the example is nearly the same problem |
| Python recomputing every sum in the working | −1 problem of 339 |
| Qwen3.5 2B, free working, inside 60 s at the board's real speed (2.5 tokens/s) | 18.9%: it finishes no working at all |

So the small model imitates what it has seen and cannot deduce: it learns the wording of a problem family, not the maths, and a worked example helps only when it is almost the same problem. That is why the one thing that raises the score is the twin copy. On the board the fine-tuned model writes its working in 34 s on average (worst 58 s), reads 11.7 and writes 5.7 tokens per second.

A statistical prior over answer positions and option shapes, learned from the training split, scored 151/562 (26.9%). We left it off: it does not solve anything.

### Teach: help for the catalogue's problems

Measured with `measure_teach.py coverage` on the 154 primary-school problems in Catalan.

| Measure | Before | After writing help per problem |
|---|---|---|
| Problems with hints about that problem | 0 | 154 |
| Hints in total | 0 | 462 |
| Checkpoints the student can be asked | 93 | 322 |
| Problems with a solution to show on request | 48 | 154 |
| Help steps per problem | 3 to 8 | 8 to 11 |
| Help items stopped by the leak check | 0 | 0 |

- **Who checked it.** In the 106 problems solved without knowing the answer, the letter matched the verified one every time. Nobody has reviewed the hint texts or the 322 checkpoint answers yet: all of it is marked `generado`.
- **Two ways of writing hints, compared blind.** We wrote a second set of hints from the solution text alone and asked a model judge to pick the better set per problem. Hints written while seeing the image won 66, hints from the solution won 53, 35 ties. On text-only problems it was 27 to 27. On problems with a figure the image-based hints won 39 to 26. The judge flagged no false hint in either set.
- **Feedback on wrong answers.** With reviewed content only, rules explain 89 of 616 possible wrong choices (14.6%). The most common diagnosis is answering an intermediate result (41).

### Teach: the live model as a hint writer

Measured on the board, on 48 primary-school problems treated as new (statement only).

| Measure | Result |
|---|---|
| Model hints that pass the guardrails | 17 of 48 (35%, 23–50%) |
| Main reasons to reject | restates the question 21, copies the problem 8 |
| Seconds per hint | 10.8 mean, 20.8 worst |

Passing the guardrails is not the same as being useful: in a first hand check of 8 problems, none of the hints was a usable hint, including the three that passed.

### Hints for problems outside the catalogue (in progress)

We tested whether the board can at least name the right strategy for a problem it has never seen. Held-out problems: the 154 of levels 0 and 1, each with every problem of its own year removed from the index.

| How the strategy is chosen | Right strategy |
|---|---|
| Two annotators reading the solution agree (the ceiling) | 137 of 154 (89%) |
| Always the most common strategy (the floor) | 23 of 154 (15%) |
| Nearest problems by embedding, best setting | 37 of 154 (24%) |
| The model picks one of the 15 strategies | 4 of 48 (8%); it chose the first option every time |

The embedding model is English and the statements are Catalan. Searching English against English did no better (38 of 154).

## Error analysis

From the baseline on the board, 281 English validation problems. Commands and how to read the report are in [docs/error-analysis.md](docs/error-analysis.md).

| Group | Correct/total | Accuracy |
|---|---|---|
| Levels 0 to 2 (grades 5 to 7) | 23/66 | 34.8% |
| Levels 3 to 7 (grades 8 to 12) | 40/215 | 18.6% |
| Arithmetic | 10/31 | 32.3% |
| Numbers | 11/40 | 27.5% |
| Counting | 7/26 | 26.9% |
| Algebra | 10/45 | 22.2% |
| Plane geometry | 13/66 | 19.7% |
| Visual | 5/26 | 19.2% |
| Solid geometry | 1/20 | 5.0% |
| Logic | 0/11 | 0.0% |
| No figure needed | 37/147 | 25.2% |
| Figure needed | 26/134 | 19.4% |
| Options read by OCR | 37/167 | 22.2% |
| No options read | 26/114 | 22.8% |

- **The model answers by letter, not by problem.** It answered D 129 times and A 95 times, and C and E once each, while the right answers are spread evenly. That alone caps the score near chance.
- **Having the options doesn't help.** Accuracy is the same with and without readable options, so the model isn't using them.
- **Easier levels go better,** but with 66 problems the interval is wide.
- **Language.** The board run covers English only; the laptop runs mix English and Catalan and land at the same accuracy.

## What didn't work, and what's next

- **The live model as a hint writer.** It restates the question or writes nonsense. We moved to hints written ahead of time, and kept the model behind guardrails as an extra.
- **A bigger model.** With one letter the 2B and 4B scored the same as the 0.8B, and inside the board's 60 seconds the 2B cannot finish any working.
- **Fine-tuning.** Three fine-tunes, none above chance on Kangaroo problems. The model learns the wording of the families it is trained on (88% in the trained wording, 35% when the same problem is told as another story).
- **Giving the model more to work with.** A worked example of a similar problem, a calculator pass over its sums, and matching its result to the options: none helped, except an example that is nearly the same problem.
- **A converter trap.** A fine-tuned model converted to GGUF with a newer llama.cpp than the board's loads on the laptop and is refused by the board. `laptop/adapter_to_gguf.py` uses the board's own converter.
- **Retrieving a strategy by embeddings, and letting the model choose one.** Both are close to the floor (see the table above).

Next:

- Have a person review the hints and the checkpoint answers, starting with the problems the writers flagged as doubtful.
- Finish the comparison of hint sources for new problems: the model with near problems as examples, and rules on the statement, each judged on the same 48 problems.
- Let the model with its vision projector read the options from the image: 40% of the problems arrive without them, and reading is closer to what this model can do than solving.
- Try a fine-tune on hints (the set is built by `laptop/make_hint_ft_set.py`, with 2023 and 2024 held out).
- Measure the letter-bias correction for `predict.py` (`calibrate.py`) on the board: the model answers A or D four times out of five.
- A demo with Wi-Fi off, and a check of the matrix and the LED colours by eye.

## Repository map

| Path | What it holds |
|---|---|
| `predict.py`, `copilot/pipeline.py`, `copilot/llm.py`, `copilot/rag.py` | The official answering run |
| `copilot/tutor.py`, `diagnose.py`, `assistant.py`, `guardrails.py`, `topics.py`, `slm.py`, `matrix.py` | The tutor |
| `teach/` | The student's page, and a server to run it on a laptop |
| `applab/` | The App Lab app and its packaging script |
| `led_demo/` | A small app to test the LED matrix and the RGB LED on their own |
| `explorer/` | A page to browse the problems and the model's answers |
| `board/` | Setup scripts, service files, and tools that run on the board |
| `laptop/` | Data preparation, catalogue, hints, training data, model comparison |
| `content/` | Method cards per topic and the list of strategies (no M3Kang text) |
| `eval.py`, `analyze_errors.py`, `error_report.py`, `calibrate.py` | Measuring the answering run |
| `measure_teach.py`, `measure_newproblem.py` | Measuring the teaching side |
| `tests/` | Unit tests, standard library only |
| `DATATHON.md` | The organizers' guide: board setup, models, baseline |

## The team

Pere Arenas, Marina Dasca, Mohamed Yousuf and Carlos Palazón, at the Datathon FME 2026 (UPC).

Built with [llama.cpp](https://github.com/ggml-org/llama.cpp), [Qwen3.5 0.8B](https://huggingface.co/Qwen), [bge-small-en-v1.5](https://huggingface.co/BAAI/bge-small-en-v1.5), Arduino App Lab, and the organizers' starter repository. Teaching content and parts of the code were written with Claude.
