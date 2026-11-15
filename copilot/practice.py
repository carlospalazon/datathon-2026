"""'One like this, but yours': a fresh practice problem of the same kind, with the mistake named.

After a wrong answer (or when the student asks), the tutor makes a new problem of the
same topic as the one on screen. Its numbers are drawn on the spot, its answer is
computed, and most wrong options are the result of one known slip, so the feedback can
say which slip it was without a language model and without giving the answer.

The problems come from the generators of the model lab (laptop/synthetic_problems.py),
which this module only imports. A generator does not say which slip made each wrong
option, so MISTAKES below works the slips out again from the numbers drawn (`params`).
A wrong option that matches none of them gets no mistake name: better silent than wrong.

    practice = Practice("cat")
    view = practice.new("aritmetica")   # text and options, never the answer; None if no generator fits
    practice.answer("B")                # {"correct": False, "mistake": {"text": ..., "code": ...}, ...}
    practice.solution()                 # only when the student asks for it

Standard library only. Nothing here touches the student memory or the tutor's session.
"""
import importlib.util
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__))
# On the laptop the generators live in laptop/; applab/package.py copies them next to this file.
GENERATOR_PATHS = (os.path.join(HERE, "synthetic_problems.py"),
                   os.path.join(os.path.dirname(HERE), "laptop", "synthetic_problems.py"))

# Generators a 5th or 6th year student can solve in about a minute, by tutor topic.
# Topics without an honest match (visual, geometria_espacial, otros) get no practice.
TOPICS = {
    "aritmetica": ["shopping", "sharing", "fraction_two_step", "average_missing"],
    "algebra": ["number_think", "coin_count", "ages"],
    "conteo": ["outfits", "handshakes"],
    "numeros": ["remainder", "multiples_in_range"],
    "patrones": ["arithmetic_sequence"],
    "geometria_plana": ["rect_area", "l_shape_area"],
    "medida": ["ribbon_pieces", "film_end_time"],
    "logica": ["race_logic"],
}
DRAWS = 8  # problems drawn each time; the one with the smallest numbers is shown


def load_generators():
    """The model lab's generator module, or None if it isn't on this machine."""
    for path in GENERATOR_PATHS:
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("synthetic_problems", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
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
        "counted_twice": ("Aquí cada encaixada s'ha comptat dues vegades, una per cada persona.",
                          "Here every handshake was counted twice, once for each person."),
        "one_person": ("Aquestes són les encaixades d'una sola persona. Et demanen les de tot el grup.",
                       "These are one person's handshakes. The question asks for the whole group's."),
    },
    "remainder": {
        "quotient": ("Aquest és el quocient: quantes vegades hi cap. El residu és el que sobra.",
                     "This is the quotient: how many times it fits. The remainder is what is left over."),
        "missing_to_next": ("Això és el que falta per arribar al múltiple següent. El residu és el que sobra de l'anterior.",
                            "This is what is missing to reach the next multiple. The remainder is what is left over from the one before."),
        "divisor": ("Aquest és el nombre pel qual divideixes. El residu sempre és més petit.",
                    "This is the number you divide by. The remainder is always smaller."),
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


def _size(problem):
    """How big the numbers of a problem are: the practice problem shown is the smallest drawn."""
    return max([int(n) for n in re.findall(r"\d+", problem["text"])] or [0])


class Practice:
    """One practice problem at a time, apart from the tutor's own session."""

    def __init__(self, language="cat", seed=None, generators=None):
        self.language = language if language in ("cat", "eng") else "eng"
        self.generators = generators if generators is not None else load_generators()
        self.rng = random.Random(seed)
        self.turn = {}       # topic -> how many practice problems made, to rotate the kinds
        self.shown = set()   # texts already shown: never the same problem twice
        self.count = 0
        self.current = None

    def available(self, topic):
        return self.generators is not None and topic in TOPICS

    def new(self, topic):
        """A fresh problem of this topic as the page may see it, or None if no generator fits."""
        if not self.available(topic):
            return None
        names = TOPICS[topic]
        name = names[self.turn.get(topic, 0) % len(names)]
        self.turn[topic] = self.turn.get(topic, 0) + 1
        draws = [self.generators.generate(name, random.Random(self.rng.random()), self.language)
                 for _ in range(DRAWS)]
        fresh = [d for d in draws if d["text"] not in self.shown] or draws
        # Prefer a draw whose wrong options can be named, then the smallest numbers
        problem = min(fresh, key=lambda d: (-min(len(mistakes(d)), 3), _size(d)))
        self.shown.add(problem["text"])
        self.count += 1
        self.current = {"problem": problem, "mistakes": mistakes(problem), "attempts": [],
                        "topic": topic, "n": self.count}
        return {"n": self.count, "topic": topic, "kind": name, "text": problem["text"],
                "options": problem["options"], "events": [{"event": "letter", "value": "?"}]}

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
        else:
            code = s["mistakes"].get(letter)
            texts = MESSAGES[problem["generator"]][code] if code else CHECK.get(problem["generator"], NO_NAME)
            result["mistake"] = {"text": texts[self.language == "eng"], "code": code, "status": "regla",
                                 "source": f"practice {problem['generator']}"}
        return result

    def solution(self):
        """The answer and the worked solution: only when the student asks for it."""
        problem = self._session()["problem"]
        return {"label": problem["label"], "answer": problem["answer"], "text": problem["rationale"],
                "events": [{"event": "letter", "value": problem["label"]}]}
