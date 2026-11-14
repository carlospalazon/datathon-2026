#!/usr/bin/env python3
"""Embed texts with the board's embedding service and keep the vectors.

    python3 board/embed_texts.py texts.jsonl vectors.jsonl

Input: one JSON per line with "key" and "text". Output: the same keys with a
normalised "vector" (384 numbers, 4 decimals) and "seconds" for the batch it was in.
Runs on the board, against 127.0.0.1:8082. Standard library only.
"""
import json
import math
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8082/v1/embeddings"
BATCH = 8


def embed(texts):
    body = json.dumps({"input": [t[:1400] for t in texts]}).encode()
    request = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        data = sorted(json.loads(response.read())["data"], key=lambda d: d["index"])
    vectors = []
    for item in data:
        v = item["embedding"]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        vectors.append([round(x / norm, 4) for x in v])
    return vectors


def main(src, dst):
    with open(src, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    with open(dst, "w", encoding="utf-8") as out:
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            start = time.perf_counter()
            vectors = embed([r["text"] for r in batch])
            seconds = round((time.perf_counter() - start) / len(batch), 3)
            for r, v in zip(batch, vectors):
                out.write(json.dumps({"key": r["key"], "vector": v, "seconds": seconds}) + "\n")
            print(f"{min(i + BATCH, len(rows))}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
