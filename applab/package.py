#!/usr/bin/env python3
"""Put together the Tutor Cangur App Lab app, ready to copy to the board.

    python3 applab/package.py                 # -> applab/build/math-tutor/
    adb push applab/build/math-tutor /home/arduino/ArduinoApps/

The app's code lives in applab/math-tutor/. This adds what it needs to run on its
own, because App Lab runs the app apart from this repository: the tutor modules,
the method cards, the page, and the catalogue problems with their images.
The build folder holds M3Kang data, so Git ignores it: never commit it.
"""
import argparse
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--catalog", default="data/catalog/problems.jsonl")
    p.add_argument("--images", default="data/images")
    p.add_argument("--stage", default="primaria")
    p.add_argument("--language", default="cat")
    p.add_argument("--out", default="applab/build/math-tutor")
    args = p.parse_args()
    out = os.path.join(ROOT, args.out)

    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(os.path.join(ROOT, "applab/math-tutor"), out)
    # As a package, so the modules' relative imports work. Only what the app needs:
    # no config.env, no predict pipeline.
    pkg = os.path.join(out, "python", "copilot")
    os.makedirs(pkg)
    for module in ("__init__.py", "tutor.py", "diagnose.py", "matrix.py", "assistant.py", "match.py", "slm.py", "guardrails.py", "topics.py", "practice.py", "exam.py", "skillmap.py", "reading.py"):
        shutil.copy(os.path.join(ROOT, "copilot", module), os.path.join(pkg, module))
    # The generators behind the practice problems (our own code, no M3Kang data)
    shutil.copy(os.path.join(ROOT, "laptop/synthetic_problems.py"), os.path.join(pkg, "synthetic_problems.py"))
    shutil.copy(os.path.join(ROOT, "content/types_primaria.json"), os.path.join(out, "python/types.json"))
    shutil.copy(os.path.join(ROOT, "teach/index.html"), os.path.join(out, "assets/index.html"))

    with open(os.path.join(ROOT, args.catalog)) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    keep = [r for r in rows if r["stage"] == args.stage and r["language"] == args.language and r["options"]]
    with open(os.path.join(out, "python/catalog.jsonl"), "w") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    img = os.path.join(out, "assets/img")
    os.makedirs(img)
    missing = 0
    for r in keep:
        src = os.path.join(ROOT, args.images, r["key"] + ".png")
        if os.path.exists(src):
            shutil.copy(src, img)
        else:
            missing += 1
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs) / 1e6
    print(f"{out}: {len(keep)} problems, {len(keep) - missing} images, {size:.1f} MB")
    if missing:
        print(f"  {missing} images missing: run laptop/prepare_m3kang.py --save-images")


if __name__ == "__main__":
    main()
