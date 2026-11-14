#!/usr/bin/env python3
"""Turn a LoRA adapter trained with mlx_lm into one GGUF file that llama-server can run.

    ~/unoq-local/train-venv/bin/python laptop/adapter_to_gguf.py \
        --adapter ~/unoq-local/ft/adapters_m3k_letter --name ft-m3k-letter [--checkpoint 400]

Steps: merge the adapter into the base model (on the CPU, so it can run next to a training job),
convert the merged model to GGUF f16, quantise to Q8_0 (what the board runs), delete the rest.
Run it with the Python of the training environment (it needs mlx_lm, torch and gguf).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home() / "unoq-local"


def run(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--adapter", required=True, help="folder with adapter_config.json and adapters.safetensors")
    p.add_argument("--name", required=True, help="the output is <models>/<name>-Q8_0.gguf")
    p.add_argument("--checkpoint", type=int, default=0, help="use the adapter saved at this step, not the last")
    p.add_argument("--base", default="Qwen/Qwen3.5-0.8B")
    p.add_argument("--models", default=str(HOME / "models"))
    p.add_argument("--llama-src", default=str(HOME / "src" / "llama.cpp-b12383"))
    p.add_argument("--quantize", default=str(HOME / "llama.cpp" / "b12383" / "llama-b12383" / "llama-quantize"))
    p.add_argument("--work", default=str(HOME / "ft" / "work"))
    args = p.parse_args(argv)

    adapter = Path(args.adapter).expanduser()
    work = Path(args.work) / args.name
    shutil.rmtree(work, ignore_errors=True)
    (work / "adapter").mkdir(parents=True)
    weights = adapter / (f"{args.checkpoint:07d}_adapters.safetensors" if args.checkpoint else "adapters.safetensors")
    if not weights.is_file():
        sys.exit(f"No adapter weights at {weights}")
    shutil.copy(adapter / "adapter_config.json", work / "adapter" / "adapter_config.json")
    shutil.copy(weights, work / "adapter" / "adapters.safetensors")

    fuse = ("import sys, mlx.core as mx; mx.set_default_device(mx.cpu); "
            "from mlx_lm import fuse; sys.argv = ['fuse'] + sys.argv[1:]; fuse.main()")
    run([sys.executable, "-c", fuse, "--model", args.base, "--adapter-path", work / "adapter",
         "--save-path", work / "fused"])
    f16 = work / "f16.gguf"
    run([sys.executable, Path(args.llama_src) / "convert_hf_to_gguf.py", work / "fused",
         "--outfile", f16, "--outtype", "f16"])
    out = Path(args.models) / f"{args.name}-Q8_0.gguf"
    run([args.quantize, f16, out, "Q8_0"])
    shutil.rmtree(work, ignore_errors=True)
    print(f"Written: {out}")


if __name__ == "__main__":
    main()
