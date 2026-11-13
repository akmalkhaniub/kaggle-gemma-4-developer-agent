"""Snapshots competition submission status into evidence/ (never edits the paper).

Usage:  python -m scripts.kaggle_status
Requires an authenticated Kaggle CLI. Writes evidence/controlled_submissions.csv
and evidence/latest_status_check.json with the statuses actually returned.
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
COMPETITION = "gemma-4-developer-agent"
TRACKED = {"58201114": "v2", "58250000": "v3", "58271330": "v4"}


def parse_submissions(csv_text: str) -> Dict[str, Dict[str, object]]:
    """Maps tracked variant name -> {ref, status, public_score} from Kaggle CSV output."""
    rows: List[dict] = list(csv.DictReader(io.StringIO(csv_text.strip())))
    out: Dict[str, Dict[str, object]] = {}
    for row in rows:
        name = TRACKED.get(row.get("ref", "").strip())
        if name:
            score = row.get("publicScore", "").strip()
            out[name] = {
                "ref": row["ref"].strip(),
                "status": row.get("status", "").replace("SubmissionStatus.", "").strip(),
                "public_score": float(score) if score else None,
            }
    return out


def _kaggle(*args: str) -> str:
    cmd = [sys.executable, "-m", "kaggle", "competitions", *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def main() -> None:
    submissions = _kaggle("submissions", "-c", COMPETITION, "--csv")
    limits = _kaggle("submission-limits", COMPETITION)
    snapshot = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "submissions": parse_submissions(submissions),
        "quota_output": limits,
    }
    (ROOT / "evidence" / "controlled_submissions.csv").write_text(submissions, encoding="utf-8")
    (ROOT / "evidence" / "latest_status_check.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
