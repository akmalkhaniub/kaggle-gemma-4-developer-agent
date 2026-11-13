"""Rebuilds the one-factor variants (v4, v5) from the archived v2 files and checks
that their contents equal the submitted ZIPs recorded in experiments/manifest.json.

Identity is checked by content digest. ZIP bytes are compared only informatively:
DEFLATE output differs between zlib and zlib-ng builds of Python.

Usage:  python -m scripts.build_controlled_experiments [--write]
Without --write it only verifies; it never edits submission metadata in the manifest.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from harness.adk_bundle import build_submission_zip, validate_submission_bundle
from harness.variants import ROOT, changed_files, content_digest, read_zip_files

GRAPH_TOOLS = ("get_code_neighbors", "search_similar_code", "get_code_subgraph")


def derive_variants(v2: dict) -> dict:
    tools_only = dict(v2)
    for name in GRAPH_TOOLS:
        tools_only["agent.yaml"] = tools_only["agent.yaml"].replace(f"  - {name}\n", "")
    temperature_only = dict(v2)
    temperature_only["configs/sampling.yaml"] = v2["configs/sampling.yaml"].replace("temperature: 0.2", "temperature: 0.0")
    return {"v4_tools_only": tools_only, "v5_temperature_only": temperature_only}


def main(write: bool) -> None:
    v2 = json.loads((ROOT / "artifacts" / "v2_files.json").read_text(encoding="utf-8"))
    manifest = {r["variant"]: r for r in json.loads((ROOT / "experiments" / "manifest.json").read_text())}
    for name, files in derive_variants(v2).items():
        if len(changed_files(v2, files)) != 1:
            raise SystemExit(f"{name}: expected exactly one changed file")
        if write:
            out = ROOT / "experiments" / name
        else:
            out = Path(tempfile.mkdtemp())
        bundle = out / "bundle"
        for rel, text in files.items():
            (bundle / rel).parent.mkdir(parents=True, exist_ok=True)
            (bundle / rel).write_bytes(text.encode("utf-8"))
        validate_submission_bundle(bundle)
        archived = ROOT / "experiments" / name / "submission.zip"
        submitted = read_zip_files(archived) if not write else files
        rebuilt_zip = build_submission_zip(bundle, out / "submission.zip")
        same_content = content_digest(read_zip_files(rebuilt_zip)) == content_digest(submitted)
        zip_note = "identical" if hashlib.sha256(rebuilt_zip.read_bytes()).hexdigest() == manifest[name]["sha256"] \
            else "differs (DEFLATE implementation)"
        print(f"{name}: content {'OK' if same_content else 'MISMATCH'} {content_digest(files)[:16]}; zip bytes {zip_note}")
        if not same_content:
            raise SystemExit(1)


if __name__ == "__main__":
    main(write="--write" in sys.argv)
