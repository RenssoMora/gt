# Batch Annotation System  v2 — Local & Deployed

Two modes, same codebase, same data format.

---

## Modes

### LOCAL (default) — solo on your machine

```bash
python app.py                         # defaults to local mode
# or explicitly:
DEPLOY_MODE=local python app.py
```

- `TARGET_RESPONSES = 1` — each batch only needs one answer (yours)
- Your identity (`session_id`) is **pinned server-side** to `LOCAL_SESSION`
  — survives browser clears, incognito tabs, different browsers
- Progress lives entirely in `server_data/` — restart Flask anytime, nothing lost
- Alias screen is **skipped** — you go straight to annotating

To label your annotations with your name:
```bash
LOCAL_SESSION=rensso LOCAL_ALIAS="Rensso" python app.py
```

### DEPLOYED — multiple annotators

```bash
DEPLOY_MODE=deployed python app.py
# or with custom target:
DEPLOY_MODE=deployed TARGET_RESPONSES=3 python app.py
```

- Each browser gets its own `session_id` (generated in localStorage on first visit)
- Each batch collects `TARGET_RESPONSES` independent answers before it's "saturated"
- Annotators enter an alias/name on first visit
- Batch assignment is random, biased toward least-annotated batches

---

## Quick start

```bash
# 1. Build manifest (run once)
python build_manifest.py --batch-size 32 --root ../image-extraction

# 2. Symlink images
cd gt/
ln -s ../image-extraction public/imgs

# 3. Start Flask
python app.py          # LOCAL mode by default

# 4. Start Vite (separate terminal)
npm run dev

# Open http://localhost:5173
```

---

## Switching from local → deployed later

Your `server_data/responses.json` stays intact. Just restart with:

```bash
DEPLOY_MODE=deployed TARGET_RESPONSES=3 python app.py
```

Your already-completed batches count as 1 of the 3 required responses.
Other annotators will fill in the remaining 2.

---

## Data structure

```
server_data/
  batches.json       — fixed list of batches (never changes after build)
  responses.json     — all submitted annotations, keyed by batch then session
  annotators.json    — session registry (who completed what)
```

`responses.json` layout:
```json
{
  "5":  {
    "rensso": {
      "submitted_at": 1234567890,
      "alias": "Rensso",
      "annotations": {
        "Inseguros-Barranco-GGZ-2016/19774833.0/heading_0.jpg": {
          "isDangerous": true,
          "notes": "Hay rejas y grafitis",
          "strokes": [...]
        }
      }
    }
  },
  "12": { "rensso": { ... } }
}
```

---

## Analysis (inter-rater reliability)

```bash
python inter_rater_analysis.py --min-raters 2 --output results/
```

Outputs:
- `results/batch_agreement.csv` — Cohen's κ + Fleiss' κ per batch
- `results/image_majority_vote.csv` — majority label per image
- `results/consensus_annotations.json` — final ground truth

In local mode with 1 rater this analysis isn't meaningful — run it after
the deployed phase when you have ≥ 2 raters per batch.

---

## API reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Progress stats + deploy mode |
| `/api/batch/claim?session_id=X` | GET | Get next open batch |
| `/api/batch/<id>/submit` | POST | Submit annotations |
| `/api/responses/export` | GET | Full data dump (admin) |
| `/api/my/status?session_id=X` | GET | Personal progress |
| `/api/admin/reset_response` | POST | Delete a bad submission |
| `/api/admin/rebuild` | POST | Rebuild manifest (resets all!) |