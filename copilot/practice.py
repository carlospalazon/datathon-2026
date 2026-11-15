"""'One like this, but yours': a fresh practice problem of the same kind, with the mistake named.

After a wrong answer (or when the student asks), the tutor makes a new problem of the
same topic as the one on screen. Its numbers are drawn on the spot, its answer is
computed, and most wrong options are the result of one known slip, so the feedback can
say which slip it was without a language model and without giving the answer.

The problems come from the generators of the model lab (laptop/synthetic_problems.py),
which this module only imports, and for the picture topics from copilot/pictures.py, whose
problems carry a figure the page draws. A generator of the model lab does not say which slip made each wrong
option, so MISTAKES below works the slips out again from the numbers drawn (`params`).
A wrong option that matches none of them gets no mistake name: better silent than wrong.

    practice = Practice("cat")
    view = practice.new("aritmetica")   # text and options, never the answer; None if no generator fits
    practice.answer("B")                # {"correct": False, "mistake": {"text": ..., "code": ...}, ...}
    practice.solution()                 # only when the student asks for it

"Explain it back": after a right answer the student picks, with one tap, which of three short
explanations matches how they solved it: the method of the worked solution and two wrong
methods, which are slips of the same generator whose results for these numbers are known
(METHODS). It is only offered where that can be done honestly: two different slips that give
two different wrong numbers for this draw. It never counts against the student.

    result = practice.answer("C")       # right: result["explain"] = [{"id": 0, "text": ...}, ...] or absent
    practice.explain(1)                 # {"correct": False, "right": 2, "text": ...}

Standard library only. Nothing here touches the student memory or the tutor's session.
"""
import importlib.util
import os
import random
import re

from . import pictures

HERE = os.path.dirname(os.path.abspath(__file__))
# On the laptop the generators live in laptop/; applab/package.py copies them next to this file.
GENERATOR_PATHS = (os.path.join(HERE, "synthetic_problems.py"),
                   os.path.join(os.path.dirname(HERE), "laptop", "synthetic_problems.py"))

# Generators a 5th or 6th year student can solve in about a minute, by tutor topic.
# The picture topics (visual, geometria_espacial) come from copilot/pictures.py, with a figure.
# A topic without an honest match (otros) gets no practice.
TOPICS = {
    **pictures.TOPICS,
    "aritmetica": ["shopping", "sharing", "fraction_two_step", "average_missing"],
    "algebra": ["number_think", "coin_count", "ages"],
    "conteo": ["outfits", "handshakes"],
    "numeros": ["remainder", "multiples_in_range"],
    "patrones": ["arithmetic_sequence"],
    "geometria_plana": ["rect_area", "l_shape_area"],
    "medida": ["film_end_time", "ribbon_pieces"],
    "logica": ["race_logic"],
}
DRAWS = 8  # problems drawn each time; the one with the smallest numbers is shown


def load_generators():
    """The model lab's generator module, or None if it isn't on this machine."""
    for path in GENERATOR_PATHS:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("synthetic_problems", path)
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception:  # noqa: BLE001  a generator file mid-edit turns practice off, not the tutor
                return None
            return module
    return None


# --- The slip behind each wrong option ------------------------------------------------
# One function per generator: params -> (the right answer, [(wrong value, code), ...]).
# The right answer is worked out again here so a test can tell when a generator changed.

def _exact(a, b):
    return a // b if b and a % b == 0 else None


def _shopping(p):
    total = p["a"] * p["p"] + p["b"] * p["q"]
    both = p["a"] + p["b"]
    return p["pay"] - total, [
        (p["pay"] - p["a"] * p["p"], "one_purchase"), (p["pay"] - p["b"] * p["q"], "one_purchase"),
        (total, "spent_not_change"),
        (p["pay"] - both * p["p"], "same_price"), (p["pay"] - both * p["q"], "same_price"),
        (p["pay"] + total, "added_spent")]


def _sharing(p):
    rest = p["n"] - p["m"]
    return rest // p["k"], [
        (_exact(p["n"], p["k"]), "shared_all"), (rest, "not_shared_yet"),
        (_exact(rest, p["k"] + 1), "one_share_more")]


def _fraction_two_step(p):
    first = p["N"] * p["a"] // p["b"]
    rest = p["N"] - first
    second = rest * p["c"] // p["d"]
    of_whole = _exact(p["N"] * p["c"], p["d"])
    return rest - second, [
        (rest, "after_first_day"), (second, "second_day_used"),
        (None if of_whole is None else p["N"] - first - of_whole, "fraction_of_whole"),
        (first + second, "used_not_left"), (p["N"] - second, "first_day_forgotten")]


def _average_missing(p):
    known = sum(p["s"])
    return 5 * p["m"] - known, [
        (p["m"], "the_mean"), (4 * p["m"] - known, "four_games"), (_exact(known, 4), "mean_of_four")]


def _number_think(p):
    result = p["k"] * p["x"] + (p["m"] if p["add"] else -p["m"])
    repeated = result + p["m"] if p["add"] else result - p["m"]
    return p["x"], [
        (_exact(repeated, p["k"]), "not_undone"), (_exact(result, p["k"]), "step_skipped"),
        (p["k"] * p["x"], "one_step_undone")]


def _coin_count(p):
    twos = p["S"] - p["n"]
    return twos, [(p["n"] - twos, "other_coins"), (_exact(p["S"], 2), "all_twos")]


def _ages(p):
    return p["y"], [
        (p["y"] + p["d"], "older_one"), (p["y"] + p["k"], "future_age"),
        (_exact(p["S"] - 2 * p["k"], 2), "same_age"), (None if p["S"] % 2 else p["S"] // 2 - p["k"], "same_age")]


def _outfits(p):
    a, b, c = p["a"], p["b"], p["c"]
    return a * b * c, [
        (a + b + c, "added_choices"), (a * b, "two_of_three"),
        (a * b + c, "added_one_kind"), (a * c + b, "added_one_kind"), ((a + b) * c, "added_one_kind")]


def _handshakes(p):
    n = p["n"]
    return n * (n - 1) // 2, [(n * (n - 1), "counted_twice"), (n - 1, "one_person")]


def _remainder(p):
    left = p["N"] % p["k"]
    return left, [(p["N"] // p["k"], "quotient"), (p["k"] - left, "missing_to_next"), (p["k"], "divisor")]


def _multiples_in_range(p):
    k, lo, hi = p["k"], p["lo"], p["hi"]
    return hi // k - (lo - 1) // k, [
        (hi // k, "from_one"), (hi // k - lo // k, "first_left_out"), ((hi - lo) // k, "range_length")]


def _arithmetic_sequence(p):
    a, d, n = p["a"], p["d"], p["n"]
    return a + (n - 1) * d, [
        (a + n * d, "step_too_many"), (a + (n - 2) * d, "step_too_few"),
        (n * d, "start_forgotten"), (a + (n - 1), "step_of_one")]


def _rect_area(p):
    w, h = p["w"], p["h"]
    perimeter = 2 * (w + h)
    return w * h, [
        (w * (perimeter - w), "one_side_off"), (w * (w + h), "half_is_two_sides"),
        (w * w, "square"), (perimeter, "perimeter")]


def _l_shape_area(p):
    W, H, w, h = p["W"], p["H"], p["w"], p["h"]
    return W * H - w * h, [
        (W * H, "whole_rectangle"), (W * H + w * h, "corner_added"), ((W - w) * (H - h), "sides_shortened"),
        (2 * (W + H), "perimeter"), (W * H - w - h, "lengths_subtracted"), (W * H - 2 * w * h, "corner_twice")]


def _ribbon_pieces(p):
    metres, cm = divmod(p["total"], 100)
    return p["total"] // p["z"], [
        (_exact(10 * metres + cm, p["z"]), "metre_is_ten"),
        (_exact(100 * metres, p["z"]) if cm else None, "cm_forgotten")]


def _clock(minutes):
    minutes %= 24 * 60
    return f"{minutes // 60}:{minutes % 60:02d}"


def _film_end_time(p):
    end = p["start"] + p["dur"]
    return _clock(end), ([(_clock(end + d), "hour_off") for d in (60, -60)]
                         + [(_clock(end + d), "minutes_off") for d in (10, -10, 20, -20, 30, -30)])


MISTAKES = {
    **pictures.MISTAKES,
    "shopping": _shopping, "sharing": _sharing, "fraction_two_step": _fraction_two_step,
    "average_missing": _average_missing, "number_think": _number_think, "coin_count": _coin_count,
    "ages": _ages, "outfits": _outfits, "handshakes": _handshakes, "remainder": _remainder,
    "multiples_in_range": _multiples_in_range, "arithmetic_sequence": _arithmetic_sequence,
    "rect_area": _rect_area, "l_shape_area": _l_shape_area, "ribbon_pieces": _ribbon_pieces,
    "film_end_time": _film_end_time,
}

# What each slip is, as a fact about the number chosen: (Catalan, English). No numbers in
# the text, so it can never contain the answer. Catalan written by the team: needs a native read.
MESSAGES = {
    **pictures.MESSAGES,
    "shopping": {
        "one_purchase": ("Aquest és el canvi si només es pagués una de les dues coses. S'han de pagar totes dues.",
                         "This is the change if only one of the two things were paid for. Both have to be paid."),
        "spent_not_change": ("Això és el que costa tot plegat. Et demanen el que tornen.",
                             "This is what everything costs. The question is how much comes back."),
        "same_price": ("Aquí totes les coses s'han comptat al mateix preu. Cada tipus té el seu preu.",
                       "Here every item was counted at the same price. Each kind has its own price."),
        "added_spent": ("Aquí el que s'ha gastat s'ha sumat als diners lliurats. El canvi és el que sobra.",
                        "Here what was spent was added to the money handed over. Change is what is left."),
    },
    "sharing": {
        "shared_all": ("Aquest és el resultat si es reparteix tot, sense treure primer el que s'aparta.",
                       "This is the result of sharing all of them, without first taking away the ones set aside."),
        "not_shared_yet": ("Això és el que queda per repartir. Encara falta repartir-ho.",
                           "These are the ones left to share. They still have to be shared out."),
        "one_share_more": ("Aquí s'ha repartit entre una persona de més. Compta bé entre quants es reparteix.",
                           "Here the sharing was among one person too many. Check how many people share."),
    },
    "fraction_two_step": {
        "after_first_day": ("Això és el que queda després del primer dia. Encara falta el segon.",
                            "This is what is left after the first day. The second day is still missing."),
        "second_day_used": ("Això és el que es gasta el segon dia. Et demanen el que queda.",
                            "This is what is used on the second day. The question is what is left."),
        "fraction_of_whole": ("Aquí la segona fracció s'ha calculat sobre tot el dipòsit. És una fracció del que quedava.",
                              "Here the second fraction was taken of the whole tank. It is a fraction of what was left."),
        "used_not_left": ("Això és tot el que s'ha gastat. Et demanen el que queda.",
                          "This is everything that was used. The question is what is left."),
        "first_day_forgotten": ("Aquí només s'ha restat el que es gasta el segon dia. El primer dia també se'n gasta.",
                                "Here only the second day's use was taken away. Some is used on the first day too."),
    },
    "average_missing": {
        "the_mean": ("Aquesta és la mitjana, no els punts de l'última partida.",
                     "This is the average, not the points of the last game."),
        "four_games": ("Aquí la mitjana s'ha multiplicat pel nombre de partides que ja saps. Compta-les totes.",
                       "Here the average was multiplied by the number of games you already know. Count all of them."),
        "mean_of_four": ("Aquesta és la mitjana de les partides que ja saps. La mitjana del problema és la de totes.",
                         "This is the average of the games you already know. The average in the problem is of all of them."),
    },
    "number_think": {
        "not_undone": ("Aquí l'últim pas s'ha tornat a fer en lloc de desfer-lo. Per tornar enrere cal l'operació contrària.",
                       "Here the last step was done again instead of undone. Going back needs the opposite operation."),
        "step_skipped": ("Aquí només s'ha desfet la multiplicació. Abans cal desfer l'altre pas.",
                         "Here only the multiplication was undone. The other step has to be undone first."),
        "one_step_undone": ("Aquest és el nombre abans de l'últim pas. Encara falta desfer la multiplicació.",
                            "This is the number before the last step. The multiplication still has to be undone."),
    },
    "coin_count": {
        "other_coins": ("Aquestes són les monedes de l'altre tipus. Mira quines et demanen.",
                        "These are the coins of the other kind. Check which ones the question asks for."),
        "all_twos": ("Aquest és el nombre de monedes si totes fossin de dos euros. N'hi ha dels dos tipus.",
                     "This is the number of coins if all were two-euro coins. There are coins of both kinds."),
    },
    "ages": {
        "older_one": ("Aquesta és l'edat de l'altra persona. Mira de qui et demanen l'edat.",
                      "This is the other person's age. Check whose age the question asks for."),
        "future_age": ("Aquesta és l'edat que tindrà d'aquí a uns anys. Et demanen la d'ara.",
                       "This is the age in a few years. The question asks for the age now."),
        "same_age": ("Aquí la suma s'ha partit per la meitat, com si tinguessin la mateixa edat. Un és més gran.",
                     "Here the sum was split in half, as if both had the same age. One of them is older."),
    },
    "outfits": {
        "added_choices": ("Aquí les opcions s'han sumat. Per cada opció d'un tipus pots triar totes les de l'altre.",
                          "Here the choices were added. For each choice of one kind you can pick every choice of the next."),
        "two_of_three": ("Això són les combinacions de només dues de les tres coses. Falta triar la tercera.",
                         "These are the combinations of only two of the three things. The third still has to be chosen."),
        "added_one_kind": ("Aquí dues coses s'han multiplicat i la tercera s'ha sumat. La tercera també multiplica.",
                           "Here two things were multiplied and the third was added. The third multiplies too."),
    },
    "handshakes": {
        "counted_twice": ("Aquí cada parella s'ha comptat dues vegades, una per cada persona.",
                          "Here every pair was counted twice, once for each person."),
        "one_person": ("Això és el que fa una sola persona. Et demanen el total de tot el grup.",
                       "This is what one person alone does. The question asks for the total of the whole group."),
    },
    "remainder": {
        "quotient": ("Aquest és el nombre de grups sencers que es fan. Et demanen el que sobra.",
                     "This is the number of full groups. The question asks for what is left over."),
        "missing_to_next": ("Això és el que falta per completar un grup més. Et demanen el que sobra.",
                            "This is what is missing to complete one more group. The question asks for what is left over."),
        "divisor": ("Aquesta és la mida de cada grup. El que sobra sempre és més petit.",
                    "This is the size of each group. What is left over is always smaller."),
    },
    "multiples_in_range": {
        "from_one": ("Aquests són tots els múltiples començant per l'u. Els d'abans del començament no hi compten.",
                     "These are all the multiples starting from one. The ones before the start do not count."),
        "first_left_out": ("Aquí falta un múltiple: el primer nombre de l'interval també ho és.",
                           "One multiple is missing here: the first number of the range is one too."),
        "range_length": ("Aquí s'ha dividit la llargada de l'interval. Mira bé què passa als dos extrems.",
                         "Here the length of the range was divided. Look carefully at what happens at both ends."),
    },
    "arithmetic_sequence": {
        "step_too_many": ("Aquí s'ha fet un pas de més. Des del primer nombre, quants passos calen?",
                          "Here one step too many was taken. From the first number, how many steps are needed?"),
        "step_too_few": ("Aquí falta un pas. Des del primer nombre, quants passos calen?",
                         "One step is missing here. From the first number, how many steps are needed?"),
        "start_forgotten": ("Aquí només s'han comptat els passos. La llista no comença al zero.",
                            "Here only the steps were counted. The list does not start at zero."),
        "step_of_one": ("Aquí cada pas ha sumat u. Mira quant suma cada pas.",
                        "Here every step added one. Check how much each step adds."),
    },
    "rect_area": {
        "one_side_off": ("Aquí al perímetre se li ha restat un sol costat. El perímetre té dos costats de cada mida.",
                         "Here one side was taken from the perimeter. The perimeter has two sides of each length."),
        "half_is_two_sides": ("Aquí la meitat del perímetre s'ha fet servir com a costat. La meitat són els dos costats diferents junts.",
                              "Here half the perimeter was used as a side. Half is the two different sides together."),
        "square": ("Aquesta és l'àrea si fos un quadrat. L'altre costat pot ser diferent.",
                   "This is the area if it were a square. The other side may be different."),
        "perimeter": ("Aquest és el perímetre. Et demanen l'àrea.", "This is the perimeter. The question asks for the area."),
    },
    "l_shape_area": {
        "whole_rectangle": ("Aquesta és l'àrea del rectangle sencer. Falta treure la cantonada tallada.",
                            "This is the area of the whole rectangle. The cut corner still has to come off."),
        "corner_added": ("Aquí l'àrea de la cantonada s'ha sumat. La cantonada es talla.",
                         "Here the area of the corner was added. The corner is cut away."),
        "sides_shortened": ("Aquí s'han escurçat els dos costats. Només es talla una cantonada, no una franja sencera.",
                            "Here both sides were shortened. Only a corner is cut, not a whole strip."),
        "perimeter": ("Aquest és el perímetre del rectangle. Et demanen l'àrea.",
                      "This is the perimeter of the rectangle. The question asks for the area."),
        "lengths_subtracted": ("Aquí s'han restat les mides de la cantonada. El que es resta és la seva àrea.",
                               "Here the lengths of the corner were taken away. What comes off is its area."),
        "corner_twice": ("Aquí la cantonada s'ha tret dues vegades. Només es talla una vegada.",
                         "Here the corner was taken off twice. It is cut only once."),
    },
    "ribbon_pieces": {
        "metre_is_ten": ("Aquí un metre s'ha comptat com a deu centímetres. Quants centímetres té un metre?",
                         "Here a metre was counted as ten centimetres. How many centimetres are in a metre?"),
        "cm_forgotten": ("Aquí només s'han comptat els metres. Els centímetres de més també són cinta.",
                         "Here only the metres were counted. The extra centimetres are ribbon too."),
    },
    "film_end_time": {
        "hour_off": ("Els minuts són bons, però hi ha una hora de diferència. Quantes hores senceres dura?",
                     "The minutes are right, but it is one hour off. How many whole hours does it last?"),
        "minutes_off": ("Molt a prop: la diferència és de mitja hora o menys. Suma primer les hores senceres i després els minuts.",
                        "Very close: it is half an hour off or less. Add the whole hours first, then the minutes."),
    },
}
NO_NAME = ("Aquest resultat no surt de cap dels errors habituals. Repassa els càlculs pas a pas.",
           "This result does not come from any of the usual slips. Go over your working step by step.")


# "Explain it back": how the problem is solved ("right") and how each slip is made, told as the
# student would tell it: (Catalan, English). No numbers, as above. Only slips that are a way of
# solving get a sentence (not "one step too few", and nothing for the film times, whose wrong
# options are distances from the answer, or for the race, whose wrong options are not slips).
# Catalan written by the team: needs a native read.
METHODS = {
    **pictures.METHODS,
    "shopping": {
        "right": ("He calculat el que costa cada tipus de cosa, ho he sumat i ho he restat dels diners lliurats.",
                  "I worked out what each kind of thing costs, added the two and took that from the money handed over."),
        "one_purchase": ("He restat dels diners lliurats el que costa un dels dos tipus de cosa.",
                         "I took what one of the two kinds of thing costs from the money handed over."),
        "spent_not_change": ("He calculat el que costa cada tipus de cosa i ho he sumat. Aquest total és la resposta.",
                             "I worked out what each kind of thing costs and added the two. That total is the answer."),
        "same_price": ("He comptat totes les coses juntes, les he multiplicat per un dels preus i ho he restat dels diners lliurats.",
                       "I counted all the things together, multiplied by one of the prices and took that from the money handed over."),
        "added_spent": ("He calculat el que costa tot i ho he sumat als diners lliurats.",
                        "I worked out what everything costs and added it to the money handed over."),
    },
    "sharing": {
        "right": ("He tret primer els que es guarden i he repartit els que queden.",
                  "I first took away the ones set aside and shared out the ones left."),
        "shared_all": ("He repartit tots els que hi havia al principi, sense treure'n cap.",
                       "I shared out all the ones there were at the start, without taking any away."),
        "not_shared_yet": ("He restat els que es guarden dels que hi havia. Aquesta resta és la resposta.",
                           "I took the ones set aside from the ones there were. That difference is the answer."),
        "one_share_more": ("He tret els que es guarden i he repartit la resta comptant una persona més.",
                           "I took away the ones set aside and shared the rest counting one person more."),
    },
    "fraction_two_step": {
        "right": ("He restat el que es gasta el primer dia. Del que quedava, n'he calculat la segona fracció i també l'he restada.",
                  "I took away what is used on the first day. Of what was left I worked out the second fraction and took that away too."),
        "after_first_day": ("He calculat el que es gasta el primer dia i ho he restat del total. Això és el que queda.",
                            "I worked out what is used on the first day and took it from the total. That is what is left."),
        "second_day_used": ("He mirat què quedava després del primer dia i n'he calculat la segona fracció. Aquest resultat és la resposta.",
                            "I found what was left after the first day and worked out the second fraction of it. That result is the answer."),
        "fraction_of_whole": ("He calculat les dues fraccions sobre la quantitat del principi i les he restades totes dues.",
                              "I worked out both fractions of the amount at the start and took both away."),
        "used_not_left": ("He sumat el que es gasta el primer dia i el que es gasta el segon.",
                          "I added what is used on the first day and what is used on the second."),
        "first_day_forgotten": ("He restat del total només el que es gasta el segon dia.",
                                "I took only what is used on the second day from the total."),
    },
    "average_missing": {
        "right": ("He multiplicat la mitjana pel nombre total de partides i n'he restat els punts de les que ja sabia.",
                  "I multiplied the average by the total number of games and took away the points of the games I knew."),
        "the_mean": ("He pensat que l'última partida ha de ser com la mitjana i he respost la mitjana.",
                     "I thought the last game must be like the average and answered the average."),
        "four_games": ("He multiplicat la mitjana pel nombre de partides que ja sabia i n'he restat els seus punts.",
                       "I multiplied the average by the number of games I knew and took away their points."),
        "mean_of_four": ("He fet la mitjana de les partides que ja sabia.",
                         "I worked out the average of the games I knew."),
    },
    "number_think": {
        "right": ("He desfet els passos del final cap al principi, cadascun amb l'operació contrària.",
                  "I undid the steps from the last to the first, each with the opposite operation."),
        "not_undone": ("He començat pel resultat, hi he tornat a fer l'últim pas tal com el diu l'enunciat i després he dividit.",
                       "I started from the result, did the last step again as the problem says it, and then divided."),
        "step_skipped": ("He dividit el resultat pel nombre que multiplica, i prou.",
                         "I divided the result by the number that multiplies, and that was all."),
        "one_step_undone": ("He desfet només l'últim pas, el de sumar o restar.",
                            "I undid only the last step, the adding or taking away."),
    },
    "coin_count": {
        "right": ("He imaginat que totes les monedes eren de les petites i he mirat quants euros faltaven: cada euro que falta és una moneda de les grans.",
                  "I imagined every coin was a small one and saw how many euros were missing: each missing euro is one of the big coins."),
        "other_coins": ("He trobat quantes monedes hi ha de cada tipus i he respost les de menys valor.",
                        "I found how many coins there are of each kind and answered the ones worth less."),
        "all_twos": ("He dividit els diners totals pel valor de la moneda gran.",
                     "I divided the total money by the value of the big coin."),
    },
    "ages": {
        "right": ("He tret de la suma els anys que passaran per a tots dos i després la diferència d'edat, i n'he fet la meitat.",
                  "I took from the sum the years that will pass for both, then the age difference, and halved what was left."),
        "older_one": ("He trobat les dues edats d'avui i he respost la de la persona més gran.",
                      "I found both ages today and answered the older person's."),
        "future_age": ("He trobat l'edat que tindrà d'aquí a uns anys i he respost aquesta.",
                       "I found the age in a few years' time and answered that one."),
        "same_age": ("He tret de la suma els anys que passaran i l'he partida per la meitat, com si tinguessin la mateixa edat.",
                     "I took from the sum the years that will pass and split it in half, as if both had the same age."),
    },
    "outfits": {
        "right": ("He multiplicat les opcions de les tres coses, perquè cada tria es pot combinar amb totes les altres.",
                  "I multiplied the choices of the three things, because each choice goes with every other one."),
        "added_choices": ("He sumat les opcions de les tres coses.", "I added the choices of the three things."),
        "two_of_three": ("He multiplicat les opcions de dues de les coses, i prou.",
                         "I multiplied the choices of two of the things, and that was all."),
        "added_one_kind": ("He multiplicat les opcions de dues coses i hi he sumat les de la tercera.",
                           "I multiplied the choices of two things and added those of the third."),
    },
    "handshakes": {
        "right": ("He multiplicat el nombre de persones pels altres que té cadascuna, i ho he dividit entre dos perquè cada parella surt dues vegades.",
                  "I multiplied the number of people by the others each one has, and halved it because every pair comes up twice."),
        "counted_twice": ("He multiplicat el nombre de persones pels altres que té cadascuna, i prou.",
                          "I multiplied the number of people by the others each one has, and that was all."),
        "one_person": ("He comptat amb quants altres tracta una persona.", "I counted how many others one person deals with."),
    },
    "remainder": {
        "right": ("He buscat el múltiple més gran que no es passa i he mirat quant falta fins al nombre.",
                  "I looked for the largest multiple that does not go past and saw how far it is from the number."),
        "quotient": ("He fet la divisió i he respost quantes vegades hi cap.",
                     "I did the division and answered how many times it fits."),
        "missing_to_next": ("He mirat quant falta per arribar al múltiple següent.",
                            "I saw how much is missing to reach the next multiple."),
    },
    "multiples_in_range": {
        "right": ("He comptat els múltiples que hi ha fins al final i n'he tret els que hi ha abans del començament.",
                  "I counted the multiples up to the end and took away the ones before the start."),
        "from_one": ("He comptat tots els múltiples que hi ha fins al final, des de l'u.",
                     "I counted all the multiples up to the end, from one."),
        "range_length": ("He restat els dos extrems i he dividit la diferència.",
                         "I took one end from the other and divided the difference."),
    },
    "arithmetic_sequence": {
        "right": ("Des del primer nombre he fet un pas menys que la posició que demanen, i cada pas suma el mateix.",
                  "From the first number I took one step fewer than the position asked for, and every step adds the same."),
        "step_too_many": ("Des del primer nombre he fet tants passos com diu la posició.",
                          "From the first number I took as many steps as the position says."),
        "start_forgotten": ("He multiplicat la posició pel que suma cada pas.",
                            "I multiplied the position by what each step adds."),
    },
    "rect_area": {
        "right": ("He fet la meitat del perímetre, n'he restat el costat que sé per trobar l'altre, i he multiplicat els dos costats.",
                  "I halved the perimeter, took away the side I know to find the other, and multiplied the two sides."),
        "one_side_off": ("He restat del perímetre el costat que sé i he multiplicat el resultat per aquest costat.",
                         "I took the side I know from the perimeter and multiplied the result by that side."),
        "half_is_two_sides": ("He fet la meitat del perímetre i l'he multiplicada pel costat que sé.",
                              "I halved the perimeter and multiplied it by the side I know."),
        "square": ("He multiplicat el costat que sé per ell mateix.", "I multiplied the side I know by itself."),
    },
    "l_shape_area": {
        "right": ("He calculat l'àrea del rectangle sencer i n'he restat l'àrea de la cantonada tallada.",
                  "I worked out the area of the whole rectangle and took away the area of the cut corner."),
        "whole_rectangle": ("He multiplicat els dos costats del rectangle gran, i prou.",
                            "I multiplied the two sides of the big rectangle, and that was all."),
        "corner_added": ("He calculat l'àrea del rectangle sencer i hi he sumat la de la cantonada.",
                         "I worked out the area of the whole rectangle and added the corner's."),
        "sides_shortened": ("He escurçat cada costat del rectangle amb la mida de la cantonada i he multiplicat els costats nous.",
                            "I shortened each side of the rectangle by the corner's length and multiplied the new sides."),
        "lengths_subtracted": ("He calculat l'àrea del rectangle sencer i n'he restat les dues mides de la cantonada.",
                               "I worked out the area of the whole rectangle and took away the corner's two lengths."),
    },
    "ribbon_pieces": {
        "right": ("Ho he passat tot a centímetres i he dividit per la llargada d'un tros.",
                  "I turned everything into centimetres and divided by the length of one piece."),
        "metre_is_ten": ("He comptat cada metre com a deu centímetres, ho he sumat tot i he dividit per la llargada d'un tros.",
                         "I counted each metre as ten centimetres, added it all up and divided by the length of one piece."),
        "cm_forgotten": ("He passat els metres a centímetres, he deixat de banda els centímetres de més i he dividit.",
                         "I turned the metres into centimetres, left the extra centimetres aside and divided."),
    },
}
# What the tutor says after the tap: (Catalan, English). The numbers go in with format().
EXPLAINED = {
    True: ("Sí: aquest és el camí que porta a la resposta.", "Yes: that is the way that leads to the answer."),
    False: ("Amb aquest camí sortiria {value}, i tu has trobat {answer}, que és la resposta bona. "
            "El camí que hi porta és el que ara veus marcat.",
            "That way would give {value}, and you found {answer}, which is the right answer. "
            "The way that leads to it is the one now marked."),
}


def explanations(problem, rng=random):
    """Three ways of solving a generated problem, in a random order: the one of the worked solution
    and two slips that give two different wrong numbers for this draw. None where that cannot be
    done honestly. Each is {"code": "right" or the slip, "value": the number that way gives}."""
    methods, rule = METHODS.get(problem["generator"]), MISTAKES.get(problem["generator"])
    if not methods or not rule:
        return None
    answer, slips = rule(problem["params"])
    if str(answer) != problem["answer"]:  # the generator changed: ask nothing rather than something wrong
        return None
    shown = set(problem["options"].values())
    wrong = {}  # slip -> the number it gives; where a slip can give two, the one among the options
    for value, code in slips:
        if value is None or code not in methods or str(value) == problem["answer"] or str(value).startswith("-"):
            continue
        if code not in wrong or (str(value) in shown and str(wrong[code]) not in shown):
            wrong[code] = value
    picked, values = [], set()
    # First the slips whose number the student has just seen among the options
    for code in sorted(wrong, key=lambda c: (str(wrong[c]) not in shown, rng.random())):
        if str(wrong[code]) not in values and len(picked) < 2:
            picked.append({"code": code, "value": str(wrong[code])})
            values.add(str(wrong[code]))
    if len(picked) < 2:
        return None
    items = [{"code": "right", "value": problem["answer"]}] + picked
    rng.shuffle(items)
    return items


# Generators whose wrong options are not slips: a way to check, instead of a mistake name
CHECK = {"race_logic": ("Escriu els cinc noms en ordre i comprova que cada pista es compleix.",
                        "Write the five names in order and check that every clue holds.")}


def mistakes(problem):
    """{option letter: code} for the wrong options of a generated problem that a known slip explains."""
    rule = MISTAKES.get(problem["generator"])
    if rule is None:
        return {}
    answer, slips = rule(problem["params"])
    if str(answer) != problem["answer"]:  # the generator changed: say nothing rather than something wrong
        return {}
    found = {}
    for letter, value in problem["options"].items():
        if letter == problem["label"]:
            continue
        for slip, code in slips:
            if slip is not None and str(slip) == value != problem["answer"]:
                found[letter] = code
                break
    return found


def make(generators, name, rng, language):
    """One problem of this kind: from our own picture generators, or from the model lab's."""
    if name in pictures.GENERATORS:
        return pictures.generate(name, rng, language)
    return generators.generate(name, rng, language)


def _same(problem):
    """What makes two problems the same one: the text, and for a picture problem its figure too."""
    return problem["text"] + repr(problem.get("figure", ""))


def _size(problem):
    """How big the numbers of a problem are: the practice problem shown is the smallest drawn."""
    if problem.get("figure"):  # a picture problem has its numbers in the figure: the fewer to count, the smaller
        return int(problem["answer"])
    return max([int(n) for n in re.findall(r"\d+", problem["text"])] or [0])


class Practice:
    """One practice problem at a time, apart from the tutor's own session."""

    def __init__(self, language="cat", seed=None, generators=None):
        self.language = language if language in ("cat", "eng") else "eng"
        self.generators = generators if generators is not None else load_generators()
        self.rng = random.Random(seed)
        self.turn = {}       # topic -> how many practice problems made, to rotate the kinds
        self.shown = set()   # problems already shown (text and figure): never the same one twice
        self.count = 0
        self.current = None

    def _kinds(self, topic):
        """The kinds of problem that can be made for a topic here: the picture kinds always, the
        others when the model lab's generators are on this machine."""
        return [name for name in TOPICS.get(topic, [])
                if name in pictures.GENERATORS or self.generators is not None]

    def available(self, topic):
        return bool(self._kinds(topic))

    def new(self, topic):
        """A fresh problem of this topic as the page may see it, or None if no generator fits."""
        names = self._kinds(topic)
        if not names:
            return None
        name = names[self.turn.get(topic, 0) % len(names)]
        self.turn[topic] = self.turn.get(topic, 0) + 1
        draws = [make(self.generators, name, random.Random(self.rng.random()), self.language)
                 for _ in range(DRAWS)]
        fresh = [d for d in draws if _same(d) not in self.shown] or draws
        # Prefer a draw whose wrong options can be named, then the smallest numbers
        problem = min(fresh, key=lambda d: (-min(len(mistakes(d)), 3), _size(d)))
        self.shown.add(_same(problem))
        self.count += 1
        self.current = {"problem": problem, "mistakes": mistakes(problem), "attempts": [],
                        "topic": topic, "n": self.count, "shown": False, "explain": None, "explained": None}
        view = {"n": self.count, "topic": topic, "kind": name, "text": problem["text"],
                "options": problem["options"], "events": [{"event": "letter", "value": "?"}]}
        if problem.get("figure"):  # a picture problem: what the page needs to draw it, never the answer
            view["figure"] = problem["figure"]
        return view

    def _session(self):
        if self.current is None:
            raise RuntimeError("no practice problem yet")
        return self.current

    def answer(self, letter):
        letter = str(letter).strip().upper()
        if len(letter) != 1 or letter not in "ABCDE":
            raise ValueError("answer with one letter, A to E")
        s = self._session()
        problem = s["problem"]
        correct = letter == problem["label"]
        s["attempts"].append(letter)
        result = {"correct": correct, "attempts": len(s["attempts"]), "mistake": None,
                  "events": [{"event": "tick" if correct else "cross"}]}
        if correct:  # solved: now the worked solution is theirs to compare with
            result["solution"] = problem["rationale"]
            if s["explain"] is None and not s["shown"]:  # "explain it back", where it can be asked honestly
                s["explain"] = explanations(problem, self.rng) or []
            if s["explain"] and s["explained"] is None:
                texts = METHODS[problem["generator"]]
                result["explain"] = [{"id": i, "text": texts[item["code"]][self.language == "eng"]}
                                     for i, item in enumerate(s["explain"])]
        else:
            code = s["mistakes"].get(letter)
            texts = MESSAGES[problem["generator"]][code] if code else CHECK.get(problem["generator"], NO_NAME)
            result["mistake"] = {"text": texts[self.language == "eng"], "code": code, "status": "regla",
                                 "source": f"practice {problem['generator']}"}
        return result

    def solution(self):
        """The answer and the worked solution: only when the student asks for it."""
        s = self._session()
        problem = s["problem"]
        s["shown"] = True  # the method has been read: no "explain it back" for this one
        return {"label": problem["label"], "answer": problem["answer"], "text": problem["rationale"],
                "events": [{"event": "letter", "value": problem["label"]}]}

    def explain(self, choice):
        """The student's one tap: which of the three explanations is how they solved it. It checks
        understanding and never counts against them: no cross, and a second tap is refused."""
        s = self._session()
        if not s["explain"] or s["problem"]["label"] not in s["attempts"]:
            raise ValueError("nothing to explain yet")
        if s["explained"] is not None:
            raise ValueError("already explained")
        try:
            picked = s["explain"][int(choice)] if int(choice) >= 0 else None
        except (TypeError, ValueError, IndexError):
            picked = None
        if picked is None:
            raise ValueError("choose one of the explanations")
        correct = picked["code"] == "right"
        s["explained"] = correct
        text = EXPLAINED[correct][self.language == "eng"].format(value=picked["value"], answer=s["problem"]["answer"])
        return {"correct": correct, "picked": int(choice), "text": text, "status": "regla",
                "right": next(i for i, item in enumerate(s["explain"]) if item["code"] == "right"),
                "events": [{"event": "tick"}] if correct else []}
