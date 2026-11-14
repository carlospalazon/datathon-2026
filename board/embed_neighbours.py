#!/usr/bin/env python3
"""Find each problem's nearest problems with the embedding model, once, ahead of time.

    python3 board/embed_neighbours.py problems.jsonl neighbours.jsonl

Input: one JSON per line with "id" and "text" (use the English text: bge-small is an
English model, and every translation of a problem shares its id). Output: one line
per id with its 20 nearest ids and cosine scores, best first.

Runs on the board, against the embedding service on 127.0.0.1:8082. 248 problems
take well under a minute. The tutor then reads the neighbours from the catalogue,
so no embedding happens while a student waits. Standard library only.
"""
import json
import math
import sys
import urllib.request

URL = "http://127.0.0.1:8082/v1/embeddings"
TOP = 20


def embed(texts):
    body = json.dumps({"input": [t[:1400] for t in texts]}).encode()
    request = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = sorted(json.loads(response.read())["data"], key=lambda d: d["index"])
    vectors = []
    for item in data:
        v = item["embedding"]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        vectors.append([x / norm for x in v])
    return vectors


def main(src, dst):
    with open(src) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    vectors = []
    for i in range(0, len(rows), 16):
        vectors += embed([r["text"] for r in rows[i:i + 16]])
    with open(dst, "w") as out:
        for r, v in zip(rows, vectors):
            scores = sorted(((sum(a * b for a, b in zip(v, w)), o["id"]) for o, w in zip(rows, vectors)
                             if o["id"] != r["id"]), reverse=True)[:TOP]
            out.write(json.dumps({"id": r["id"], "neighbours": [[i, round(s, 3)] for s, i in scores]}) + "\n")
    print(f"{len(rows)} problems -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
