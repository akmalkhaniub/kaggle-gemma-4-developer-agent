# Gemma 4 Developer Agent: configurations, audits and paper

Declarative Google ADK bundles submitted to the Gemma 4 Developer Agent competition, plus the
analyses behind the paper-track report *What Prompt Compression Removes*.

## Results (authenticated Kaggle CLI)

| Variant | Ref | Change vs v2 | Status | Public score |
|---|---|---|---|---:|
| v2 (control) | 58201114 | — | COMPLETE | 0.18 |
| v3 | 58250000 | prompt −37.6%, 3 tools removed, T 0.2→0.4, 7→8 min | COMPLETE | 0.15 |
| v4 | 58271330 | 3 graph-tool declarations removed only | COMPLETE | 0.17 |
| v5 | — | temperature 0.0 only | not submitted (daily quota) | — |
| v6 | 58319383 | v3 + the 12 dropped guidance units restored (prompt only; vs v3) | PENDING (submitted 13 Nov) | — |

**Best observed candidate: v2** (`artifacts/v2_submission.zip`). Single public runs; not a prediction of private performance.

## Layout

| Path | Purpose |
|---|---|
| `harness/adk_bundle.py` | v3 bundle source, validator (raises `BundleError`), deterministic ZIP packager |
| `harness/variants.py` | Loads v2–v5 from archived bytes; diffs; content digests |
| `analysis/prompt_units.py` | Instruction-unit audit of the v2→v3 prompt (verbatim-checked) |
| `analysis/score_resolution.py` | Which evaluation sizes reproduce the displayed scores; implied task gaps |
| `analysis/interrater.py` | Agreement between our unit labels and an independent second rater (`evidence/second_rater.json`) |
| `analysis/run_all.py` | Regenerates `evidence/analysis_report.json` and `paper/figures/*.png` |
| `scripts/kaggle_status.py` | Snapshots submission status into `evidence/` (never edits the paper) |
| `scripts/build_controlled_experiments.py` | Rebuilds v4/v5 and checks contents match the submitted ZIPs |
| `scripts/verify_release.py` | Read-only release check: rebuild check, tests, paper word count |
| `harness/tools.py`, `harness/agent.py` | Local diagnostic helpers (no model calls, no patch synthesis) |
| `paper/` | Paper, figures, cover image, companion-notebook builder |

## Reproduce

Python 3.12+ with `pip install -r requirements-dev.txt`:

```sh
python -m analysis.run_all
python build_gemma_notebook.py
python paper/build_paper_companion_nb.py
python -m scripts.verify_release
```

Configurations are identified by content digest (SHA-256 over sorted path/bytes pairs), because ZIP
bytes differ between Python builds using zlib and zlib-ng even when contents are identical.

The companion notebook runs the official-data audit, both analyses and the official v3 compilation on
Kaggle CPU: https://www.kaggle.com/code/akmalshahbaz/gemma-4-adk-kv-roofline-power-companion

## Caveats

The local toolkit runs commands without a shell but is not sandboxed. Tests cover bundle rules,
artifact integrity and the analyses, not autonomous repair quality. The paper Writeup must be
*submitted* (not just saved) on the paper-track page; the CLI cannot verify Writeup state.
