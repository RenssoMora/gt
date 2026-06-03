#!/usr/bin/env python3
"""
filter_invalid_images.py
========================
Scans all images in the district folders and detects "invalid" ones —
Google Street View "Sorry, we have no imagery here" placeholders, corrupt
files, or other non-useful images.

Strategy: DO NOT DELETE anything. Instead writes a blacklist file
  server_data/blacklist.json
which build_manifest.py and app.py both respect. This preserves the
original folder/file structure and lets you audit what was filtered.

Detection methods (in order of speed):
  1. File size < SIZE_THRESHOLD  → almost certainly a placeholder (they are ~5-8 KB)
  2. Image hash match            → exact match against known placeholder hashes
  3. Text pixel detection        → image is mostly grey/white and contains a
                                   horizontal text band (the "Sorry..." message)
     This catches resized variants of the placeholder.

Usage:
    python filter_invalid_images.py
    python filter_invalid_images.py --root ../image-extraction --dry-run
    python filter_invalid_images.py --root ../image-extraction --show-samples

After running, rebuild the manifest to exclude blacklisted images:
    python build_manifest.py --root ../image-extraction
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from PIL import Image
    import numpy as np
except ImportError:
    print("Install dependencies first:  pip install Pillow numpy")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_ROOT = Path("../image-extraction")

DISTRICT_GLOBS = [
    "Inseguros-Barranco-GGZ-2016/**/*.jpg",
    "Inseguros-La_Victoria-GGZ-2016/**/*.jpg",
]

# Files smaller than this (bytes) are almost always the placeholder
SIZE_THRESHOLD = 15_000   # 15 KB  — real street view JPEGs are typically 80–300 KB

# Known MD5 hashes of the exact Google placeholder image variants
# (add more if you find other variants)
KNOWN_BAD_HASHES = {
    # The standard "Sorry, we have no imagery here." grey box
    # Populate this after a first run with --show-samples
}

# ──────────────────────────────────────────────────────────────────────────────
# DETECTION
# ──────────────────────────────────────────────────────────────────────────────

def md5(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def is_placeholder_by_pixels(path: Path) -> bool:
    """
    The Google 'no imagery' placeholder is a near-white/light-grey image
    with a single thin dark-text band near the vertical centre.
    Heuristic: std-dev of the whole image is very low (almost uniform colour).
    """
    try:
        img  = Image.open(path).convert("L")   # greyscale
        arr  = np.array(img, dtype=np.float32)
        std  = arr.std()
        mean = arr.mean()
        # Placeholder: very light (mean > 200) AND very uniform (std < 20)
        if mean > 200 and std < 25:
            return True
        return False
    except Exception:
        return True   # corrupt → also invalid


def classify(path: Path) -> tuple[bool, str]:
    """Returns (is_invalid, reason)."""
    size = path.stat().st_size
    if size < SIZE_THRESHOLD:
        return True, f"tiny_file ({size} bytes)"

    h = md5(path)
    if h in KNOWN_BAD_HASHES:
        return True, f"known_bad_hash ({h[:8]})"

    if is_placeholder_by_pixels(path):
        return True, "placeholder_pixels"

    return False, "ok"


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root",       type=Path, default=DEFAULT_ROOT,
                        help="Path to image-extraction folder")
    parser.add_argument("--dry-run",    action="store_true",
                        help="Print what would be blacklisted without saving")
    parser.add_argument("--show-samples", action="store_true",
                        help="Open the first 5 detected placeholders with PIL for visual check")
    parser.add_argument("--size-threshold", type=int, default=SIZE_THRESHOLD,
                        help=f"File size threshold in bytes (default {SIZE_THRESHOLD})")
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"❌ Root not found: {root}")
        sys.exit(1)

    import glob
    all_paths = []
    for pattern in DISTRICT_GLOBS:
        found = sorted(glob.glob(str(root / pattern), recursive=True))
        all_paths += [Path(p) for p in found]

    print(f"🔍 Scanning {len(all_paths):,} images in {root}")

    blacklist  = {}   # rel_path → reason
    samples    = []
    ok_count   = 0

    for i, path in enumerate(all_paths):
        if i % 1000 == 0:
            print(f"  {i:,} / {len(all_paths):,}  ({len(blacklist):,} bad so far)…", end="\r")

        invalid, reason = classify(path)
        rel = str(path.relative_to(root))

        if invalid:
            blacklist[rel] = reason
            if args.show_samples and len(samples) < 5:
                samples.append(path)
        else:
            ok_count += 1

    print(f"\n\n{'DRY RUN — ' if args.dry_run else ''}Results:")
    print(f"  ✅ Valid images  : {ok_count:,}")
    print(f"  ❌ Invalid images: {len(blacklist):,}")

    # Breakdown by reason
    from collections import Counter
    reasons = Counter(blacklist.values())
    for reason, count in reasons.most_common():
        print(f"     {reason}: {count:,}")

    # Show samples
    if args.show_samples and samples:
        print(f"\nOpening {len(samples)} sample(s) for visual verification…")
        for p in samples:
            try:
                Image.open(p).show()
            except Exception as e:
                print(f"  Could not open {p}: {e}")

    # Save blacklist
    server_data = Path("server_data")
    server_data.mkdir(exist_ok=True)
    blacklist_path = server_data / "blacklist.json"

    if not args.dry_run:
        # Merge with any existing blacklist (don't overwrite manual entries)
        existing = {}
        if blacklist_path.exists():
            with open(blacklist_path) as f:
                existing = json.load(f)
        merged = {**existing, **blacklist}
        with open(blacklist_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Blacklist saved → {blacklist_path}  ({len(merged):,} entries)")
        print("   Now run:  python build_manifest.py  to rebuild without invalid images.")
    else:
        print("\n(Dry run — nothing saved)")

    # Print MD5s of detected files so you can add them to KNOWN_BAD_HASHES
    if blacklist:
        print("\nSample MD5s of invalid images (add to KNOWN_BAD_HASHES if consistent):")
        for path in list(p for p in all_paths if str(p.relative_to(root)) in blacklist)[:10]:
            print(f"  {md5(path)}  {path.name}")


if __name__ == "__main__":
    main()