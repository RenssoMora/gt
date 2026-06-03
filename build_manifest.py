#!/usr/bin/env python3
"""
build_manifest.py
=================
Scans image-extraction/, filters invalid images via server_data/blacklist.json,
shuffles and splits into batches.

Run filter_invalid_images.py FIRST to build the blacklist, then run this.

Usage:
    python build_manifest.py [--batch-size 32] [--root ../image-extraction]
"""

import argparse, glob, json, random
from pathlib import Path

DEFAULT_BATCH_SIZE = 32
DEFAULT_ROOT       = Path(__file__).parent.parent / "image-extraction"

DISTRICT_GLOBS = [
    "Inseguros-Barranco-GGZ-2016/**/*.jpg",
    "Inseguros-La_Victoria-GGZ-2016/**/*.jpg",
]


def load_blacklist() -> set:
    bl_path = Path("server_data/blacklist.json")
    if bl_path.exists():
        with open(bl_path) as f:
            data = json.load(f)
        print(f"  Blacklist: {len(data):,} invalid images will be excluded")
        return set(data.keys())
    print("  No blacklist found — run filter_invalid_images.py first (recommended)")
    return set()


def discover(root: Path) -> list:
    blacklist = load_blacklist()
    images = []
    total_skipped = 0
    for pattern in DISTRICT_GLOBS:
        found = sorted(glob.glob(str(root / pattern), recursive=True))
        rel   = [str(Path(p).relative_to(root)) for p in found]
        clean = [r for r in rel if r not in blacklist]
        skipped = len(rel) - len(clean)
        total_skipped += skipped
        images.extend(clean)
        label = pattern.split("/")[0]
        print(f"  {label}: {len(clean):,} valid  ({skipped:,} blacklisted)")
    if total_skipped:
        print(f"  Total excluded: {total_skipped:,}")
    return images


def build_batches(images: list, size: int) -> dict:
    random.shuffle(images)
    batches = {}
    for i in range(0, len(images), size):
        bid = str(i // size)
        batches[bid] = {"id": int(bid), "images": images[i : i + size]}
    return batches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--root",       type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--seed",       type=int,  default=42)
    args = parser.parse_args()

    root = args.root.resolve()
    print(f"\n🔍 Scanning: {root}")
    if not root.exists():
        print(f"❌ Root not found: {root}")
        raise SystemExit(1)

    images = discover(root)
    print(f"\n📸 Total valid images: {len(images):,}")

    random.seed(args.seed)
    batches = build_batches(images, args.batch_size)
    print(f"📦 Batches: {len(batches):,} (size ≤ {args.batch_size})")

    Path("server_data").mkdir(exist_ok=True)
    out = Path("server_data/batches.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(batches, f, indent=2, ensure_ascii=False)
    print(f"✅ Wrote {out}")
    print(f"\n🎉 Done. {len(images):,} images → {len(batches):,} batches of ≤{args.batch_size}\n")


if __name__ == "__main__":
    main()