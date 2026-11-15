# Error analysis of the delivered configuration

Qwen3.5 0.8B answering one letter, with the twin copy before it (`predict.py` as delivered), on the 562 validation problems (M3Kang, English and Catalan). Tables written by `analyze_errors.py`; brackets are 95% intervals. The last table compares it, problem by problem, with the model alone.

### Overall

| correct/total | accuracy | 95% CI |
|---|---|---|
| 147/562 | 26.2% | 22.7-29.9 |

### By language

| group | correct/total | accuracy | 95% CI |
|---|---|---|---|
| cat | 77/281 | 27.4% | 22.5-32.9 |
| eng | 70/281 | 24.9% | 20.2-30.3 |

### By level

| group | correct/total | accuracy | 95% CI |
|---|---|---|---|
| 0 | 12/40 | 30.0% | 18.1-45.4 |
| 1 | 14/34 | 41.2% | 26.4-57.8 |
| 2 | 24/58 | 41.4% | 29.6-54.2 |
| 3 | 6/24 | 25.0% | 12.0-44.9 |
| 4 | 33/124 | 26.6% | 19.6-35.0 |
| 5 | 25/106 | 23.6% | 16.5-32.5 |
| 6 | 17/98 | 17.3% | 11.1-26.0 |
| 7 | 16/78 | 20.5% | 13.0-30.8 |

### By topic

| group | correct/total | accuracy | 95% CI |
|---|---|---|---|
| algebra | 17/90 | 18.9% | 12.1-28.2 |
| aritmetica | 21/62 | 33.9% | 23.3-46.3 |
| conteo | 12/52 | 23.1% | 13.7-36.1 |
| geometria_espacial | 6/40 | 15.0% | 7.1-29.1 |
| geometria_plana | 38/132 | 28.8% | 21.8-37.0 |
| logica | 3/22 | 13.6% | 4.7-33.3 |
| medida | 6/14 | 42.9% | 21.4-67.4 |
| numeros | 21/80 | 26.2% | 17.9-36.8 |
| patrones | 8/18 | 44.4% | 24.6-66.3 |
| visual | 15/52 | 28.8% | 18.3-42.3 |

### By has_options

| group | correct/total | accuracy | 95% CI |
|---|---|---|---|
| False | 61/223 | 27.4% | 21.9-33.6 |
| True | 86/339 | 25.4% | 21.0-30.3 |

### By needs_figure

| group | correct/total | accuracy | 95% CI |
|---|---|---|---|
| False | 76/294 | 25.9% | 21.2-31.1 |
| True | 71/268 | 26.5% | 21.6-32.1 |

### Answerable from text (has options and no figure needed)

| group | correct/total | accuracy | 95% CI |
|---|---|---|---|
| False | 96/358 | 26.8% | 22.5-31.6 |
| True | 51/204 | 25.0% | 19.6-31.4 |

### Letter confusion (rows: true, columns: predicted)

| true \ pred | A | B | C | D | E | total |
|---|---|---|---|---|---|---|
| A | 30 | 22 | 7 | 48 | 3 | 110 |
| B | 28 | 39 | 1 | 55 | 1 | 124 |
| C | 28 | 21 | 13 | 40 | 2 | 104 |
| D | 25 | 42 | 2 | 58 | 3 | 130 |
| E | 27 | 17 | 1 | 42 | 7 | 94 |

### Share of answers per letter

| letter | predicted | predicted % | true | true % |
|---|---|---|---|---|
| A | 138 | 24.6% | 110 | 19.6% |
| B | 141 | 25.1% | 124 | 22.1% |
| C | 24 | 4.3% | 104 | 18.5% |
| D | 243 | 43.2% | 130 | 23.1% |
| E | 16 | 2.8% | 94 | 16.7% |

### Latency (seconds)

| count | mean | median | p90 | max | over 60 s |
|---|---|---|---|---|---|
| 562 | 0.0 | 0.1 | 0.1 | 0.1 | 0 |

### Status

| status | count |
|---|---|
| ok | 512 |
| presolve | 50 |

### Paired comparison on 562 shared problems (A = delivered: model with the twin copy, B = the model alone)

| both right | only A right | only B right | both wrong | McNemar exact p |
|---|---|---|---|---|
| 121 | 26 | 7 | 408 | 0.0013 |

- Significant at 5%: A 26.2% vs B 22.8% (26 vs 7 discordant problems, p = 0.0013).
