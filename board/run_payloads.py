#!/usr/bin/env python3
"""Send prepared chat requests to the board's language model, one at a time, and keep what it wrote.

    python3 board/run_payloads.py payloads.jsonl results.jsonl [http://127.0.0.1:8083]

Input: one JSON per line with "key" and "payload" (the body for /v1/chat/completions).
Output: one line per request, appended as soon as it's done, with the text, the seconds
and the token counts. Keys already in the output are skipped, so a run can be resumed.
Runs on the board, against 127.0.0.1:8081. Standard library only.
"""
import json
import os
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8081/v1/chat/completions"


def main(src, dst, base=None):
    url = (base.rstrip("/") + "/v1/chat/completions") if base else URL
    done = set()
    if os.path.exists(dst):
        with open(dst, encoding="utf-8") as f:
            done = {json.loads(line)["key"] for line in f if line.strip()}
    with open(src, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    for row in rows:
        if row["key"] in done:
            continue
        start = time.perf_counter()
        result = {"key": row["key"]}
        try:
            request = urllib.request.Request(url, json.dumps(row["payload"]).encode(),
                                             {"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=120) as response:
                reply = json.loads(response.read())
            choice, timings = reply["choices"][0], reply.get("timings", {})
            result.update(text=choice["message"]["content"], finish=choice.get("finish_reason"),
                          read_ms=timings.get("prompt_ms"), write_ms=timings.get("predicted_ms"),
                          prompt_tokens=timings.get("prompt_n"), cached_tokens=timings.get("cache_n"),
                          generated_tokens=timings.get("predicted_n"), error=None)
        except Exception as error:  # noqa: BLE001 - keep going, record the failure
            result.update(text="", error=f"{type(error).__name__}: {error}")
        result["seconds"] = round(time.perf_counter() - start, 1)
        with open(dst, "a", encoding="utf-8") as out:
            out.write(json.dumps(result, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:4])
