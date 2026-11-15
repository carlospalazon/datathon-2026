#!/usr/bin/env python3
"""Turn a LoRA adapter trained with mlx_lm into one GGUF file that llama-server can run.

    ~/unoq-local/train-venv/bin/python laptop/adapter_to_gguf.py \
        --adapter ~/unoq-local/ft/adapters_m3k_letter --name ft-m3k-letter [--checkpoint 400]

Steps: add the adapter's updates to the base model's original weight file, convert the merged
model to GGUF f16, quantise to Q8_0 (what the board runs), delete the rest.
Run it with the Python of the training environment (it needs torch, safetensors and gguf).
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home() / "unoq-local"


def run(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def merge(base, adapter_dir, out_dir):
    """Add the adapter's low-rank updates to the base model's own weight file.

    mlx_lm's fuse writes weights in MLX's layout (convolutions are stored differently), and the GGUF
    converter then builds a model that only writes noise. So the original PyTorch-layout file is
    patched instead: for every adapted linear layer, W += scale * (lora_a @ lora_b).T.
    """
    import torch
    from huggingface_hub import snapshot_download
    from safetensors import safe_open
    from safetensors.torch import load_file, save_file

    snap = Path(snapshot_download(base))
    out_dir.mkdir(parents=True)
    weight_files = sorted(snap.glob("*.safetensors"))
    if len(weight_files) != 1:
        sys.exit(f"Expected one weight file in {snap}, found {len(weight_files)}")
    for f in snap.iterdir():
        if f.suffix != ".safetensors":
            shutil.copy(f, out_dir / f.name)
    weights = load_file(str(weight_files[0]))
    with safe_open(str(weight_files[0]), "pt") as f:
        meta = f.metadata() or {"format": "pt"}
    cfg = json.loads((adapter_dir / "adapter_config.json").read_text())
    scale = float(cfg["lora_parameters"]["scale"])
    lora = load_file(str(adapter_dir / "adapters.safetensors"))
    done = 0
    for key in sorted(k for k in lora if k.endswith(".lora_a")):
        stem = key[: -len(".lora_a")]
        hf = stem.replace("language_model.model.", "model.language_model.", 1)  # MLX name -> PyTorch name
        target = next((c for c in (f"{hf}.weight", f"model.{stem}.weight", f"{stem}.weight") if c in weights), None)
        if target is None:
            sys.exit(f"No base weight for adapter tensor {key}")
        a, b = lora[key].float(), lora[stem + ".lora_b"].float()
        delta = scale * (a @ b).T
        w = weights[target]
        if delta.shape != w.shape:
            sys.exit(f"{target}: update is {tuple(delta.shape)}, weight is {tuple(w.shape)}")
        weights[target] = (w.float() + delta).to(w.dtype)
        done += 1
    if done * 2 != len(lora):
        sys.exit(f"Merged {done} layers but the adapter has {len(lora)} tensors")
    save_file(weights, str(out_dir / weight_files[0].name), metadata=meta)
    print(f"Merged {done} adapted layers (scale {scale}) into {out_dir}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--adapter", required=True, help="folder with adapter_config.json and adapters.safetensors")
    p.add_argument("--name", required=True, help="the output is <models>/<name>-Q8_0.gguf")
    p.add_argument("--checkpoint", type=int, default=0, help="use the adapter saved at this step, not the last")
    p.add_argument("--base", default="Qwen/Qwen3.5-0.8B")
    p.add_argument("--models", default=str(HOME / "models"))
    board_src = HOME / "src" / "llama.cpp-board"
    p.add_argument("--llama-src", default=str(board_src if board_src.is_dir() else HOME / "src" / "llama.cpp-b12383"),
                   help="folder with convert_hf_to_gguf.py. It MUST be the board's own llama.cpp version "
                        "(copy convert_hf_to_gguf.py, gguf-py/ and conversion/ from the board): a newer "
                        "converter writes merged tensors that the board's server refuses to load")
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

    merge(args.base, work / "adapter", work / "fused")
    f16 = work / "f16.gguf"
    run([sys.executable, Path(args.llama_src) / "convert_hf_to_gguf.py", work / "fused",
         "--outfile", f16, "--outtype", "f16"])
    out = Path(args.models) / f"{args.name}-Q8_0.gguf"
    run([args.quantize, f16, out, "Q8_0"])
    shutil.rmtree(work, ignore_errors=True)
    print(f"Written: {out}")


if __name__ == "__main__":
    main()
