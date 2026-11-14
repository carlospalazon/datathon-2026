"""Synthetic Kangaroo-style multiple-choice problems whose answer the code computes.

Every generator takes a seeded random.Random and a language ("eng", "cat", "esp")
and returns a dict:
    text, options {"A".."E": str}, label, rationale, answer (the correct option text),
    params (the numbers drawn), generator, language.
The rationale is 2-4 short sentences and never mentions an option letter.
Use generate(name, rng, lang); GENERATOR_NAMES lists the generators.
"""
import math
import random

LANGS = ("eng", "cat", "esp")
LI = {"eng": 0, "cat": 1, "esp": 2}
MAX_RATIONALE = 350

NAMES = ["Anna", "Marc", "Laia", "Pau", "Joan", "Maria", "Pere", "Clara", "Nil", "Júlia",
         "Hugo", "Lucía", "Sara", "Biel"]

# (eng, cat, esp) plural item names, no agreement needed anywhere they are used
ITEMS = [("pencils", "llapis", "lápices"), ("notebooks", "quaderns", "cuadernos"),
         ("erasers", "gomes", "gomas"), ("rulers", "regles", "reglas"),
         ("stickers", "cromos", "cromos"), ("apples", "pomes", "manzanas"),
         ("lollipops", "xupa-xups", "piruletas"), ("balloons", "globus", "globos"),
         ("postcards", "postals", "postales"), ("oranges", "taronges", "naranjas")]
# with plural definite article (cat, esp) for "of the N apples"
ITEMS_ART = [("apples", "pomes", "manzanas", "les", "las"), ("stickers", "cromos", "cromos", "els", "los"),
             ("marbles", "boles", "canicas", "les", "las"), ("cookies", "galetes", "galletas", "les", "las"),
             ("books", "llibres", "libros", "els", "los")]
COLORS = [("red", "vermell", "rojo"), ("blue", "blau", "azul"), ("green", "verd", "verde"),
          ("yellow", "groc", "amarillo"), ("white", "blanc", "blanco"), ("black", "negre", "negro"),
          ("orange", "taronja", "naranja")]
DAYS = {"eng": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "cat": ["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"],
        "esp": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]}


class Retry(Exception):
    """The drawn numbers do not give a clean problem: draw again."""


def cap(s):
    return s[0].upper() + s[1:]


def pick(rng, templates, lang, **kw):
    return rng.choice(templates[lang]).format(**kw)


def _as_int(v):
    if isinstance(v, float):
        return int(v) if v.is_integer() else None
    return v


def make(rng, name, lang, text, answer, wrong, rationale, numeric=True, params=None):
    """Build the result dict: the answer plus four distinct plausible wrong options."""
    ans = str(answer)
    opts, seen = [], {ans}
    pool = [_as_int(w) for w in wrong] if numeric else list(wrong)
    if numeric:
        near = [answer + d for d in (1, -1, 2, -2, 3, -3, 5, -5, 10, -10)]
        rng.shuffle(near)
        pool += near
    for w in pool:
        if w is None:
            continue
        if numeric and w < 0:
            continue
        s = str(w)
        if s in seen:
            continue
        seen.add(s)
        opts.append(s)
        if len(opts) == 4:
            break
    if len(opts) < 4:
        raise Retry()
    if len(rationale) > MAX_RATIONALE:
        raise ValueError(f"{name}: rationale too long ({len(rationale)})")
    slot = rng.randrange(5)
    values = opts[:slot] + [ans] + opts[slot:]
    return {"text": text, "options": dict(zip("ABCDE", values)), "label": "ABCDE"[slot],
            "rationale": rationale, "answer": ans, "params": params or {},
            "generator": name, "language": lang}


# --------------------------------------------------------------------------- generators

def g_shopping(rng, L):
    name = rng.choice(NAMES)
    i1, i2 = rng.sample(ITEMS, 2)
    a, b, p, q = rng.randint(2, 6), rng.randint(2, 6), rng.randint(1, 9), rng.randint(1, 9)
    total = a * p + b * q
    pay = (total // 10 + 1) * 10 + rng.choice([0, 10])
    change = pay - total
    kw = dict(name=name, a=a, b=b, p=p, q=q, pay=pay, i1=i1[LI[L]], i2=i2[LI[L]])
    text = pick(rng, {
        "eng": ["{name} buys {a} {i1} at {p} euros each and {b} {i2} at {q} euros each, and pays with {pay} euros. How many euros of change does {name} get?",
                "In a shop, {a} {i1} cost {p} euros each and {b} {i2} cost {q} euros each. {name} buys them all and hands over {pay} euros. How many euros of change?"],
        "cat": ["{name} compra {a} {i1} a {p} euros la unitat i {b} {i2} a {q} euros la unitat. Paga amb {pay} euros. Quants euros li tornen?",
                "En una botiga, {a} {i1} costen {p} euros la unitat i {b} {i2} costen {q} euros la unitat. {name} ho compra tot i lliura {pay} euros. Quants euros de canvi rep?"],
        "esp": ["{name} compra {a} {i1} a {p} euros la unidad y {b} {i2} a {q} euros la unidad. Paga con {pay} euros. ¿Cuántos euros le devuelven?",
                "En una tienda, {a} {i1} cuestan {p} euros la unidad y {b} {i2} cuestan {q} euros la unidad. {name} lo compra todo y entrega {pay} euros. ¿Cuántos euros de cambio recibe?"]}, L, **kw)
    r = {"eng": "The first kind costs {a}*{p} = {x} euros and the second kind {b}*{q} = {y} euros, so {total} euros in all. The change is {pay} - {total} = {change}.",
         "cat": "El primer tipus costa {a}*{p} = {x} euros i el segon {b}*{q} = {y} euros, en total {total} euros. El canvi és {pay} - {total} = {change}.",
         "esp": "El primer tipo cuesta {a}*{p} = {x} euros y el segundo {b}*{q} = {y} euros, en total {total} euros. El cambio es {pay} - {total} = {change}."}[L]
    rat = r.format(a=a, b=b, p=p, q=q, x=a * p, y=b * q, total=total, pay=pay, change=change)
    wrong = [pay - a * p, pay - b * q, total, pay - (a + b) * p, pay - (a + b) * q, pay + total]
    return make(rng, "shopping", L, text, change, wrong, rat, params=dict(a=a, b=b, p=p, q=q, pay=pay))


def g_ages(rng, L):
    n1, n2 = rng.sample(NAMES, 2)
    y, d, k = rng.randint(4, 15), rng.randint(2, 9), rng.randint(2, 8)
    S = (y + k) + (y + d + k)
    text = pick(rng, {
        "eng": ["{n1} is {d} years older than {n2}. In {k} years, the sum of their ages will be {S}. How old is {n2} now?",
                "The sum of the ages of {n1} and {n2} will be {S} in {k} years. {n1} is {d} years older than {n2}. How old is {n2} today?"],
        "cat": ["{n1} té {d} anys més que {n2}. D'aquí a {k} anys, la suma de les seves edats serà {S}. Quants anys té {n2} ara?",
                "D'aquí a {k} anys, la suma de les edats de {n1} i {n2} serà {S}. {n1} té {d} anys més que {n2}. Quants anys té {n2} avui?"],
        "esp": ["{n1} tiene {d} años más que {n2}. Dentro de {k} años, la suma de sus edades será {S}. ¿Cuántos años tiene {n2} ahora?",
                "Dentro de {k} años, la suma de las edades de {n1} y {n2} será {S}. {n1} tiene {d} años más que {n2}. ¿Cuántos años tiene {n2} hoy?"]},
        L, n1=n1, n2=n2, d=d, k=k, S=S)
    now = S - 2 * k
    r = {"eng": "Now the sum of their ages is {S} - 2*{k} = {now}. Twice the younger age is {now} - {d} = {t}. So {n2} is {y}.",
         "cat": "Ara la suma de les edats és {S} - 2*{k} = {now}. El doble de l'edat del petit és {now} - {d} = {t}. Per tant, {n2} té {y}.",
         "esp": "Ahora la suma de las edades es {S} - 2*{k} = {now}. El doble de la edad del menor es {now} - {d} = {t}. Por tanto, {n2} tiene {y}."}[L]
    rat = r.format(S=S, k=k, now=now, d=d, t=now - d, n2=n2, y=y)
    wrong = [y + d, y + k, now // 2, S // 2 - k, (S - d) // 2, y + d + k]
    return make(rng, "ages", L, text, y, wrong, rat, params=dict(y=y, d=d, k=k, S=S))


def g_sharing(rng, L):
    name = rng.choice(NAMES)
    it = rng.choice(ITEMS)
    k, per, m = rng.randint(3, 8), rng.randint(3, 12), rng.randint(2, 15)
    n = m + k * per
    text = pick(rng, {
        "eng": ["{name} has {n} {it}. {name} gives {m} of them to a cousin and shares the rest equally among {k} friends. How many does each friend get?",
                "There are {n} {it}. First {m} are put aside. The others are shared equally among {k} children. How many does each child get?"],
        "cat": ["{name} té {n} {it}. En dóna {m} a un cosí i reparteix la resta a parts iguals entre {k} amics. Quants en rep cada amic?",
                "Hi ha {n} {it}. Primer se'n guarden {m}. Les altres es reparteixen a parts iguals entre {k} nens. Quants en rep cada nen?"],
        "esp": ["{name} tiene {n} {it}. Da {m} a un primo y reparte el resto a partes iguales entre {k} amigos. ¿Cuántas recibe cada amigo?",
                "Hay {n} {it}. Primero se guardan {m}. Las demás se reparten a partes iguales entre {k} niños. ¿Cuántas recibe cada niño?"]},
        L, name=name, n=n, m=m, k=k, it=it[LI[L]])
    r = {"eng": "After setting aside {m}, there are {n} - {m} = {rest} left. Shared among {k}: {rest} / {k} = {per}.",
         "cat": "Després de treure'n {m}, en queden {n} - {m} = {rest}. Repartits entre {k}: {rest} / {k} = {per}.",
         "esp": "Tras apartar {m}, quedan {n} - {m} = {rest}. Repartidas entre {k}: {rest} / {k} = {per}."}[L]
    rat = r.format(m=m, n=n, rest=n - m, k=k, per=per)
    wrong = [n // k, per + 1, per - 1, n - m, (n - m) // (k + 1), per + m]
    return make(rng, "sharing", L, text, per, wrong, rat, params=dict(n=n, m=m, k=k))


def g_fraction_two_step(rng, L):
    b, d = rng.choice([2, 3, 4, 5]), rng.choice([2, 3, 4])
    a, c = rng.randint(1, b - 1), rng.randint(1, d - 1)
    mult = rng.randint(1, 4)
    N = b * d * mult * 2
    u1 = N * a // b
    rest = N - u1
    if rest * c % d:
        raise Retry()
    u2 = rest * c // d
    ans = rest - u2
    text = pick(rng, {
        "eng": ["A tank holds {N} litres of water. On Monday {a}/{b} of the water is used, and on Tuesday {c}/{d} of what was left. How many litres are left?"],
        "cat": ["Un dipòsit conté {N} litres d'aigua. El dilluns es gasta {a}/{b} de l'aigua i el dimarts {c}/{d} de la que quedava. Quants litres queden?"],
        "esp": ["Un depósito contiene {N} litros de agua. El lunes se gasta {a}/{b} del agua y el martes {c}/{d} de la que quedaba. ¿Cuántos litros quedan?"]},
        L, N=N, a=a, b=b, c=c, d=d)
    r = {"eng": "Monday uses {u1} litres, so {rest} litres remain. Tuesday uses {c}/{d} of {rest}, which is {u2}. What is left is {rest} - {u2} = {ans}.",
         "cat": "El dilluns se'n gasten {u1} litres, i en queden {rest}. El dimarts se'n gasta {c}/{d} de {rest}, que són {u2}. Queden {rest} - {u2} = {ans}.",
         "esp": "El lunes se gastan {u1} litros, y quedan {rest}. El martes se gasta {c}/{d} de {rest}, que son {u2}. Quedan {rest} - {u2} = {ans}."}[L]
    rat = r.format(u1=u1, rest=rest, c=c, d=d, u2=u2, ans=ans)
    wrong = [rest, u2, N - u1 - N * c // d if N * c % d == 0 else None, u1 + u2, N - u2]
    return make(rng, "fraction_two_step", L, text, ans, wrong, rat, params=dict(N=N, a=a, b=b, c=c, d=d))


PRICED = [("a jacket", "una jaqueta", "una chaqueta"), ("a bike", "una bicicleta", "una bicicleta"),
          ("a backpack", "una motxilla", "una mochila"), ("a video game", "un videojoc", "un videojuego"),
          ("a pair of shoes", "un parell de sabates", "un par de zapatos")]


def g_percent_discount(rng, L):
    it = rng.choice(PRICED)[LI[L]]
    P = rng.randrange(20, 401, 20)
    p = rng.choice([5, 10, 20, 25, 30, 40, 50])
    disc = P * p // 100
    ans = P - disc
    text = pick(rng, {
        "eng": ["{It} costs {P} euros. In the sales it gets a {p}% discount. How many euros does it cost now?",
                "In the sales, all prices are reduced by {p}%. {It} used to cost {P} euros. What is its new price in euros?"],
        "cat": ["{It} costa {P} euros. A les rebaixes té un {p}% de descompte. Quants euros costa ara?",
                "A les rebaixes, tots els preus baixen un {p}%. {It} costava {P} euros. Quin és el preu nou en euros?"],
        "esp": ["{It} cuesta {P} euros. En las rebajas tiene un {p}% de descuento. ¿Cuántos euros cuesta ahora?",
                "En las rebajas, todos los precios bajan un {p}%. {It} costaba {P} euros. ¿Cuál es el precio nuevo en euros?"]},
        L, It=cap(it), P=P, p=p)
    r = {"eng": "The discount is {p}% of {P} = {disc} euros. The new price is {P} - {disc} = {ans} euros.",
         "cat": "El descompte és el {p}% de {P} = {disc} euros. El preu nou és {P} - {disc} = {ans} euros.",
         "esp": "El descuento es el {p}% de {P} = {disc} euros. El precio nuevo es {P} - {disc} = {ans} euros."}[L]
    rat = r.format(p=p, P=P, disc=disc, ans=ans)
    wrong = [disc, P + disc, P - p, P - 2 * disc, ans + disc // 2 if disc % 2 == 0 else None]
    return make(rng, "percent_discount", L, text, ans, wrong, rat, params=dict(P=P, p=p))


def g_rect_area(rng, L):
    w, h = rng.sample(range(2, 15), 2)
    P = 2 * (w + h)
    A = w * h
    text = pick(rng, {
        "eng": ["A rectangle has a perimeter of {P} cm and one of its sides measures {w} cm. What is its area in square centimetres?"],
        "cat": ["Un rectangle té un perímetre de {P} cm i un dels seus costats mesura {w} cm. Quina és la seva àrea en centímetres quadrats?"],
        "esp": ["Un rectángulo tiene un perímetro de {P} cm y uno de sus lados mide {w} cm. ¿Cuál es su área en centímetros cuadrados?"]},
        L, P=P, w=w)
    r = {"eng": "Half the perimeter is {P}/2 = {s}, so the other side is {s} - {w} = {h} cm. The area is {w}*{h} = {A}.",
         "cat": "La meitat del perímetre és {P}/2 = {s}, per tant l'altre costat fa {s} - {w} = {h} cm. L'àrea és {w}*{h} = {A}.",
         "esp": "La mitad del perímetro es {P}/2 = {s}, así que el otro lado mide {s} - {w} = {h} cm. El área es {w}*{h} = {A}."}[L]
    rat = r.format(P=P, s=P // 2, w=w, h=h, A=A)
    wrong = [w * (P - w), w * P // 2, w * w, w * (P // 2), (w + h) * 2, P * w // 4]
    return make(rng, "rect_area", L, text, A, wrong, rat, params=dict(w=w, h=h))


def g_l_shape_area(rng, L):
    W, H = rng.randint(6, 14), rng.randint(5, 12)
    w, h = rng.randint(2, W - 2), rng.randint(2, H - 2)
    ans = W * H - w * h
    text = pick(rng, {
        "eng": ["An L-shaped floor is made from a rectangle {W} m by {H} m by cutting out a rectangular corner {w} m by {h} m. What is the area of the floor in square metres?"],
        "cat": ["Un terra en forma d'L es fa amb un rectangle de {W} m per {H} m al qual es talla una cantonada rectangular de {w} m per {h} m. Quina és l'àrea del terra en metres quadrats?"],
        "esp": ["Un suelo con forma de L se hace con un rectángulo de {W} m por {H} m al que se le corta una esquina rectangular de {w} m por {h} m. ¿Cuál es el área del suelo en metros cuadrados?"]},
        L, W=W, H=H, w=w, h=h)
    r = {"eng": "The whole rectangle has area {W}*{H} = {big}. The cut corner has area {w}*{h} = {small}. The floor is {big} - {small} = {ans}.",
         "cat": "El rectangle sencer té àrea {W}*{H} = {big}. La cantonada tallada té àrea {w}*{h} = {small}. El terra fa {big} - {small} = {ans}.",
         "esp": "El rectángulo entero tiene área {W}*{H} = {big}. La esquina cortada tiene área {w}*{h} = {small}. El suelo mide {big} - {small} = {ans}."}[L]
    rat = r.format(W=W, H=H, w=w, h=h, big=W * H, small=w * h, ans=ans)
    wrong = [W * H, W * H + w * h, (W - w) * (H - h), 2 * (W + H), W * H - w - h, W * H - 2 * w * h]
    return make(rng, "l_shape_area", L, text, ans, wrong, rat, params=dict(W=W, H=H, w=w, h=h))


def g_handshakes(rng, L):
    n = rng.randint(4, 16)
    ans = n * (n - 1) // 2
    text = pick(rng, {
        "eng": ["At a party, {n} friends each shake hands exactly once with every other friend. How many handshakes are there in total?",
                "In a chess tournament, each of the {n} players plays exactly one game against each other player. How many games are played?"],
        "cat": ["En una festa, {n} amics es donen la mà exactament una vegada amb cadascun dels altres. Quantes encaixades de mans hi ha en total?",
                "En un torneig d'escacs, cadascun dels {n} jugadors juga exactament una partida contra cada un dels altres. Quantes partides es juguen?"],
        "esp": ["En una fiesta, {n} amigos se dan la mano exactamente una vez con cada uno de los demás. ¿Cuántos apretones de manos hay en total?",
                "En un torneo de ajedrez, cada uno de los {n} jugadores juega exactamente una partida contra cada uno de los demás. ¿Cuántas partidas se juegan?"]},
        L, n=n)
    r = {"eng": "Each of the {n} people deals with {m} others: {n}*{m} = {x}. Every pair is counted twice, so we divide by 2: {x}/2 = {ans}.",
         "cat": "Cadascuna de les {n} persones tracta amb {m} més: {n}*{m} = {x}. Cada parella es compta dues vegades, així que dividim per 2: {x}/2 = {ans}.",
         "esp": "Cada una de las {n} personas trata con {m} más: {n}*{m} = {x}. Cada pareja se cuenta dos veces, así que dividimos entre 2: {x}/2 = {ans}."}[L]
    rat = r.format(n=n, m=n - 1, x=n * (n - 1), ans=ans)
    wrong = [n * (n - 1), n * n // 2, n - 1, n * (n + 1) // 2, ans + n, n * (n - 1) // 2 - n]
    return make(rng, "handshakes", L, text, ans, wrong, rat, params=dict(n=n))


def g_outfits(rng, L):
    a, b, c = rng.randint(2, 6), rng.randint(2, 5), rng.randint(2, 4)
    name = rng.choice(NAMES)
    text = pick(rng, {
        "eng": ["{name} has {a} T-shirts, {b} pairs of trousers and {c} pairs of shoes. An outfit is one T-shirt, one pair of trousers and one pair of shoes. How many different outfits can {name} make?",
                "A restaurant menu has {a} starters, {b} main courses and {c} desserts. A meal is one of each. How many different meals can be chosen?"],
        "cat": ["{name} té {a} samarretes, {b} pantalons i {c} parells de sabates. Un conjunt és una samarreta, uns pantalons i un parell de sabates. Quants conjunts diferents pot fer {name}?",
                "El menú d'un restaurant té {a} entrants, {b} plats principals i {c} postres. Un àpat és un de cada. Quants àpats diferents es poden triar?"],
        "esp": ["{name} tiene {a} camisetas, {b} pantalones y {c} pares de zapatos. Un conjunto consta de una camiseta, unos pantalones y un par de zapatos. ¿Cuántos conjuntos diferentes puede formar {name}?",
                "El menú de un restaurante tiene {a} entrantes, {b} platos principales y {c} postres. Una comida consiste en uno de cada. ¿Cuántas comidas diferentes se pueden elegir?"]},
        L, name=name, a=a, b=b, c=c)
    ans = a * b * c
    r = {"eng": "For each of the {a} choices of the first kind there are {b} choices of the second, which gives {a}*{b} = {ab}. Each of those has {c} choices of the third: {ab}*{c} = {ans}.",
         "cat": "Per a cadascuna de les {a} opcions del primer tipus hi ha {b} opcions del segon, cosa que dóna {a}*{b} = {ab}. Cadascuna té {c} opcions del tercer: {ab}*{c} = {ans}.",
         "esp": "Para cada una de las {a} opciones del primer tipo hay {b} opciones del segundo, lo que da {a}*{b} = {ab}. Cada una tiene {c} opciones del tercero: {ab}*{c} = {ans}."}[L]
    rat = r.format(a=a, b=b, c=c, ab=a * b, ans=ans)
    wrong = [a + b + c, a * b, a * b + c, a * c + b, (a + b) * c, ans + a * b]
    return make(rng, "outfits", L, text, ans, wrong, rat, params=dict(a=a, b=b, c=c))


def g_line_up_together(rng, L):
    n = rng.randint(4, 6)
    n1, n2 = rng.sample(NAMES, 2)
    ans = 2 * math.factorial(n - 1)
    text = pick(rng, {
        "eng": ["In how many ways can {n} friends, including {n1} and {n2}, stand in a row if {n1} and {n2} must stand next to each other?"],
        "cat": ["De quantes maneres es poden posar en fila {n} amics, entre ells {n1} i {n2}, si {n1} i {n2} han d'estar un al costat de l'altre?"],
        "esp": ["¿De cuántas maneras se pueden colocar en fila {n} amigos, entre ellos {n1} y {n2}, si {n1} y {n2} deben estar uno al lado del otro?"]},
        L, n=n, n1=n1, n2=n2)
    f = math.factorial(n - 1)
    r = {"eng": "Treat the two friends as one block: there are {u} units, which can be arranged in {f} ways. Inside the block the two can swap places, so {f}*2 = {ans}.",
         "cat": "Considerem els dos amics com un bloc: hi ha {u} unitats, que es poden ordenar de {f} maneres. Dins del bloc poden canviar de lloc, així que {f}*2 = {ans}.",
         "esp": "Consideramos a los dos amigos como un bloque: hay {u} unidades, que se pueden ordenar de {f} maneras. Dentro del bloque pueden cambiar de sitio, así que {f}*2 = {ans}."}[L]
    rat = r.format(u=n - 1, f=f, ans=ans)
    wrong = [math.factorial(n), f, math.factorial(n) // 2, 2 * n, 2 * math.factorial(n - 2), n * (n - 1)]
    return make(rng, "line_up_together", L, text, ans, wrong, rat, params=dict(n=n))


def g_grid_routes(rng, L):
    a, b = rng.randint(2, 5), rng.randint(2, 4)
    ans = math.comb(a + b, a)
    text = pick(rng, {
        "eng": ["A robot walks along the lines of a grid from the bottom-left corner to the top-right corner. The grid is {a} squares wide and {b} squares tall. The robot only moves right or up, one side of a square at a time. How many different routes can it take?"],
        "cat": ["Un robot camina per les línies d'una quadrícula des de la cantonada inferior esquerra fins a la superior dreta. La quadrícula té {a} quadrats d'ample i {b} d'alt. El robot només es mou cap a la dreta o cap amunt, un costat de quadrat cada vegada. Quants camins diferents pot fer?"],
        "esp": ["Un robot camina por las líneas de una cuadrícula desde la esquina inferior izquierda hasta la superior derecha. La cuadrícula tiene {a} cuadrados de ancho y {b} de alto. El robot solo se mueve hacia la derecha o hacia arriba, un lado de cuadrado cada vez. ¿Cuántos caminos diferentes puede hacer?"]},
        L, a=a, b=b)
    r = {"eng": "Every route has {a} moves right and {b} moves up, {t} moves in all. We choose which {a} of the {t} moves go right, and that can be done in {ans} ways.",
         "cat": "Cada camí té {a} moviments a la dreta i {b} cap amunt, {t} en total. Triem quins {a} dels {t} moviments van a la dreta, i es pot fer de {ans} maneres.",
         "esp": "Cada camino tiene {a} movimientos a la derecha y {b} hacia arriba, {t} en total. Elegimos cuáles {a} de los {t} movimientos van a la derecha, y se puede hacer de {ans} maneras."}[L]
    rat = r.format(a=a, b=b, t=a + b, ans=ans)
    wrong = [a * b, a + b, 2 * (a + b), math.comb(a + b, a) - 1, math.comb(a + b + 1, a) // 2, (a + 1) * (b + 1)]
    return make(rng, "grid_routes", L, text, ans, wrong, rat, params=dict(a=a, b=b))


def g_multiples_in_range(rng, L):
    k = rng.randint(3, 9)
    lo = rng.randint(2, 40)
    hi = lo + rng.randint(30, 150)
    ans = hi // k - (lo - 1) // k
    if ans < 3:
        raise Retry()
    text = pick(rng, {
        "eng": ["How many multiples of {k} are there from {lo} to {hi}, with {lo} and {hi} included?",
                "How many numbers between {lo} and {hi} (the ends included) can be divided exactly by {k}?"],
        "cat": ["Quants múltiples de {k} hi ha des de {lo} fins a {hi}, amb {lo} i {hi} inclosos?",
                "Quants nombres entre {lo} i {hi} (extrems inclosos) es poden dividir exactament per {k}?"],
        "esp": ["¿Cuántos múltiplos de {k} hay desde {lo} hasta {hi}, con {lo} y {hi} incluidos?",
                "¿Cuántos números entre {lo} y {hi} (extremos incluidos) se pueden dividir exactamente entre {k}?"]},
        L, k=k, lo=lo, hi=hi)
    r = {"eng": "Up to {hi} there are {x} multiples of {k} (whole part of {hi}/{k}). Below {lo} there are {y}. So {x} - {y} = {ans}.",
         "cat": "Fins a {hi} hi ha {x} múltiples de {k} (part entera de {hi}/{k}). Abans de {lo} n'hi ha {y}. Per tant, {x} - {y} = {ans}.",
         "esp": "Hasta {hi} hay {x} múltiplos de {k} (parte entera de {hi}/{k}). Antes de {lo} hay {y}. Por tanto, {x} - {y} = {ans}."}[L]
    rat = r.format(hi=hi, lo=lo, k=k, x=hi // k, y=(lo - 1) // k, ans=ans)
    wrong = [ans + 1, ans - 1, hi // k, (hi - lo) // k, (hi - lo) // k + 2, hi // k - lo // k]
    return make(rng, "multiples_in_range", L, text, ans, wrong, rat, params=dict(k=k, lo=lo, hi=hi))


def g_remainder(rng, L):
    k = rng.randint(4, 9)
    q = rng.randint(6, 40)
    r_ = rng.randint(1, k - 1)
    N = k * q + r_
    it = rng.choice(ITEMS)[LI[L]]
    text = pick(rng, {
        "eng": ["There are {N} {it}. They are packed in boxes of {k}, filling as many boxes as possible. How many {it} are left over?",
                "What is the remainder when {N} is divided by {k}?"],
        "cat": ["Hi ha {N} {it}. Es posen en caixes de {k}, omplint-ne totes les que es pugui. Quants {it} sobren?",
                "Quin és el residu de dividir {N} entre {k}?"],
        "esp": ["Hay {N} {it}. Se meten en cajas de {k}, llenando todas las que se pueda. ¿Cuántos {it} sobran?",
                "¿Cuál es el resto de dividir {N} entre {k}?"]},
        L, N=N, k=k, it=it)
    r = {"eng": "The largest multiple of {k} not above {N} is {k}*{q} = {m}. What is left over is {N} - {m} = {r}.",
         "cat": "El múltiple de {k} més gran que no passa de {N} és {k}*{q} = {m}. El que sobra és {N} - {m} = {r}.",
         "esp": "El mayor múltiplo de {k} que no pasa de {N} es {k}*{q} = {m}. Lo que sobra es {N} - {m} = {r}."}[L]
    rat = r.format(k=k, N=N, q=q, m=k * q, r=r_)
    wrong = [q, k - r_, r_ + 1, r_ - 1, k - 1, k]
    return make(rng, "remainder", L, text, r_, wrong, rat, params=dict(N=N, k=k))


def g_digit_sum_count(rng, L):
    S = rng.randint(3, 16)
    good = [t for t in range(1, 10) if 0 <= S - t <= 9]
    ans = len(good)
    text = pick(rng, {
        "eng": ["How many two-digit numbers have digits that add up to {S}?"],
        "cat": ["Quants nombres de dues xifres tenen les xifres que sumen {S}?"],
        "esp": ["¿Cuántos números de dos cifras tienen las cifras que suman {S}?"]}, L, S=S)
    r = {"eng": "The tens digit can be any digit from 1 to 9 whose partner digit {S} - tens is between 0 and 9. The possible tens digits are {lst}. So there are {ans} numbers.",
         "cat": "La xifra de les desenes pot ser qualsevol de 1 a 9 tal que l'altra xifra, {S} menys les desenes, sigui entre 0 i 9. Les desenes possibles són {lst}. Per tant, hi ha {ans} nombres.",
         "esp": "La cifra de las decenas puede ser cualquiera de 1 a 9 tal que la otra cifra, {S} menos las decenas, esté entre 0 y 9. Las decenas posibles son {lst}. Por tanto, hay {ans} números."}[L]
    rat = r.format(S=S, lst=", ".join(map(str, good)), ans=ans)
    wrong = [S, S - 1, S + 1, 9, 10, ans + 1, ans - 1]
    return make(rng, "digit_sum_count", L, text, ans, wrong, rat, params=dict(S=S))


def g_arithmetic_sequence(rng, L):
    a, d, n = rng.randint(2, 20), rng.randint(2, 9), rng.randint(8, 30)
    ans = a + (n - 1) * d
    seq = ", ".join(str(a + i * d) for i in range(4))
    text = pick(rng, {
        "eng": ["The numbers {seq}, ... continue by always adding {d}. What number is in position {n}?"],
        "cat": ["Els nombres {seq}, ... continuen sumant sempre {d}. Quin nombre ocupa la posició {n}?"],
        "esp": ["Los números {seq}, ... continúan sumando siempre {d}. ¿Qué número ocupa la posición {n}?"]},
        L, seq=seq, d=d, n=n)
    r = {"eng": "Each step adds {d}. To reach position {n} we take {m} steps from the first number. So the number is {a} + {m}*{d} = {ans}.",
         "cat": "Cada pas suma {d}. Per arribar a la posició {n} fem {m} passos des del primer nombre. Per tant, el nombre és {a} + {m}*{d} = {ans}.",
         "esp": "Cada paso suma {d}. Para llegar a la posición {n} damos {m} pasos desde el primer número. Por tanto, el número es {a} + {m}*{d} = {ans}."}[L]
    rat = r.format(d=d, n=n, m=n - 1, a=a, ans=ans)
    wrong = [a + n * d, a + (n - 2) * d, n * d, a + (n - 1), a * n, a + (n + 1) * d]
    return make(rng, "arithmetic_sequence", L, text, ans, wrong, rat, params=dict(a=a, d=d, n=n))


def g_color_pattern(rng, L):
    cols = rng.sample(COLORS, 5)
    plen = rng.randint(3, 4)
    pat = cols[:plen]
    n = rng.randint(12, 60)
    if n % plen == 0 or n <= plen * 2:
        n += 1
    pos = (n - 1) % plen
    name = rng.choice(NAMES)
    pc = [c[LI[L]] for c in pat]
    text = pick(rng, {
        "eng": ["{name} threads beads in a repeating pattern: {lst}, {lst}, and so on. What colour is bead number {n}?"],
        "cat": ["{name} enfila comptes seguint un patró que es repeteix: {lst}, {lst}, i així successivament. De quin color és el compte número {n}?"],
        "esp": ["{name} ensarta cuentas siguiendo un patrón que se repite: {lst}, {lst}, y así sucesivamente. ¿De qué color es la cuenta número {n}?"]},
        L, name=name, lst=", ".join(pc), n=n)
    ans = pc[pos]
    r = {"eng": "The pattern repeats every {plen} beads. {n} divided by {plen} leaves remainder {rem}, so bead {n} has the same colour as bead {p}, which is {ans}.",
         "cat": "El patró es repeteix cada {plen} comptes. {n} dividit entre {plen} dóna residu {rem}, així que el compte {n} té el mateix color que el compte {p}, que és {ans}.",
         "esp": "El patrón se repite cada {plen} cuentas. {n} dividido entre {plen} da resto {rem}, así que la cuenta {n} tiene el mismo color que la cuenta {p}, que es {ans}."}[L]
    rat = r.format(plen=plen, n=n, rem=n % plen, p=pos + 1, ans=ans)
    wrong = [c[LI[L]] for c in cols if c[LI[L]] != ans]
    return make(rng, "color_pattern", L, text, ans, wrong, rat, numeric=False, params=dict(plen=plen, n=n, pos=pos))


def _hm(m):
    m %= 24 * 60
    return f"{m // 60}:{m % 60:02d}"


def g_film_end_time(rng, L):
    h, mi = rng.randint(8, 16), rng.randrange(0, 60, 5)
    dur = rng.randint(65, 200)
    if dur % 60 == 0:
        dur += 5
    start = h * 60 + mi
    end = start + dur
    dh, dm = divmod(dur, 60)
    text = pick(rng, {
        "eng": ["A film starts at {t} and lasts {dur} minutes. At what time does it end?"],
        "cat": ["Una pel·lícula comença a les {t} i dura {dur} minuts. A quina hora acaba?"],
        "esp": ["Una película empieza a las {t} y dura {dur} minutos. ¿A qué hora termina?"]},
        L, t=_hm(start), dur=dur)
    r = {"eng": "{dur} minutes is {dh} h {dm} min. Starting at {t}, after {dh} h it is {t1}. Adding {dm} more minutes gives {end}.",
         "cat": "{dur} minuts són {dh} h {dm} min. Començant a les {t}, passades {dh} h són les {t1}. Afegint-hi {dm} minuts més, són les {end}.",
         "esp": "{dur} minutos son {dh} h {dm} min. Empezando a las {t}, pasadas {dh} h son las {t1}. Añadiendo {dm} minutos más, son las {end}."}[L]
    rat = r.format(dur=dur, dh=dh, dm=dm, t=_hm(start), t1=_hm(start + dh * 60), end=_hm(end))
    wrong = [_hm(end + d) for d in (60, -60, 10, -10, 20, -20, 30, -30)]
    return make(rng, "film_end_time", L, text, _hm(end), wrong, rat, numeric=False, params=dict(start=start, dur=dur))


def g_weekday_shift(rng, L):
    today = rng.randrange(7)
    N = rng.randint(10, 100)
    r_ = N % 7
    if r_ == 0:
        raise Retry()
    ans_i = (today + r_) % 7
    days = DAYS[L]
    text = pick(rng, {
        "eng": ["Today is {d}. What day of the week will it be in {N} days?"],
        "cat": ["Avui és {d}. Quin dia de la setmana serà d'aquí a {N} dies?"],
        "esp": ["Hoy es {d}. ¿Qué día de la semana será dentro de {N} días?"]}, L, d=days[today], N=N)
    r = {"eng": "There are 7 days in a week. {N} = {q}*7 + {r}, so only the {r} extra days matter. {r} days after {d} is {ans}.",
         "cat": "Una setmana té 7 dies. {N} = {q}*7 + {r}, així que només importen els {r} dies de més. {r} dies després de {d} és {ans}.",
         "esp": "Una semana tiene 7 días. {N} = {q}*7 + {r}, así que solo importan los {r} días de más. {r} días después de {d} es {ans}."}[L]
    rat = r.format(N=N, q=N // 7, r=r_, d=days[today], ans=days[ans_i])
    wrong = [days[(ans_i + o) % 7] for o in (1, -1, 2, -2)]
    return make(rng, "weekday_shift", L, text, days[ans_i], wrong, rat, numeric=False, params=dict(today=today, N=N))


def g_average_missing(rng, L):
    m = rng.randint(8, 20)
    s = [max(1, m + rng.randint(-7, 7)) for _ in range(4)]
    fifth = 5 * m - sum(s)
    if not 1 <= fifth <= 40:
        raise Retry()
    name = rng.choice(NAMES)
    text = pick(rng, {
        "eng": ["{name} scored {a}, {b}, {c} and {d} points in four games. After the fifth game, the average of the five games is {m}. How many points did {name} score in the fifth game?"],
        "cat": ["{name} ha fet {a}, {b}, {c} i {d} punts en quatre partides. Després de la cinquena, la mitjana de les cinc partides és {m}. Quants punts ha fet {name} a la cinquena partida?"],
        "esp": ["{name} ha hecho {a}, {b}, {c} y {d} puntos en cuatro partidas. Tras la quinta, la media de las cinco partidas es {m}. ¿Cuántos puntos ha hecho {name} en la quinta partida?"]},
        L, name=name, a=s[0], b=s[1], c=s[2], d=s[3], m=m)
    r = {"eng": "Five games with average {m} add up to 5*{m} = {T}. The first four add up to {S}. So the fifth game gave {T} - {S} = {fifth}.",
         "cat": "Cinc partides amb mitjana {m} sumen 5*{m} = {T}. Les quatre primeres sumen {S}. Per tant, la cinquena ha donat {T} - {S} = {fifth}.",
         "esp": "Cinco partidas con media {m} suman 5*{m} = {T}. Las cuatro primeras suman {S}. Por tanto, la quinta dio {T} - {S} = {fifth}."}[L]
    rat = r.format(m=m, T=5 * m, S=sum(s), fifth=fifth)
    wrong = [m, 4 * m - sum(s), sum(s) // 4, fifth + 5, fifth - 4, sum(s) - 4 * m]
    return make(rng, "average_missing", L, text, fifth, wrong, rat, params=dict(m=m, s=s))


def g_ribbon_pieces(rng, L):
    z = rng.choice([10, 20, 25, 30, 40, 50])
    count = rng.randint(6, 30)
    total = z * count
    if total < 120:
        raise Retry()
    m, cm = divmod(total, 100)
    name = rng.choice(NAMES)
    length = {"eng": f"{m} m {cm} cm" if cm else f"{m} m", "cat": f"{m} m {cm} cm" if cm else f"{m} m",
              "esp": f"{m} m {cm} cm" if cm else f"{m} m"}[L]
    text = pick(rng, {
        "eng": ["{name} has a ribbon {length} long and cuts it into pieces of {z} cm each. How many pieces does {name} get?"],
        "cat": ["{name} té una cinta de {length} de llarg i la talla en trossos de {z} cm cadascun. Quants trossos obté {name}?"],
        "esp": ["{name} tiene una cinta de {length} de largo y la corta en trozos de {z} cm cada uno. ¿Cuántos trozos obtiene {name}?"]},
        L, name=name, length=length, z=z)
    r = {"eng": "{length} is {total} cm, because 1 m is 100 cm. The number of pieces is {total}/{z} = {count}.",
         "cat": "{length} són {total} cm, perquè 1 m són 100 cm. El nombre de trossos és {total}/{z} = {count}.",
         "esp": "{length} son {total} cm, porque 1 m son 100 cm. El número de trozos es {total}/{z} = {count}."}[L]
    rat = r.format(length=length, total=total, z=z, count=count)
    wrong = [(10 * m + cm) // z, (100 * m) // z, count + 1, count - 1, total // (z * 10) if total % (z * 10) == 0 else None, (m + cm) // z]
    return make(rng, "ribbon_pieces", L, text, count, wrong, rat, params=dict(total=total, z=z))


def g_number_think(rng, L):
    x, k, m = rng.randint(2, 20), rng.randint(2, 9), rng.randint(1, 20)
    add = rng.random() < 0.5
    R = k * x + m if add else k * x - m
    if R <= 0:
        raise Retry()
    name = rng.choice(NAMES)
    opw = {"eng": "adds" if add else "subtracts", "cat": "suma" if add else "resta", "esp": "suma" if add else "resta"}[L]
    text = pick(rng, {
        "eng": ["{name} thinks of a number, multiplies it by {k} and then {opw} {m}. The result is {R}. What number did {name} think of?"],
        "cat": ["{name} pensa un nombre, el multiplica per {k} i després {opw} {m}. El resultat és {R}. Quin nombre ha pensat {name}?"],
        "esp": ["{name} piensa un número, lo multiplica por {k} y después {opw} {m}. El resultado es {R}. ¿Qué número ha pensado {name}?"]},
        L, name=name, k=k, opw=opw, m=m, R=R)
    t = R - m if add else R + m
    sign = "-" if add else "+"
    r = {"eng": "Undo the steps backwards. {R} {sign} {m} = {t}. Then {t}/{k} = {x}.",
         "cat": "Desfem els passos del final cap al principi. {R} {sign} {m} = {t}. Després {t}/{k} = {x}.",
         "esp": "Deshacemos los pasos de atrás hacia delante. {R} {sign} {m} = {t}. Después {t}/{k} = {x}."}[L]
    rat = r.format(R=R, sign=sign, m=m, t=t, k=k, x=x)
    other = R + m if add else R - m
    wrong = [other // k if other % k == 0 else None, R // k if R % k == 0 else None, R - m if not add else R + m, t // k + 1, t // k - 1, k * x]
    return make(rng, "number_think", L, text, x, wrong, rat, params=dict(x=x, k=k, m=m, add=add))


def g_race_logic(rng, L):
    names = rng.sample(NAMES, 5)
    a, b, c, d, e = names
    pos = rng.choice([2, 3, 4])
    ans = names[pos - 1]
    clues = {
        "eng": [f"{e} finished last.", f"{b} finished just before {c}.", f"{d} finished just after {c}.", f"{a} finished before {b}."],
        "cat": [f"{e} va arribar en últim lloc.", f"{b} va arribar just abans que {c}.", f"{d} va arribar just després de {c}.", f"{a} va arribar abans que {b}."],
        "esp": [f"{e} llegó en último lugar.", f"{b} llegó justo antes que {c}.", f"{d} llegó justo después de {c}.", f"{a} llegó antes que {b}."]}[L]
    clues = clues[:]
    rng.shuffle(clues)
    shown = names[:]
    rng.shuffle(shown)
    ordn = {"eng": {2: "second", 3: "third", 4: "fourth"}, "cat": {2: "segona", 3: "tercera", 4: "quarta"},
            "esp": {2: "segunda", 3: "tercera", 4: "cuarta"}}[L][pos]
    text = pick(rng, {
        "eng": ["{ns} ran a race with no ties. {cl} Who finished in {o} place?"],
        "cat": ["{ns} van córrer una cursa sense empats. {cl} Qui va arribar en {o} posició?"],
        "esp": ["{ns} corrieron una carrera sin empates. {cl} ¿Quién llegó en {o} posición?"]},
        L, ns=", ".join(shown), cl=" ".join(clues), o=ordn)
    r = {"eng": "From the clues, the finishing order is {order}. So the runner in {o} place is {ans}.",
         "cat": "Segons les pistes, l'ordre d'arribada és {order}. Per tant, el corredor en {o} posició és {ans}.",
         "esp": "Con las pistas, el orden de llegada es {order}. Por tanto, el corredor en {o} posición es {ans}."}[L]
    rat = r.format(order=", ".join(names), o=ordn, ans=ans)
    wrong = [n for n in names if n != ans]
    return make(rng, "race_logic", L, text, ans, wrong, rat, numeric=False, params=dict(names=names, pos=pos))


def g_ratio_mix(rng, L):
    a, b = rng.choice([(1, 2), (1, 3), (2, 3), (3, 2), (2, 5), (3, 4), (1, 4), (3, 5)])
    m = rng.randint(2, 9)
    x = a * m
    ans = (a + b) * m
    text = pick(rng, {
        "eng": ["A fruit punch is made with orange juice and water in the ratio {a}:{b}. {x} litres of orange juice were used. How many litres of punch were made?",
                "In a class, the ratio of boys to girls is {a}:{b}. There are {x} boys. How many students are in the class?"],
        "cat": ["Un refresc es prepara amb suc de taronja i aigua en la proporció {a}:{b}. S'han fet servir {x} litres de suc. Quants litres de refresc s'han preparat?",
                "En una classe, la proporció de nois i noies és {a}:{b}. Hi ha {x} nois. Quants alumnes hi ha a la classe?"],
        "esp": ["Un refresco se prepara con zumo de naranja y agua en la proporción {a}:{b}. Se han usado {x} litros de zumo. ¿Cuántos litros de refresco se han preparado?",
                "En una clase, la proporción de chicos y chicas es {a}:{b}. Hay {x} chicos. ¿Cuántos alumnos hay en la clase?"]},
        L, a=a, b=b, x=x)
    r = {"eng": "The first quantity is {a} parts, so one part is {x}/{a} = {m}. In all there are {a}+{b} = {s} parts, so {s}*{m} = {ans}.",
         "cat": "La primera quantitat són {a} parts, així que una part és {x}/{a} = {m}. En total hi ha {a}+{b} = {s} parts, per tant {s}*{m} = {ans}.",
         "esp": "La primera cantidad son {a} partes, así que una parte es {x}/{a} = {m}. En total hay {a}+{b} = {s} partes, por tanto {s}*{m} = {ans}."}[L]
    rat = r.format(a=a, b=b, x=x, m=m, s=a + b, ans=ans)
    wrong = [b * m, x + b, x * b, x * (a + b), a * b * m, x + m]
    return make(rng, "ratio_mix", L, text, ans, wrong, rat, params=dict(a=a, b=b, m=m))


VEHICLES = [("A bus", "Un autobús", "Un autobús"), ("A train", "Un tren", "Un tren"), ("A car", "Un cotxe", "Un coche")]


def g_speed_minutes(rng, L):
    v = rng.choice([12, 18, 24, 30, 36, 48, 60, 72, 90])
    mins = rng.randrange(10, 100, 10)
    d = v * mins // 60
    veh = rng.choice(VEHICLES)[LI[L]]
    text = pick(rng, {
        "eng": ["{veh} travels at a constant speed of {v} km/h. How many kilometres does it cover in {mins} minutes?"],
        "cat": ["{veh} va a una velocitat constant de {v} km/h. Quants quilòmetres recorre en {mins} minuts?"],
        "esp": ["{veh} va a una velocidad constante de {v} km/h. ¿Cuántos kilómetros recorre en {mins} minutos?"]},
        L, veh=veh, v=v, mins=mins)
    r = {"eng": "{mins} minutes is {mins}/60 of an hour. The distance is {v}*{mins}/60 = {v_m}/60 = {d} km.",
         "cat": "{mins} minuts són {mins}/60 d'hora. La distància és {v}*{mins}/60 = {v_m}/60 = {d} km.",
         "esp": "{mins} minutos son {mins}/60 de hora. La distancia es {v}*{mins}/60 = {v_m}/60 = {d} km."}[L]
    rat = r.format(mins=mins, v=v, v_m=v * mins, d=d)
    wrong = [v * mins, v * mins // 100 if v * mins % 100 == 0 else None, v * mins // 10 if v * mins % 10 == 0 else None, v + mins, d * 2, d // 2 if d % 2 == 0 else None]
    return make(rng, "speed_minutes", L, text, d, wrong, rat, params=dict(v=v, mins=mins))


def g_coin_count(rng, L):
    n = rng.randint(6, 20)
    b = rng.randint(1, n - 1)
    S = n + b
    name = rng.choice(NAMES)
    text = pick(rng, {
        "eng": ["{name} has {n} coins, each worth 1 euro or 2 euros, with a total value of {S} euros. How many 2-euro coins does {name} have?"],
        "cat": ["{name} té {n} monedes, cadascuna d'1 euro o de 2 euros, que sumen {S} euros en total. Quantes monedes de 2 euros té {name}?"],
        "esp": ["{name} tiene {n} monedas, cada una de 1 euro o de 2 euros, que suman {S} euros en total. ¿Cuántas monedas de 2 euros tiene {name}?"]},
        L, name=name, n=n, S=S)
    r = {"eng": "If all {n} coins were worth 1 euro, the total would be {n}. The real total is {S}, which is {b} more. Each 2-euro coin adds 1 extra, so there are {b} of them.",
         "cat": "Si les {n} monedes fossin d'1 euro, el total seria {n}. El total real és {S}, que són {b} més. Cada moneda de 2 euros hi afegeix 1 de més, així que n'hi ha {b}.",
         "esp": "Si las {n} monedas fueran de 1 euro, el total sería {n}. El total real es {S}, que son {b} más. Cada moneda de 2 euros añade 1 de más, así que hay {b}."}[L]
    rat = r.format(n=n, S=S, b=b)
    wrong = [n - b, S // 2, n // 2, S - n + 1, S - n - 1, S - 2 * n if S > 2 * n else None]
    return make(rng, "coin_count", L, text, b, wrong, rat, params=dict(n=n, S=S))


# --------------------------------------------------------------------------- harder levels
# Generators for grades 9-12. Shared helpers first.

AND = {"eng": "and", "cat": "i", "esp": "y"}
NDIG = {3: ("three", "tres", "tres"), 4: ("four", "quatre", "cuatro")}
# plural item, then "one of them" with its article (eng, cat, esp)
ITEMS_SG = [("pencils", "llapis", "lápices", "a pencil", "un llapis", "un lápiz"),
            ("notebooks", "quaderns", "cuadernos", "a notebook", "un quadern", "un cuaderno"),
            ("erasers", "gomes", "gomas", "an eraser", "una goma", "una goma"),
            ("rulers", "regles", "reglas", "a ruler", "un regle", "una regla"),
            ("pens", "bolígrafs", "bolígrafos", "a pen", "un bolígraf", "un bolígrafo"),
            ("markers", "retoladors", "rotuladores", "a marker", "un retolador", "un rotulador"),
            ("folders", "carpetes", "carpetas", "a folder", "una carpeta", "una carpeta"),
            ("sharpeners", "maquinetes", "sacapuntas", "a sharpener", "una maquineta", "un sacapuntas")]
# ball colours: eng, cat plural, esp plural, cat singular, esp singular (feminine: boles / bolas)
BALLS = [("red", "vermelles", "rojas", "vermella", "roja"), ("blue", "blaves", "azules", "blava", "azul"),
         ("green", "verdes", "verdes", "verda", "verde"), ("white", "blanques", "blancas", "blanca", "blanca"),
         ("black", "negres", "negras", "negra", "negra"), ("yellow", "grogues", "amarillas", "groga", "amarilla")]


def frac(n, d):
    """n/d in lowest terms, the one way every fraction option is written."""
    g = math.gcd(n, d)
    n, d = n // g, d // g
    return str(n) if d == 1 else f"{n}/{d}"


def _fracs(pairs, ans):
    """Distinct proper fractions (as text) from (n, d) pairs, none equal to the answer."""
    out = []
    for n, d in pairs:
        if d > 0 and 0 < n < d:
            s = frac(n, d)
            if s != ans and s not in out:
                out.append(s)
    return out


def _div(a, b):
    return a // b if b and a % b == 0 else None


def _de(n):
    """Catalan "de" before a number: d'1, d'11, de 7."""
    return f"d'{n}" if n in (1, 11) else f"de {n}"


def _de_name(name):
    """Catalan "de" before a person's name: d'Anna, d'Hugo, de Marc."""
    return f"d'{name}" if name[0] in "AEIOUH" else f"de {name}"


def _join(xs, L):
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + f" {AND[L]} " + xs[-1]


def _mk(rng, name, L, text, answer, wrong, rat, numeric=True, params=None):
    """make(), but a rationale that came out too long is a redraw, not a crash."""
    if len(rat) > MAX_RATIONALE:
        raise Retry()
    return make(rng, name, L, text, answer, wrong, rat, numeric=numeric, params=params)


def _factorize(n):
    out, p = [], 2
    while p * p <= n:
        e = 0
        while n % p == 0:
            n //= p
            e += 1
        if e:
            out.append((p, e))
        p += 1
    if n > 1:
        out.append((n, 1))
    return out


def _prod(xs):
    r = 1
    for x in xs:
        r *= x
    return r


def _comb_expr(n, k):
    """How the number of ways to choose k of n is computed, e.g. "8*7/(2*1) = 28"."""
    if k == 1:
        return str(n)
    top = "*".join(str(n - i) for i in range(k))
    bottom = "*".join(str(k - i) for i in range(k))
    return f"{top}/({bottom}) = {math.comb(n, k)}"


# ----- number theory

def g_divisor_count(rng, L):
    N = rng.randint(24, 2000)
    f = _factorize(N)
    tau = _prod(e + 1 for _, e in f)
    if len(f) < 2 or tau < 6 or f[-1][0] > 13:
        raise Retry()
    text = pick(rng, {
        "eng": ["How many positive divisors does the number {N} have?",
                "How many positive integers divide {N} exactly (1 and {N} itself also count)?"],
        "cat": ["Quants divisors positius té el nombre {N}?",
                "Quants nombres enters positius divideixen exactament {N} (l'1 i el mateix {N} també compten)?"],
        "esp": ["¿Cuántos divisores positivos tiene el número {N}?",
                "¿Cuántos enteros positivos dividen exactamente a {N} (el 1 y el propio {N} también cuentan)?"]}, L, N=N)
    fact = " * ".join(f"{p}^{e}" if e > 1 else str(p) for p, e in f)
    prod = "*".join(f"({e}+1)" for _, e in f)
    r = {"eng": "{N} = {fact}. Each divisor takes every prime with an exponent from 0 up to the one shown, so we multiply the exponents plus 1: {prod} = {tau}.",
         "cat": "{N} = {fact}. Cada divisor agafa cada primer amb un exponent des de 0 fins al que hi apareix, així que multipliquem els exponents més 1: {prod} = {tau}.",
         "esp": "{N} = {fact}. Cada divisor toma cada primo con un exponente desde 0 hasta el que aparece, así que multiplicamos los exponentes más 1: {prod} = {tau}."}[L]
    rat = r.format(N=N, fact=fact, prod=prod, tau=tau)
    se = sum(e for _, e in f)
    wrong = [_prod(e for _, e in f), se, tau - 2, len(f), se + 1, tau - 1, 2 * tau]
    return _mk(rng, "divisor_count", L, text, tau, wrong, rat, params=dict(N=N))


def g_last_digit_power(rng, L):
    a = rng.randint(2, 99)
    if a % 10 not in (2, 3, 4, 7, 8, 9):
        raise Retry()
    n = rng.randint(11, 2030)
    cyc, d = [], a % 10
    while d not in cyc:
        cyc.append(d)
        d = d * a % 10
    c = len(cyc)
    rem = n % c
    pos = rem or c
    ans = cyc[pos - 1]
    text = pick(rng, {
        "eng": ["What is the last digit of {a}^{n}?", "What is the units digit of the number {a}^{n}?"],
        "cat": ["Quina és l'última xifra de {a}^{n}?", "Quina és la xifra de les unitats del nombre {a}^{n}?"],
        "esp": ["¿Cuál es la última cifra de {a}^{n}?", "¿Cuál es la cifra de las unidades del número {a}^{n}?"]},
        L, a=a, n=n)
    if rem:
        mid = {"eng": "Dividing {n} by {c} leaves remainder {rem}, so we look at position {pos} of the cycle.",
               "cat": "En dividir {n} entre {c} el residu és {rem}, així que mirem la posició {pos} del cicle.",
               "esp": "Al dividir {n} entre {c} el resto es {rem}, así que miramos la posición {pos} del ciclo."}[L]
    else:
        mid = {"eng": "{n} is a multiple of {c}, so we look at the last position of the cycle.",
               "cat": "{n} és múltiple de {c}, així que mirem l'última posició del cicle.",
               "esp": "{n} es múltiplo de {c}, así que miramos la última posición del ciclo."}[L]
    r = {"eng": "The last digits of the powers of {a} repeat in a cycle of length {c}: {cyc}. " + mid + " The last digit is {ans}.",
         "cat": "Les últimes xifres de les potències de {a} es repeteixen en un cicle de longitud {c}: {cyc}. " + mid + " L'última xifra és {ans}.",
         "esp": "Las últimas cifras de las potencias de {a} se repiten en un ciclo de longitud {c}: {cyc}. " + mid + " La última cifra es {ans}."}[L]
    rat = r.format(a=a, n=n, c=c, cyc=", ".join(map(str, cyc)), rem=rem, pos=pos, ans=ans)
    wrong = [x for x in cyc if x != ans] + [cyc[rem % c], n % 10, 1, 6, 5, 0, 3, 7, 9]
    return _mk(rng, "last_digit_power", L, text, ans, wrong, rat, params=dict(a=a, n=n))


def g_gcd_lcm(rng, L):
    kind = rng.choice(["squares", "bells"])
    x, y = rng.sample(range(2, 10 if kind == "squares" else 8), 2)
    if math.gcd(x, y) != 1:
        raise Retry()
    g = rng.randint(2, 12 if kind == "squares" else 10)
    a, b = g * x, g * y
    if kind == "squares":
        ans = x * y
        text = pick(rng, {
            "eng": ["A rectangular sheet of paper measuring {a} cm by {b} cm is cut into equal squares that are as large as possible, with no paper left over. How many squares are obtained?"],
            "cat": ["Un full de paper rectangular de {a} cm per {b} cm es talla en quadrats iguals tan grans com sigui possible, sense que sobri paper. Quants quadrats s'obtenen?"],
            "esp": ["Una hoja de papel rectangular de {a} cm por {b} cm se corta en cuadrados iguales lo más grandes posible, sin que sobre papel. ¿Cuántos cuadrados se obtienen?"]},
            L, a=a, b=b)
        r = {"eng": "The side of the squares must divide {a} and {b}, and the largest such number is their greatest common divisor, {g}. Along one side fit {a}/{g} = {x} squares and along the other {b}/{g} = {y}. That makes {x}*{y} = {ans}.",
             "cat": "El costat dels quadrats ha de dividir {a} i {b}, i el nombre més gran que ho fa és el seu màxim comú divisor, {g}. En un costat hi caben {a}/{g} = {x} quadrats i en l'altre {b}/{g} = {y}. En total són {x}*{y} = {ans}.",
             "esp": "El lado de los cuadrados debe dividir a {a} y a {b}, y el mayor número que lo hace es su máximo común divisor, {g}. En un lado caben {a}/{g} = {x} cuadrados y en el otro {b}/{g} = {y}. En total son {x}*{y} = {ans}."}[L]
        wrong = [g, a * b, x + y, g * x * y, a * b // g, g * g]
    else:
        ans = g * x * y
        text = pick(rng, {
            "eng": ["One bell rings every {a} minutes and another every {b} minutes. They have just rung at the same time. After how many minutes will they next ring at the same time?"],
            "cat": ["Una campana sona cada {a} minuts i una altra cada {b} minuts. Acaben de sonar alhora. D'aquí a quants minuts tornaran a sonar alhora per primera vegada?"],
            "esp": ["Una campana suena cada {a} minutos y otra cada {b} minutos. Acaban de sonar a la vez. ¿Dentro de cuántos minutos volverán a sonar a la vez por primera vez?"]},
            L, a=a, b=b)
        r = {"eng": "They ring together at the common multiples of {a} and {b}. The greatest common divisor of {a} and {b} is {g}, so the least common multiple is {a}*{b}/{g} = {ans}.",
             "cat": "Sonen alhora en els múltiples comuns de {a} i {b}. El màxim comú divisor de {a} i {b} és {g}, així que el mínim comú múltiple és {a}*{b}/{g} = {ans}.",
             "esp": "Suenan a la vez en los múltiplos comunes de {a} y {b}. El máximo común divisor de {a} y {b} es {g}, así que el mínimo común múltiplo es {a}*{b}/{g} = {ans}."}[L]
        wrong = [a * b, g, a + b, x * y, 2 * ans, abs(a - b)]
    rat = r.format(a=a, b=b, g=g, x=x, y=y, ans=ans)
    return _mk(rng, "gcd_lcm", L, text, ans, wrong, rat, params=dict(kind=kind, a=a, b=b))


def g_consecutive_sum(rng, L):
    k, f = rng.randint(3, 8), rng.randint(2, 150)
    big = rng.random() < 0.6
    T = k * (k - 1) // 2
    S = k * f + T
    ans = f + k - 1 if big else f
    q = {"eng": ("What is the largest of them?", "What is the smallest of them?"),
         "cat": ("Quin és el més gran?", "Quin és el més petit?"),
         "esp": ("¿Cuál es el mayor?", "¿Cuál es el menor?")}[L][0 if big else 1]
    text = pick(rng, {
        "eng": ["The sum of {k} consecutive integers is {S}. {q}"],
        "cat": ["La suma de {k} nombres enters consecutius és {S}. {q}"],
        "esp": ["La suma de {k} números enteros consecutivos es {S}. {q}"]}, L, k=k, S=S, q=q)
    tail = {"eng": ", and the largest is {f} + {k1} = {ans}", "cat": ", i el més gran és {f} + {k1} = {ans}",
            "esp": ", y el mayor es {f} + {k1} = {ans}"}[L] if big else ""
    r = {"eng": "Call the smallest number n. The others are n+1 up to n+{k1}, so the sum is {k}n + {T} = {S}. Then n = ({S} - {T})/{k} = {f}" + tail + ".",
         "cat": "Anomenem n el nombre més petit. Els altres són n+1 fins a n+{k1}, així que la suma és {k}n + {T} = {S}. Llavors n = ({S} - {T})/{k} = {f}" + tail + ".",
         "esp": "Llamamos n al número menor. Los demás son n+1 hasta n+{k1}, así que la suma es {k}n + {T} = {S}. Entonces n = ({S} - {T})/{k} = {f}" + tail + "."}[L]
    rat = r.format(k=k, k1=k - 1, T=T, S=S, f=f, ans=ans)
    wrong = [S // k, f if big else f + k - 1, f + k, f + (k - 1) // 2, S // k + k, S // k - k]
    return _mk(rng, "consecutive_sum", L, text, ans, wrong, rat, params=dict(k=k, S=S, largest=big))


def g_digit_extreme(rng, L):
    nd = rng.choice([3, 4])
    S = rng.randint(6, 24 if nd == 3 else 30)
    par = rng.randrange(2)
    big = rng.random() < 0.5
    lo, hi = 10 ** (nd - 1), 10 ** nd

    def ok(x, need_distinct=True, need_par=True):
        s = str(x)
        return (sum(map(int, s)) == S and (not need_distinct or len(set(s)) == nd)
                and (not need_par or x % 2 == par))

    best = max if big else min
    cands = sorted((x for x in range(lo, hi) if ok(x)), reverse=big)
    if len(cands) < 3:
        raise Retry()
    ans = cands[0]
    i = LI[L]
    w = dict(nd=NDIG[nd][i], S=S,
             par=[("even", "odd"), ("parell", "senar"), ("par", "impar")][i][par],
             big=[("largest", "smallest"), ("gran", "petit"), ("mayor", "menor")][i][0 if big else 1])
    text = pick(rng, {
        "eng": ["What is the {big} {nd}-digit {par} number whose digits are all different and add up to {S}?"],
        "cat": ["Quin és el nombre {par} de {nd} xifres més {big} que té totes les xifres diferents i la suma de les xifres igual a {S}?"],
        "esp": ["¿Cuál es el {big} número {par} de {nd} cifras que tiene todas las cifras diferentes y cuya suma de cifras es {S}?"]},
        L, **w)
    how = [("each as large as possible", "each as small as possible (the first one cannot be 0)"),
           ("cadascuna tan gran com es pugui", "cadascuna tan petita com es pugui (la primera no pot ser 0)"),
           ("cada una lo más grande posible", "cada una lo más pequeña posible (la primera no puede ser 0)")][i][0 if big else 1]
    par2 = [("even", "odd"), ("parella", "senar"), ("par", "impar")][i][par]
    r = {"eng": "Choose the digits from left to right, {how}, while the remaining places can still reach the sum {S} with different digits and an {par2} last digit. This gives the digits {digs}. The number is {ans}.",
         "cat": "Triem les xifres d'esquerra a dreta, {how}, de manera que les posicions restants encara puguin arribar a la suma {S} amb xifres diferents i una última xifra {par2}. Així surten les xifres {digs}. El nombre és {ans}.",
         "esp": "Elegimos las cifras de izquierda a derecha, {how}, de modo que las posiciones restantes aún puedan llegar a la suma {S} con cifras diferentes y una última cifra {par2}. Así salen las cifras {digs}. El número es {ans}."}[L]
    rat = r.format(how=how, S=S, par2=par2, digs=", ".join(str(ans)), ans=ans)
    no_par = best(x for x in range(lo, hi) if ok(x, need_par=False))
    no_dist = best(x for x in range(lo, hi) if ok(x, need_distinct=False))
    s = str(ans)
    wrong = [no_par, no_dist, cands[1], cands[2], int(s[:-2] + s[-1] + s[-2])]
    return _mk(rng, "digit_extreme", L, text, ans, wrong, rat, params=dict(nd=nd, S=S, parity=par, largest=big))


def g_remainder_ops(rng, L):
    m = rng.randint(5, 13)
    r1, r2 = rng.randint(1, m - 1), rng.randint(1, m - 1)
    kind = rng.choice(["sum", "product", "combo"])
    u, v = (rng.randint(2, 5), rng.randint(2, 5)) if kind == "combo" else (1, 1)
    if kind == "sum":
        expr, calc, val = "a + b", f"{r1} + {r2}", r1 + r2
    elif kind == "product":
        expr, calc, val = "a × b", f"{r1}*{r2}", r1 * r2
    else:
        expr, calc, val = f"{u}a + {v}b", f"{u}*{r1} + {v}*{r2}", u * r1 + v * r2
    if val < m:
        raise Retry()
    ans = val % m
    text = pick(rng, {
        "eng": ["When the integer a is divided by {m} the remainder is {r1}, and when the integer b is divided by {m} the remainder is {r2}. What is the remainder when {expr} is divided by {m}?"],
        "cat": ["En dividir el nombre enter a entre {m} el residu és {r1}, i en dividir el nombre enter b entre {m} el residu és {r2}. Quin és el residu de dividir {expr} entre {m}?"],
        "esp": ["Al dividir el número entero a entre {m} el resto es {r1}, y al dividir el número entero b entre {m} el resto es {r2}. ¿Cuál es el resto de dividir {expr} entre {m}?"]},
        L, m=m, r1=r1, r2=r2, expr=expr)
    r = {"eng": "Remainders can be added and multiplied like the numbers themselves, reducing at the end. {calc} = {val}. Dividing {val} by {m} leaves remainder {ans}.",
         "cat": "Els residus es poden sumar i multiplicar com els mateixos nombres, i al final es redueix. {calc} = {val}. En dividir {val} entre {m} el residu és {ans}.",
         "esp": "Los restos se pueden sumar y multiplicar como los propios números, y al final se reduce. {calc} = {val}. Al dividir {val} entre {m} el resto es {ans}."}[L]
    rat = r.format(calc=calc, val=val, m=m, ans=ans)
    wrong = [(r1 + r2) % m, (r1 * r2) % m, r1, r2, abs(r1 - r2)] + [(ans + d) % m for d in (1, m - 1, 2, m - 2)]
    return _mk(rng, "remainder_ops", L, text, ans, wrong, rat,
               params=dict(m=m, r1=r1, r2=r2, kind=kind, u=u, v=v))


def g_count_div_digit(rng, L):
    nd = rng.choice([3, 4])
    k = rng.choice([3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 19])
    d = rng.randrange(10)
    lo, hi = 10 ** (nd - 1), 10 ** nd
    hits = [x for x in range(lo, hi) if x % k == 0 and x % 10 == d]
    ans = len(hits)
    if ans < 3:
        raise Retry()
    M = k * 10 // math.gcd(k, 10)
    i = LI[L]
    text = pick(rng, {
        "eng": ["How many {nd}-digit numbers are multiples of {k} and end in the digit {d}?",
                "How many multiples of {k} with {nd} digits have {d} as their last digit?"],
        "cat": ["Quants nombres de {nd} xifres són múltiples {dek} i acaben en {d}?",
                "Quants múltiples {dek} de {nd} xifres tenen un {d} com a última xifra?"],
        "esp": ["¿Cuántos números de {nd} cifras son múltiplos de {k} y acaban en {d}?",
                "¿Cuántos múltiplos de {k} de {nd} cifras tienen un {d} como última cifra?"]},
        L, nd=NDIG[nd][i], k=k, dek=_de(k), d=d)
    r = {"eng": "The smallest such number is {first}. Multiples of {k} with the same last digit repeat every {M}, the least common multiple of {k} and 10. The largest is {last}, so there are ({last} - {first})/{M} + 1 = {ans}.",
         "cat": "El més petit d'aquests nombres és {first}. Els múltiples {dek} amb la mateixa última xifra es repeteixen cada {M}, el mínim comú múltiple {dek} i 10. El més gran és {last}, així que n'hi ha ({last} - {first})/{M} + 1 = {ans}.",
         "esp": "El menor de estos números es {first}. Los múltiplos de {k} con la misma última cifra se repiten cada {M}, el mínimo común múltiplo de {k} y 10. El mayor es {last}, así que hay ({last} - {first})/{M} + 1 = {ans}."}[L]
    rat = r.format(first=hits[0], last=hits[-1], k=k, dek=_de(k), M=M, ans=ans)
    mult = (hi - 1) // k - (lo - 1) // k
    wrong = [ans - 1, mult // 10, (hi - lo) // (10 * k), ans + 1, mult, (hi - lo) // M + 1, (hi - lo) // 10 // k + 2]
    return _mk(rng, "count_div_digit", L, text, ans, wrong, rat, params=dict(nd=nd, k=k, d=d))


# ----- algebra

def g_two_equations(rng, L):
    it1, it2 = rng.sample(ITEMS_SG, 2)
    i = LI[L]
    x, y = rng.sample(range(1, 13), 2)
    a = rng.randint(2, 7)
    kind = rng.choice(["each", "first"])
    kw = dict(i1=it1[i], i2=it2[i], s1=it1[3 + i], s2=it2[3 + i], a=a)
    if kind == "each":
        b = rng.choice([v for v in range(2, 8) if v != a])
        P, Q = a * x + b * y, b * x + a * y
        ans = x + y
        text = pick(rng, {
            "eng": ["{a} {i1} and {b} {i2} cost {P} euros. {b} {i1} and {a} {i2} cost {Q} euros. How many euros do {s1} and {s2} cost together?"],
            "cat": ["{a} {i1} i {b} {i2} costen {P} euros. {b} {i1} i {a} {i2} costen {Q} euros. Quants euros costen en total {s1} i {s2}?"],
            "esp": ["{a} {i1} y {b} {i2} cuestan {P} euros. {b} {i1} y {a} {i2} cuestan {Q} euros. ¿Cuántos euros cuestan en total {s1} y {s2}?"]},
            L, b=b, P=P, Q=Q, **kw)
        r = {"eng": "Adding the two purchases gives {t} of each kind for {P} + {Q} = {PQ} euros. So one of each costs {PQ}/{t} = {ans}.",
             "cat": "Sumant les dues compres tenim {t} de cada tipus per {P} + {Q} = {PQ} euros. Per tant, un de cada costa {PQ}/{t} = {ans}.",
             "esp": "Sumando las dos compras tenemos {t} de cada tipo por {P} + {Q} = {PQ} euros. Por tanto, uno de cada cuesta {PQ}/{t} = {ans}."}[L]
        rat = r.format(t=a + b, P=P, Q=Q, PQ=P + Q, ans=ans)
        wrong = [x, y, abs(P - Q), _div(P + Q, 2), _div(P + Q, a * b), abs(x - y)]
        params = dict(kind=kind, eq1=[a, b, P], eq2=[b, a, Q])
    else:
        d = rng.randint(2, 5)
        b = d + rng.randint(2, 4)
        P, Q = a * x + b * y, a * x + d * y
        ans = x
        text = pick(rng, {
            "eng": ["{a} {i1} and {b} {i2} cost {P} euros. {a} {i1} and {d} {i2} cost {Q} euros. How many euros does {s1} cost?"],
            "cat": ["{a} {i1} i {b} {i2} costen {P} euros. {a} {i1} i {d} {i2} costen {Q} euros. Quants euros costa {s1}?"],
            "esp": ["{a} {i1} y {b} {i2} cuestan {P} euros. {a} {i1} y {d} {i2} cuestan {Q} euros. ¿Cuántos euros cuesta {s1}?"]},
            L, b=b, d=d, P=P, Q=Q, **kw)
        r = {"eng": "The purchases differ only in {bd} {i2}, which cost {P} - {Q} = {PQd} euros, so each of these costs {y}. Then {a} {i1} cost {P} - {b}*{y} = {rest} euros. Each of them costs {rest}/{a} = {ans}.",
             "cat": "Les compres només es diferencien en {bd} {i2}, que costen {P} - {Q} = {PQd} euros, així que cada unitat costa {y}. Llavors {a} {i1} costen {P} - {b}*{y} = {rest} euros. Cada unitat costa {rest}/{a} = {ans}.",
             "esp": "Las compras solo se diferencian en {bd} {i2}, que cuestan {P} - {Q} = {PQd} euros, así que cada unidad cuesta {y}. Entonces {a} {i1} cuestan {P} - {b}*{y} = {rest} euros. Cada unidad cuesta {rest}/{a} = {ans}."}[L]
        rat = r.format(bd=b - d, i1=it1[i], i2=it2[i], P=P, Q=Q, PQd=P - Q, y=y, a=a, b=b, rest=a * x, ans=ans)
        wrong = [y, x + y, P - Q, _div(P, a + b), _div(Q, a), a * x]
        params = dict(kind=kind, eq1=[a, b, P], eq2=[a, d, Q])
    return _mk(rng, "two_equations", L, text, ans, wrong, rat, params=params)


def g_sum_product_squares(rng, L):
    kind = rng.choice(["sum", "sum", "diff", "diff", "recip"])
    if kind == "recip":
        k = rng.randint(3, 40)
        ans = k * k - 2
        text = pick(rng, {"eng": ["If x + 1/x = {k}, what is the value of x^2 + 1/x^2?"],
                          "cat": ["Si x + 1/x = {k}, quin és el valor de x^2 + 1/x^2?"],
                          "esp": ["Si x + 1/x = {k}, ¿cuál es el valor de x^2 + 1/x^2?"]}, L, k=k)
        r = {"eng": "Squaring gives (x + 1/x)^2 = x^2 + 2 + 1/x^2. So x^2 + 1/x^2 = {k}^2 - 2 = {ans}.",
             "cat": "Elevant al quadrat, (x + 1/x)^2 = x^2 + 2 + 1/x^2. Per tant, x^2 + 1/x^2 = {k}^2 - 2 = {ans}.",
             "esp": "Elevando al cuadrado, (x + 1/x)^2 = x^2 + 2 + 1/x^2. Por tanto, x^2 + 1/x^2 = {k}^2 - 2 = {ans}."}[L]
        rat = r.format(k=k, ans=ans)
        wrong = [k * k, k * k + 2, k * k - 1, 2 * k, k * k - 4]
        return _mk(rng, "sum_product_squares", L, text, ans, wrong, rat, params=dict(kind=kind, k=k))
    b, a = sorted(rng.sample(range(1, 16), 2))
    p = a * b
    ans = a * a + b * b
    if kind == "sum":
        s = a + b
        text = pick(rng, {
            "eng": ["Two numbers have sum {s} and product {p}. What is the sum of their squares?",
                    "If x + y = {s} and xy = {p}, what is the value of x^2 + y^2?"],
            "cat": ["Dos nombres tenen suma {s} i producte {p}. Quina és la suma dels seus quadrats?",
                    "Si x + y = {s} i xy = {p}, quin és el valor de x^2 + y^2?"],
            "esp": ["Dos números tienen suma {s} y producto {p}. ¿Cuál es la suma de sus cuadrados?",
                    "Si x + y = {s} y xy = {p}, ¿cuál es el valor de x^2 + y^2?"]}, L, s=s, p=p)
        r = {"eng": "We use (x + y)^2 = x^2 + 2xy + y^2. So x^2 + y^2 = {s}^2 - 2*{p} = {s2} - {tp} = {ans}.",
             "cat": "Fem servir (x + y)^2 = x^2 + 2xy + y^2. Per tant, x^2 + y^2 = {s}^2 - 2*{p} = {s2} - {tp} = {ans}.",
             "esp": "Usamos (x + y)^2 = x^2 + 2xy + y^2. Por tanto, x^2 + y^2 = {s}^2 - 2*{p} = {s2} - {tp} = {ans}."}[L]
        rat = r.format(s=s, p=p, s2=s * s, tp=2 * p, ans=ans)
        wrong = [s * s, s * s - p, s * s + 2 * p, s * s - 4 * p, 2 * s, s * s + p]
        params = dict(kind=kind, s=s, p=p)
    else:
        d = a - b
        text = pick(rng, {
            "eng": ["Two numbers have difference {d} and product {p}. What is the sum of their squares?",
                    "If x - y = {d} and xy = {p}, what is the value of x^2 + y^2?"],
            "cat": ["Dos nombres tenen diferència {d} i producte {p}. Quina és la suma dels seus quadrats?",
                    "Si x - y = {d} i xy = {p}, quin és el valor de x^2 + y^2?"],
            "esp": ["Dos números tienen diferencia {d} y producto {p}. ¿Cuál es la suma de sus cuadrados?",
                    "Si x - y = {d} y xy = {p}, ¿cuál es el valor de x^2 + y^2?"]}, L, d=d, p=p)
        r = {"eng": "We use (x - y)^2 = x^2 - 2xy + y^2. So x^2 + y^2 = {d}^2 + 2*{p} = {d2} + {tp} = {ans}.",
             "cat": "Fem servir (x - y)^2 = x^2 - 2xy + y^2. Per tant, x^2 + y^2 = {d}^2 + 2*{p} = {d2} + {tp} = {ans}.",
             "esp": "Usamos (x - y)^2 = x^2 - 2xy + y^2. Por tanto, x^2 + y^2 = {d}^2 + 2*{p} = {d2} + {tp} = {ans}."}[L]
        rat = r.format(d=d, p=p, d2=d * d, tp=2 * p, ans=ans)
        wrong = [d * d, d * d + p, d * d - 2 * p, d * d + 4 * p, 2 * p, d * d + 2 * p + 2]
        params = dict(kind=kind, d=d, p=p)
    return _mk(rng, "sum_product_squares", L, text, ans, wrong, rat, params=params)


def g_power_simplify(rng, L):
    B = rng.choice([2, 3])
    kind = rng.choice(["prod", "quot", "same"])
    i = LI[L]
    if kind == "same":
        base, m = rng.choice({2: [(2, 2), (2, 4), (4, 2), (4, 4), (8, 2), (8, 4)], 3: [(3, 3), (9, 3), (27, 3)]}[B])
        a = rng.randint(3, 30)
        lb = {B: 1, B * B: 2, B ** 3: 3}[base]
        u, w = {B: 1, B * B: 2}[m], a * lb
        ans = u + w
        expr = " + ".join([f"{base}^{a}"] * m)
        extra = "" if base == B else f" {AND[L]} {base}^{a} = {B}^{w}"
        r = {"eng": "There are {m} equal terms, so the sum is {m} * {base}^{a}. As powers of {B}, {m} = {B}^{u}{extra}. The exponent is {u} + {w} = {ans}.",
             "cat": "Hi ha {m} termes iguals, així que la suma és {m} * {base}^{a}. Com a potències de {B}, {m} = {B}^{u}{extra}. L'exponent és {u} + {w} = {ans}.",
             "esp": "Hay {m} términos iguales, así que la suma es {m} * {base}^{a}. Como potencias de {B}, {m} = {B}^{u}{extra}. El exponente es {u} + {w} = {ans}."}[L]
        rat = r.format(m=m, base=base, a=a, B=B, u=u, w=w, extra=extra, ans=ans)
        wrong = [m * a, w, m * w, a + 1 if base != B else a + m, w + m, a * m + 1]
        params = dict(B=B, mul=[[base, a]], div=[], copies=m)
    else:
        a, b, c = rng.randint(2, 15), rng.randint(2, 12), rng.randint(2, 9)
        q, c8 = B * B, B ** 3
        if kind == "prod":
            ans = a + 2 * b + 3 * c
            expr = f"{B}^{a} · {q}^{b} · {c8}^{c}"
            rule = ["Multiplying powers adds the exponents", "En multiplicar potències se sumen els exponents",
                    "Al multiplicar potencias se suman los exponentes"][i]
            calc = f"{a} + {2 * b} + {3 * c}"
            wrong = [a + b + c, a + 2 * b + 2 * c, a + b + 3 * c, a * b * c, 2 * a + 2 * b + 3 * c, a + 2 * b + c]
            params = dict(B=B, mul=[[B, a], [q, b], [c8, c]], div=[], copies=1)
        else:
            ans = a + 2 * b - 3 * c
            if ans < 1:
                raise Retry()
            expr = f"({B}^{a} · {q}^{b}) / {c8}^{c}"
            rule = ["Multiplying adds the exponents and dividing subtracts them",
                    "En multiplicar se sumen els exponents i en dividir es resten",
                    "Al multiplicar se suman los exponentes y al dividir se restan"][i]
            calc = f"{a} + {2 * b} - {3 * c}"
            wrong = [a + 2 * b + 3 * c, a + b - c, a + 2 * b - c, a + 2 * b - 2 * c, a + b - 3 * c, a + 2 * b]
            params = dict(B=B, mul=[[B, a], [q, b]], div=[[c8, c]], copies=1)
        r = {"eng": "Write everything as powers of {B}: {q}^{b} = {B}^{b2} and {c8}^{c} = {B}^{c3}. {rule}: {calc} = {ans}.",
             "cat": "Ho escrivim tot com a potències de {B}: {q}^{b} = {B}^{b2} i {c8}^{c} = {B}^{c3}. {rule}: {calc} = {ans}.",
             "esp": "Lo escribimos todo como potencias de {B}: {q}^{b} = {B}^{b2} y {c8}^{c} = {B}^{c3}. {rule}: {calc} = {ans}."}[L]
        rat = r.format(B=B, q=q, b=b, b2=2 * b, c8=c8, c=c, c3=3 * c, rule=rule, calc=calc, ans=ans)
    text = pick(rng, {
        "eng": ["If {expr} = {B}^n, what is the value of n?",
                "The number {expr} is written as a power of {B}. What is the exponent?"],
        "cat": ["Si {expr} = {B}^n, quin és el valor de n?",
                "El nombre {expr} s'escriu com una potència de {B}. Quin n'és l'exponent?"],
        "esp": ["Si {expr} = {B}^n, ¿cuál es el valor de n?",
                "El número {expr} se escribe como una potencia de {B}. ¿Cuál es el exponente?"]}, L, expr=expr, B=B)
    return _mk(rng, "power_simplify", L, text, ans, wrong, rat, params=params)


def g_successive_percent(rng, L):
    pcts = [10, 20, 25, 30, 40, 50, 60, 75, 80]
    p, q = rng.choice(pcts), rng.choice(pcts)
    up1, up2 = rng.random() < 0.5, rng.random() < 0.5
    m1 = 100 + p if up1 else 100 - p
    if m1 * q % 100:
        raise Retry()
    delta = m1 * q // 100
    ans = m1 + delta if up2 else m1 - delta
    i = LI[L]
    it = rng.choice(PRICED)[i]
    v1 = [("raised", "reduced"), ("puja", "baixa"), ("sube", "baja")][i]
    v2 = [("raises", "reduces"), ("apuja", "abaixa"), ("sube", "baja")][i]
    kw = dict(it=it, p=p, q=q, a1=v1[0 if up1 else 1], a2=v1[0 if up2 else 1],
              b1=v2[0 if up1 else 1], b2=v2[0 if up2 else 1])
    text = pick(rng, {
        "eng": ["The price of {it} is first {a1} by {p}% and then {a2} by {q}%. What percentage of the original price is the final price?",
                "A shop {b1} the price of {it} by {p}% and a week later {b2} the new price by {q}%. The final price is what percentage of the original price?"],
        "cat": ["El preu d'{it} primer {a1} un {p}% i després {a2} un {q}%. Quin percentatge del preu original és el preu final?",
                "Una botiga {b1} un {p}% el preu d'{it} i una setmana més tard {b2} un {q}% el preu nou. Quin percentatge del preu original és el preu final?"],
        "esp": ["El precio de {it} primero {a1} un {p}% y después {a2} un {q}%. ¿Qué porcentaje del precio original es el precio final?",
                "Una tienda {b1} un {p}% el precio de {it} y una semana después {b2} un {q}% el precio nuevo. ¿Qué porcentaje del precio original es el precio final?"]},
        L, **kw)
    r = {"eng": "Take an original price of 100. After the first change it is {m1}. The second change is {q}% of {m1}, which is {delta}, so the final price is {m1} {sign} {delta} = {ans}.",
         "cat": "Prenem un preu original de 100. Després del primer canvi és {m1}. El segon canvi és el {q}% de {m1}, que és {delta}, així que el preu final és {m1} {sign} {delta} = {ans}.",
         "esp": "Tomamos un precio original de 100. Tras el primer cambio es {m1}. El segundo cambio es el {q}% de {m1}, que es {delta}, así que el precio final es {m1} {sign} {delta} = {ans}."}[L]
    rat = r.format(m1=m1, q=q, delta=delta, sign="+" if up2 else "-", ans=ans)
    naive = m1 + q if up2 else m1 - q
    wrong = [naive, 100, m1, 200 - ans if ans < 200 else None, 100 + q if up2 else 100 - q, naive + 5]
    return _mk(rng, "successive_percent", L, text, ans, wrong, rat, params=dict(p=p, q=q, up1=up1, up2=up2))


_SPEEDS = [v for v in range(20, 121) if v % 2 == 0 or v % 5 == 0]
_SPEED_PAIRS = [(v1, v2) for v1 in _SPEEDS for v2 in _SPEEDS
                if v1 != v2 and max(v1, v2) <= 3 * min(v1, v2) and 2 * v1 * v2 % (v1 + v2) == 0
                and v1 * v2 // math.gcd(v1, v2) <= 600]


def g_average_speed(rng, L):
    v1, v2 = rng.choice(_SPEED_PAIRS)
    lcm = v1 * v2 // math.gcd(v1, v2)
    d = lcm * rng.choice([1, 2, 3]) if lcm <= 200 else lcm
    given = rng.random() < 0.5
    ans = 2 * v1 * v2 // (v1 + v2)
    i = LI[L]
    veh = rng.choice(VEHICLES)[i]
    if given:
        text = pick(rng, {
            "eng": ["Two towns are {d} km apart. {veh} goes from one to the other at {v1} km/h and returns at {v2} km/h. What is its average speed for the round trip, in km/h?"],
            "cat": ["Dos pobles són a {d} km de distància. {veh} va de l'un a l'altre a {v1} km/h i torna a {v2} km/h. Quina és la seva velocitat mitjana en el viatge d'anada i tornada, en km/h?"],
            "esp": ["Dos pueblos están a {d} km de distancia. {veh} va de uno a otro a {v1} km/h y vuelve a {v2} km/h. ¿Cuál es su velocidad media en el viaje de ida y vuelta, en km/h?"]},
            L, d=d, veh=veh, v1=v1, v2=v2)
        lead = ["Each way is {d} km.", "Cada trajecte fa {d} km.", "Cada trayecto mide {d} km."][i]
    else:
        text = pick(rng, {
            "eng": ["{veh} travels from one town to another at {v1} km/h and comes back along the same road at {v2} km/h. What is its average speed for the whole trip, in km/h?"],
            "cat": ["{veh} va d'un poble a un altre a {v1} km/h i torna pel mateix camí a {v2} km/h. Quina és la seva velocitat mitjana en tot el trajecte, en km/h?"],
            "esp": ["{veh} va de un pueblo a otro a {v1} km/h y vuelve por el mismo camino a {v2} km/h. ¿Cuál es su velocidad media en todo el trayecto, en km/h?"]},
            L, veh=veh, v1=v1, v2=v2)
        lead = ["Suppose the towns are {d} km apart.", "Suposem que els pobles són a {d} km.",
                "Supongamos que los pueblos están a {d} km."][i]
    r = {"eng": lead + " The way out takes {d}/{v1} = {t1} h and the way back {d}/{v2} = {t2} h. In total, {dd} km in {T} h, so the average speed is {dd}/{T} = {ans}.",
         "cat": lead + " L'anada dura {d}/{v1} = {t1} h i la tornada {d}/{v2} = {t2} h. En total, {dd} km en {T} h, així que la velocitat mitjana és {dd}/{T} = {ans}.",
         "esp": lead + " La ida dura {d}/{v1} = {t1} h y la vuelta {d}/{v2} = {t2} h. En total, {dd} km en {T} h, así que la velocidad media es {dd}/{T} = {ans}."}[L]
    t1, t2 = d // v1, d // v2
    rat = r.format(d=d, v1=v1, v2=v2, t1=t1, t2=t2, dd=2 * d, T=t1 + t2, ans=ans)
    wrong = [(v1 + v2) // 2, v1, v2, v1 + v2, abs(v1 - v2), (v1 + v2) // 2 + 1]
    return _mk(rng, "average_speed", L, text, ans, wrong, rat,
               params=dict(v1=v1, v2=v2, d=d if given else None))


def g_mean_change(rng, L):
    n, m = rng.randint(4, 12), rng.randint(10, 40)
    m2 = m + rng.choice([-4, -3, -2, -1, 1, 2, 3, 4])
    remove = rng.random() < 0.5
    n1 = n - 1 if remove else n + 1
    T, T2 = n * m, n1 * m2
    ans = T - T2 if remove else T2 - T
    if ans < 1:
        raise Retry()
    if remove:
        text = pick(rng, {
            "eng": ["The mean of {n} numbers is {m}. When one of the numbers is removed, the mean of the remaining numbers is {m2}. Which number was removed?"],
            "cat": ["La mitjana {den} nombres és {m}. Si en traiem un, la mitjana dels que queden és {m2}. Quin nombre hem tret?"],
            "esp": ["La media de {n} números es {m}. Si quitamos uno, la media de los que quedan es {m2}. ¿Qué número hemos quitado?"]},
            L, n=n, den=_de(n), m=m, m2=m2)
        r = {"eng": "The {n} numbers add up to {n}*{m} = {T}. The remaining {n1} add up to {n1}*{m2} = {T2}. The removed number is {T} - {T2} = {ans}.",
             "cat": "Els {n} nombres sumen {n}*{m} = {T}. Els {n1} que queden sumen {n1}*{m2} = {T2}. El nombre tret és {T} - {T2} = {ans}.",
             "esp": "Los {n} números suman {n}*{m} = {T}. Los {n1} que quedan suman {n1}*{m2} = {T2}. El número quitado es {T} - {T2} = {ans}."}[L]
    else:
        text = pick(rng, {
            "eng": ["The mean of {n} numbers is {m}. When one more number is added, the mean becomes {m2}. Which number was added?"],
            "cat": ["La mitjana {den} nombres és {m}. Si hi afegim un nombre més, la mitjana passa a ser {m2}. Quin nombre hi hem afegit?"],
            "esp": ["La media de {n} números es {m}. Si añadimos un número más, la media pasa a ser {m2}. ¿Qué número hemos añadido?"]},
            L, n=n, den=_de(n), m=m, m2=m2)
        r = {"eng": "The {n} numbers add up to {n}*{m} = {T}. With the new one, the {n1} numbers add up to {n1}*{m2} = {T2}. The added number is {T2} - {T} = {ans}.",
             "cat": "Els {n} nombres sumen {n}*{m} = {T}. Amb el nou, els {n1} nombres sumen {n1}*{m2} = {T2}. El nombre afegit és {T2} - {T} = {ans}.",
             "esp": "Los {n} números suman {n}*{m} = {T}. Con el nuevo, los {n1} números suman {n1}*{m2} = {T2}. El número añadido es {T2} - {T} = {ans}."}[L]
    rat = r.format(n=n, m=m, T=T, n1=n1, m2=m2, T2=T2, ans=ans)
    wrong = [m2, m, abs(m - m2) * n, abs(n * m - n * m2 + m), 2 * m2 - m if 2 * m2 > m else None, abs(m - m2) * n1]
    return _mk(rng, "mean_change", L, text, ans, wrong, rat, params=dict(n=n, m=m, m2=m2, remove=remove))


def g_inequality_count(rng, L):
    k = rng.randint(2, 7)
    c = rng.choice([v for v in range(-15, 16) if v])
    lo = rng.randint(-30, 40)
    hi = lo + rng.randint(8, 60)
    s1, s2 = rng.choice(["<", "≤"]), rng.choice(["<", "≤"])

    def good(n):
        v = k * n + c
        return (lo < v or (s1 == "≤" and lo == v)) and (v < hi or (s2 == "≤" and v == hi))

    sol = [n for n in range(-200, 201) if good(n)]
    ans = len(sol)
    if not 3 <= ans <= 15:
        raise Retry()
    p, q = sol[0], sol[-1]
    expr = f"{k}n {'+' if c > 0 else '-'} {abs(c)}"
    ineq = f"{lo} {s1} {expr} {s2} {hi}"
    text = pick(rng, {
        "eng": ["How many integers n satisfy {ineq}?", "For how many integers n is {ineq} true?"],
        "cat": ["Quants nombres enters n compleixen {ineq}?", "Per a quants nombres enters n es compleix {ineq}?"],
        "esp": ["¿Cuántos números enteros n cumplen {ineq}?", "¿Para cuántos números enteros n se cumple {ineq}?"]},
        L, ineq=ineq)
    r = {"eng": "The values of {expr} for consecutive n go up in steps of {k}. The smallest n that works is {p}, giving {vp}, and the largest is {q}, giving {vq}. From {p} to {q} there are {q} - {pp} + 1 = {ans} integers.",
         "cat": "Els valors de {expr} per a n consecutius augmenten de {k} en {k}. El n més petit que serveix és {p}, que dóna {vp}, i el més gran és {q}, que dóna {vq}. Entre {p} i {q}, tots dos inclosos, hi ha {q} - {pp} + 1 = {ans} enters.",
         "esp": "Los valores de {expr} para n consecutivos aumentan de {k} en {k}. El menor n que sirve es {p}, que da {vp}, y el mayor es {q}, que da {vq}. De {p} a {q} hay {q} - {pp} + 1 = {ans} enteros."}[L]
    rat = r.format(expr=expr, k=k, p=p, q=q, vp=k * p + c, vq=k * q + c, pp=f"({p})" if p < 0 else p, ans=ans)
    wrong = [ans - 1, ans + 1, (hi - lo) // k, hi - lo, ans + 2, abs(q) if abs(q) != ans else None, (hi - lo) // k + 2]
    return _mk(rng, "inequality_count", L, text, ans, wrong, rat,
               params=dict(k=k, c=c, lo=lo, hi=hi, s1=s1, s2=s2))


def g_geometric_sequence(rng, L):
    a, ratio = rng.randint(1, 12), rng.choice([2, 3, 4, 5])
    if rng.random() < 0.5:
        n = rng.randint(5, 8)
        ans = a * ratio ** (n - 1)
        if ans > 200000:
            raise Retry()
        t2, t3 = a * ratio, a * ratio * ratio
        text = pick(rng, {
            "eng": ["In a geometric sequence, the second term is {t2} and the third term is {t3}. What is term number {n}?"],
            "cat": ["En una progressió geomètrica, el segon terme és {t2} i el tercer terme és {t3}. Quin és el terme número {n}?"],
            "esp": ["En una progresión geométrica, el segundo término es {t2} y el tercero es {t3}. ¿Cuál es el término número {n}?"]},
            L, t2=t2, t3=t3, n=n)
        r = {"eng": "The ratio is {t3}/{t2} = {r}, so the first term is {t2}/{r} = {a}. Term {n} is the first term multiplied by the ratio {n1} times: {a}*{r}^{n1} = {ans}.",
             "cat": "La raó és {t3}/{t2} = {r}, així que el primer terme és {t2}/{r} = {a}. El terme {n} és el primer multiplicat per la raó {n1} vegades: {a}*{r}^{n1} = {ans}.",
             "esp": "La razón es {t3}/{t2} = {r}, así que el primer término es {t2}/{r} = {a}. El término {n} es el primero multiplicado por la razón {n1} veces: {a}*{r}^{n1} = {ans}."}[L]
        rat = r.format(t2=t2, t3=t3, r=ratio, a=a, n=n, n1=n - 1, ans=ans)
        wrong = [ans * ratio, ans // ratio, a + (n - 1) * (t3 - t2), t2 * n, t3 * (n - 2), a * ratio * (n - 1)]
        params = dict(kind="term", t2=t2, t3=t3, n=n)
    else:
        n = rng.randint(4, 6)
        terms = [a * ratio ** j for j in range(n)]
        ans = sum(terms)
        text = pick(rng, {
            "eng": ["A sequence starts with the number {a} and each term is obtained by multiplying the previous term by {r}. What is the sum of the first {n} terms?"],
            "cat": ["Una successió comença amb el nombre {a} i cada terme s'obté multiplicant per {r} el terme precedent. Quina és la suma dels {n} primers termes?"],
            "esp": ["Una sucesión empieza con el número {a} y cada término se obtiene multiplicando por {r} el término anterior. ¿Cuál es la suma de los {n} primeros términos?"]},
            L, a=a, r=ratio, n=n)
        r = {"eng": "The first {n} terms are {lst}. Their sum is {plus} = {ans}.",
             "cat": "Els {n} primers termes són {lst}. La seva suma és {plus} = {ans}.",
             "esp": "Los {n} primeros términos son {lst}. Su suma es {plus} = {ans}."}[L]
        rat = r.format(n=n, lst=", ".join(map(str, terms)), plus=" + ".join(map(str, terms)), ans=ans)
        wrong = [terms[-1], ans - a, ans + terms[-1] * ratio, a * ratio * n, ans - terms[-1], terms[-1] * ratio]
        params = dict(kind="sum", a=a, r=ratio, n=n)
    return _mk(rng, "geometric_sequence", L, text, ans, wrong, rat, params=params)


def g_arith_two_terms(rng, L):
    a, d = rng.randint(1, 30), rng.randint(2, 12)
    i = rng.randint(2, 5)
    j = i + rng.randint(2, 6)
    n = j + rng.randint(3, 30)
    ti, tj = a + (i - 1) * d, a + (j - 1) * d
    ans = a + (n - 1) * d
    text = pick(rng, {
        "eng": ["In an arithmetic sequence, term number {i} is {ti} and term number {j} is {tj}. What is term number {n}?",
                "A sequence grows by the same amount at every step. Its term number {i} is {ti} and its term number {j} is {tj}. What is its term number {n}?"],
        "cat": ["En una progressió aritmètica, el terme número {i} és {ti} i el terme número {j} és {tj}. Quin és el terme número {n}?",
                "Una successió augmenta la mateixa quantitat a cada pas. El terme número {i} és {ti} i el terme número {j} és {tj}. Quin és el terme número {n}?"],
        "esp": ["En una progresión aritmética, el término número {i} es {ti} y el término número {j} es {tj}. ¿Cuál es el término número {n}?",
                "Una sucesión aumenta la misma cantidad en cada paso. El término número {i} es {ti} y el término número {j} es {tj}. ¿Cuál es el término número {n}?"]},
        L, i=i, j=j, n=n, ti=ti, tj=tj)
    r = {"eng": "From term {i} to term {j} there are {ji} steps that add {tj} - {ti} = {D}, so each step adds {D}/{ji} = {d}. From term {j} to term {n} there are {nj} more steps. So the term is {tj} + {nj}*{d} = {ans}.",
         "cat": "Del terme {i} al terme {j} hi ha {ji} passos que sumen {tj} - {ti} = {D}, així que cada pas suma {D}/{ji} = {d}. Del terme {j} al terme {n} hi ha {nj} passos més. Per tant, el terme és {tj} + {nj}*{d} = {ans}.",
         "esp": "Del término {i} al término {j} hay {ji} pasos que suman {tj} - {ti} = {D}, así que cada paso suma {D}/{ji} = {d}. Del término {j} al término {n} hay {nj} pasos más. Por tanto, el término es {tj} + {nj}*{d} = {ans}."}[L]
    rat = r.format(i=i, j=j, n=n, ti=ti, tj=tj, ji=j - i, D=tj - ti, d=d, nj=n - j, ans=ans)
    wrong = [tj + n * d, ti + n * d, ans + d, ans - d, n * d, tj + (n - j) * (tj - ti)]
    return _mk(rng, "arith_two_terms", L, text, ans, wrong, rat, params=dict(i=i, j=j, n=n, ti=ti, tj=tj))


# ----- counting and probability

def g_arrangements_restricted(rng, L):
    n = rng.randint(4, 7)
    kind = rng.choice(["apart", "end", "left"])
    n1, n2 = rng.sample(NAMES, 2)
    F, f = math.factorial(n), math.factorial(n - 1)
    i = LI[L]
    cond = {"apart": ["{n1} and {n2} must not sit next to each other",
                      "{n1} i {n2} no poden seure en cadires contigües",
                      "{n1} y {n2} no pueden sentarse en sillas contiguas"],
            "end": ["{n1} must sit at one of the two ends of the row",
                    "{n1} ha de seure en un dels dos extrems de la fila",
                    "{n1} debe sentarse en uno de los dos extremos de la fila"],
            "left": ["{n1} must sit somewhere to the left of {n2}",
                     "{n1} ha de seure en algun lloc a l'esquerra {den2}",
                     "{n1} debe sentarse en algún lugar a la izquierda de {n2}"]}[kind][i]
    cond = cond.format(n1=n1, n2=n2, den2=_de_name(n2))
    who = n1 if kind == "end" else f"{n1} {AND[L]} {n2}"
    text = pick(rng, {
        "eng": ["In how many ways can {n} friends, including {who}, sit in a row of {n} chairs if {cond}?"],
        "cat": ["De quantes maneres poden seure {n} amics, entre ells {who}, en una fila de {n} cadires si {cond}?"],
        "esp": ["¿De cuántas maneras pueden sentarse {n} amigos, entre ellos {who}, en una fila de {n} sillas si {cond}?"]},
        L, n=n, who=who, cond=cond)
    if kind == "apart":
        tog = 2 * f
        ans = F - tog
        r = {"eng": "Without the condition there are {n}! = {F} orders. With the two sitting together, treat them as one block: {m}! * 2 = {tog} orders. So the orders with them apart are {F} - {tog} = {ans}.",
             "cat": "Sense la condició hi ha {n}! = {F} ordenacions. Si els dos seuen junts, els considerem un bloc: {m}! * 2 = {tog} ordenacions. Per tant, les ordenacions en què estan separats són {F} - {tog} = {ans}.",
             "esp": "Sin la condición hay {n}! = {F} ordenaciones. Si los dos se sientan juntos, los consideramos un bloque: {m}! * 2 = {tog} ordenaciones. Por tanto, las ordenaciones en que están separados son {F} - {tog} = {ans}."}[L]
        rat = r.format(n=n, F=F, m=n - 1, tog=tog, ans=ans)
        wrong = [tog, F, F - f, F // 2, f, F - 2 * math.factorial(n - 2)]
    elif kind == "end":
        ans = 2 * f
        r = {"eng": "{n1} has 2 possible seats. The other {m} friends can fill the remaining seats in {m}! = {f} ways. In total, 2*{f} = {ans}.",
             "cat": "{n1} té 2 seients possibles. Els altres {m} amics poden ocupar la resta de seients de {m}! = {f} maneres. En total, 2*{f} = {ans}.",
             "esp": "{n1} tiene 2 asientos posibles. Los otros {m} amigos pueden ocupar el resto de asientos de {m}! = {f} maneras. En total, 2*{f} = {ans}."}[L]
        rat = r.format(n1=n1, m=n - 1, f=f, ans=ans)
        wrong = [f, F, 2 * math.factorial(n - 2), F // 2 if F // 2 != ans else None, 2 * n, F - f]
    else:
        ans = F // 2
        r = {"eng": "There are {n}! = {F} orders in all. Swapping the two friends pairs each order with one where they are the other way round, so exactly half are good. That gives {F}/2 = {ans}.",
             "cat": "En total hi ha {n}! = {F} ordenacions. Si intercanviem els dos amics, cada ordenació s'aparella amb una altra on estan al revés, així que exactament la meitat són bones. Això dóna {F}/2 = {ans}.",
             "esp": "En total hay {n}! = {F} ordenaciones. Si intercambiamos a los dos amigos, cada ordenación se empareja con otra donde están al revés, así que exactamente la mitad son buenas. Eso da {F}/2 = {ans}."}[L]
        rat = r.format(n=n, F=F, ans=ans)
        wrong = [F, f, 2 * f if 2 * f != ans else None, F - 2 * f, F - f, math.factorial(n - 2)]
    return _mk(rng, "arrangements_restricted", L, text, ans, wrong, rat, params=dict(kind=kind, n=n))


def g_committee(rng, L):
    b, g, k = rng.randint(3, 8), rng.randint(3, 8), rng.randint(3, 5)
    exact = rng.random() < 0.6
    T = math.comb(b + g, k)
    if exact:
        j = rng.randint(1, k - 1)
        if j >= g or k - j >= b:
            raise Retry()
        cg, cb = math.comb(g, j), math.comb(b, k - j)
        ans = cg * cb
        cond = ["the team must contain exactly {j} of the girls", "l'equip ha de tenir exactament {j} de les noies",
                "el equipo debe tener exactamente {j} de las chicas"][LI[L]].format(j=j)
        r = {"eng": "From the {g} girls we choose {j}: {ge} ways. From the {b} boys we choose {kj}: {be} ways. In total, {cg}*{cb} = {ans}.",
             "cat": "De les {g} noies en triem {j}: {ge} maneres. Dels {b} nois en triem {kj}: {be} maneres. En total, {cg}*{cb} = {ans}.",
             "esp": "De las {g} chicas elegimos {j}: {ge} maneras. De los {b} chicos elegimos {kj}: {be} maneras. En total, {cg}*{cb} = {ans}."}[L]
        rat = r.format(g=g, j=j, ge=_comb_expr(g, j), b=b, kj=k - j, be=_comb_expr(b, k - j), cg=cg, cb=cb, ans=ans)
        wrong = [cg + cb, T, cg * math.comb(b, k), math.comb(g, j) * (k - j), cg, cb, T - ans]
        params = dict(kind="exact", b=b, g=g, k=k, j=j)
    else:
        if b <= k:
            raise Retry()
        B0 = math.comb(b, k)
        ans = T - B0
        cond = ["the team must contain at least one girl", "l'equip ha de tenir almenys una noia",
                "el equipo debe tener al menos una chica"][LI[L]]
        r = {"eng": "There are {te} teams in all. Those with only boys number {be}. The teams with at least one girl are {T} - {B0} = {ans}.",
             "cat": "En total hi ha {te} equips. Els que només tenen nois són {be}. Els equips amb almenys una noia són {T} - {B0} = {ans}.",
             "esp": "En total hay {te} equipos. Los que solo tienen chicos son {be}. Los equipos con al menos una chica son {T} - {B0} = {ans}."}[L]
        rat = r.format(te=_comb_expr(b + g, k), be=_comb_expr(b, k), T=T, B0=B0, ans=ans)
        wrong = [T, B0, g * math.comb(b + g - 1, k - 1), T - math.comb(g, k) if g >= k else None,
                 g * math.comb(b, k - 1), T - 1]
        params = dict(kind="atleast", b=b, g=g, k=k)
    text = pick(rng, {
        "eng": ["A class has {b} boys and {g} girls. In how many ways can a team of {k} students be chosen if {cond}?"],
        "cat": ["En una classe hi ha {b} nois i {g} noies. De quantes maneres es pot triar un equip de {k} alumnes si {cond}?"],
        "esp": ["En una clase hay {b} chicos y {g} chicas. ¿De cuántas maneras se puede elegir un equipo de {k} alumnos si {cond}?"]},
        L, b=b, g=g, k=k, cond=cond)
    return _mk(rng, "committee", L, text, ans, wrong, rat, params=params)


_DICE_TEST = {"sum_eq": lambda a, b, v: a + b == v, "sum_gt": lambda a, b, v: a + b > v,
              "sum_lt": lambda a, b, v: a + b < v, "prod_eq": lambda a, b, v: a * b == v,
              "prod_gt": lambda a, b, v: a * b > v, "diff_eq": lambda a, b, v: abs(a - b) == v,
              "max_eq": lambda a, b, v: max(a, b) == v, "sum_mult": lambda a, b, v: (a + b) % v == 0,
              "prod_mult": lambda a, b, v: (a * b) % v == 0}
_DICE_EVENTS = ([("sum_eq", v) for v in range(2, 13)] + [("sum_gt", v) for v in range(3, 11)]
                + [("sum_lt", v) for v in range(4, 12)]
                + [("prod_eq", v) for v in (1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 15, 16, 18, 20, 24, 25, 30, 36)]
                + [("prod_gt", v) for v in (5, 8, 10, 12, 15, 18, 20, 24)] + [("diff_eq", v) for v in range(6)]
                + [("max_eq", v) for v in range(1, 7)] + [("sum_mult", v) for v in range(2, 7)]
                + [("prod_mult", v) for v in range(2, 7)])
_DICE_TEXT = {
    "sum_eq": ("the sum of the two numbers is {v}", "la suma dels dos nombres sigui {v}", "la suma de los dos números sea {v}"),
    "sum_gt": ("the sum of the two numbers is greater than {v}", "la suma dels dos nombres sigui més gran que {v}", "la suma de los dos números sea mayor que {v}"),
    "sum_lt": ("the sum of the two numbers is less than {v}", "la suma dels dos nombres sigui més petita que {v}", "la suma de los dos números sea menor que {v}"),
    "prod_eq": ("the product of the two numbers is {v}", "el producte dels dos nombres sigui {v}", "el producto de los dos números sea {v}"),
    "prod_gt": ("the product of the two numbers is greater than {v}", "el producte dels dos nombres sigui més gran que {v}", "el producto de los dos números sea mayor que {v}"),
    "diff_eq": ("the difference between the larger and the smaller number is {v}", "la diferència entre el nombre més gran i el més petit sigui {v}", "la diferencia entre el número mayor y el menor sea {v}"),
    "equal": ("the two numbers are equal", "els dos nombres siguin iguals", "los dos números sean iguales"),
    "max_eq": ("the largest number shown is {v}", "el nombre més gran que surt sigui {v}", "el mayor número que sale sea {v}"),
    "sum_mult": ("the sum of the two numbers is a multiple of {v}", "la suma dels dos nombres sigui múltiple de {v}", "la suma de los dos números sea múltiplo de {v}"),
    "prod_mult": ("the product of the two numbers is a multiple of {v}", "el producte dels dos nombres sigui múltiple de {v}", "el producto de los dos números sea múltiplo de {v}")}


def g_dice_probability(rng, L):
    kind, v = rng.choice(_DICE_EVENTS)
    name = rng.choice(NAMES)
    i = LI[L]
    fav = [(a, b) for a in range(1, 7) for b in range(1, 7) if _DICE_TEST[kind](a, b, v)]
    c = len(fav)
    if not 0 < c < 36:
        raise Retry()
    ans = frac(c, 36)
    ev = _DICE_TEXT["equal" if (kind, v) == ("diff_eq", 0) else kind][i].format(v=v)
    text = pick(rng, {
        "eng": ["Two fair dice are rolled. What is the probability that {ev}?",
                "{name} rolls two fair six-sided dice. What is the probability that {ev}?"],
        "cat": ["Es llancen dos daus equilibrats. Quina és la probabilitat que {ev}?",
                "{name} llança dos daus equilibrats de sis cares. Quina és la probabilitat que {ev}?"],
        "esp": ["Se lanzan dos dados equilibrados. ¿Cuál es la probabilidad de que {ev}?",
                "{name} lanza dos dados equilibrados de seis caras. ¿Cuál es la probabilidad de que {ev}?"]},
        L, ev=ev, name=name)
    lst = ", ".join(f"({a},{b})" for a, b in fav)
    if c == 1:
        mid = ["The only favourable one is {lst}.", "L'únic favorable és {lst}.", "El único favorable es {lst}."][i]
    elif c <= 6:
        mid = ["The favourable ones are {lst}, {c} in total.", "Els favorables són {lst}, {c} en total.",
               "Los favorables son {lst}, {c} en total."][i]
    else:
        mid = ["Counting them by the value of the first die: {per} = {c} favourable ones.",
               "Comptant-los segons el valor del primer dau: {per} = {c} favorables.",
               "Contándolos según el valor del primer dado: {per} = {c} favorables."][i]
    per = "+".join(str(sum(1 for a, _ in fav if a == d)) for d in range(1, 7))
    tail = f"{c}/36" if ans == f"{c}/36" else f"{c}/36 = {ans}"
    r = {"eng": "Two dice give 6*6 = 36 equally likely results. " + mid + " The probability is {tail}.",
         "cat": "Dos daus donen 6*6 = 36 resultats igualment probables. " + mid + " La probabilitat és {tail}.",
         "esp": "Dos dados dan 6*6 = 36 resultados igualmente probables. " + mid + " La probabilidad es {tail}."}[L]
    rat = r.format(lst=lst, c=c, per=per, tail=tail)
    u = sum(1 for a, b in fav if a <= b)
    wrong = _fracs([(u, 21), (u, 36), (c + 1, 36), (c - 1, 36), (c, 12), (36 - c, 36), (c + 2, 36), (c, 30),
                    (1, 6), (1, 12), (1, 9), (1, 4), (1, 3), (1, 2)], ans)
    return _mk(rng, "dice_probability", L, text, ans, wrong, rat, numeric=False, params=dict(kind=kind, v=v))


def g_balls_probability(rng, L):
    col1, col2 = rng.sample(BALLS, 2)
    r_, b = rng.randint(2, 9), rng.randint(2, 9)
    kind = rng.choice(["same", "diff", "two", "atleast"])
    i = LI[L]
    N = r_ + b
    tot = N * (N - 1)
    c1, c2 = col1[i], col2[i]
    s1, s2 = (c1, c2) if L == "eng" else (col1[2 + i], col2[2 + i])
    x, y = r_ * (r_ - 1), b * (b - 1)
    num = {"same": x + y, "diff": 2 * r_ * b, "two": x, "atleast": tot - y}[kind]
    ans = frac(num, tot)
    ev = {"same": ["the two balls have the same colour", "les dues boles siguin del mateix color", "las dos bolas sean del mismo color"],
          "diff": ["the two balls have different colours", "les dues boles siguin de colors diferents", "las dos bolas sean de colores diferentes"],
          "two": ["the two balls are {c1}", "les dues boles siguin {c1}", "las dos bolas sean {c1}"],
          "atleast": ["at least one of the two balls is {s1}", "almenys una de les dues boles sigui {s1}", "al menos una de las dos bolas sea {s1}"]}[kind][i].format(c1=c1, s1=s1)
    text = pick(rng, {
        "eng": ["A bag contains {r} {c1} balls and {b} {c2} balls. Two balls are taken out at random, one after the other, without putting the first one back. What is the probability that {ev}?"],
        "cat": ["Una bossa conté {r} boles {c1} i {b} boles {c2}. Es treuen dues boles a l'atzar, l'una després de l'altra, sense tornar la primera a la bossa. Quina és la probabilitat que {ev}?"],
        "esp": ["Una bolsa contiene {r} bolas {c1} y {b} bolas {c2}. Se sacan dos bolas al azar, una tras otra, sin devolver la primera a la bolsa. ¿Cuál es la probabilidad de que {ev}?"]},
        L, r=r_, b=b, c1=c1, c2=c2, ev=ev)
    lead = ["There are {N}*{N1} = {tot} ordered ways to take two balls.", "Hi ha {N}*{N1} = {tot} maneres ordenades de treure dues boles.",
            "Hay {N}*{N1} = {tot} maneras ordenadas de sacar dos bolas."][i]
    body = {
        "same": ["Two {c1}: {r}*{r1} = {x} ways, and two {c2}: {b}*{b1} = {y} ways. The probability is ({x} + {y})/{tot} = {ans}.",
                 "Dues {c1}: {r}*{r1} = {x} maneres, i dues {c2}: {b}*{b1} = {y} maneres. La probabilitat és ({x} + {y})/{tot} = {ans}.",
                 "Dos {c1}: {r}*{r1} = {x} maneras, y dos {c2}: {b}*{b1} = {y} maneras. La probabilidad es ({x} + {y})/{tot} = {ans}."],
        "diff": ["First {s1} then {s2}: {r}*{b} = {rb} ways, and the other order gives {rb} more. The probability is {num}/{tot} = {ans}.",
                 "Primer {s1} i després {s2}: {r}*{b} = {rb} maneres, i l'ordre contrari en dóna {rb} més. La probabilitat és {num}/{tot} = {ans}.",
                 "Primero {s1} y después {s2}: {r}*{b} = {rb} maneras, y el orden contrario da {rb} más. La probabilidad es {num}/{tot} = {ans}."],
        "two": ["Two {c1} balls can be taken in {r}*{r1} = {x} ways. The probability is {num}/{tot} = {ans}.",
                "Dues boles {c1} es poden treure de {r}*{r1} = {x} maneres. La probabilitat és {num}/{tot} = {ans}.",
                "Dos bolas {c1} se pueden sacar de {r}*{r1} = {x} maneras. La probabilidad es {num}/{tot} = {ans}."],
        "atleast": ["With no {s1} ball: {b}*{b1} = {y} ways, so with at least one there are {tot} - {y} = {num}. The probability is {num}/{tot} = {ans}.",
                    "Sense cap bola {s1}: {b}*{b1} = {y} maneres, així que amb almenys una n'hi ha {tot} - {y} = {num}. La probabilitat és {num}/{tot} = {ans}.",
                    "Sin ninguna bola {s1}: {b}*{b1} = {y} maneras, así que con al menos una hay {tot} - {y} = {num}. La probabilidad es {num}/{tot} = {ans}."]}[kind][i]
    rat = (lead + " " + body).format(N=N, N1=N - 1, tot=tot, c1=c1, c2=c2, s1=s1, s2=s2, r=r_, r1=r_ - 1, b=b,
                                     b1=b - 1, x=x, y=y, rb=r_ * b, num=num, ans=ans)
    NN = N * N
    wrong = _fracs({"same": [(r_ * r_ + b * b, NN), (tot - num, tot), (r_ * b, tot), (x, tot), (y, tot)],
                    "diff": [(r_ * b, tot), (2 * r_ * b, NN), (tot - num, tot), (r_ * b, NN), (r_, N)],
                    "two": [(r_ * r_, NN), (r_, N), (r_ - 1, N - 1), (x, NN), (2, N)],
                    "atleast": [(r_, N), (y, tot), (NN - b * b, NN), (x, tot), (2 * r_ * b, tot)]}[kind]
                   + [(1, 2), (1, 3), (2, 3), (1, 4), (3, 4), (2, 5), (3, 5)], ans)
    return _mk(rng, "balls_probability", L, text, ans, wrong, rat, numeric=False,
               params=dict(kind=kind, first=r_, second=b))


def g_routes_via(rng, L):
    a, b = rng.randint(4, 7), rng.randint(4, 6)
    c, d = rng.randint(2, a - 2), rng.randint(2, b - 2)
    e, f = a - c, b - d
    name = rng.choice(NAMES)
    w1, w2 = math.comb(c + d, c), math.comb(e + f, e)
    ans = w1 * w2
    text = pick(rng, {
        "eng": ["{name} walks from home to school, which is {a} blocks east and {b} blocks north, always going east or north along the streets. On the way {name} wants to pass the bakery, which is {c} blocks east and {d} blocks north of home. How many different routes are possible?"],
        "cat": ["{name} va de casa a l'escola, que és a {a} illes de cases cap a l'est i {b} cap al nord, caminant pels carrers sempre cap a l'est o cap al nord. Pel camí vol passar per la fleca, que és a {c} illes de cases cap a l'est i {d} cap al nord de casa. Quants camins diferents pot fer?"],
        "esp": ["{name} va de casa al colegio, que está a {a} manzanas al este y {b} al norte, caminando por las calles siempre hacia el este o hacia el norte. Por el camino quiere pasar por la panadería, que está a {c} manzanas al este y {d} al norte de casa. ¿Cuántos caminos diferentes puede hacer?"]},
        L, name=name, a=a, b=b, c=c, d=d)
    r = {"eng": "From home to the bakery the moves needed are {c} east and {d} north, which can be ordered in {w1} ways. From the bakery to school they are {e} east and {f} north, in {w2} ways. In total, {w1}*{w2} = {ans}.",
         "cat": "De casa a la fleca calen {c} moviments a l'est i {d} al nord, que es poden ordenar de {w1} maneres. De la fleca a l'escola en calen {e} a l'est i {f} al nord, de {w2} maneres. En total, {w1}*{w2} = {ans}.",
         "esp": "De casa a la panadería hacen falta {c} movimientos al este y {d} al norte, que se pueden ordenar de {w1} maneras. De la panadería al colegio hacen falta {e} al este y {f} al norte, de {w2} maneras. En total, {w1}*{w2} = {ans}."}[L]
    rat = r.format(c=c, d=d, e=e, f=f, w1=w1, w2=w2, ans=ans)
    allr = math.comb(a + b, a)
    wrong = [allr, w1 + w2, w1, w2, allr - ans, c * d * e * f]
    return _mk(rng, "routes_via", L, text, ans, wrong, rat, params=dict(a=a, b=b, c=c, d=d))


def g_numbers_from_digits(rng, L):
    m = rng.randint(4, 6)
    digs = sorted(rng.sample(range(10), m))
    ln = rng.choice([3, 4])
    cond = rng.choice(["any", "even", "odd", "mult5"])
    i = LI[L]
    has0 = 0 in digs
    allowed = {"any": digs, "even": [x for x in digs if x % 2 == 0], "odd": [x for x in digs if x % 2],
               "mult5": [x for x in digs if x % 5 == 0]}[cond]
    if not allowed:
        raise Retry()
    f1 = [m - 1 - t for t in range(ln - 1)]              # last digit fixed, the rest free
    f2 = [m - 2] + [m - 2 - t for t in range(ln - 2)]    # last digit fixed and not 0, first digit not 0
    e1, c1 = "*".join(map(str, f1)), _prod(f1)
    e2, c2 = "*".join(map(str, f2)), _prod(f2)
    nz = [x for x in allowed if x]
    kw = dict(e1=e1, c1=c1, e2=e2, c2=c2, E=", ".join(map(str, allowed)), NZ=", ".join(map(str, nz)),
              k=len(allowed), k2=len(nz))
    if cond == "any":
        fa = [m - (1 if has0 else 0)] + f1
        ans = _prod(fa)
        kw.update(f=fa[0], seq=_join(f1, L), expr="*".join(map(str, fa)))
        first = [("The first digit has {f} choices.", "The first digit cannot be 0, so it has {f} choices."),
                 ("La primera xifra té {f} opcions.", "La primera xifra no pot ser 0, així que té {f} opcions."),
                 ("La primera cifra tiene {f} opciones.", "La primera cifra no puede ser 0, así que tiene {f} opciones.")][i][has0]
        r = first + [" The following digits have {seq} choices, since no digit repeats. That gives {expr} = {ans}.",
                     " Les xifres següents tenen {seq} opcions, perquè no se'n repeteix cap. Això dóna {expr} = {ans}.",
                     " Las cifras siguientes tienen {seq} opciones, porque no se repite ninguna. Eso da {expr} = {ans}."][i]
    elif not has0 and len(allowed) == 1:
        ans = c1
        r = ["The last digit must be {E}. The other places can be filled in {e1} = {ans} ways.",
             "L'última xifra ha de ser {E}. Les altres posicions es poden omplir de {e1} = {ans} maneres.",
             "La última cifra debe ser {E}. Las otras posiciones se pueden rellenar de {e1} = {ans} maneras."][i]
    elif not has0:
        ans = len(allowed) * c1
        r = ["Possible last digits: {E}. For each one, the other places can be filled in {e1} = {c1} ways. In total, {k}*{c1} = {ans}.",
             "Últimes xifres possibles: {E}. Per a cadascuna, les altres posicions es poden omplir de {e1} = {c1} maneres. En total, {k}*{c1} = {ans}.",
             "Últimas cifras posibles: {E}. Para cada una, las otras posiciones se pueden rellenar de {e1} = {c1} maneras. En total, {k}*{c1} = {ans}."][i]
    elif 0 in allowed and len(nz) == 1:
        ans = c1 + c2
        r = ["Last digit 0: the other places can be filled in {e1} = {c1} ways. Last digit {NZ}: the first digit cannot be 0, so there are {e2} = {c2} ways. In total, {c1} + {c2} = {ans}.",
             "Última xifra 0: les altres posicions es poden omplir de {e1} = {c1} maneres. Última xifra {NZ}: la primera xifra no pot ser 0, així que hi ha {e2} = {c2} maneres. En total, {c1} + {c2} = {ans}.",
             "Última cifra 0: las otras posiciones se pueden rellenar de {e1} = {c1} maneras. Última cifra {NZ}: la primera cifra no puede ser 0, así que hay {e2} = {c2} maneras. En total, {c1} + {c2} = {ans}."][i]
    elif 0 in allowed and nz:
        ans = c1 + len(nz) * c2
        r = ["Last digit 0: the other places can be filled in {e1} = {c1} ways. Last digit {NZ}: the first digit cannot be 0, so each case has {e2} = {c2} ways. In total, {c1} + {k2}*{c2} = {ans}.",
             "Última xifra 0: les altres posicions es poden omplir de {e1} = {c1} maneres. Última xifra {NZ}: la primera xifra no pot ser 0, així que cada cas té {e2} = {c2} maneres. En total, {c1} + {k2}*{c2} = {ans}.",
             "Última cifra 0: las otras posiciones se pueden rellenar de {e1} = {c1} maneras. Última cifra {NZ}: la primera cifra no puede ser 0, así que cada caso tiene {e2} = {c2} maneras. En total, {c1} + {k2}*{c2} = {ans}."][i]
    elif 0 in allowed:
        ans = c1
        r = ["The last digit must be 0. The other places can be filled in {e1} = {ans} ways.",
             "L'última xifra ha de ser 0. Les altres posicions es poden omplir de {e1} = {ans} maneres.",
             "La última cifra debe ser 0. Las otras posiciones se pueden rellenar de {e1} = {ans} maneras."][i]
    elif len(nz) == 1:
        ans = c2
        r = ["The last digit must be {NZ}. The first digit cannot be 0 or {NZ}, so the other places can be filled in {e2} = {ans} ways.",
             "L'última xifra ha de ser {NZ}. La primera xifra no pot ser 0 ni {NZ}, així que les altres posicions es poden omplir de {e2} = {ans} maneres.",
             "La última cifra debe ser {NZ}. La primera cifra no puede ser 0 ni {NZ}, así que las otras posiciones se pueden rellenar de {e2} = {ans} maneras."][i]
    else:
        ans = len(nz) * c2
        r = ["Possible last digits: {NZ}. The first digit cannot be 0 or the chosen last digit, so each case has {e2} = {c2} ways. In total, {k2}*{c2} = {ans}.",
             "Últimes xifres possibles: {NZ}. La primera xifra no pot ser 0 ni l'última xifra triada, així que cada cas té {e2} = {c2} maneres. En total, {k2}*{c2} = {ans}.",
             "Últimas cifras posibles: {NZ}. La primera cifra no puede ser 0 ni la última cifra elegida, así que cada caso tiene {e2} = {c2} maneras. En total, {k2}*{c2} = {ans}."][i]
    rat = r.format(ans=ans, **kw)
    cw = {"any": ("", "", ""), "even": (" that are even", " parells", " pares"), "odd": (" that are odd", " senars", " impares"),
          "mult5": (" that are multiples of 5", " múltiples de 5", " múltiplos de 5")}[cond][i]
    text = pick(rng, {
        "eng": ["How many {nd}-digit numbers{cw} can be formed with the digits {lst}, if no digit may be used more than once?"],
        "cat": ["Quants nombres{cw} de {nd} xifres es poden formar amb les xifres {lst}, sense repetir-ne cap?"],
        "esp": ["¿Cuántos números{cw} de {nd} cifras se pueden formar con las cifras {lst}, sin repetir ninguna?"]},
        L, nd=NDIG[ln][i], cw=cw, lst=_join(digs, L))
    lead0 = len(allowed) * c1 if cond != "any" else _prod([m] + f1)       # forgetting that 0 cannot lead
    rep = (m - has0) * m ** (ln - 2) * (len(allowed) if cond != "any" else m)  # digits repeated
    wrong = [lead0, rep, math.perm(m, ln), len(allowed) * c2 if cond != "any" else None, c1, ans + c2, ans - c2]
    return _mk(rng, "numbers_from_digits", L, text, ans, wrong, rat, params=dict(digits=digs, length=ln, cond=cond))


# ----- geometry in words

def g_isosceles_angle(rng, L):
    kind = rng.choice(["apex", "base", "obtuse", "exterior"])
    i = LI[L]
    if kind == "apex":
        x = rng.randrange(2, 179, 2)
        rest, ans = 180 - x, (180 - x) // 2
        wrong = [180 - x, x // 2, abs(90 - x), 2 * x if 2 * x < 180 else None, (180 - x) // 2 + x // 2, 90]
    elif kind == "base":
        x = rng.randint(1, 89)
        rest, ans = 2 * x, 180 - 2 * x
        wrong = [180 - x, 90 - x, 2 * x, x, _div(180 - x, 2), 360 - 2 * x]
    elif kind == "obtuse":
        x = rng.randrange(92, 179, 2)
        rest, ans = 180 - x, (180 - x) // 2
        wrong = [180 - x, x // 2, x - 90, 90, 360 - 2 * x]
    else:
        x = rng.randrange(20, 161, 2)
        rest, ans = 180 - x, x // 2
        wrong = [180 - x, (180 - x) // 2, x, 90, abs(90 - x)]
    T = {"apex": ["In an isosceles triangle, the angle between the two equal sides measures {x}°. How many degrees does each of the other two angles measure?",
                  "En un triangle isòsceles, l'angle format pels dos costats iguals mesura {x}°. Quants graus mesura cadascun dels altres dos angles?",
                  "En un triángulo isósceles, el ángulo formado por los dos lados iguales mide {x}°. ¿Cuántos grados mide cada uno de los otros dos ángulos?"],
         "base": ["In an isosceles triangle, each of the two equal angles measures {x}°. How many degrees does the third angle measure?",
                  "En un triangle isòsceles, cadascun dels dos angles iguals mesura {x}°. Quants graus mesura el tercer angle?",
                  "En un triángulo isósceles, cada uno de los dos ángulos iguales mide {x}°. ¿Cuántos grados mide el tercer ángulo?"],
         "obtuse": ["One angle of an isosceles triangle measures {x}°. How many degrees does the smallest angle of the triangle measure?",
                    "Un angle d'un triangle isòsceles mesura {x}°. Quants graus mesura l'angle més petit del triangle?",
                    "Un ángulo de un triángulo isósceles mide {x}°. ¿Cuántos grados mide el ángulo más pequeño del triángulo?"],
         "exterior": ["In an isosceles triangle, the exterior angle at the vertex where the two equal sides meet measures {x}°. How many degrees does each of the other two interior angles measure?",
                      "En un triangle isòsceles, l'angle exterior en el vèrtex on es troben els dos costats iguals mesura {x}°. Quants graus mesura cadascun dels altres dos angles interiors?",
                      "En un triángulo isósceles, el ángulo exterior en el vértice donde se unen los dos lados iguales mide {x}°. ¿Cuántos grados mide cada uno de los otros dos ángulos interiores?"]}[kind][i]
    R = {"apex": ["The three angles add up to 180°, so the other two add up to 180 - {x} = {rest}. They are equal, so each measures {rest}/2 = {ans}.",
                  "Els tres angles sumen 180°, així que els altres dos sumen 180 - {x} = {rest}. Són iguals, de manera que cadascun mesura {rest}/2 = {ans}.",
                  "Los tres ángulos suman 180°, así que los otros dos suman 180 - {x} = {rest}. Son iguales, de modo que cada uno mide {rest}/2 = {ans}."],
         "base": ["The two equal angles add up to 2*{x} = {rest}. The three angles add up to 180°, so the third measures 180 - {rest} = {ans}.",
                  "Els dos angles iguals sumen 2*{x} = {rest}. Els tres angles sumen 180°, així que el tercer mesura 180 - {rest} = {ans}.",
                  "Los dos ángulos iguales suman 2*{x} = {rest}. Los tres ángulos suman 180°, así que el tercero mide 180 - {rest} = {ans}."],
         "obtuse": ["Two angles of {x}° would add up to more than 180°, so {x}° is the angle that is not repeated. The other two are equal and add up to 180 - {x} = {rest}. Each one measures {rest}/2 = {ans}.",
                    "Dos angles de {x}° sumarien més de 180°, així que {x}° és l'angle que no es repeteix. Els altres dos són iguals i sumen 180 - {x} = {rest}. Cadascun mesura {rest}/2 = {ans}.",
                    "Dos ángulos de {x}° sumarían más de 180°, así que {x}° es el ángulo que no se repite. Los otros dos son iguales y suman 180 - {x} = {rest}. Cada uno mide {rest}/2 = {ans}."],
         "exterior": ["The interior angle at that vertex is 180 - {x} = {rest}. The other two angles are equal and add up to 180 - {rest} = {x}. Each one measures {x}/2 = {ans}.",
                      "L'angle interior en aquest vèrtex és 180 - {x} = {rest}. Els altres dos angles són iguals i sumen 180 - {rest} = {x}. Cadascun mesura {x}/2 = {ans}.",
                      "El ángulo interior en ese vértice es 180 - {x} = {rest}. Los otros dos ángulos son iguales y suman 180 - {rest} = {x}. Cada uno mide {x}/2 = {ans}."]}[kind][i]
    return _mk(rng, "isosceles_angle", L, T.format(x=x), ans, wrong, R.format(x=x, rest=rest, ans=ans),
               params=dict(kind=kind, x=x))


_POLY_N = [n for n in range(3, 361) if 360 % n == 0]


def g_regular_polygon(rng, L):
    kind = rng.choice(["interior", "sides_int", "sides_ext", "diagonals", "diagonals", "sum"])
    i = LI[L]
    if kind in ("interior", "sides_int", "sides_ext"):
        n = rng.choice(_POLY_N)
        e = 360 // n
        x = {"interior": n, "sides_int": 180 - e, "sides_ext": e}[kind]
        ans = 180 - e if kind == "interior" else n
        wrong = {"interior": [e, 180 * (n - 2), 180 - 2 * e if 2 * e < 180 else None, _div(180, n), 360 - e, 90],
                 "sides_int": [_div(360, x), e, _div(180, e), n + 2, n - 2 if n > 4 else None, 2 * n],
                 "sides_ext": [180 - x, _div(180, x), 2 * n, n + 2, n - 2 if n > 4 else None, x]}[kind]
        kw = dict(x=x, dex=_de(x), e=e, n=n)
    elif kind == "diagonals":
        n = rng.randint(5, 40)
        x, p = n, n * (n - 3)
        ans = p // 2
        wrong = [p, n * (n - 1) // 2, _div(n * (n - 2), 2), n - 3, n * (n - 1), 2 * n]
        kw = dict(x=n, dex=_de(n), n=n, n3=n - 3, p=p)
    else:
        n = rng.randint(5, 40)
        x = 180 * (n - 2)
        ans = n
        wrong = [n - 2, n - 1, _div(x, 360), _div(x, 90), n + 2, n + 1]
        kw = dict(x=x, dex=_de(x), k=n - 2)
    T = {"interior": ["How many degrees does each interior angle of a regular polygon with {x} sides measure?",
                      "Quants graus mesura cada angle interior d'un polígon regular {dex} costats?",
                      "¿Cuántos grados mide cada ángulo interior de un polígono regular de {x} lados?"],
         "sides_int": ["Each interior angle of a regular polygon measures {x}°. How many sides does the polygon have?",
                       "Cada angle interior d'un polígon regular mesura {x}°. Quants costats té el polígon?",
                       "Cada ángulo interior de un polígono regular mide {x}°. ¿Cuántos lados tiene el polígono?"],
         "sides_ext": ["Each exterior angle of a regular polygon measures {x}°. How many sides does the polygon have?",
                       "Cada angle exterior d'un polígon regular mesura {x}°. Quants costats té el polígon?",
                       "Cada ángulo exterior de un polígono regular mide {x}°. ¿Cuántos lados tiene el polígono?"],
         "diagonals": ["How many diagonals does a convex polygon with {x} sides have?",
                       "Quantes diagonals té un polígon convex {dex} costats?",
                       "¿Cuántas diagonales tiene un polígono convexo de {x} lados?"],
         "sum": ["The interior angles of a convex polygon add up to {x}°. How many sides does the polygon have?",
                 "Els angles interiors d'un polígon convex sumen {x}°. Quants costats té el polígon?",
                 "Los ángulos interiores de un polígono convexo suman {x}°. ¿Cuántos lados tiene el polígono?"]}[kind][i]
    R = {"interior": ["The exterior angles of any convex polygon add up to 360°, so each one measures 360/{n} = {e}. The interior angle is 180 - {e} = {ans}.",
                      "Els angles exteriors de qualsevol polígon convex sumen 360°, així que cadascun mesura 360/{n} = {e}. L'angle interior és 180 - {e} = {ans}.",
                      "Los ángulos exteriores de cualquier polígono convexo suman 360°, así que cada uno mide 360/{n} = {e}. El ángulo interior es 180 - {e} = {ans}."],
         "sides_int": ["Each exterior angle measures 180 - {x} = {e}. The exterior angles add up to 360°, so the number of sides is 360/{e} = {ans}.",
                       "Cada angle exterior mesura 180 - {x} = {e}. Els angles exteriors sumen 360°, així que el nombre de costats és 360/{e} = {ans}.",
                       "Cada ángulo exterior mide 180 - {x} = {e}. Los ángulos exteriores suman 360°, así que el número de lados es 360/{e} = {ans}."],
         "sides_ext": ["The exterior angles of a convex polygon add up to 360°. They are all equal, so the number of sides is 360/{x} = {ans}.",
                       "Els angles exteriors d'un polígon convex sumen 360°. Són tots iguals, així que el nombre de costats és 360/{x} = {ans}.",
                       "Los ángulos exteriores de un polígono convexo suman 360°. Son todos iguales, así que el número de lados es 360/{x} = {ans}."],
         "diagonals": ["From each vertex we can draw a diagonal to every vertex except itself and its 2 neighbours, that is {n3} diagonals. That gives {n}*{n3} = {p}, but each diagonal was counted from its two ends. So there are {p}/2 = {ans}.",
                       "Des de cada vèrtex es pot traçar una diagonal a tots els vèrtexs excepte ell mateix i els seus 2 veïns, és a dir, {n3} diagonals. Això dóna {n}*{n3} = {p}, però cada diagonal s'ha comptat des dels dos extrems. Per tant, n'hi ha {p}/2 = {ans}.",
                       "Desde cada vértice se puede trazar una diagonal a todos los vértices excepto él mismo y sus 2 vecinos, es decir, {n3} diagonales. Eso da {n}*{n3} = {p}, pero cada diagonal se ha contado desde sus dos extremos. Por tanto, hay {p}/2 = {ans}."],
         "sum": ["The interior angles of a polygon with n sides add up to (n - 2)*180°. So n - 2 = {x}/180 = {k}. The polygon has {k} + 2 = {ans} sides.",
                 "Els angles interiors d'un polígon de n costats sumen (n - 2)*180°. Per tant, n - 2 = {x}/180 = {k}. El polígon té {k} + 2 = {ans} costats.",
                 "Los ángulos interiores de un polígono de n lados suman (n - 2)*180°. Por tanto, n - 2 = {x}/180 = {k}. El polígono tiene {k} + 2 = {ans} lados."]}[kind][i]
    return _mk(rng, "regular_polygon", L, T.format(**kw), ans, wrong, R.format(ans=ans, **kw),
               params=dict(kind=kind, x=x))


_TRIPLES = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (9, 40, 41), (12, 35, 37)]


def g_pythagoras(rng, L):
    t = rng.choice(_TRIPLES)
    s = rng.randint(1, 10)
    a, b = rng.sample([t[0] * s, t[1] * s], 2)
    c = t[2] * s
    if c > 75:
        raise Retry()
    kind = rng.choice(["walk", "ladder", "rhombus", "rect"])
    name = rng.choice(NAMES)
    i = LI[L]
    kw = dict(a=a, b=b, c=c, a2=a * a, b2=b * b, c2=c * c, d1=2 * a, d2=2 * b, name=name)
    ans = {"walk": c, "ladder": b, "rhombus": 4 * c, "rect": a * b}[kind]
    wrong = {"walk": [a + b, abs(a - b), (a + b) // 2, c + 1, 2 * c, max(a, b)],
             "ladder": [c - a, c + a, c, (c + a) // 2, a, 2 * b],
             "rhombus": [2 * (a + b), 4 * (a + b), c, 2 * c, 2 * a * b, 8 * c],
             "rect": [a * c, 2 * (a + b), a * b // 2, b * c, c * c, a * (c - a)]}[kind]
    T = {"walk": ["{name} walks {a} m north and then {b} m east. How many metres is {name} from the starting point, in a straight line?",
                  "{name} camina {a} m cap al nord i després {b} m cap a l'est. A quants metres en línia recta es troba del punt de sortida?",
                  "{name} camina {a} m hacia el norte y después {b} m hacia el este. ¿A cuántos metros en línea recta está del punto de partida?"],
         "ladder": ["A ladder {c} dm long leans against a vertical wall. Its foot is {a} dm from the wall. How many decimetres up the wall does the ladder reach?",
                    "Una escala de {c} dm de llargada es recolza en una paret vertical. El peu de l'escala és a {a} dm de la paret. A quants decímetres d'alçada arriba l'escala?",
                    "Una escalera de {c} dm de largo se apoya en una pared vertical. El pie de la escalera está a {a} dm de la pared. ¿A cuántos decímetros de altura llega la escalera?"],
         "rhombus": ["The diagonals of a rhombus measure {d1} cm and {d2} cm. What is the perimeter of the rhombus in centimetres?",
                     "Les diagonals d'un rombe mesuren {d1} cm i {d2} cm. Quin és el perímetre del rombe en centímetres?",
                     "Las diagonales de un rombo miden {d1} cm y {d2} cm. ¿Cuál es el perímetro del rombo en centímetros?"],
         "rect": ["The diagonal of a rectangle measures {c} cm and one of its sides measures {a} cm. What is the area of the rectangle in square centimetres?",
                  "La diagonal d'un rectangle mesura {c} cm i un dels costats mesura {a} cm. Quina és l'àrea del rectangle en centímetres quadrats?",
                  "La diagonal de un rectángulo mide {c} cm y uno de sus lados mide {a} cm. ¿Cuál es el área del rectángulo en centímetros cuadrados?"]}[kind][i]
    R = {"walk": ["The two stretches are the legs of a right triangle. By Pythagoras, the distance squared is {a}^2 + {b}^2 = {a2} + {b2} = {c2}. The distance is the square root of {c2}, which is {ans}.",
                  "Els dos trams són els catets d'un triangle rectangle. Per Pitàgores, el quadrat de la distància és {a}^2 + {b}^2 = {a2} + {b2} = {c2}. La distància és l'arrel quadrada de {c2}, que és {ans}.",
                  "Los dos tramos son los catetos de un triángulo rectángulo. Por Pitágoras, el cuadrado de la distancia es {a}^2 + {b}^2 = {a2} + {b2} = {c2}. La distancia es la raíz cuadrada de {c2}, que es {ans}."],
         "ladder": ["The ladder, the wall and the ground form a right triangle with hypotenuse {c}. By Pythagoras, the height squared is {c}^2 - {a}^2 = {c2} - {a2} = {b2}. The height is the square root of {b2}, which is {ans}.",
                    "L'escala, la paret i el terra formen un triangle rectangle d'hipotenusa {c}. Per Pitàgores, el quadrat de l'alçada és {c}^2 - {a}^2 = {c2} - {a2} = {b2}. L'alçada és l'arrel quadrada de {b2}, que és {ans}.",
                    "La escalera, la pared y el suelo forman un triángulo rectángulo de hipotenusa {c}. Por Pitágoras, el cuadrado de la altura es {c}^2 - {a}^2 = {c2} - {a2} = {b2}. La altura es la raíz cuadrada de {b2}, que es {ans}."],
         "rhombus": ["The diagonals cross at right angles at their midpoints, making right triangles with legs {a} and {b}. By Pythagoras, the side squared is {a2} + {b2} = {c2}, so the side is {c}. The perimeter is 4*{c} = {ans}.",
                     "Les diagonals es tallen perpendicularment pel punt mitjà i formen triangles rectangles de catets {a} i {b}. Per Pitàgores, el quadrat del costat és {a2} + {b2} = {c2}, així que el costat fa {c}. El perímetre és 4*{c} = {ans}.",
                     "Las diagonales se cortan perpendicularmente en su punto medio y forman triángulos rectángulos de catetos {a} y {b}. Por Pitágoras, el cuadrado del lado es {a2} + {b2} = {c2}, así que el lado mide {c}. El perímetro es 4*{c} = {ans}."],
         "rect": ["The diagonal and two sides form a right triangle. By Pythagoras, the other side squared is {c}^2 - {a}^2 = {c2} - {a2} = {b2}, so that side is {b}. The area is {a}*{b} = {ans}.",
                  "La diagonal i dos costats formen un triangle rectangle. Per Pitàgores, el quadrat de l'altre costat és {c}^2 - {a}^2 = {c2} - {a2} = {b2}, així que aquest costat fa {b}. L'àrea és {a}*{b} = {ans}.",
                  "La diagonal y dos lados forman un triángulo rectángulo. Por Pitágoras, el cuadrado del otro lado es {c}^2 - {a}^2 = {c2} - {a2} = {b2}, así que ese lado mide {b}. El área es {a}*{b} = {ans}."]}[kind][i]
    given = {"walk": [a, b], "ladder": [c, a], "rhombus": [2 * a, 2 * b], "rect": [c, a]}[kind]
    return _mk(rng, "pythagoras", L, T.format(**kw), ans, wrong, R.format(ans=ans, **kw),
               params=dict(kind=kind, given=given))


def g_scale_ratio(rng, L):
    kind = rng.choice(["area", "volume", "perimeter"])
    i = LI[L]
    k = rng.randint(2, 5)
    if kind == "area":
        q = rng.randint(6, 60)
        ans = q * k * k
        wrong = [q * k, 2 * q * k, q * k ** 3, q + k * k, q * (k + 1) ** 2, q * k * k // 2]
    elif kind == "volume":
        q = rng.randint(2, 30)
        ans = q * k ** 3
        wrong = [q * k, q * k * k, 3 * q * k, q + k ** 3, q * k * k * 2, 2 * q * k]
    else:
        q = 4 * rng.randint(1, 30)
        ans = q * k
        wrong = [q * k * k, q * k * k // 2, 2 * q * k, q + k, q * k // 2, q * (k + 1)]
    kw = dict(q=q, deq=_de(q), k=k, k2=k * k, k3=k ** 3)
    T = {"area": ["A photo has an area of {q} square centimetres. It is enlarged so that its width and its height are each multiplied by {k}. What is the area of the enlarged photo, in square centimetres?",
                  "Una fotografia té una àrea {deq} centímetres quadrats. S'amplia de manera que l'amplada i l'alçada es multipliquen per {k}. Quina és l'àrea de l'ampliació, en centímetres quadrats?",
                  "Una fotografía tiene un área de {q} centímetros cuadrados. Se amplía de modo que la anchura y la altura se multiplican por {k}. ¿Cuál es el área de la ampliación, en centímetros cuadrados?"],
         "volume": ["A small statue weighs {q} kg. A larger statue of the same shape and the same material is {k} times as tall. How many kilograms does the larger statue weigh?",
                    "Una estàtua petita pesa {q} kg. Una estàtua més gran, de la mateixa forma i del mateix material, té {k} vegades l'alçada de la petita. Quants quilograms pesa l'estàtua gran?",
                    "Una estatua pequeña pesa {q} kg. Una estatua más grande, de la misma forma y del mismo material, tiene {k} veces la altura de la pequeña. ¿Cuántos kilogramos pesa la estatua grande?"],
         "perimeter": ["The area of a large square is {k2} times the area of a small square. The perimeter of the small square is {q} cm. What is the perimeter of the large square in centimetres?",
                       "L'àrea d'un quadrat gran és {k2} vegades l'àrea d'un quadrat petit. El perímetre del quadrat petit fa {q} cm. Quin és el perímetre del quadrat gran en centímetres?",
                       "El área de un cuadrado grande es {k2} veces el área de un cuadrado pequeño. El perímetro del cuadrado pequeño mide {q} cm. ¿Cuál es el perímetro del cuadrado grande en centímetros?"]}[kind][i]
    R = {"area": ["When every length is multiplied by {k}, the area is multiplied by {k}^2 = {k2}. The new area is {q}*{k2} = {ans}.",
                  "Quan totes les longituds es multipliquen per {k}, l'àrea es multiplica per {k}^2 = {k2}. L'àrea nova és {q}*{k2} = {ans}.",
                  "Cuando todas las longitudes se multiplican por {k}, el área se multiplica por {k}^2 = {k2}. El área nueva es {q}*{k2} = {ans}."],
         "volume": ["When every length is multiplied by {k}, the volume, and so the weight, is multiplied by {k}^3 = {k3}. The larger statue weighs {q}*{k3} = {ans}.",
                    "Quan totes les longituds es multipliquen per {k}, el volum, i per tant el pes, es multiplica per {k}^3 = {k3}. L'estàtua gran pesa {q}*{k3} = {ans}.",
                    "Cuando todas las longitudes se multiplican por {k}, el volumen, y por tanto el peso, se multiplica por {k}^3 = {k3}. La estatua grande pesa {q}*{k3} = {ans}."],
         "perimeter": ["If the area is multiplied by {k2}, every length is multiplied by the square root of {k2}, which is {k}. The perimeter is a length, so it is {q}*{k} = {ans}.",
                       "Si l'àrea es multiplica per {k2}, totes les longituds es multipliquen per l'arrel quadrada de {k2}, que és {k}. El perímetre és una longitud, així que fa {q}*{k} = {ans}.",
                       "Si el área se multiplica por {k2}, todas las longitudes se multiplican por la raíz cuadrada de {k2}, que es {k}. El perímetro es una longitud, así que mide {q}*{k} = {ans}."]}[kind][i]
    return _mk(rng, "scale_ratio", L, T.format(**kw), ans, wrong, R.format(ans=ans, **kw),
               params=dict(kind=kind, q=q, factor=k * k if kind == "perimeter" else k))


def g_painted_cuboid(rng, L):
    a, b, c = rng.randint(3, 9), rng.randint(3, 9), rng.randint(3, 9)
    j = rng.randrange(3)
    i = LI[L]
    a2, b2, c2 = a - 2, b - 2, c - 2
    s = a2 * b2 + a2 * c2 + b2 * c2
    ans = [a2 * b2 * c2, 2 * s, 4 * (a2 + b2 + c2)][j]
    if ans < 2:
        raise Retry()
    ph = [("have no painted face", "no tenen cap cara pintada", "no tienen ninguna cara pintada"),
          ("have exactly one painted face", "tenen exactament una cara pintada", "tienen exactamente una cara pintada"),
          ("have exactly two painted faces", "tenen exactament dues cares pintades", "tienen exactamente dos caras pintadas")][j][i]
    text = pick(rng, {
        "eng": ["A wooden block measuring {a} cm by {b} cm by {c} cm is painted on all its faces and then cut into cubes of side 1 cm. How many of these small cubes {ph}?"],
        "cat": ["Un bloc de fusta de {a} cm per {b} cm per {c} cm es pinta per totes les cares i després es talla en cubs d'1 cm d'aresta. Quants d'aquests cubs petits {ph}?"],
        "esp": ["Un bloque de madera de {a} cm por {b} cm por {c} cm se pinta por todas las caras y después se corta en cubos de 1 cm de arista. ¿Cuántos de estos cubos pequeños {ph}?"]},
        L, a=a, b=b, c=c, ph=ph)
    R = [["The unpainted cubes are the inner ones, after removing one layer from every side. They form a block of {a2} by {b2} by {c2}. So there are {a2}*{b2}*{c2} = {ans}.",
          "Els cubs sense pintar són els interiors, després de treure una capa de cada costat. Formen un bloc {da2} per {b2} per {c2}. Per tant, n'hi ha {a2}*{b2}*{c2} = {ans}.",
          "Los cubos sin pintar son los interiores, tras quitar una capa de cada lado. Forman un bloque de {a2} por {b2} por {c2}. Por tanto, hay {a2}*{b2}*{c2} = {ans}."],
         ["Cubes with one painted face lie in the middle of a face, away from the edges. The three pairs of opposite faces give 2*({a2}*{b2} + {a2}*{c2} + {b2}*{c2}) = 2*{s} = {ans}.",
          "Els cubs amb una cara pintada són al mig d'una cara, lluny de les arestes. Els tres parells de cares oposades donen 2*({a2}*{b2} + {a2}*{c2} + {b2}*{c2}) = 2*{s} = {ans}.",
          "Los cubos con una cara pintada están en el centro de una cara, lejos de las aristas. Los tres pares de caras opuestas dan 2*({a2}*{b2} + {a2}*{c2} + {b2}*{c2}) = 2*{s} = {ans}."],
         ["Cubes with two painted faces lie along the edges, away from the corners. There are 4 edges of each length, with {a2}, {b2} and {c2} such cubes. So there are 4*({a2} + {b2} + {c2}) = {ans}.",
          "Els cubs amb dues cares pintades són al llarg de les arestes, lluny dels vèrtexs. Hi ha 4 arestes de cada longitud, amb {a2}, {b2} i {c2} cubs d'aquests. Per tant, n'hi ha 4*({a2} + {b2} + {c2}) = {ans}.",
          "Los cubos con dos caras pintadas están a lo largo de las aristas, lejos de los vértices. Hay 4 aristas de cada longitud, con {a2}, {b2} y {c2} cubos de estos. Por tanto, hay 4*({a2} + {b2} + {c2}) = {ans}."]][j][i]
    rat = R.format(a2=a2, b2=b2, c2=c2, da2=_de(a2), s=s, ans=ans)
    wrong = [[a * b * c, (a - 1) * (b - 1) * (c - 1), a * b * c - 2 * (a * b + a * c + b * c), 2 * s, a2 * b2 * c2 + 8],
             [s, 2 * (a * b + a * c + b * c), 6 * a2 * b2, a2 * b2 * c2, 4 * (a2 + b2 + c2)],
             [a2 + b2 + c2, 4 * (a + b + c), 12, 2 * s, 2 * (a2 + b2 + c2), 8]][j]
    return _mk(rng, "painted_cuboid", L, text, ans, wrong, rat, params=dict(a=a, b=b, c=c, faces=j))


def g_cube_measures(rng, L):
    s = rng.randint(2, 30)
    kind = rng.choice(["s2v", "v2s", "e2v", "e2s"])
    i = LI[L]
    f, S, V, E = s * s, 6 * s * s, s ** 3, 12 * s
    x = {"s2v": S, "v2s": V, "e2v": E, "e2s": E}[kind]
    ans = V if kind in ("s2v", "e2v") else S
    wrong = {"s2v": [f, 3 * f, s, 2 * V, S * s, f * 4],
             "v2s": [f, 4 * f, 6 * s, 12 * s, V, 2 * S],
             "e2v": [f, S, 3 * s, (2 * s) ** 3, s, E * s],
             "e2s": [f, V, 4 * f, 12 * s * s, 6 * s, 2 * f]}[kind]
    T = {"s2v": ["The total surface area of a cube is {x} square centimetres. What is its volume in cubic centimetres?",
                 "La superfície total d'un cub és de {x} centímetres quadrats. Quin és el seu volum en centímetres cúbics?",
                 "La superficie total de un cubo es de {x} centímetros cuadrados. ¿Cuál es su volumen en centímetros cúbicos?"],
         "v2s": ["The volume of a cube is {x} cubic centimetres. What is its total surface area in square centimetres?",
                 "El volum d'un cub és de {x} centímetres cúbics. Quina és la seva superfície total en centímetres quadrats?",
                 "El volumen de un cubo es de {x} centímetros cúbicos. ¿Cuál es su superficie total en centímetros cuadrados?"],
         "e2v": ["The lengths of all the edges of a cube add up to {x} cm. What is its volume in cubic centimetres?",
                 "Les longituds de totes les arestes d'un cub sumen {x} cm. Quin és el seu volum en centímetres cúbics?",
                 "Las longitudes de todas las aristas de un cubo suman {x} cm. ¿Cuál es su volumen en centímetros cúbicos?"],
         "e2s": ["The lengths of all the edges of a cube add up to {x} cm. What is its total surface area in square centimetres?",
                 "Les longituds de totes les arestes d'un cub sumen {x} cm. Quina és la seva superfície total en centímetres quadrats?",
                 "Las longitudes de todas las aristas de un cubo suman {x} cm. ¿Cuál es su superficie total en centímetros cuadrados?"]}[kind][i]
    R = {"s2v": ["The cube has 6 equal faces, so each face has area {x}/6 = {f}. The edge is the square root of {f}, which is {s}. The volume is {s}^3 = {ans}.",
                 "El cub té 6 cares iguals, així que cada cara té àrea {x}/6 = {f}. L'aresta és l'arrel quadrada de {f}, que és {s}. El volum és {s}^3 = {ans}.",
                 "El cubo tiene 6 caras iguales, así que cada cara tiene área {x}/6 = {f}. La arista es la raíz cuadrada de {f}, que es {s}. El volumen es {s}^3 = {ans}."],
         "v2s": ["The edge is the cube root of {x}, which is {s}, because {s}*{s}*{s} = {x}. Each face has area {s}^2 = {f}. The 6 faces give 6*{f} = {ans}.",
                 "L'aresta és l'arrel cúbica de {x}, que és {s}, perquè {s}*{s}*{s} = {x}. Cada cara té àrea {s}^2 = {f}. Les 6 cares donen 6*{f} = {ans}.",
                 "La arista es la raíz cúbica de {x}, que es {s}, porque {s}*{s}*{s} = {x}. Cada cara tiene área {s}^2 = {f}. Las 6 caras dan 6*{f} = {ans}."],
         "e2v": ["The cube has 12 equal edges, so each edge measures {x}/12 = {s}. The volume is {s}^3 = {ans}.",
                 "El cub té 12 arestes iguals, així que cada aresta fa {x}/12 = {s}. El volum és {s}^3 = {ans}.",
                 "El cubo tiene 12 aristas iguales, así que cada arista mide {x}/12 = {s}. El volumen es {s}^3 = {ans}."],
         "e2s": ["The cube has 12 equal edges, so each edge measures {x}/12 = {s}. Each face has area {s}^2 = {f}, and the 6 faces give 6*{f} = {ans}.",
                 "El cub té 12 arestes iguals, així que cada aresta fa {x}/12 = {s}. Cada cara té àrea {s}^2 = {f}, i les 6 cares donen 6*{f} = {ans}.",
                 "El cubo tiene 12 aristas iguales, así que cada arista mide {x}/12 = {s}. Cada cara tiene área {s}^2 = {f}, y las 6 caras dan 6*{f} = {ans}."]}[kind][i]
    return _mk(rng, "cube_measures", L, T.format(x=x), ans, wrong, R.format(x=x, f=f, s=s, ans=ans),
               params=dict(kind=kind, x=x))


def g_rect_square(rng, L):
    kind = rng.choice(["ratio", "same", "cut"])
    i = LI[L]
    if kind == "ratio":
        k, w = rng.randint(2, 5), rng.randint(2, 15)
        P, ln = 2 * w * (k + 1), k * w
        ans = w * ln
        kw = dict(k=k, P=P, m=2 * (k + 1), w=w, l=ln)
        wrong = [w * w, ln * ln, P * k, (P // (k + 1)) * (k * P // (k + 1)), 2 * ans, _div(P * P, 16)]
        params = dict(kind=kind, k=k, P=P)
    elif kind == "same":
        w, h = sorted(rng.sample(range(2, 31), 2))
        if (w + h) % 2:
            raise Retry()
        P, s = 2 * (w + h), (w + h) // 2
        ans = s * s
        kw = dict(w=w, dew=_de(w), h=h, P=P, s=s)
        wrong = [w * h, (w + h) ** 2, P, 4 * s, w * w, h * h]
        params = dict(kind=kind, w=w, h=h)
    else:
        n, t = rng.randint(2, 5), rng.randint(1, 12)
        s, P = n * t, 2 * t * (n + 1)
        ans = 4 * s
        kw = dict(n=n, P=P, m=2 * (n + 1), t=t, s=s)
        wrong = [n * P, 2 * P, P, 4 * t, s * s, n * P - 2 * s * (n - 1) + 2]
        params = dict(kind=kind, n=n, P=P)
    T = {"ratio": ["The length of a rectangle is {k} times its width, and its perimeter is {P} cm. What is its area in square centimetres?",
                   "La llargada d'un rectangle és {k} vegades la seva amplada, i el seu perímetre és de {P} cm. Quina és la seva àrea en centímetres quadrats?",
                   "El largo de un rectángulo es {k} veces su ancho, y su perímetro es de {P} cm. ¿Cuál es su área en centímetros cuadrados?"],
         "same": ["A square has the same perimeter as a rectangle measuring {w} cm by {h} cm. What is the area of the square in square centimetres?",
                  "Un quadrat té el mateix perímetre que un rectangle {dew} cm per {h} cm. Quina és l'àrea del quadrat en centímetres quadrats?",
                  "Un cuadrado tiene el mismo perímetro que un rectángulo de {w} cm por {h} cm. ¿Cuál es el área del cuadrado en centímetros cuadrados?"],
         "cut": ["A square is cut into {n} equal rectangles by straight cuts parallel to one of its sides. Each rectangle has a perimeter of {P} cm. What is the perimeter of the square in centimetres?",
                 "Un quadrat es talla en {n} rectangles iguals amb talls rectes paral·lels a un dels costats. Cada rectangle té un perímetre de {P} cm. Quin és el perímetre del quadrat en centímetres?",
                 "Un cuadrado se corta en {n} rectángulos iguales con cortes rectos paralelos a uno de sus lados. Cada rectángulo tiene un perímetro de {P} cm. ¿Cuál es el perímetro del cuadrado en centímetros?"]}[kind][i]
    R = {"ratio": ["Call the width w, so the length is {k}w and the perimeter is 2*(w + {k}w) = {m}w. Then w = {P}/{m} = {w} and the length is {l}. The area is {w}*{l} = {ans}.",
                   "Anomenem w l'amplada: la llargada és {k}w i el perímetre és 2*(w + {k}w) = {m}w. Llavors w = {P}/{m} = {w} i la llargada és {l}. L'àrea és {w}*{l} = {ans}.",
                   "Llamamos w al ancho: el largo es {k}w y el perímetro es 2*(w + {k}w) = {m}w. Entonces w = {P}/{m} = {w} y el largo es {l}. El área es {w}*{l} = {ans}."],
         "same": ["The rectangle has perimeter 2*({w} + {h}) = {P}. The side of the square is {P}/4 = {s}. Its area is {s}^2 = {ans}.",
                  "El rectangle té perímetre 2*({w} + {h}) = {P}. El costat del quadrat és {P}/4 = {s}. La seva àrea és {s}^2 = {ans}.",
                  "El rectángulo tiene perímetro 2*({w} + {h}) = {P}. El lado del cuadrado es {P}/4 = {s}. Su área es {s}^2 = {ans}."],
         "cut": ["Call the short side of a rectangle t, so its long side, the side of the square, is {n}t. The perimeter of a rectangle is 2*(t + {n}t) = {m}t = {P}, so t = {t} and the square has side {s}. Its perimeter is 4*{s} = {ans}.",
                 "Anomenem t el costat curt d'un rectangle: el costat llarg, que és el costat del quadrat, fa {n}t. El perímetre d'un rectangle és 2*(t + {n}t) = {m}t = {P}, així que t = {t} i el quadrat té costat {s}. El seu perímetre és 4*{s} = {ans}.",
                 "Llamamos t al lado corto de un rectángulo: el lado largo, que es el lado del cuadrado, mide {n}t. El perímetro de un rectángulo es 2*(t + {n}t) = {m}t = {P}, así que t = {t} y el cuadrado tiene lado {s}. Su perímetro es 4*{s} = {ans}."]}[kind][i]
    return _mk(rng, "rect_square", L, T.format(**kw), ans, wrong, R.format(ans=ans, **kw), params=params)


def g_clock_angle(rng, L):
    h, m = rng.randint(1, 12), rng.randrange(0, 60, 2)
    h0 = h % 12
    am, ah = 6 * m, 30 * h0 + m // 2
    raw = abs(am - ah)
    ans = min(raw, 360 - raw)
    if ans in (0, 180):
        raise Retry()
    i = LI[L]
    t = f"{h}:{m:02d}"
    art = ["", "la" if h == 1 else "les", "la" if h == 1 else "las"][i]
    text = pick(rng, {
        "eng": ["What is the smaller angle, in degrees, between the hour hand and the minute hand of a clock at {t}?",
                "It is {t} on a clock with hands. How many degrees is the smaller angle between the two hands?"],
        "cat": ["Quants graus mesura l'angle més petit que formen l'agulla de les hores i la dels minuts d'un rellotge a {art} {t}?",
                "Un rellotge d'agulles marca {art} {t}. Quants graus mesura l'angle més petit entre les dues agulles?"],
        "esp": ["¿Cuántos grados mide el ángulo más pequeño que forman la aguja de las horas y la de los minutos de un reloj a {art} {t}?",
                "Un reloj de agujas marca {art} {t}. ¿Cuántos grados mide el ángulo más pequeño entre las dos agujas?"]},
        L, t=t, art=art)
    tail = "" if raw == ans else [", and the smaller angle is 360 - {raw} = {ans}", ", i l'angle més petit és 360 - {raw} = {ans}",
                                  ", y el ángulo más pequeño es 360 - {raw} = {ans}"][i]
    r = {"eng": "Measured from the 12, the minute hand is at 6*{m} = {am}°. The hour hand is at 30*{h0} + {m}/2 = {ah}°, since it moves half a degree per minute. The difference is {raw}°" + tail + ".",
         "cat": "Mesurant des del 12, l'agulla dels minuts és a 6*{m} = {am}°. La de les hores és a 30*{h0} + {m}/2 = {ah}°, perquè avança mig grau per minut. La diferència és {raw}°" + tail + ".",
         "esp": "Midiendo desde el 12, la aguja de los minutos está en 6*{m} = {am}°. La de las horas está en 30*{h0} + {m}/2 = {ah}°, porque avanza medio grado por minuto. La diferencia es {raw}°" + tail + "."}[L]
    rat = r.format(m=m, am=am, h0=h0, ah=ah, raw=raw, ans=ans)
    flat = abs(30 * h0 - am)
    wrong = [min(flat, 360 - flat), 360 - ans, max(flat, 360 - flat), ans + m // 2, abs(ans - m // 2), 180 - ans]
    return _mk(rng, "clock_angle", L, text, ans, wrong, rat, params=dict(h=h, m=m))


# ----- logic, checked by exhaustive search

def _stmt_true(st, speaker, culprit):
    kind, x, y = st
    return {"is": culprit == x, "not": culprit != x, "notme": culprit != speaker, "me": culprit == speaker,
            "or": culprit in (x, y)}[kind]


def g_truth_one(rng, L):
    names = rng.sample(NAMES, 5)
    one_true = rng.random() < 0.6
    need = 1 if one_true else 4
    i = LI[L]
    for _ in range(80):
        stmts = []
        for sp_ in range(5):
            others = [j for j in range(5) if j != sp_]
            kind = rng.choice(["is", "is", "not", "not", "notme", "or", "me"])
            x, y = rng.sample(others, 2)
            stmts.append([kind, x, y] if kind == "or" else [kind, x, -1] if kind in ("is", "not") else [kind, -1, -1])
        counts = [sum(_stmt_true(st, sp_, c) for sp_, st in enumerate(stmts)) for c in range(5)]
        fit = [c for c in range(5) if counts[c] == need]
        if len(fit) == 1 and sum(st[0] == "me" for st in stmts) <= 1:
            break
    else:
        raise Retry()
    culprit = fit[0]
    S = {"is": ("It was {x}.", "Ha estat {x}.", "Ha sido {x}."),
         "not": ("It was not {x}.", "No ha estat {x}.", "No ha sido {x}."),
         "notme": ("It was not me.", "Jo no he estat.", "Yo no he sido."),
         "me": ("It was me.", "He estat jo.", "He sido yo."),
         "or": ("It was {x} or {y}.", "Ha estat {x} o {y}.", "Ha sido {x} o {y}.")}
    said = " ".join('{}: "{}"'.format(names[sp_], S[st[0]][i].format(x=names[st[1]], y=names[st[2]]))
                    for sp_, st in enumerate(stmts))
    cond = [("Exactly one of the five statements is true.", "Exactly one of the five statements is false."),
            ("Exactament una de les cinc afirmacions és certa.", "Exactament una de les cinc afirmacions és falsa."),
            ("Exactamente una de las cinco afirmaciones es verdadera.", "Exactamente una de las cinco afirmaciones es falsa.")][i][0 if one_true else 1]
    text = pick(rng, {
        "eng": ["One of five friends ate the last piece of cake. {said} {cond} Who ate the cake?"],
        "cat": ["Un dels cinc amics s'ha menjat l'últim tros de pastís. {said} {cond} Qui s'ha menjat el pastís?"],
        "esp": ["Uno de cinco amigos se ha comido el último trozo de tarta. {said} {cond} ¿Quién se ha comido la tarta?"]},
        L, said=said, cond=cond)
    shown = [c if one_true else 5 - c for c in counts]
    tally = ", ".join(f"{names[c]} {shown[c]}" for c in range(5))
    r = [("Count the true statements for each possible culprit: {tally}. Only with {ans} is exactly one statement true. So it was {ans}.",
          "Count the false statements for each possible culprit: {tally}. Only with {ans} is exactly one statement false. So it was {ans}."),
         ("Comptem les afirmacions certes per a cada possible culpable: {tally}. Només amb {ans} n'hi ha exactament una de certa. Per tant, ha estat {ans}.",
          "Comptem les afirmacions falses per a cada possible culpable: {tally}. Només amb {ans} n'hi ha exactament una de falsa. Per tant, ha estat {ans}."),
         ("Contamos las afirmaciones verdaderas para cada posible culpable: {tally}. Solo con {ans} hay exactamente una verdadera. Por tanto, ha sido {ans}.",
          "Contamos las afirmaciones falsas para cada posible culpable: {tally}. Solo con {ans} hay exactamente una falsa. Por tanto, ha sido {ans}.")][i][0 if one_true else 1]
    ans = names[culprit]
    rat = r.format(tally=tally, ans=ans)
    wrong = [n for n in names if n != ans]
    return _mk(rng, "truth_one", L, text, ans, wrong, rat, numeric=False,
               params=dict(names=names, statements=stmts, true_count=need))


def _clue_ok(clue, order):
    kind, x, y = clue
    px = order.index(x)
    if kind == "notlast":
        return px != len(order) - 1
    if kind == "notfirst":
        return px != 0
    py = order.index(y)
    return {"before": px < py, "just": px + 1 == py, "between": abs(px - py) == 2}[kind]


def _orders_fitting(names, clues):
    return [list(p) for p in _permutations(names) if all(_clue_ok(c, p) for c in clues)]


def _permutations(xs):
    if len(xs) <= 1:
        yield tuple(xs)
        return
    for k in range(len(xs)):
        for rest in _permutations(xs[:k] + xs[k + 1:]):
            yield (xs[k],) + rest


def g_order_clues(rng, L):
    order = rng.sample(NAMES, 5)
    base = sorted(order)
    pool = []
    for p in range(5):
        for q in range(p + 1, 5):
            pool.append(["before", order[p], order[q]])
            if q == p + 1:
                pool.append(["just", order[p], order[q]])
            if q == p + 2:
                pool.append(["between"] + rng.sample([order[p], order[q]], 2))
    pool += [["notlast", n, ""] for n in order[:4]] + [["notfirst", n, ""] for n in order[1:]]
    rng.shuffle(pool)
    clues = []
    for cl in pool:
        clues.append(cl)
        if len(_orders_fitting(base, clues)) == 1:
            break
    for cl in clues[:]:
        fewer = [c for c in clues if c is not cl]
        if len(_orders_fitting(base, fewer)) == 1:
            clues = fewer
    if not 3 <= len(clues) <= 6 or _orders_fitting(base, clues) != [order]:
        raise Retry()
    i = LI[L]
    C = {"before": ("{x} finished before {y}.", "{x} va arribar abans que {y}.", "{x} llegó antes que {y}."),
         "just": ("{x} finished immediately before {y}.", "{x} va arribar just abans que {y}.", "{x} llegó justo antes que {y}."),
         "between": ("Exactly one swimmer finished between {x} and {y}.", "Entre {x} i {y} va arribar exactament un nedador.",
                     "Entre {x} y {y} llegó exactamente un nadador."),
         "notlast": ("{x} did not finish last.", "{x} no va arribar en últim lloc.", "{x} no llegó en último lugar."),
         "notfirst": ("{x} did not win.", "{x} no va guanyar.", "{x} no ganó.")}
    pos = rng.randint(1, 5)
    o = [("first", "second", "third", "fourth", "fifth"), ("primera", "segona", "tercera", "quarta", "cinquena"),
         ("primera", "segunda", "tercera", "cuarta", "quinta")][i][pos - 1]
    shown = order[:]
    rng.shuffle(shown)
    text = pick(rng, {
        "eng": ["{ns} swam in a final with no ties. {cl} Who finished in {o} place?"],
        "cat": ["{ns} van nedar una final sense empats. {cl} Qui va arribar en {o} posició?"],
        "esp": ["{ns} nadaron una final sin empates. {cl} ¿Quién llegó en {o} posición?"]},
        L, ns=_join(shown, L), cl=" ".join(C[k][i].format(x=x, y=y) for k, x, y in clues), o=o)
    ans = order[pos - 1]
    r = {"eng": "From the clues, the only possible finishing order is {order}. So the swimmer in {o} place is {ans}.",
         "cat": "Segons les pistes, l'únic ordre d'arribada possible és {order}. Per tant, qui va arribar en {o} posició és {ans}.",
         "esp": "Con las pistas, el único orden de llegada posible es {order}. Por tanto, quien llegó en {o} posición es {ans}."}[L]
    rat = r.format(order=", ".join(order), o=o, ans=ans)
    wrong = [n for n in order if n != ans]
    return _mk(rng, "order_clues", L, text, ans, wrong, rat, numeric=False,
               params=dict(names=shown, clues=clues, pos=pos))


_REGISTRY = [
    ("shopping", g_shopping), ("ages", g_ages), ("sharing", g_sharing),
    ("fraction_two_step", g_fraction_two_step), ("percent_discount", g_percent_discount),
    ("rect_area", g_rect_area), ("l_shape_area", g_l_shape_area), ("handshakes", g_handshakes),
    ("outfits", g_outfits), ("line_up_together", g_line_up_together), ("grid_routes", g_grid_routes),
    ("multiples_in_range", g_multiples_in_range), ("remainder", g_remainder),
    ("digit_sum_count", g_digit_sum_count), ("arithmetic_sequence", g_arithmetic_sequence),
    ("color_pattern", g_color_pattern), ("film_end_time", g_film_end_time),
    ("weekday_shift", g_weekday_shift), ("average_missing", g_average_missing),
    ("ribbon_pieces", g_ribbon_pieces), ("number_think", g_number_think), ("race_logic", g_race_logic),
    ("ratio_mix", g_ratio_mix), ("speed_minutes", g_speed_minutes), ("coin_count", g_coin_count),
]
# grades 9-12 (number theory, algebra, counting and probability, geometry in words, logic)
HARD_NAMES = []


def _register_hard(*fns):
    for fn in fns:
        _REGISTRY.append((fn.__name__[2:], fn))
        HARD_NAMES.append(fn.__name__[2:])


_register_hard(g_divisor_count, g_last_digit_power, g_gcd_lcm, g_consecutive_sum, g_digit_extreme,
               g_remainder_ops, g_count_div_digit,
               g_two_equations, g_sum_product_squares, g_power_simplify, g_successive_percent,
               g_average_speed, g_mean_change, g_inequality_count, g_geometric_sequence, g_arith_two_terms,
               g_arrangements_restricted, g_committee, g_dice_probability, g_balls_probability, g_routes_via,
               g_numbers_from_digits,
               g_isosceles_angle, g_regular_polygon, g_pythagoras, g_scale_ratio, g_painted_cuboid,
               g_cube_measures, g_rect_square, g_clock_angle,
               g_truth_one, g_order_clues)
GENERATORS = dict(_REGISTRY)
GENERATOR_NAMES = [n for n, _ in _REGISTRY]


def generate(name, rng, lang):
    """One problem from the named generator; redraws the numbers until they are clean."""
    fn = GENERATORS[name]
    for _ in range(200):
        try:
            return fn(rng, lang)
        except Retry:
            continue
    raise RuntimeError(f"{name}: no clean draw in 200 tries")
