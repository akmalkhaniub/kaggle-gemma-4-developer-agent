"""Builds v6: the v3 bundle with the guidance dropped by the v2 -> v3 compression restored.

Only ``prompts/system.md`` changes; tools, sampling (T=0.4) and the 8-minute budget stay as in v3,
so v6 vs v3 isolates the dropped units. Each restored unit reuses its v2 wording verbatim
(checked against ``analysis.prompt_units.UNITS``). U18/U19 are not restored: they forbid the three
graph tools, which v3 no longer declares.

Usage:  python -m scripts.build_restoration_variant [--write]
Without --write it builds into a temporary directory and only verifies.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from analysis.prompt_units import UNITS
from harness.adk_bundle import build_submission_zip, validate_submission_bundle
from harness.variants import ROOT, changed_files, content_digest, load_variants

NOT_APPLICABLE = {"U18", "U19"}  # graph-tool guidance; v3 removed those tools

# (anchor in v3, replacement). Every anchor must occur exactly once.
INSERTIONS = [
    ("so hidden tests pass. Treat exact symbol names",
     "so hidden tests pass. Hidden tests were written from the issue specification, so treat exact symbol names"),  # U02
    ("is graded; an unedited tree always scores 0.",
     "is graded. An edit on disk counts; an unedited tree always scores 0."),  # U07
    ("`sitecustomize.py`, `usercustomize.py`).",
     "`sitecustomize.py`, `usercustomize.py`). Phase 2 resets them before grading."),  # U09
    ("strictly under `/tmp` via `run_command`; any untracked file inside `/workspace` enters your graded patch.",
     "strictly under `/tmp` via `run_command` (for example `cat > /tmp/repro.py << 'EOF'`). "
     "`read_file`/`write_file`/`edit_file` only accept paths inside `/workspace`, "
     "and any untracked file inside `/workspace` enters your graded patch."),  # U11, U12
    ("(`run_command` keeps only the first 5,000 chars).",
     "(`run_command` keeps only the first 5,000 chars, while pytest prints its verdict at the end)."),  # U17
    ("`git grep -n -F` and `git ls-files` (`head -n 30`).",
     "`git grep -n -F` and `git ls-files` (`rg` and `tree` are not installed; `head -n 30`)."),  # U30
    ("verbatim from the file. Never repeat",
     "verbatim from the file. Use `write_file` only if the issue genuinely requires a new source module. Never repeat"),  # U36
    ("Keep unrelated code and signatures intact.",
     "Fix the root cause cleanly. Keep unrelated code and signatures intact."),  # U38
    ("from missing optional fixtures or unrelated modules.",
     "from missing optional fixtures or unrelated modules; judge by the tests covering the modified code path."),  # U43
    ("**Submit**: Run `git status --short && git diff`,",
     "**Submit**: Run `git status --short && git diff` (`git diff` alone hides untracked files that `submit_patch` captures),"),  # U45
    ("- Stuck on empty searches:",
     "- Multiple candidate sites: edit where wrong behaviour is produced rather than where it is merely observed.\n"
     "- Stuck on empty searches:"),  # U49
]


def restored_prompt(v3_prompt: str) -> str:
    text = v3_prompt
    for anchor, replacement in INSERTIONS:
        if text.count(anchor) != 1:
            raise SystemExit(f"anchor not unique in v3 prompt: {anchor!r}")
        text = text.replace(anchor, replacement)
    return text


def derive_v6(v3: dict) -> dict:
    files = dict(v3)
    files["prompts/system.md"] = restored_prompt(v3["prompts/system.md"])
    return files


def check(v3: dict, v6: dict) -> list[str]:
    """Returns the restored unit ids; raises if anything else changed or a unit is missing."""
    if changed_files(v3, v6) != ["prompts/system.md"]:
        raise SystemExit(f"expected only prompts/system.md to change, got {changed_files(v3, v6)}")
    prompt = v6["prompts/system.md"]
    dropped = [u for u in UNITS if u.v3_excerpt is None and u.uid not in NOT_APPLICABLE]
    missing = [u.uid for u in dropped if u.v2_excerpt not in prompt]
    if missing:
        raise SystemExit(f"restored prompt lacks the v2 wording of {missing}")
    lost = [u.uid for u in UNITS if u.v3_excerpt is not None and u.v3_excerpt not in prompt]
    if lost:
        raise SystemExit(f"restoration removed surviving v3 guidance {lost}")
    return [u.uid for u in dropped]


def main(write: bool) -> None:
    v3 = dict(load_variants()["v3"].files)
    v6 = derive_v6(v3)
    restored = check(v3, v6)
    out = ROOT / "experiments" / "v6_restoration" if write else Path(tempfile.mkdtemp())
    bundle = out / "bundle"
    for rel, text in v6.items():
        (bundle / rel).parent.mkdir(parents=True, exist_ok=True)
        (bundle / rel).write_bytes(text.encode("utf-8"))
    validate_submission_bundle(bundle)
    zip_path = build_submission_zip(bundle, out / "submission.zip")
    v2_len = len(load_variants()["v2"].files["prompts/system.md"])
    print(f"v6_restoration: restored {', '.join(restored)}; prompt {len(v3['prompts/system.md'])} -> "
          f"{len(v6['prompts/system.md'])} chars (v2 {v2_len}); content {content_digest(v6)[:16]}; zip {zip_path}")


if __name__ == "__main__":
    main(write="--write" in sys.argv)
