#!/usr/bin/env python3
"""
inter_rater_analysis.py
=======================
Computes inter-rater reliability on the collected annotation responses.

Data model (responses.json):
  {
    "5":  {                           ← batch_id
      "session_abc": {
        "submitted_at": 1234567890,
        "annotations": {
          "Inseguros-Barranco-GGZ-2016/19774833.0/heading_0.jpg": {
            "isDangerous": true,
            "notes": "...",
            "strokes": [...]
          },
          ...
        }
      },
      "session_xyz": { ... }
    },
    "12": { ... }
  }

Outputs:
  - Per-batch agreement table (Cohen's Kappa for every pair)
  - Per-image majority vote + confidence
  - Fleiss' Kappa across all raters (batch-level)
  - CSV exports

Usage:
    python inter_rater_analysis.py
    python inter_rater_analysis.py --min-raters 2 --output results/
"""

import json
import argparse
import csv
import math
from pathlib import Path
from collections import defaultdict
from itertools import combinations

RESPONSES_FILE = Path("server_data/responses.json")


# ──────────────────────────────────────────────────────────────────────────────
# AGREEMENT METRICS
# ──────────────────────────────────────────────────────────────────────────────

def cohen_kappa(labels_a: list, labels_b: list) -> float:
    """
    Cohen's Kappa for two raters on the same items.
    Binary labels (True/False or 1/0).
    Returns kappa in [-1, 1].  NaN if undefined (all same label).
    """
    assert len(labels_a) == len(labels_b) and len(labels_a) > 0
    n = len(labels_a)

    # Observed agreement
    po = sum(a == b for a, b in zip(labels_a, labels_b)) / n

    # Expected agreement
    p_pos_a = sum(labels_a) / n
    p_pos_b = sum(labels_b) / n
    pe = p_pos_a * p_pos_b + (1 - p_pos_a) * (1 - p_pos_b)

    if pe == 1.0:
        return float("nan")
    return (po - pe) / (1 - pe)


def fleiss_kappa(ratings_matrix: list[list[int]], n_categories: int = 2) -> float:
    """
    Fleiss' Kappa for multiple raters.
    ratings_matrix: list of subjects, each a list of category counts.
      e.g. for 3 raters, binary: [[2, 1], [3, 0], [1, 2]]  (n_pos, n_neg)
    """
    N = len(ratings_matrix)      # subjects
    n = sum(ratings_matrix[0])   # raters per subject (assumed constant)
    if N == 0 or n <= 1:
        return float("nan")

    # P_j: proportion of all assignments in category j
    P_j = [0.0] * n_categories
    for row in ratings_matrix:
        for j, count in enumerate(row):
            P_j[j] += count
    total = N * n
    P_j = [p / total for p in P_j]

    # P_i: extent of agreement for subject i
    P_i_sum = 0.0
    for row in ratings_matrix:
        P_i = sum(c * (c - 1) for c in row) / (n * (n - 1))
        P_i_sum += P_i
    P_bar    = P_i_sum / N
    P_e_bar  = sum(p ** 2 for p in P_j)

    if P_e_bar == 1.0:
        return float("nan")
    return (P_bar - P_e_bar) / (1 - P_e_bar)


def kappa_label(k: float) -> str:
    if math.isnan(k):   return "N/A"
    if k < 0.00:        return "Poor (< chance)"
    if k < 0.20:        return "Slight"
    if k < 0.40:        return "Fair"
    if k < 0.60:        return "Moderate"
    if k < 0.80:        return "Substantial"
    return "Almost perfect"


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ANALYSIS
# ──────────────────────────────────────────────────────────────────────────────

def analyse(responses: dict, min_raters: int = 2):
    """
    Returns:
      batch_stats   — list of dicts, one per batch
      image_stats   — list of dicts, one per image (majority vote)
    """
    batch_stats = []
    image_stats = []

    for batch_id, rater_map in sorted(responses.items(), key=lambda x: int(x[0])):
        sessions = list(rater_map.keys())
        n_raters = len(sessions)

        if n_raters < min_raters:
            continue

        # Collect all images in this batch
        all_images = set()
        for sess_data in rater_map.values():
            all_images.update(sess_data["annotations"].keys())
        all_images = sorted(all_images)

        # Build rater × image label matrix
        # label = 1 if isDangerous else 0, None if not annotated
        def get_label(sess_data, img):
            ann = sess_data["annotations"].get(img)
            if ann is None:
                return None
            v = ann.get("isDangerous")
            if v is None:
                return None
            return 1 if v else 0

        rater_labels = {
            sid: [get_label(rater_map[sid], img) for img in all_images]
            for sid in sessions
        }

        # ── Per-image majority vote ──────────────────────────────────────────
        for img in all_images:
            votes = [rater_labels[sid][all_images.index(img)]
                     for sid in sessions
                     if rater_labels[sid][all_images.index(img)] is not None]
            if not votes:
                continue
            n_dangerous    = sum(votes)
            n_safe         = len(votes) - n_dangerous
            majority_vote  = 1 if n_dangerous > n_safe else 0
            confidence     = max(n_dangerous, n_safe) / len(votes)
            agreement      = "unanimous" if confidence == 1.0 else "majority" if confidence > 0.5 else "tied"
            image_stats.append({
                "batch_id":      int(batch_id),
                "image":         img,
                "n_raters":      len(votes),
                "n_dangerous":   n_dangerous,
                "n_safe":        n_safe,
                "majority_vote": "dangerous" if majority_vote else "safe",
                "confidence":    round(confidence, 3),
                "agreement":     agreement,
            })

        # ── Per-batch pairwise Cohen's Kappa ────────────────────────────────
        # Only images where BOTH raters gave a label
        pairwise_kappas = []
        for s1, s2 in combinations(sessions, 2):
            paired = [
                (rater_labels[s1][i], rater_labels[s2][i])
                for i in range(len(all_images))
                if rater_labels[s1][i] is not None and rater_labels[s2][i] is not None
            ]
            if len(paired) < 2:
                continue
            l1, l2 = zip(*paired)
            k = cohen_kappa(list(l1), list(l2))
            pairwise_kappas.append(k)

        mean_kappa = (
            sum(k for k in pairwise_kappas if not math.isnan(k)) /
            max(1, sum(1 for k in pairwise_kappas if not math.isnan(k)))
        ) if pairwise_kappas else float("nan")

        # ── Fleiss Kappa ─────────────────────────────────────────────────────
        # Only for images with a response from EVERY rater
        full_rows = []
        for i, img in enumerate(all_images):
            row_labels = [rater_labels[sid][i] for sid in sessions]
            if None not in row_labels:
                n_pos = sum(row_labels)
                full_rows.append([n_pos, n_raters - n_pos])

        fk = fleiss_kappa(full_rows, n_categories=2) if len(full_rows) >= 2 else float("nan")

        # ── Percent dangerous ────────────────────────────────────────────────
        all_labels = [
            v for sid in sessions
            for v in rater_labels[sid]
            if v is not None
        ]
        pct_dangerous = round(sum(all_labels) / len(all_labels) * 100, 1) if all_labels else 0.0

        batch_stats.append({
            "batch_id":        int(batch_id),
            "n_images":        len(all_images),
            "n_raters":        n_raters,
            "mean_cohen_kappa": round(mean_kappa, 4) if not math.isnan(mean_kappa) else "NaN",
            "kappa_label":     kappa_label(mean_kappa),
            "fleiss_kappa":    round(fk, 4) if not math.isnan(fk) else "NaN",
            "pct_dangerous":   pct_dangerous,
            "n_full_rows":     len(full_rows),
        })

    return batch_stats, image_stats


def print_summary(batch_stats, image_stats):
    print("\n" + "="*72)
    print("  INTER-RATER RELIABILITY SUMMARY")
    print("="*72)

    valid_kappas = [b["mean_cohen_kappa"] for b in batch_stats if b["mean_cohen_kappa"] != "NaN"]
    if valid_kappas:
        overall = sum(valid_kappas) / len(valid_kappas)
        print(f"\n  Overall mean Cohen's Kappa  : {overall:.4f}  ({kappa_label(overall)})")
        print(f"  Batches analysed            : {len(batch_stats)}")
        print(f"  Images analysed             : {len(image_stats)}")

    print("\n  Top 10 batches by kappa:")
    top = sorted([b for b in batch_stats if b["mean_cohen_kappa"] != "NaN"],
                 key=lambda x: x["mean_cohen_kappa"], reverse=True)[:10]
    for b in top:
        print(f"    Batch {b['batch_id']:>4}  κ={b['mean_cohen_kappa']:.3f}  ({b['kappa_label']})  "
              f"{b['n_raters']} raters  {b['pct_dangerous']}% dangerous")

    print("\n  Batches with LOW agreement (κ < 0.4):")
    low = [b for b in batch_stats
           if b["mean_cohen_kappa"] != "NaN" and b["mean_cohen_kappa"] < 0.4]
    if low:
        for b in low[:10]:
            print(f"    Batch {b['batch_id']:>4}  κ={b['mean_cohen_kappa']:.3f}  ({b['kappa_label']})  "
                  f"{b['pct_dangerous']}% dangerous")
    else:
        print("    None — great agreement!")

    tied = [i for i in image_stats if i["agreement"] == "tied"]
    print(f"\n  Images with tied votes       : {len(tied)}")
    print("="*72 + "\n")


def write_csvs(batch_stats, image_stats, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # Batch-level
    batch_csv = output_dir / "batch_agreement.csv"
    if batch_stats:
        with open(batch_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=batch_stats[0].keys())
            w.writeheader(); w.writerows(batch_stats)
        print(f"  Wrote {batch_csv}")

    # Image-level majority vote
    img_csv = output_dir / "image_majority_vote.csv"
    if image_stats:
        with open(img_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=image_stats[0].keys())
            w.writeheader(); w.writerows(image_stats)
        print(f"  Wrote {img_csv}")

    # Consensus JSON (only images with clear majority, confidence > 0.5)
    consensus = {
        row["image"]: {
            "isDangerous": row["majority_vote"] == "dangerous",
            "confidence":  row["confidence"],
            "n_raters":    row["n_raters"],
            "agreement":   row["agreement"],
        }
        for row in image_stats
        if row["agreement"] != "tied"
    }
    cons_json = output_dir / "consensus_annotations.json"
    with open(cons_json, "w", encoding="utf-8") as f:
        json.dump(consensus, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {cons_json}  ({len(consensus)} images with clear majority)")


# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", type=Path, default=RESPONSES_FILE)
    parser.add_argument("--min-raters", type=int, default=2,
                        help="Minimum raters per batch to include in analysis")
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()

    if not args.responses.exists():
        print(f"❌ Responses file not found: {args.responses}")
        raise SystemExit(1)

    with open(args.responses, encoding="utf-8") as f:
        responses = json.load(f)

    print(f"Loaded {len(responses)} batches with responses")

    batch_stats, image_stats = analyse(responses, min_raters=args.min_raters)
    print_summary(batch_stats, image_stats)
    write_csvs(batch_stats, image_stats, args.output)


if __name__ == "__main__":
    main()