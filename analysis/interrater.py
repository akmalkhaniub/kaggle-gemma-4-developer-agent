"""Agreement between the first rater (analysis.prompt_units) and an independent second rater.

The second rater saw only the two prompts, the category definitions and verbatim v2 excerpts,
never the first rater's kinds, summaries or v3 excerpts. Its raw output is stored in
evidence/second_rater.json and compared here on two judgements per unit:

  kind      - directive / rationale / environment / example
  retained  - is the same idea still present in v3 (yes / partly / no)

Usage:  python -m analysis.interrater      (writes evidence/interrater_report.json)
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from analysis.prompt_units import UNITS, Unit, _rates

ROOT = Path(__file__).resolve().parents[1]
SECOND_RATER_PATH = ROOT / "evidence" / "second_rater.json"
REPORT_PATH = ROOT / "evidence" / "interrater_report.json"
KINDS = ("directive", "rationale", "environment", "example")
RETAINED = ("yes", "partly", "no")


def cohens_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Chance-corrected agreement between two label sequences of equal length."""
    if len(a) != len(b) or not a:
        raise ValueError("label sequences must be non-empty and of equal length")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n**2
    if expected == 1:
        return 1.0 if observed == 1 else 0.0
    return (observed - expected) / (1 - expected)


def load_second_rater(path: Path = SECOND_RATER_PATH) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(labels: Mapping[str, Mapping[str, object]], ids: Sequence[str]) -> None:
    missing = [i for i in ids if i not in labels]
    if missing:
        raise ValueError(f"second rater did not label: {missing}")
    for i in ids:
        if labels[i]["kind"] not in KINDS:
            raise ValueError(f"{i}: invalid kind {labels[i]['kind']!r}")
        if labels[i]["retained"] not in RETAINED:
            raise ValueError(f"{i}: invalid retained {labels[i]['retained']!r}")


def compare(units: List[Unit] = UNITS, second: Optional[Mapping[str, object]] = None) -> Dict[str, object]:
    second = second if second is not None else load_second_rater()
    labels = second["labels"]
    ids = [u.uid for u in units]
    _validate(labels, ids)

    first_kind = {u.uid: u.kind for u in units}
    second_kind = {i: labels[i]["kind"] for i in ids}
    first_dropped = {u.uid for u in units if u.v3_excerpt is None}

    kind_pairs = [(first_kind[i], second_kind[i]) for i in ids]
    confusion = {k: {m: sum(1 for x, y in kind_pairs if x == k and y == m) for m in KINDS} for k in KINDS}
    kind_agree = sum(x == y for x, y in kind_pairs)

    # "partly" is ambiguous, so retention is compared under both readings.
    retention = {}
    headline = {}
    for name, dropped_values in (("partly_counts_as_kept", {"no"}), ("partly_counts_as_dropped", {"no", "partly"})):
        second_dropped = {i for i in ids if labels[i]["retained"] in dropped_values}
        agree = sum((i in first_dropped) == (i in second_dropped) for i in ids)
        retention[name] = {
            "agreement": agree,
            "fraction": round(agree / len(ids), 3),
            "kappa": round(cohens_kappa(["dropped" if i in first_dropped else "kept" for i in ids],
                                        ["dropped" if i in second_dropped else "kept" for i in ids]), 3),
            "disagreements": [i for i in ids if (i in first_dropped) != (i in second_dropped)],
        }
        headline[name] = _rates(units, second_kind, second_dropped)

    return {
        "units": len(ids),
        "kind": {
            "agreement": kind_agree,
            "fraction": round(kind_agree / len(ids), 3),
            "kappa": round(cohens_kappa([x for x, _ in kind_pairs], [y for _, y in kind_pairs]), 3),
            "confusion_first_by_second": confusion,
            "disagreements": [{"id": i, "first": first_kind[i], "second": second_kind[i]}
                              for i in ids if first_kind[i] != second_kind[i]],
            "second_rater_borderline": [i for i in ids if labels[i].get("borderline")],
        },
        "retention": retention,
        "headline_under_second_rater": headline,
        "headline_under_first_rater": _rates(units, first_kind, first_dropped),
        "second_rater_uncovered_ideas": second.get("uncovered", []),
    }


def main() -> None:
    report = compare()
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    k, r = report["kind"], report["retention"]
    print(f"kind agreement {k['agreement']}/{report['units']} (kappa {k['kappa']}); "
          f"retention agreement strict {r['partly_counts_as_kept']['agreement']}, "
          f"lenient {r['partly_counts_as_dropped']['agreement']}")


if __name__ == "__main__":
    main()
