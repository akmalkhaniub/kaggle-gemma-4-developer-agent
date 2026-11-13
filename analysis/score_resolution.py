"""What two rounded leaderboard scores can and cannot tell us.

Assumption (stated, not verified): each hidden task contributes a binary pass/fail
and the public score is the pass fraction rounded half-up to two decimals.
Under that assumption we enumerate every evaluation size N whose integer pass
counts reproduce both displayed scores, and the task-count gaps they imply.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Tuple


def displayed(passes: int, n: int, places: int = 2) -> float:
    quantum = Decimal(1).scaleb(-places)
    return float((Decimal(passes) / Decimal(n)).quantize(quantum, rounding=ROUND_HALF_UP))


def pass_counts(score: float, n: int) -> List[int]:
    """Integer pass counts k for which k/N displays as ``score``."""
    return [k for k in range(n + 1) if displayed(k, n) == score]


def consistent_sizes(a: float, b: float, n_min: int = 1, n_max: int = 300) -> Dict[int, Tuple[List[int], List[int]]]:
    """Evaluation sizes N at which both scores are attainable, with their pass counts."""
    out = {}
    for n in range(n_min, n_max + 1):
        ka, kb = pass_counts(a, n), pass_counts(b, n)
        if ka and kb:
            out[n] = (ka, kb)
    return out


def task_gap_range(ka: List[int], kb: List[int]) -> Tuple[int, int]:
    gaps = [x - y for x in ka for y in kb]
    return min(gaps), max(gaps)


def required_n_independent(p: float, delta: float, z: float = 1.96) -> int:
    """Smallest N at which a difference ``delta`` between two independent binomial
    proportions near ``p`` exceeds ``z`` standard errors: delta > z*sqrt(2p(1-p)/N)."""
    return math.ceil(2 * p * (1 - p) * (z / delta) ** 2)


def summarize(a: float = 0.18, b: float = 0.15, n_max: int = 300) -> Dict[str, object]:
    sizes = consistent_sizes(a, b, 1, n_max)
    inconsistent_small = [n for n in range(1, 130) if n not in sizes]
    gaps = {n: task_gap_range(*sizes[n]) for n in sizes}
    up_to_129 = [g for n, g in gaps.items() if n <= 129]
    return {
        "assumption": "binary per-task outcomes; score = pass fraction rounded half-up to 2 decimals",
        "scores": [a, b],
        "smallest_consistent_n": min(sizes),
        "consistent_n_count_up_to": {"n_max": n_max, "count": len(sizes)},
        "inconsistent_n_up_to_129": inconsistent_small,
        "task_gap_min_max_for_n_le_129": [min(g[0] for g in up_to_129), max(g[1] for g in up_to_129)],
        "gap_by_n": {str(n): list(g) for n, g in gaps.items()},
        "required_n_two_sigma_independent": required_n_independent((a + b) / 2, a - b),
    }
