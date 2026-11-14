#!/usr/bin/env python3
"""M3Kang explorer: look at problems, answer them yourself, then ask the model.

    python3 explorer/server.py
    python3 explorer/server.py --input data/val.jsonl --images data/images --rag 1

Then open http://127.0.0.1:8000 in a browser on the board, or forward the
port to your laptop (see the README). Standard library only.
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.client import get  # noqa: E402
from copilot.config import CONFIG, ROOT  # noqa: E402
from copilot.llm import build_messages  # noqa: E402
from copilot.pipeline import solve  # noqa: E402
from copilot.rag import Index  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LLM = f"http://127.0.0.1:{CONFIG['LLM_PORT']}"
EMBED = f"http://127.0.0.1:{CONFIG['EMBED_PORT']}"
VISION = f"http://127.0.0.1:{CONFIG['VISION_PORT']}"
# Reading an image takes the board much longer than reading text
VISION_TIME_LIMIT = 300

# SOCRATIC HINTS (Layer 1: instant, local, no LLM)
# 5 problem types x 3 progressive hints x 3 languages (cat / esp / eng).
import re
import unicodedata

HINTS = {
    "geometria": {
        "cat": ["Pista 1: Dibuixa la figura i marca-hi totes les mides i angles que dona l'enunciat.",
                "Pista 2: Quina fórmula connecta el que tens (costats, angles) amb el que et demanen (àrea, perímetre, angle)?",
                "Pista 3: Si la figura és complicada, divideix-la en rectangles o triangles i calcula cada part per separat."],
        "esp": ["Pista 1: Dibuja la figura y marca todas las medidas y ángulos que da el enunciado.",
                "Pista 2: ¿Qué fórmula conecta lo que tienes (lados, ángulos) con lo que te piden (área, perímetro, ángulo)?",
                "Pista 3: Si la figura es complicada, divídela en rectángulos o triángulos y calcula cada parte por separado."],
        "eng": ["Hint 1: Draw the figure and mark every length and angle the problem gives you.",
                "Hint 2: Which formula connects what you have (sides, angles) with what you need (area, perimeter, angle)?",
                "Hint 3: If the figure is complicated, split it into rectangles or triangles and work out each part separately."],
    },
    "conteo": {
        "cat": ["Pista 1: Què has de comptar exactament? Digues-ho amb les teves paraules.",
                "Pista 2: Importa l'ordre? (Ab i Ba compten com a dues maneres o com a una?) I es poden repetir els elements?",
                "Pista 3: Si hi ha pocs casos, fes-ne la llista ordenada. Si n'hi ha molts, multiplica les opcions de cada pas."],
        "esp": ["Pista 1: ¿Qué tienes que contar exactamente? Dilo con tus palabras.",
                "Pista 2: ¿Importa el orden? (¿Ab y Ba cuentan como dos formas o como una?) ¿Se pueden repetir los elementos?",
                "Pista 3: Si hay pocos casos, haz una lista ordenada. Si hay muchos, multiplica las opciones de cada paso."],
        "eng": ["Hint 1: What exactly do you have to count? Say it in your own words.",
                "Hint 2: Does order matter? (Do Ab and Ba count as two ways or one?) Can items repeat?",
                "Hint 3: If there are few cases, list them in an organised way. If there are many, multiply the choices at each step."],
    },
    "algebra": {
        "cat": ["Pista 1: Quin és el valor que no coneixes? Dona-li una lletra (per exemple x).",
                "Pista 2: Tradueix l'enunciat a una igualtat: «el doble de», «més que», «la meitat» són operacions.",
                "Pista 3: Resol la igualtat desfent les operacions en ordre invers i comprova el resultat amb l'enunciat."],
        "esp": ["Pista 1: ¿Cuál es el valor que no conoces? Ponle una letra (por ejemplo x).",
                "Pista 2: Traduce el enunciado a una igualdad: «el doble de», «más que», «la mitad» son operaciones.",
                "Pista 3: Resuelve la igualdad deshaciendo las operaciones en orden inverso y comprueba el resultado con el enunciado."],
        "eng": ["Hint 1: Which value don't you know? Give it a letter (for example x).",
                "Hint 2: Translate the text into an equation: \"twice\", \"more than\", \"half of\" are operations.",
                "Hint 3: Solve the equation by undoing the operations in reverse order, then check the result against the text."],
    },
    "aritmetica": {
        "cat": ["Pista 1: Subratlla les dades: quins números hi ha i què vol dir cadascun?",
                "Pista 2: Què et demanen exactament? Fixa't que no sigui un resultat intermedi.",
                "Pista 3: Fes un sol càlcul cada vegada, en ordre (primer × i ÷, després + i −), i escriu què representa cada resultat."],
        "esp": ["Pista 1: Subraya los datos: ¿qué números hay y qué significa cada uno?",
                "Pista 2: ¿Qué te piden exactamente? Asegúrate de que no es un resultado intermedio.",
                "Pista 3: Haz un solo cálculo cada vez, en orden (primero × y ÷, luego + y −), y anota qué representa cada resultado."],
        "eng": ["Hint 1: Underline the data: which numbers are there and what does each one mean?",
                "Hint 2: What exactly are you asked? Make sure it isn't an intermediate result.",
                "Hint 3: Do one calculation at a time, in order (× and ÷ first, then + and −), and note what each result represents."],
    },
    "logica": {
        "cat": ["Pista 1: Posa en una llista tot el que és cert segons l'enunciat.",
                "Pista 2: Descarta primer les opcions que no poden ser possibles (massa grans, massa petites, que contradiuen una dada).",
                "Pista 3: Prova les opcions que queden una per una i comprova si compleixen totes les condicions."],
        "esp": ["Pista 1: Haz una lista de todo lo que es cierto según el enunciado.",
                "Pista 2: Descarta primero las opciones imposibles (demasiado grandes, demasiado pequeñas, que contradicen un dato).",
                "Pista 3: Prueba las opciones que quedan una a una y comprueba si cumplen todas las condiciones."],
        "eng": ["Hint 1: List everything that is true according to the problem.",
                "Hint 2: First rule out options that can't be possible (too big, too small, contradicting a fact).",
                "Hint 3: Try the remaining options one by one and check whether each meets every condition."],
    },
}

# Word beginnings (accents stripped, lowercase) that suggest each type: cat / esp / eng
KEYWORDS = {
    "geometria": ["triangl", "triangul", "angle", "angul", "area", "perimetr", "perimeter", "cercle", "circul",
                  "circle", "quadrat", "cuadrad", "square", "rectangl", "rectangul", "cub", "volum", "diagonal",
                  "costat", "lado", "side", "figura", "figure", "dibuix", "dibujo", "pentagon", "hexagon",
                  "poligon", "polygon", "simetri", "symmetr", "grau", "grado", "degree"],
    "conteo": ["quantes maneres", "cuantas maneras", "how many ways", "de quantes", "de cuantas", "combinacion",
               "combinacio", "combination", "ordenar", "ordre", "orden", "order", "parella", "pareja", "pair",
               "cami", "camino", "path", "triar", "elegir", "choose", "permut", "arrang", "colocar",
               "quants nombres", "cuantos numeros", "how many numbers", "nombres de", "numeros de", "numbers with", "quantes", "cuantas", "diferents",
               "diferentes", "different"],
    "algebra": ["equacio", "ecuacion", "equation", "incognita", "unknown", "edat", "edad", "age", "anys", "anos",
                "years old", "el doble", "doble", "twice", "double", "triple", "la meitat", "la mitad", "half",
                "mes que", "mas que", "more than", "menys que", "menos que", "less than", "quin nombre",
                "que numero", "which number", "what number", "diferencia", "difference"],
    "aritmetica": ["suma", "sumar", "resta", "restar", "multipli", "divis", "fraccio", "fraccion", "fraction",
                   "percent", "mitjana", "promedio", "average", "residu", "resto",
                   "remainder", "total", "cromos", "pomes", "manzanas",
                   "apples", "preu", "precio", "price", "euro"],
}


def _norm(text):
    text = unicodedata.normalize("NFD", str(text).lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def detect_category(problem):
    """Pick the problem type from its text (and options) in any of cat/esp/eng."""
    text = _norm(problem.get("text", "") + " " + " ".join(str(v) for v in (problem.get("options") or {}).values()))
    scores = {}
    for category, stems in KEYWORDS.items():
        scores[category] = sum(1 for stem in stems if re.search(r"(?<![a-z])" + re.escape(stem), text))
    best = max(scores.values())
    if best == 0:
        return "aritmetica" if re.search(r"\d", text) else "logica"
    # ties resolved by this priority order
    for category in ("geometria", "conteo", "algebra", "aritmetica"):
        if scores[category] == best:
            return category
    return "logica"


def process_socratic_step(problem, step):
    """Return hint number `step` (0, 1 or 2) for this problem, in the problem's language."""
    category = detect_category(problem)
    language = problem.get("language") if problem.get("language") in ("cat", "esp", "eng") else "eng"
    hints = HINTS[category][language]
    idx = max(0, min(step, len(hints) - 1))
    print(f"[Server] Socratic hint -> type: {category}, lang: {language}, hint {idx + 1}/{len(hints)}")
    return {
        "type": "smart_socratic",
        "category": category,
        "content": hints[idx],
        "step": idx + 1,
        "total": len(hints),
        "next_step": min(idx + 1, len(hints) - 1),  # stays on the last hint instead of looping
        "done": idx == len(hints) - 1,
    }


def analyze_distractor(selected_option, correct_option):
  """Analyzes common errors based on the chosen option (Layer 2)."""
  print(
      f"[Server] Analyzing user distractor choice: {selected_option}"
      f" (Correct: {correct_option})"
  )
  if selected_option == correct_option:
    return {
        "type": "error_analysis",
        "content": "That option is correct! Excellent reasoning.",
    }
  else:
    return {
        "type": "error_analysis",
        "content": (
            f"Option {selected_option} is a common pitfall. Review your"
            " intermediate calculations or check if you missed a condition in"
            " the text."
        ),
    }


def call_llm_wildcard(problem):
  """Layer 3: local LLM wildcard. One short conceptual hint, no step template."""
  language = {"cat": "Catalan", "esp": "Spanish", "eng": "English"}.get(problem.get("language"), "English")
  options = problem.get("options") or {}
  options_text = "\n".join(f"{k}) {v}" for k, v in options.items())
  payload = {
      "messages": [
          {"role": "system", "content": (
              f"You are a Socratic math tutor for primary school children. Answer in {language}. "
              "Give ONE short hint (max 2 sentences) specific to this problem. "
              "Never give the final answer or an option letter. "
              "Do not write numbered steps and do not write 'Step 1', 'Step 2' or 'Step 3'.")},
          {"role": "user", "content": f"Problem:\n{problem.get('text', '')}\n{options_text}\n\nGive one hint."},
      ],
      "temperature": 0.3,
      "max_tokens": 120,
  }
  req = urllib.request.Request(LLM + "/v1/chat/completions", data=json.dumps(payload).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
  try:
    print(f"[Server] Calling local LLM wildcard on {LLM} ...")
    with urllib.request.urlopen(req, timeout=60) as response:
      answer = json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
    return {"type": "llm_wildcard", "content": answer}
  except Exception as e:
    print(f"[Server Error] Failed to reach local LLM: {e}")
    return {"type": "llm_wildcard", "content": "Local AI copilot is currently offline."}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/val.jsonl", help="problems to explore")
    p.add_argument("--images", default="data/images", help="folder written by prepare_m3kang.py --save-images")
    p.add_argument("--index", default="data/index.db", help="retrieval index from build_index.py")
    p.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to open it to your network")
    p.add_argument("--port", type=int, default=8000)
    return p.parse_args()


def key_of(problem):
    return f"{problem['id']}_{problem['language']}"


def is_up(base):
    try:
        return get(base + "/health", timeout=2).get("status") == "ok"
    except (OSError, ValueError):
        return False


def sees_images(base):
    try:
        return bool(get(base + "/props", timeout=2).get("modalities", {}).get("vision"))
    except (OSError, ValueError):
        return False


def public(problem, images):
    """A problem without its label, so the page can't give the answer away."""
    shown = {k: v for k, v in problem.items() if k != "label"}
    shown["key"] = key_of(problem)
    shown["image"] = os.path.exists(os.path.join(images, key_of(problem) + ".png"))
    return shown


def printable(messages):
    """The prompt as plain text, with the image replaced by a marker."""
    lines = []
    for m in messages:
        content = m["content"]
        if isinstance(content, list):
            content = "\n".join("[image]" if part["type"] == "image_url" else part["text"] for part in content)
        lines.append(f"--- {m['role']} ---\n{content}")
    return "\n".join(lines)


class App:
    def __init__(self, args):
        os.chdir(ROOT)
        self.images = args.images
        with open(args.input) as f:
            self.problems = [json.loads(line) for line in f if line.strip()]
        self.by_key = {key_of(p): p for p in self.problems}
        self.index = Index(args.index) if os.path.exists(args.index) else None
        self.input = args.input
        # Images the page may ask for: the problems, and the solved problems in the index
        self.image_keys = set(self.by_key)
        if self.index:
            self.image_keys |= {row[0].replace("|", "_") for row in self.index.rows}

    def info(self):
        return {
            "input": self.input,
            "count": len(self.problems),
            "languages": sorted({p["language"] for p in self.problems}),
            "levels": sorted({p["level"] for p in self.problems}),
            "images": sum(os.path.exists(os.path.join(self.images, k + ".png")) for k in self.by_key),
            "index": len(self.index.rows) if self.index else 0,
            "llm": is_up(LLM),
            "embed": is_up(EMBED),
            "vision": is_up(VISION) and sees_images(VISION),
            "time_limit": float(CONFIG["TIME_LIMIT_SECONDS"]),
        }

    def listing(self):
        return [{"key": key_of(p), "id": p["id"], "language": p["language"], "level": p["level"],
                 "options": bool(p.get("options"))} for p in self.problems]

    def image_b64(self, key):
        with open(os.path.join(self.images, key + ".png"), "rb") as f:
            return base64.b64encode(f.read()).decode()

    def check(self, key, choice):
        label = self.by_key[key]["label"]
        return {"correct": choice == label, "label": label}

    def ask(self, key, rag, vision):
        problem = self.by_key[key]
        image = self.image_b64(key) if vision else None
        result = solve(problem, index=self.index if rag else None, k=rag, exclude_id=problem["id"],
                       image_b64=image, llm_url=(VISION if vision else LLM) + "/v1/chat/completions",
                       time_limit=VISION_TIME_LIMIT if vision else float(CONFIG["TIME_LIMIT_SECONDS"]))
        examples = [p for _score, p in result["examples"]]
        return {
            "answer": result["answer"],
            "status": result["status"],
            "seconds": result["seconds"],
            "prompt_tokens": result["prompt_tokens"],
            "correct": result["answer"] == problem["label"],
            "label": problem["label"],
            "prompt": printable(build_messages(problem, examples, image)),
            "examples": [{"score": round(s, 3), **public(p, self.images), "label": p["label"]}
                         for s, p in result["examples"]],
        }

    def similar(self, key, k):
        if not self.index:
            return []
        problem = self.by_key[key]
        hits = self.index.search(problem, k=k, exclude_id=problem["id"])
        return [{"score": round(s, 3), **public(p, self.images), "label": p["label"]} for s, p in hits]


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("  " + fmt % args + "\n")

        def send(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            params = {k: urllib.parse.unquote(v) for k, v in (pair.split("=", 1) for pair in query.split("&") if "=" in pair)}
            if path == "/":
                with open(os.path.join(HERE, "index.html"), "rb") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")
            if path == "/api/info":
                return self.send(200, app.info())
            if path == "/api/problems":
                return self.send(200, app.listing())
            if path == "/api/problem" and params.get("key") in app.by_key:
                return self.send(200, public(app.by_key[params["key"]], app.images))
            if path == "/api/similar" and params.get("key") in app.by_key:
                return self.send(200, app.similar(params["key"], int(params.get("k", 3))))
            if path.startswith("/image/"):
                key = path[len("/image/"):]
                # Only known keys reach the disk, so a request can't name any other file
                file = os.path.join(app.images, key + ".png")
                if key in app.image_keys and os.path.exists(file):
                    with open(file, "rb") as f:
                        return self.send(200, f.read(), "image/png")
            if path == "/api/socratic":
                step = int(params.get("step", 0))
                key = params.get("key")
                problem = app.by_key.get(key) if key else None
                if not problem:
                    # Fallback si no hay problema seleccionado
                    return self.send(200, {"type": "local_socratic", "content": "Please select a problem first.", "next_step": 0})
                return self.send(200, process_socratic_step(problem, step))
            return self.send(404, {"error": "not found"})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            key = body.get("key")
            if key not in app.by_key:
                return self.send(404, {"error": "unknown problem"})
            try:
                if self.path == "/api/check" and body.get("choice") in list("ABCDE"):
                    return self.send(200, app.check(key, body["choice"]))
                if self.path == "/api/ask":
                    return self.send(200, app.ask(key, int(body.get("rag", 0)), bool(body.get("vision"))))
                if self.path == "/api/wildcard":
                    return self.send(200, call_llm_wildcard(app.by_key[key]))
            except (OSError, urllib.error.URLError) as error:
                return self.send(502, {"error": f"model server: {error}"})
            return self.send(400, {"error": "bad request"})

    return Handler

def main():
    args = parse_args()
    app = App(args)
    info = app.info()
    print(f"{info['count']} problems from {args.input}, {info['images']} with images, "
          f"{info['index']} in the retrieval index")
    print(f"Servers: language model {'up' if info['llm'] else 'DOWN'}, "
          f"embeddings {'up' if info['embed'] else 'DOWN'}, "
          f"vision {'up' if info['vision'] else 'off'}")
    print(f"Open http://{args.host}:{args.port} (Ctrl+C to stop)", flush=True)
    ThreadingHTTPServer((args.host, args.port), make_handler(app)).serve_forever()


if __name__ == "__main__":
    main()
