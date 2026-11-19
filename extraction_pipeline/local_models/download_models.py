#!/usr/bin/env python3
"""Curated local vision-language model downloader for Ollama.

Five small VLMs, suitable for initial benchmarking with ~8 GB VRAM and
64 GB system RAM. Download size is not total VRAM usage; keep context small.

Usage:
    python download_models.py --list
    python download_models.py --pull qwen3_vl_4b
    python download_models.py --pull qwen3_vl_4b --quant q8
    python download_models.py --all

Only downloads on explicit --pull or --all. Existing tags are skipped.
"""

import argparse
import shutil
import subprocess
import sys

# Exact, verified Ollama registry tags; Q4_K_M etc. are quantization names,
# not memory guarantees. Approximate pull sizes (GB) from Ollama tag pages.
MODELS = {
    "qwen3_vl_2b": {
        "family": "Qwen3-VL", "parameters": "2B", "purpose": "small baseline",
        "variants": {"q4": ("qwen3-vl:2b-instruct-q4_K_M", 1.9),
                     "q8": ("qwen3-vl:2b-instruct-q8_0", 2.6)},
    },
    "qwen3_vl_4b": {
        "family": "Qwen3-VL", "parameters": "4B", "purpose": "primary candidate",
        "variants": {"q4": ("qwen3-vl:4b-instruct-q4_K_M", 3.3),
                     "q8": ("qwen3-vl:4b-instruct-q8_0", 5.1)},
    },
    "gemma3_4b": {
        "family": "Gemma 3", "parameters": "4B", "purpose": "independent-family comparison",
        "variants": {"q4": ("gemma3:4b-it-q4_K_M", 3.3),
                     "q8": ("gemma3:4b-it-q8_0", 5.0)},
    },
    "granite_vision_2b": {
        "family": "Granite Vision 3.2", "parameters": "2B", "purpose": "compact image baseline",
        "variants": {"q4": ("granite3.2-vision:2b-q4_K_M", 2.4),
                     "q8": ("granite3.2-vision:2b-q8_0", 3.6)},
    },
    "llava_phi3_3_8b": {
        "family": "LLaVA-Phi3", "parameters": "3.8B", "purpose": "older architecture baseline",
        "variants": {"q4": ("llava-phi3:3.8b-mini-q4_0", 2.9)},
    },
}


def run(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


def installed_tags():
    try:
        result = run("ollama", "list")
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Ollama is not available; start its service first. " + e.stderr) from e
    lines = result.stdout.splitlines()[1:]
    return {line.split()[0] for line in lines if line.strip()}


def pull(tag):
    if tag in installed_tags():
        print(f"SKIP {tag}: already installed")
        return
    print(f"Pulling {tag}", flush=True)
    subprocess.run(["ollama", "pull", tag], check=True)
    run("ollama", "show", tag)
    print(f"VERIFIED {tag}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="show curated models and variants")
    group.add_argument("--pull", choices=MODELS, help="download one model")
    group.add_argument("--all", action="store_true", help="download the Q4 variant of all five")
    p.add_argument("--quant", choices=["q4", "q8"], default="q4",
                   help="variant for --pull (default: q4)")
    args = p.parse_args()

    if args.list:
        for key, item in MODELS.items():
            print(f"{key}: {item['family']} {item['parameters']} | {item['purpose']}")
            for quant, (tag, size) in item["variants"].items():
                print(f"  {quant}: {tag} (~{size} GB pull)")
        return

    if not shutil.which("ollama"):
        p.error("ollama executable not found")
    choices = list(MODELS) if args.all else [args.pull]
    failed = []
    for key in choices:
        variants = MODELS[key]["variants"]
        quant = "q4" if args.all else args.quant
        if quant not in variants:
            failed.append((key, f"{quant} is not available"))
            continue
        tag, _ = variants[quant]
        try:
            pull(tag)
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            failed.append((tag, str(exc)))
            print(f"ERROR {tag}: {exc}", file=sys.stderr)
    if failed:
        print("Failed: " + ", ".join(k for k, _ in failed), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
