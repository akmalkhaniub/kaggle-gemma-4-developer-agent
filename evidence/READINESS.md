# Submission readiness — 2026-11-12 (revised)

- Kaggle API (20:29 UTC): v2 58201114 COMPLETE 0.18; v3 58250000 COMPLETE 0.15; v4 58271330 PENDING; quota 0 remaining today.
- Best observed candidate: artifacts/v2_submission.zip (content digest 3a47fac2...a9707).
- v4/v5 contents verified equal to submitted ZIPs by content digest; ZIP bytes differ only by DEFLATE implementation (zlib-ng).
- Paper: paper/PAPER_WRITEUP.md (paste-ready copy paper/WRITEUP_FINAL.md, 2,909 words incl. references); figures in paper/figures/; cover paper/cover_image.png.
- All paper numbers regenerate via `python -m analysis.run_all`; test_committed_report_is_current guards drift.
- Public companion is version 10 (COMPLETE, 2026-11-12 22:23 UTC). It reproduces the data audit, prompt bytes, instruction
  audit with sensitivity analysis, score resolution, both figures, content digests and the official v3 compile. Its audit and
  score outputs equal the local ones (the notebook omits only the bulky gap_by_n table); outputs are in evidence/paper_v10/.
  History: v8 failed (missing Mapping import under Python 3.13); v9 completed; v10 added the sensitivity analysis and the
  per-unit Figure 1(b).
- Writeup submission state: not verified (CLI cannot see it).
- Second-rater check (2026-11-12): an independent Claude (Sonnet) instance labelled the 51 units blind (prompts, definitions and
  verbatim v2 excerpts only). Kind agreement 47/51 (kappa 0.845; all 4 disagreements are rationale vs environment); retention
  agreement 49-51/51. Under its labels rationales were dropped 3-4 of 8 vs 5/34 directives (ratio 2.6-3.4, vs 5.1 for ours).
  Raw output: evidence/second_rater.json; analysis: evidence/interrater_report.json (repository only, not in notebook v10).
- Paper word count 2,959 (whitespace tokens, incl. references and tables).
