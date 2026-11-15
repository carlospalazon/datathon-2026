"""A transfer test for a model tuned on laptop/synthetic_problems.py: same maths, new wording.

Nine families the tuned model solves in their trained wording (46 of 50 on fresh numbers, lab
notebook 15 Nov 10:30) are told here as another story with other sentences. The numbers are drawn
the same way and the wrong options follow the same rules, so the only thing that changes is the
text. A model that learned the maths keeps its score; a model that learned the templates falls to
chance.

THIS IS A TEST SET. Never add its output to a training set: once trained on, it measures nothing.

    python3 laptop/reworded_problems.py --n 20 --seed 7 --out /somewhere/outside/git/reworded.jsonl

writes, per family and language (eng, cat), n reworded problems (ids "rew-<family>-...") and n in
the trained wording (ids "orig-<family>-...") as the control, in the format eval.py reads.
"""
import argparse
import json
import random

from synthetic_problems import NAMES, Retry, generate, make

LANGS = ("eng", "cat")
ADD = {"eng": {True: "puts {m} more loose marbles on the table", False: "takes {m} marbles away"},
       "cat": {True: "posa {m} bales soltes més sobre la taula", False: "treu {m} bales"}}


def r_shopping(rng, L):
    a, b, p, q = rng.randint(2, 6), rng.randint(2, 6), rng.randint(1, 9), rng.randint(1, 9)
    total = a * p + b * q
    pay = (total // 10 + 1) * 10 + rng.choice([0, 10])
    text = {"eng": "Entrance to the museum is {p} euros per adult and {q} euros per child. A family of {a} adults "
                   "and {b} children hands the cashier {pay} euros. How much money, in euros, does the cashier "
                   "give back?",
            "cat": "L'entrada al museu val {p} euros per adult i {q} euros per infant. Una família de {a} adults i "
                   "{b} infants dóna {pay} euros a la taquillera. Quants diners, en euros, els ha de tornar la "
                   "taquillera?"}[L].format(a=a, b=b, p=p, q=q, pay=pay)
    wrong = [pay - a * p, pay - b * q, total, pay - (a + b) * p, pay - (a + b) * q, pay + total]
    return make(rng, "shopping", L, text, pay - total, wrong, "", params=dict(a=a, b=b, p=p, q=q, pay=pay))


def r_sharing(rng, L):
    k, per, m = rng.randint(3, 8), rng.randint(3, 12), rng.randint(2, 15)
    n = m + k * per
    text = {"eng": "A baker made {n} rolls this morning. {m} of them got burnt and were thrown away. The good ones "
                   "were packed into {k} bags with the same number in every bag. How many rolls are in one bag?",
            "cat": "Una fornera ha fet {n} panets aquest matí. {m} s'han cremat i s'han llençat. Els bons s'han "
                   "posat en {k} bosses amb el mateix nombre a cada bossa. Quants panets hi ha en una bossa?"}[L]
    wrong = [n // k, per + 1, per - 1, n - m, (n - m) // (k + 1), per + m]
    return make(rng, "sharing", L, text.format(n=n, m=m, k=k), per, wrong, "", params=dict(n=n, m=m, k=k))


def r_fraction_two_step(rng, L):
    b, d = rng.choice([2, 3, 4, 5]), rng.choice([2, 3, 4])
    a, c = rng.randint(1, b - 1), rng.randint(1, d - 1)
    N = b * d * rng.randint(1, 4) * 2
    u1 = N * a // b
    rest = N - u1
    if rest * c % d:
        raise Retry()
    u2 = rest * c // d
    name = rng.choice(NAMES)
    text = {"eng": "A book has {N} pages. {name} read {a}/{b} of the book in the first week. In the second week "
                   "{name} read {c}/{d} of the pages not yet read. How many pages does {name} still have to read?",
            "cat": "Un llibre té {N} pàgines. {name} en va llegir {a}/{b} la primera setmana. La segona setmana va "
                   "llegir {c}/{d} de les pàgines que encara no havia llegit. Quantes pàgines li falten per "
                   "llegir?"}[L].format(N=N, a=a, b=b, c=c, d=d, name=name)
    wrong = [rest, u2, N - u1 - N * c // d if N * c % d == 0 else None, u1 + u2, N - u2]
    return make(rng, "fraction_two_step", L, text, rest - u2, wrong, "", params=dict(N=N, a=a, b=b, c=c, d=d))


def r_percent_discount(rng, L):
    P = rng.randrange(20, 401, 20)
    p = rng.choice([5, 10, 20, 25, 30, 40, 50])
    disc = P * p // 100
    ans = P - disc
    text = {"eng": "Last year a season ticket for the swimming pool was {P} euros. Members who sign up before "
                   "March pay {p}% less than that. How many euros does such a member pay?",
            "cat": "L'any passat l'abonament de la piscina valia {P} euros. Els socis que s'apunten abans del "
                   "març paguen un {p}% menys. Quants euros paga un d'aquests socis?"}[L].format(P=P, p=p)
    wrong = [disc, P + disc, P - p, P - 2 * disc, ans + disc // 2 if disc % 2 == 0 else None]
    return make(rng, "percent_discount", L, text, ans, wrong, "", params=dict(P=P, p=p))


def r_rect_area(rng, L):
    w, h = rng.sample(range(2, 15), 2)
    P = 2 * (w + h)
    text = {"eng": "A farmer needed exactly {P} m of fence to go once around a field with four right angles. "
                   "One edge of the field is {w} m long. How many square metres of grass does the field have?",
            "cat": "Un pagès ha necessitat exactament {P} m de tanca per fer la volta sencera a un camp amb quatre "
                   "angles rectes. Una vora del camp fa {w} m. Quants metres quadrats d'herba té el camp?"}[L]
    wrong = [w * (P - w), w * P // 2, w * w, w * (P // 2), (w + h) * 2, P * w // 4]
    return make(rng, "rect_area", L, text.format(P=P, w=w), w * h, wrong, "", params=dict(w=w, h=h))


def r_ribbon_pieces(rng, L):
    z = rng.choice([10, 20, 25, 30, 40, 50])
    count = rng.randint(6, 30)
    total = z * count
    if total < 120:
        raise Retry()
    m, cm = divmod(total, 100)
    length = f"{m} m {cm} cm" if cm else f"{m} m"
    text = {"eng": "An electrician needs lengths of cable of {z} cm. The roll in the van holds {length} of "
                   "cable. How many such lengths can be cut from the roll, with nothing left over?",
            "cat": "Una electricista necessita trams de cable de {z} cm. El rotlle que porta a la furgoneta té "
                   "{length} de cable. Quants trams en pot tallar, sense que en sobri gens?"}[L]
    wrong = [(10 * m + cm) // z, (100 * m) // z, count + 1, count - 1,
             total // (z * 10) if total % (z * 10) == 0 else None, (m + cm) // z]
    return make(rng, "ribbon_pieces", L, text.format(z=z, length=length), count, wrong, "",
                params=dict(total=total, z=z))


def r_number_think(rng, L):
    x, k, m = rng.randint(2, 20), rng.randint(2, 9), rng.randint(1, 20)
    add = rng.random() < 0.5
    R = k * x + m if add else k * x - m
    if R <= 0:
        raise Retry()
    name = rng.choice(NAMES)
    text = {"eng": "On a table there are {k} closed boxes, each holding the same number of marbles. {name} opens "
                   "them all, pours the marbles out and then {change}. Now there are {R} marbles on the table. "
                   "How many marbles were in each box?",
            "cat": "Sobre una taula hi ha {k} capses tancades, totes amb el mateix nombre de bales. {name} les "
                   "obre totes, n'aboca les bales i després {change}. Ara hi ha {R} bales sobre la taula. "
                   "Quantes bales hi havia a cada capsa?"}[L]
    text = text.format(k=k, name=name, R=R, change=ADD[L][add].format(m=m))
    t = R - m if add else R + m
    other = R + m if add else R - m
    wrong = [other // k if other % k == 0 else None, R // k if R % k == 0 else None,
             R - m if not add else R + m, t // k + 1, t // k - 1, k * x]
    return make(rng, "number_think", L, text, x, wrong, "", params=dict(x=x, k=k, m=m, add=add))


def r_speed_minutes(rng, L):
    v = rng.choice([12, 18, 24, 30, 36, 48, 60, 72, 90])
    mins = rng.randrange(10, 100, 10)
    d = v * mins // 60
    text = {"eng": "A delivery drone flies {v} km every hour and never changes its pace. Its battery is empty "
                   "after {mins} minutes in the air. How far, in kilometres, can it fly on one battery?",
            "cat": "Un dron de repartiment vola {v} km cada hora i no canvia mai de ritme. La bateria se li acaba "
                   "al cap de {mins} minuts de vol. Fins a quina distància, en quilòmetres, pot volar amb una "
                   "bateria?"}[L]
    wrong = [v * mins, v * mins // 100 if v * mins % 100 == 0 else None,
             v * mins // 10 if v * mins % 10 == 0 else None, v + mins, d * 2, d // 2 if d % 2 == 0 else None]
    return make(rng, "speed_minutes", L, text.format(v=v, mins=mins), d, wrong, "", params=dict(v=v, mins=mins))


def r_coin_count(rng, L):
    n = rng.randint(6, 20)
    b = rng.randint(1, n - 1)
    S = n + b
    text = {"eng": "At the school fair, a ride costs 1 euro for a child and 2 euros for an adult. Today {n} people "
                   "took the ride and the school collected {S} euros. How many of the riders were adults?",
            "cat": "A la fira de l'escola, pujar a l'atracció val 1 euro per als infants i 2 euros per als adults. "
                   "Avui hi han pujat {n} persones i l'escola ha recollit {S} euros. Quantes de les persones que "
                   "hi han pujat eren adultes?"}[L]
    wrong = [n - b, S // 2, n // 2, S - n + 1, S - n - 1, S - 2 * n if S > 2 * n else None]
    return make(rng, "coin_count", L, text.format(n=n, S=S), b, wrong, "", params=dict(n=n, S=S))


REWORDED = {fn.__name__[2:]: fn for fn in (
    r_shopping, r_sharing, r_fraction_two_step, r_percent_discount, r_rect_area, r_ribbon_pieces,
    r_number_think, r_speed_minutes, r_coin_count)}


def reworded(name, rng, lang):
    """One reworded problem of the family; redraws the numbers until they are clean."""
    for _ in range(200):
        try:
            return REWORDED[name](rng, lang)
        except Retry:
            continue
    raise RuntimeError(f"{name}: no clean draw in 200 tries")


def build(n=20, seed=7):
    """Rows for eval.py: n reworded and n trained-wording problems per family and language."""
    rng, rows = random.Random(seed), []
    for name in REWORDED:
        for lang in LANGS:
            for kind, fn in (("rew", reworded), ("orig", generate)):
                for i in range(n):
                    p = fn(name, rng, lang)
                    rows.append({"id": f"{kind}-{name}-{lang}-{i}", "language": lang, "level": 0, "year": 2000,
                                 "text_only": True, "text": p["text"], "options": p["options"],
                                 "label": p["label"], "family": name, "wording": kind})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", required=True, help="a file outside git: this is a test set")
    args = parser.parse_args()
    out = build(args.n, args.seed)
    with open(args.out, "w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(out)} problems written to {args.out}")
