"""Single source of truth for every submitted or prepared bundle configuration.

Each variant is a mapping ``relative path -> file text`` for the four files in a
declarative ADK bundle. Variants are loaded from the archived artifacts rather
than reconstructed, so analyses always see the exact bytes that were submitted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from harness.adk_bundle import SUBMISSION_FILES

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_FILES = ("agent.yaml", "configs/sampling.yaml", "eval_config.yaml", "prompts/system.md")

Files = Dict[str, str]


@dataclass(frozen=True)
class Variant:
    name: str
    submission_ref: Optional[str]
    description: str
    files: Mapping[str, str]


def _read_bundle_dir(bundle_dir: Path) -> Files:
    return {rel: (bundle_dir / rel).read_bytes().decode("utf-8") for rel in BUNDLE_FILES}


def load_variants(root: Path = ROOT) -> Dict[str, Variant]:
    """Returns v2 (control), v3 (bundled revision), v4 and v5 (one-factor variants)."""
    v2 = json.loads((root / "artifacts" / "v2_files.json").read_text(encoding="utf-8"))
    experiments = root / "experiments"
    return {
        "v2": Variant("v2", "58201114", "Control: 9 tools, T=0.2, 7 min", v2),
        "v3": Variant("v3", "58250000", "Bundled revision: 6 tools, compressed prompt, T=0.4, 8 min",
                      dict(SUBMISSION_FILES)),
        "v4": Variant("v4", "58271330", "v2 minus three graph-tool declarations",
                      _read_bundle_dir(experiments / "v4_tools_only" / "bundle")),
        "v5": Variant("v5", None, "v2 with temperature 0.0 (not evaluated)",
                      _read_bundle_dir(experiments / "v5_temperature_only" / "bundle")),
    }


def changed_files(base: Mapping[str, str], other: Mapping[str, str]) -> List[str]:
    """Bundle files whose bytes differ between two variants."""
    names = sorted(set(base) | set(other))
    return [n for n in names if base.get(n) != other.get(n)]


def changed_lines(base: str, other: str) -> List[str]:
    """Unified-diff lines (without headers) between two file texts."""
    import difflib

    diff = difflib.unified_diff(base.splitlines(), other.splitlines(), lineterm="", n=0)
    return [line for line in diff if line[:1] in "+-" and not line.startswith(("+++", "---"))]


def content_digest(files: Mapping[str, str]) -> str:
    """SHA-256 over sorted (path, bytes) pairs.

    Unlike a ZIP hash, this does not depend on the DEFLATE implementation
    (e.g. zlib vs zlib-ng), so it identifies a configuration across Python builds.
    """
    import hashlib

    h = hashlib.sha256()
    for name in sorted(files):
        data = files[name].encode("utf-8")
        h.update(name.encode("utf-8") + b"\0" + len(data).to_bytes(8, "big") + data)
    return h.hexdigest()


def read_zip_files(zip_path: Path) -> Files:
    import zipfile

    with zipfile.ZipFile(zip_path) as zf:
        if zf.testzip() is not None:
            raise ValueError(f"{zip_path}: CRC check failed")
        return {n: zf.read(n).decode("utf-8") for n in zf.namelist()}
