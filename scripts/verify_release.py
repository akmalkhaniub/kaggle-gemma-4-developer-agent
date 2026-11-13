"""Read-only release check: tests the archived bundles and reports the paper word count.

Usage:  python -m scripts.verify_release
"""

from __future__ import annotations

import hashlib
import subprocess
import sys

from harness.variants import ROOT


def main() -> None:
    subprocess.run([sys.executable, "-m", "scripts.build_controlled_experiments"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=ROOT, check=True)
    v2_zip = (ROOT / "artifacts" / "v2_submission.zip").read_bytes()
    print("v2 archive SHA-256:", hashlib.sha256(v2_zip).hexdigest())
    paper = (ROOT / "paper" / "PAPER_WRITEUP.md").read_text(encoding="utf-8")
    words = len(paper.split())
    print("Paper whitespace word count:", words)
    if words > 3000:
        raise SystemExit("paper exceeds the 3,000-word limit")


if __name__ == "__main__":
    main()
