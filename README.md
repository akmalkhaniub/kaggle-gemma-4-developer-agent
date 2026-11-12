# Gemma 4 developer-agent and paper submissions

## Verified competition results

Kaggle CLI checked on November 12, 2026; raw snapshot: `evidence/kaggle_submissions.csv`.

| Configuration | Submission | Status | Public score |
|---|---|---|---:|
| v2, nine tools, temperature 0.2 | 58201114 | COMPLETE | 0.18 |
| v3, six tools, temperature 0.4 | 58250000 | COMPLETE | 0.15 |

**Best observed candidate: v2.** Its archived bundle is `artifacts/v2_submission.zip`; its contents are also available as `artifacts/v2_files.json`. v3 remains a reproducible experiment, not a demonstrated upgrade. Neither score is a prediction of private performance.

## Paper

`paper/PAPER_WRITEUP.md` reports the negative result, measured prompt bytes and experimental limitations. The revised companion requires official task data, records its SHA-256, and compiles the v3 bundle with the official wheelhouse. It does not use fallback task summaries or claim measured tokens, GPU performance or statistical significance.

Public companion: https://www.kaggle.com/code/akmalshahbaz/gemma-4-adk-kv-roofline-power-companion

The paper track requires a Kaggle Writeup with title, subtitle, abstract, methods, experiments and citations, at most 3,000 words. Attach the public companion in Project Links. Saving a draft is insufficient: the Writeup must be submitted. The CLI's ordinary competition-submission list does not verify Writeup status.

## Local verification

Run from this directory with Python 3.12 and `pytest`, `PyYAML`, `numpy` installed:

```sh
python build_gemma_notebook.py
python paper/build_paper_companion_nb.py
python -m pytest -q tests
```

Notebook builders check source generation; the companion's official-data audit and official compilation execute on Kaggle. Local tests cover diagnostic helpers and packaging, not autonomous repair quality. The local agent does not invoke a model or synthesize patches. Shell execution in the diagnostic toolkit is not sandboxed.

No final submission selection or paper Writeup submission is asserted by this README.
