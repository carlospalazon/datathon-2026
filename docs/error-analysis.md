# Error analysis for the Math Copilot

`eval.py` measures an answering run and writes one CSV row per problem. `analyze_errors.py` joins that CSV to the local teaching catalogue by **problem ID and language**, then creates a Markdown report and a short manual-review queue.

## Run it

Prepare the catalogue first with `laptop/build_catalog.py` and the team's topic labels. The catalogue contains M3Kang text, so it remains in `data/` and is never committed. Copy the evaluation CSV from the board to your laptop if necessary, then run:

```bash
python3 analyze_errors.py \
  --eval results/eval-YYYYMMDD-HHMMSS-baseline.csv \
  --catalog data/catalog/problems.jsonl \
  --out results/error-report.md \
  --review-out results/error-review.csv \
  --review-limit 10
```

If you omit `--out` and `--review-out`, each output filename is derived from the evaluation CSV name, so analysing a second run does not overwrite the first report.

The report shows correct/total, accuracy, and mean response time by **topic, language, M3Kang level, estimated difficulty, answer-option evidence, figure dependency, and prediction status**. Every group includes its sample size. The difficulty score comes from the catalogue's estimate; it is not a measured student skill level.

The companion review CSV lists a small spread of wrong answers across topics. Open the original problems and images locally, then fill in `suspected_cause` and `review_notes`. Suggested causes: `OCR/figure`, `reading`, `mathematical reasoning`, `retrieval`, `timeout/service`, or `unclear`. Do not decide the cause from the answer letter alone. The report and review CSV are in `results/`, which Git ignores.

## Interpret the option groups carefully

- **No options:** the catalogue has no readable answer choices.
- **OCR flagged:** the catalogue's simple checks found suspicious options, such as duplicates or unusually long text.
- **OCR/unreviewed:** options exist, but no person has confirmed them against the image.
- **Human reviewed:** the catalogue marks the options as reviewed.

These groups are evidence about data quality, not proof of a specific OCR failure. Compare the original image before recording a cause.

The script rejects duplicate result rows, missing catalogue metadata, and disagreement between the CSV and catalogue labels. This prevents a misleading report when two runs or different dataset versions are mixed. It does not call a model, so it runs on a laptop or the board with Python's standard library.

When publishing, share only aggregate findings and anonymised examples whose dataset licence allows them. Keep the report and review queue local unless the team has checked what can be shared.
