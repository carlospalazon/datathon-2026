"""Practice problems for the picture topics: the figure is drawn by the page from parameters.

Three kinds, each with a computed answer and wrong options that are the result of one named
slip, in the same shape as the model lab's generators (laptop/synthetic_problems.py, which
this module neither imports nor edits), plus "figure": what the page needs to draw it as
inline SVG. No image file, no M3Kang data.

  stair_squares  (visual)              a staircase of small squares: how many squares?
  folded_strip   (visual)              a strip folded in a zigzag and cut through all its layers
                                       along dotted lines: how many pieces?
  cube_stack     (geometria_espacial)  cubes piled in a corner, drawn from above and in front:
                                       how many cubes, the hidden ones too?

Every figure can be read without doubt: the stair is drawn square by square; the strip shows
every layer and every cut; and the cube piles never get taller towards the viewer, so the top
of every pile is in sight and, with no holes, the count is settled.

    problem = pictures.generate("cube_stack", random.Random(1), "cat")
    problem["figure"]    # {"kind": "cubes", "heights": [[3, 2], [1, 1]]}
    pictures.MISTAKES["cube_stack"](problem["params"])   # (the answer, [(wrong value, slip code), ...])

MISTAKES, MESSAGES and METHODS are read by copilot/practice.py, which names the slip behind a
wrong option and asks "how did you solve it?". Standard library only, no model.
"""

LETTERS = "ABCDE"


# --- The numbers: the answer and what each slip gives -----------------------------------------

def stair_cells(heights):
    """The squares of the staircase as (column, row), row 0 at the bottom."""
    return [(c, r) for c, h in enumerate(heights) for r in range(h)]


def _stair_squares(p):
    heights = p["heights"]
    total = sum(heights)
    return total, [
        (len(heights) * max(heights), "whole_rectangle"),
        (2 * (len(heights) + max(heights)), "perimeter"),
        (len(heights), "top_squares"),
        (total - len(heights), "row_missing")]


def strip_cut_points(layers, cuts):
    """Where the cuts fall along the strip laid flat again (length = layers): each dotted line goes
    through every layer, and the layers run in turn one way and the other."""
    return sorted({layer + (f if layer % 2 == 0 else 1 - f) for layer in range(layers) for f in cuts})


def _folded_strip(p):
    layers, lines = p["layers"], len(p["cuts"])
    made = layers * lines
    return made + 1, [
        (made, "cuts_counted"),
        (lines + 1, "not_folded"),
        (2 * made, "double"),
        (layers if lines > 1 else None, "layers_counted")]


def cubes(heights):
    """The cubes as (x, y, z): heights[x][y] cubes piled at (x, y). The viewer looks from large x, y and z."""
    return [(x, y, z) for x, row in enumerate(heights) for y, h in enumerate(row) for z in range(h)]


def _height(heights, x, y):
    return heights[x][y] if x < len(heights) and y < len(heights[x]) else 0


def cube_faces(heights):
    """The faces in sight, as (x, y, z, side): the top of each pile, and every side towards the viewer
    with no cube in front of it. With piles that never get taller towards the viewer, nothing
    covers them."""
    faces = []
    for x, y, z in cubes(heights):
        if z == heights[x][y] - 1:
            faces.append((x, y, z, "top"))
        if _height(heights, x + 1, y) <= z:
            faces.append((x, y, z, "x"))
        if _height(heights, x, y + 1) <= z:
            faces.append((x, y, z, "y"))
    return faces


def _cube_stack(p):
    heights = p["heights"]
    faces = cube_faces(heights)
    return len(cubes(heights)), [
        (len({(x, y, z) for x, y, z, _ in faces}), "visible_only"),
        (sum(1 for row in heights for h in row if h), "tops_only"),
        (len(faces), "faces_counted")]


MISTAKES = {"stair_squares": _stair_squares, "folded_strip": _folded_strip, "cube_stack": _cube_stack}
TOPICS = {"visual": ["stair_squares", "folded_strip"], "geometria_espacial": ["cube_stack"]}


# --- The draws ----------------------------------------------------------------------------------

def _draw_stairs(rng):
    while True:
        heights = [rng.randint(1, 2)]
        for _ in range(rng.randint(2, 4)):
            heights.append(heights[-1] + rng.choice((0, 1, 1, 2)))
        if 3 <= max(heights) <= 6 and len(set(heights)) >= 2:
            return {"heights": heights}


def _draw_strip(rng):
    lines = rng.choice((1, 1, 2))
    cuts = [rng.choice((0.35, 0.5, 0.62))] if lines == 1 else [0.3, 0.66]
    return {"layers": rng.randint(3, 6), "cuts": cuts}


def _draw_cubes(rng):
    while True:
        rows, cols = rng.randint(2, 3), rng.randint(2, 3)
        heights = [[0] * cols for _ in range(rows)]
        for x in range(rows):
            for y in range(cols):
                top = min(heights[x - 1][y] if x else 3, heights[x][y - 1] if y else 3)  # never taller towards the viewer
                heights[x][y] = rng.randint(2, 3) if x == y == 0 else rng.randint(max(0, top - 2), top)
        total = sum(map(sum, heights))
        hidden = total - len({f[:3] for f in cube_faces(heights)})
        if 5 <= total <= 14 and hidden >= 1 and all(row[0] for row in heights) and all(heights[0]):
            return {"heights": heights}


def _figure(name, p):
    if name == "stair_squares":
        return {"kind": "stairs", "heights": list(p["heights"])}
    if name == "folded_strip":
        return {"kind": "strip", "layers": p["layers"], "cuts": list(p["cuts"])}
    return {"kind": "cubes", "heights": [list(row) for row in p["heights"]]}


# --- The words: (Catalan, English). Catalan written by the team: needs a native read. -------------

def _text(name, p, eng):
    if name == "stair_squares":
        return ("This staircase is made of small squares, all the same. How many small squares does it have?" if eng else
                "Aquesta escala està feta de quadradets iguals. Quants quadradets té?")
    if name == "folded_strip":
        layers, one = p["layers"], len(p["cuts"]) == 1
        if eng:
            return (f"A strip of paper is folded in a zigzag into {layers} layers, as the figure shows from the side. "
                    + ("Then it is cut through all the layers along the dotted line. " if one else
                       "Then it is cut through all the layers along each of the 2 dotted lines. ")
                    + "How many pieces of paper are there after the cutting?")
        return (f"Una tira de paper es plega en ziga-zaga fins a fer {layers} capes, com es veu de costat a la figura. "
                + ("Després es tallen totes les capes per la línia de punts. " if one else
                   "Després es tallen totes les capes per cadascuna de les 2 línies de punts. ")
                + "Quants trossos de paper queden després de tallar?")
    return ("This building is made of equal cubes piled on a table, with no holes: under every cube there is another "
            "cube or the table. How many cubes does it have?" if eng else
            "Aquesta construcció està feta de cubs iguals apilats sobre una taula, sense forats: sota de cada cub "
            "n'hi ha un altre o hi ha la taula. Quants cubs té?")


def _rationale(name, p, answer, eng):
    if name == "stair_squares":
        columns = " + ".join(str(h) for h in p["heights"])
        return (f"Count column by column: {columns} = {answer} small squares." if eng else
                f"Compta columna per columna: {columns} = {answer} quadradets.")
    if name == "folded_strip":
        layers, lines = p["layers"], len(p["cuts"])
        made = layers * lines
        if eng:
            return ((f"The dotted line goes through the {layers} layers, so the strip gets {made} cuts. " if lines == 1 else
                     f"Each dotted line goes through the {layers} layers: {lines} × {layers} = {made} cuts in the strip. ")
                    + f"Every cut adds one piece to the single strip there was: {made} + 1 = {answer} pieces.")
        return ((f"La línia de punts travessa les {layers} capes, o sigui que la tira rep {made} talls. " if lines == 1 else
                 f"Cada línia de punts travessa les {layers} capes: {lines} × {layers} = {made} talls a la tira. ")
                + f"Cada tall afegeix un tros a la tira sencera que hi havia: {made} + 1 = {answer} trossos.")
    piles = " + ".join(str(h) for row in p["heights"] for h in row if h)
    return (f"Count pile by pile, from the back to the front: {piles} = {answer} cubes. "
            "The ones out of sight are there too: they hold up the ones above." if eng else
            f"Compta pila per pila, de darrere cap endavant: {piles} = {answer} cubs. "
            "Els que no es veuen també hi són: aguanten els de sobre.")


# What each slip is, as a fact about the number chosen. No numbers in the text.
MESSAGES = {
    "stair_squares": {
        "whole_rectangle": ("Aquests són els quadradets del rectangle sencer que envolta la figura. A l'escala n'hi falten uns quants.",
                            "These are the squares of the whole rectangle around the figure. The staircase is missing some of them."),
        "perimeter": ("Això són els costats de quadradet que fan la vora de la figura. Et demanen els quadradets de dins.",
                      "These are the little sides that make the edge of the figure. The question asks for the squares inside."),
        "top_squares": ("Aquí s'ha comptat un quadradet per columna. Cada columna en té tants com la seva alçada.",
                        "Here one square per column was counted. Each column has as many as its height."),
        "row_missing": ("Aquí falta una fila sencera: la de baix també compta.",
                        "A whole row is missing here: the bottom row counts too."),
    },
    "folded_strip": {
        "cuts_counted": ("Aquest és el nombre de talls que rep la tira. De trossos sempre n'hi ha un més que de talls.",
                         "This is the number of cuts the strip gets. There is always one piece more than cuts."),
        "not_folded": ("Això passaria amb la tira sense plegar. Cada línia de punts travessa totes les capes alhora.",
                       "This is what would happen with the strip unfolded. Each dotted line goes through all the layers at once."),
        "double": ("Aquí cada tall s'ha comptat com dos trossos nous. Cada tall només n'afegeix un.",
                   "Here every cut was counted as two new pieces. Each cut adds only one."),
        "layers_counted": ("Aquest és el nombre de capes. Compta quants talls rep la tira en total.",
                           "This is the number of layers. Count how many cuts the strip gets in all."),
    },
    "cube_stack": {
        "visible_only": ("Aquests són els cubs que es veuen. N'hi ha d'amagats, a sota i al darrere, que aguanten els altres.",
                         "These are the cubes in sight. Some are hidden, below and behind, holding up the others."),
        "tops_only": ("Aquí s'ha comptat un cub per pila. Cada pila té tants cubs com la seva alçada.",
                      "Here one cube per pile was counted. Each pile has as many cubes as its height."),
        "faces_counted": ("Això són les cares que es veuen, no els cubs. Un mateix cub pot ensenyar més d'una cara.",
                          "These are the faces in sight, not the cubes. One cube can show more than one face."),
    },
}

# "Explain it back": the way that leads to the answer and the way behind each slip, as the student would say it.
METHODS = {
    "stair_squares": {
        "right": ("He comptat els quadradets de cada columna i els he sumat.",
                  "I counted the squares of each column and added them up."),
        "whole_rectangle": ("He multiplicat l'amplada de la figura per la seva alçada.",
                            "I multiplied the width of the figure by its height."),
        "perimeter": ("He resseguit la vora de la figura comptant els costats dels quadradets.",
                      "I went round the edge of the figure counting the sides of the squares."),
        "top_squares": ("He comptat els esglaons, un per columna.", "I counted the steps, one per column."),
    },
    "folded_strip": {
        "right": ("He comptat els talls que rep la tira, un per cada capa que travessa cada línia de punts, i n'hi he afegit un.",
                  "I counted the cuts the strip gets, one for each layer each dotted line goes through, and added one."),
        "cuts_counted": ("He comptat els talls que rep la tira, un per cada capa que travessa cada línia de punts. Aquests són els trossos.",
                         "I counted the cuts the strip gets, one for each layer each dotted line goes through. Those are the pieces."),
        "not_folded": ("He comptat les línies de punts i n'hi he afegit un, com en una tira sense plegar.",
                       "I counted the dotted lines and added one, as with a strip that is not folded."),
        "double": ("He comptat dos trossos per cada capa que travessa cada línia de punts.",
                   "I counted two pieces for each layer each dotted line goes through."),
    },
    "cube_stack": {
        "right": ("He comptat els cubs pila per pila, també els que queden tapats, i els he sumat.",
                  "I counted the cubes pile by pile, the covered ones too, and added them up."),
        "visible_only": ("He comptat un per un els cubs que es veuen al dibuix.",
                         "I counted one by one the cubes that can be seen in the drawing."),
        "tops_only": ("He comptat les piles, una per cada cara de dalt.", "I counted the piles, one for each top face."),
        "faces_counted": ("He comptat totes les cares que es veuen al dibuix.",
                          "I counted all the faces that can be seen in the drawing."),
    },
}

GENERATORS = {"stair_squares": _draw_stairs, "folded_strip": _draw_strip, "cube_stack": _draw_cubes}


def _options(answer, slips, rng):
    """Five different numbers, smallest first as in the Cangur: the answer, the results of slips,
    and near misses. The place of the answer is drawn first, so it is not always the middle one:
    that many options are smaller than it (slips first, then near misses), the rest larger."""
    wrong = []
    for value, _ in slips:
        if value is not None and value > 0 and value != answer and value not in wrong:
            wrong.append(value)
    rng.shuffle(wrong)
    place = rng.randint(0, 4)
    smaller = [v for v in wrong if v < answer][:place]
    for near in range(answer - 1, 0, -1):
        if len(smaller) < place and near not in smaller:
            smaller.append(near)
    larger = [v for v in wrong if v > answer][:4 - len(smaller)]
    near = answer
    while len(smaller) + len(larger) < 4:
        near += 1
        if near not in larger:
            larger.append(near)
    values = sorted(smaller + [answer] + larger)
    return {letter: str(value) for letter, value in zip(LETTERS, values)}


def generate(name, rng, language="cat"):
    """One problem of this kind: text, five options, the right letter, a worked solution, the
    numbers drawn (params) and the figure for the page to draw."""
    params = GENERATORS[name](rng)
    answer, slips = MISTAKES[name](params)
    options = _options(answer, slips, rng)
    eng = language == "eng"
    return {"generator": name, "params": params, "figure": _figure(name, params),
            "text": _text(name, params, eng), "options": options,
            "label": next(letter for letter, value in options.items() if value == str(answer)),
            "answer": str(answer), "rationale": _rationale(name, params, answer, eng)}
