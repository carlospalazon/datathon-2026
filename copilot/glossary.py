"""Written answers to questions about the syllabus: "què és un nombre primer?", "com es calcula l'àrea?".

    found = glossary.lookup(text, problem)   # {"text", "status", "source"} or None

Why written and not the model: asked on the laptop what a prime number is, the 0.8B model answered
"the first one that appears in the order of operations", and that passed every guardrail, because
the guardrails check leaks and format, not truth. A definition a child will remember has to be right.

Each entry: a pattern (regular expression on the text without accents, lower case), the definition and
an example. The first entries win, so the longer names come first. Catalan only: the tutor runs in Catalan.
"""
import re

from .guardrails import strip_accents
from .tutor import leaks_answer

STATUS = "generado"  # written with a model's help and not yet checked by a teacher

ENTRIES = [
    ("minim comu multiple", r"minim comu multiple|\bmcm\b",
     "El mínim comú múltiple de dos nombres és el més petit dels múltiples que tenen en comú.",
     "Per exemple, el de 4 i 6 és 12."),
    ("maxim comu divisor", r"maxim comu divisor|\bmcd\b",
     "El màxim comú divisor de dos nombres és el més gran dels divisors que tenen en comú.",
     "Per exemple, el de 12 i 18 és 6."),
    ("nombre primer", r"(nombres?|numeros?) prim(er|o)s?|\b(es|sigui|son) primers?\b",
     "Un nombre primer és un nombre més gran que 1 que només es pot dividir exactament per 1 i per ell mateix.",
     "Per exemple, 2, 3, 5 i 7 són primers; 6 no ho és, perquè es pot dividir per 2 i per 3."),
    ("parell", r"\bparells?\b|\bpar\b|\bpares\b",
     "Un nombre parell és el que es pot repartir en dos grups iguals sense que sobri res.", "Acaba en 0, 2, 4, 6 o 8."),
    ("senar", r"\bsenars?\b|\bimparells?\b|\bimpar(es)?\b",
     "Un nombre senar és el que no es pot repartir en dos grups iguals: sempre en sobra un.", "Acaba en 1, 3, 5, 7 o 9."),
    ("multiple", r"\bmultipl[eo]s?\b",
     "Un múltiple d'un nombre és el resultat de multiplicar-lo per 1, per 2, per 3, i així successivament.",
     "Per exemple, els múltiples de 5 són 5, 10, 15, 20…"),
    ("divisor", r"\bdivisors?\b",
     "Un divisor d'un nombre és un nombre que el divideix sense que sobri res.",
     "Per exemple, els divisors de 6 són 1, 2, 3 i 6."),
    ("residu", r"\bresidus?\b|\bresto\b",
     "El residu és el que sobra en una divisió quan no surt exacta.",
     "Per exemple, 17 entre 5 dona 3 i en sobren 2: el residu és 2."),
    ("quocient", r"\bquocients?\b|\bcocientes?\b",
     "El quocient és el resultat d'una divisió: quantes vegades hi cap el divisor.", ""),
    ("consecutius", r"\bconsecuti\w+",
     "Dos nombres són consecutius quan van l'un darrere l'altre, sense cap enmig.",
     "Per exemple, 7 i 8, o 14, 15 i 16."),
    ("xifra", r"\bxifr\w+|\bdigits?\b|\bcifras?\b",
     "Una xifra és cadascun dels símbols del 0 al 9 amb què s'escriuen els nombres.",
     "Per exemple, el nombre 305 té tres xifres: 3, 0 i 5."),
    ("fraccions equivalents", r"fraccio\w* equivalents?",
     "Dues fraccions són equivalents quan valen el mateix encara que s'escriguin diferent.",
     "Per exemple, una meitat i dos quarts són la mateixa quantitat."),
    ("sumar fraccions", r"(sum\w+|rest\w+) (les |de |dues |unes )?fraccions",
     "Per sumar o restar fraccions han de tenir el mateix denominador; aleshores se sumen o es resten només els numeradors.",
     "Si els denominadors són diferents, primer es busquen fraccions equivalents que el tinguin igual."),
    ("numerador i denominador", r"\bnumeradors?\b|\bdenominadors?\b",
     "En una fracció, el denominador (a sota) diu en quantes parts iguals es divideix el tot, "
     "i el numerador (a dalt) diu quantes d'aquestes parts s'agafen.", ""),
    ("fraccio", r"\bfraccio\w*",
     "Una fracció indica parts d'un tot dividit en parts iguals: el número de sota diu en quantes parts es divideix "
     "i el de dalt, quantes se n'agafen.", "Per exemple, tres quarts vol dir 3 de les 4 parts iguals."),
    ("terc", r"\bterc\w*|\btercio\b",
     "Un terç és una de les tres parts iguals en què es divideix una cosa.",
     "Per trobar un terç d'una quantitat, es divideix entre 3."),
    ("quart", r"\bun quart\b|\bquarts\b|\bquarta part\b",
     "Un quart és una de les quatre parts iguals en què es divideix una cosa.",
     "Per trobar un quart d'una quantitat, es divideix entre 4."),
    ("meitat", r"\bmeitat\b|\bmitad\b",
     "La meitat és una de les dues parts iguals en què es divideix una cosa.",
     "Per trobar la meitat d'una quantitat, es divideix entre 2."),
    ("doble i triple", r"\bdobles?\b|\btriples?\b",
     "El doble d'un nombre és aquest nombre dues vegades, és a dir, multiplicat per 2; el triple és multiplicat per 3.", ""),
    ("percentatge", r"\bpercentatges?\b|\btant per cent\b|\bper cent\b|\bporcentajes?\b",
     "Un percentatge diu quantes parts s'agafen de cada 100.",
     "Per exemple, el 50 % és la meitat i el 25 % és la quarta part."),
    ("mitjana", r"\bmitjan\w+|\bpromedio\b|\bmedia\b",
     "La mitjana d'uns quants nombres es troba sumant-los tots i dividint el resultat entre quants n'hi ha.",
     "Per exemple, la mitjana de 4, 6 i 8 és 18 entre 3."),
    ("regla de tres", r"regla de tres|\bproporcio\w*",
     "Una regla de tres serveix quan dues quantitats creixen alhora: si saps quant val una unitat, "
     "multipliques per les que necessites.",
     "Per exemple, si 2 llibretes costen 6 euros, una en costa 3, i 5 en costen 15."),
    ("equacio", r"\bequaci\w+|\becuaci\w+",
     "Una equació és una igualtat amb un nombre amagat. Resoldre-la és trobar el nombre que fa que els dos costats valguin el mateix.",
     "Pots provar nombres o desfer les operacions de darrere cap endavant."),
    ("taules de multiplicar", r"taul\w+ de multiplicar",
     "Les taules de multiplicar són els resultats de multiplicar els nombres de l'1 al 10 entre ells. "
     "Multiplicar és sumar el mateix nombre diverses vegades.", "Per exemple, 3 vegades 4 és 4 + 4 + 4."),
    ("multiplicar per 10", r"multipli\w+ per (10|deu|100|cent)\b",
     "Per multiplicar un nombre enter per deu s'hi afegeix un zero al final; per cent, dos zeros.", ""),
    ("dividir per 10", r"divid\w+ (per|entre) (10|deu|100|cent)\b",
     "Per dividir per deu un nombre enter que acaba en zero, se li treu aquest zero; per cent, dos zeros.", ""),
    ("decimal", r"\bdecimals?\b",
     "Un nombre decimal té una part entera i, després de la coma, una part més petita que la unitat: dècimes, centèsimes…",
     "Per sumar o restar decimals es posen les comes l'una sota l'altra."),
    ("unitats, desenes i centenes", r"\bdesen\w+|\bcenten\w+|\bunitats\b",
     "Una desena són deu unitats i una centena són deu desenes, és a dir, cent unitats.", ""),
    ("arrodonir", r"\barrodon\w+|\baproxim\w+|\bredonde\w+",
     "Arrodonir és canviar un nombre pel nombre rodó que té més a prop, per fer els càlculs més fàcils.",
     "Per exemple, 48 s'arrodoneix a 50."),
    ("divisio", r"\bdivisio\w*|\bdividir\b",
     "Dividir és repartir una quantitat en parts iguals, o veure quantes vegades hi cap un nombre dins d'un altre.",
     "Per exemple, 12 entre 3 és 4, perquè 3 vegades 4 fa 12."),
    ("area del rectangle", r"area\b.*\b(rectangle|quadrat)|\b(rectangle|quadrat)\w*\b.*\barea",
     "L'àrea d'un rectangle es troba multiplicant el que fa de llarg pel que fa d'ample. "
     "En un quadrat, costat per costat.", ""),
    ("area del triangle", r"area\b.*\btriangle|\btriangle\w*\b.*\barea",
     "L'àrea d'un triangle és la base per l'altura, dividit entre 2: la meitat del rectangle que el conté.", ""),
    ("area i perimetre", r"area\b.*\bperimetre|perimetre\b.*\barea",
     "El perímetre és la llargada de la vora d'una figura: se sumen tots els costats. "
     "L'àrea és l'espai que ocupa per dins: quants quadradets hi caben.", ""),
    ("perimetre", r"\bperimetr\w+",
     "El perímetre d'una figura és la llargada de tota la seva vora: es troba sumant la llargada de tots els costats.", ""),
    ("area", r"\barea\b|\barees\b|\bsuperficie\b",
     "L'àrea d'una figura és l'espai que ocupa per dins. Es mesura comptant quants quadradets iguals hi caben.", ""),
    ("volum", r"\bvolum\w*",
     "El volum d'un cos és l'espai que ocupa. Es mesura comptant quants cubets iguals hi caben.", ""),
    ("angle recte", r"angles? rectes?",
     "Un angle recte és el que fan dues línies perpendiculars, com la cantonada d'un full.", "Fa 90 graus."),
    ("angle", r"\bangles?\b|\bangulos?\b",
     "Un angle és l'obertura entre dues línies que surten del mateix punt. Es mesura en graus.", ""),
    ("eix de simetria", r"\bsimetri\w+",
     "Un eix de simetria és una línia que parteix una figura en dues meitats iguals, "
     "de manera que si la doblegues per aquesta línia les dues meitats coincideixen.", ""),
    ("hipotenusa", r"\bhipotenus\w+",
     "La hipotenusa és el costat més llarg d'un triangle rectangle: el que queda davant de l'angle recte.", ""),
    ("triangle", r"\btriangles?\b|\btriangulos?\b",
     "Un triangle és un polígon de tres costats i tres angles.", ""),
    ("quadrilater", r"\bquadrilater\w*",
     "Un quadrilàter és un polígon de quatre costats.", "El quadrat, el rectangle i el rombe en són exemples."),
    ("rombe", r"\brombes?\b|\brombos?\b",
     "Un rombe és un quadrilàter amb els quatre costats iguals, com un quadrat inclinat.", ""),
    ("cercle", r"\bcercles?\b|\bcircumferenci\w+|\bradis?\b|\bdiametres?\b",
     "Un cercle és una figura rodona: tots els punts de la vora són a la mateixa distància del centre. "
     "Aquesta distància és el radi, i el diàmetre és el doble: va de banda a banda passant pel centre.", ""),
    ("pentagon", r"\bpentagon\w*", "Un pentàgon és un polígon de cinc costats.", ""),
    ("hexagon", r"\bhexagon\w*", "Un hexàgon és un polígon de sis costats.", ""),
    ("poligon", r"\bpoligon\w*",
     "Un polígon és una figura plana tancada feta de costats rectes.", "Per exemple, un triangle o un quadrat."),
    ("diagonal", r"\bdiagonals?\b",
     "Una diagonal és una línia recta que uneix dos vèrtexs d'una figura que no estan l'un al costat de l'altre.", ""),
    ("vertex", r"\bvertexs?\b|\bvertice\w*",
     "Un vèrtex és un punt on es troben dos costats d'una figura, o tres arestes d'un cos: una punta.", ""),
    ("aresta", r"\barest\w+",
     "Una aresta és la línia on es troben dues cares d'un cos, com cadascuna de les vores d'un cub.", ""),
    ("cub", r"\bcubs?\b",
     "Un cub és un cos amb sis cares quadrades iguals, com un dau.", "Té 8 vèrtexs i 12 arestes."),
    ("cara", r"\bcares\b|\bcara\b",
     "Una cara és cadascuna de les superfícies planes d'un cos, com els costats d'una capsa.", ""),
    ("paral·leles i perpendiculars", r"\bparal\W?lel\w*|\bperpendicular\w*",
     "Dues línies paral·leles no es troben mai, com els rails d'un tren. "
     "Dues línies perpendiculars es tallen fent un angle recte, com una creu.", ""),
    ("metres i centimetres", r"\b(centimetres?|metres?|quilometres?|mil\W?limetres?)\b.*\b(centimetres?|metres?|quilometres?|mil\W?limetres?)\b",
     "Un metre són 100 centímetres i un quilòmetre són 1000 metres. "
     "Per passar a una unitat més petita es multiplica; per passar a una de més gran es divideix.", ""),
    ("hores i minuts", r"\b(minuts?|hor\w+|segons?)\b.*\b(minuts?|hor\w+|segons?)\b",
     "Una hora té 60 minuts i un minut té 60 segons.", ""),
    ("dies i setmanes", r"\b(dies|setman\w+)\b.*\b(dies|setman\w+)\b",
     "Una setmana té 7 dies.", ""),
    ("litre", r"\blitres?\b|\bmil\W?lilitres?\b|\bcapacitat\b",
     "El litre és la unitat amb què es mesura quant líquid hi cap en un recipient.", "Un litre són 1000 mil·lilitres."),
    ("quilos i grams", r"\b(grams?|quilos?|quilograms?)\b.*\b(grams?|quilos?|quilograms?)\b",
     "Un quilo són 1000 grams.", ""),
    ("grafic de barres", r"\bgrafi\w+",
     "En un gràfic de barres, cada barra és una cosa i la seva alçada diu quantes n'hi ha: "
     "es llegeix mirant fins a quin número de l'eix arriba la barra.", ""),
]
COMPILED = [(name, re.compile(pattern), text, example) for name, pattern, text, example in ENTRIES]

# A question about the syllabus, not about the step the student is on
ASKS = re.compile(r"que (es|son|vol dir|volen dir|significa)|que es (un|una|el|la|l')|com es (calcul|fa|fan|sum|rest|multipli|divid"
                  r"|resol|llegeix|trob|mesur|pass)|com (passo|calculo|sumo|resto|multiplico|divideixo|trobo)|explica|diferencia"
                  r"|no se que|no entenc que|per que serveix|quant(s|es)? .*\b(te|tenen|hi ha en|son)\b|quin\w* .*\b(te|tenen)\b")
MAX_SHOWN = 2


def clean(text):
    return re.sub(r"\s+", " ", strip_accents(str(text).lower())).strip()


def terms(text):
    """The names of the entries the text mentions, in the glossary's order, without overlaps."""
    t = clean(text)
    found, taken = [], []
    for name, pattern, _text, _example in COMPILED:
        m = pattern.search(t)
        if m and not any(m.start() < end and start < m.end() for start, end in taken):
            found.append(name)
            taken.append(m.span())
    return found


def asks(text):
    """True if the text asks what something is or how something is done in general."""
    t = clean(text)
    return bool(ASKS.search(t)) or (len(t.split()) <= 4 and not re.search(r"\d", t))


def lookup(text, problem):
    """The written definition for what the student asks about, or None. Never gives the answer away."""
    if problem.get("language") != "cat" or not asks(text):
        return None
    names = terms(text)[:MAX_SHOWN]
    parts = []
    for name, _pattern, definition, example in COMPILED:
        if name not in names or leaks_answer(definition, problem):
            continue
        parts.append(definition + (" " + example if example and not leaks_answer(example, problem) else ""))
    if not parts:
        return None
    return {"text": " ".join(parts), "status": STATUS, "source": "glossary: " + ", ".join(names)}
