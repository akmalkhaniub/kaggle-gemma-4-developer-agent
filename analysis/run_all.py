"""Regenerates every number and figure the paper cites from archived artifacts.

Usage:  python -m analysis.run_all
Writes: evidence/analysis_report.json, paper/figures/fig1_prompt_audit.png,
        paper/figures/fig2_score_resolution.png
Read-only with respect to the paper text and all submission artifacts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis.prompt_units import audit_units
from analysis.score_resolution import summarize
from harness.variants import ROOT, changed_files, changed_lines, content_digest, load_variants

BLUE, AMBER, GREY = "#2f6fdb", "#d08a00", "#6b7280"
SECTIONS = ["preamble", "hard limits", "call plan", "procedure", "decision rules", "issue"]  # "procedure" = v3 "WORKFLOW"


def build_report(root: Path = ROOT) -> dict:
    variants = load_variants(root)
    v2 = variants["v2"].files
    prompts = {name: v.files["prompts/system.md"] for name, v in variants.items()}
    controlled = {}
    for name in ("v3", "v4", "v5"):
        files = variants[name].files
        controlled[name] = {
            "submission_ref": variants[name].submission_ref,
            "changed_files": changed_files(v2, files),
            "config_diff": {f: changed_lines(v2[f], files[f]) for f in changed_files(v2, files) if f != "prompts/system.md"},
        }
    return {
        "prompt_bytes": {n: len(p.encode("utf-8")) for n, p in prompts.items()},
        "prompt_sha256": {n: hashlib.sha256(p.encode("utf-8")).hexdigest() for n, p in prompts.items()},
        "bundle_content_digest": {n: content_digest(v.files) for n, v in variants.items()},
        "variant_diffs_vs_v2": controlled,
        "instruction_audit": audit_units(prompts["v2"], prompts["v3"]),
        "score_resolution": summarize(0.18, 0.15),
    }


KIND_COLORS = {"directive": "#2f6fdb", "rationale": "#d08a00", "environment": "#1b9e77", "example": "#7b5ea7"}
MAP_SECTIONS = ["preamble", "hard limits", "call plan", "procedure", "decision rules"]


def _unit_map(ax, audit: dict) -> None:
    """One square per v2 guidance unit: colour = kind, solid = kept in v3, hatched outline = absent."""
    from matplotlib.patches import Patch, Rectangle

    for row, section in enumerate(MAP_SECTIONS):
        units = [u for u in audit["units"] if u["section"] == section]
        for col, u in enumerate(units):
            color = KIND_COLORS[u["kind"]]
            if u["dropped"]:
                ax.add_patch(Rectangle((col, row), 0.86, 0.8, facecolor="white", edgecolor=color,
                                       hatch="////", linewidth=1.4))
            else:
                ax.add_patch(Rectangle((col, row), 0.86, 0.8, facecolor=color, edgecolor=color))
    ax.set_xlim(0, 22)
    ax.set_ylim(len(MAP_SECTIONS), -0.1)
    ax.set_yticks([i + 0.4 for i in range(len(MAP_SECTIONS))], MAP_SECTIONS)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)
    ax.set_title("(b) The 51 v2 guidance units: kept or absent in v3", loc="left")
    handles = [Patch(facecolor=c, edgecolor=c, label=k) for k, c in KIND_COLORS.items()]
    handles.append(Patch(facecolor="white", edgecolor="#444", hatch="////", label="absent from v3"))
    ax.legend(handles=handles, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=5,
              fontsize=8, handlelength=1.2, columnspacing=1.0)


def make_figures(report: dict, out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    out_dir.mkdir(parents=True, exist_ok=True)

    audit = report["instruction_audit"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [1, 1.25]})
    sb = audit["section_bytes"]
    y = range(len(SECTIONS))
    ax1.barh([i + 0.2 for i in y], [sb["v2"].get(s, 0) for s in SECTIONS], 0.4, color="#a7adba", label="v2 (5,351 B)")
    ax1.barh([i - 0.2 for i in y], [sb["v3"].get(s, 0) for s in SECTIONS], 0.4, color="#2b3140", label="v3 (3,340 B)")
    ax1.set_yticks(list(y), SECTIONS)
    ax1.invert_yaxis()
    ax1.set_xlabel("UTF-8 bytes")
    ax1.set_title("(a) Prompt bytes by section", loc="left")
    ax1.legend(frameon=False, loc="lower right")

    _unit_map(ax2, audit)
    fig.tight_layout()
    fig.savefig(out_dir / "fig1_prompt_audit.png", dpi=200)
    plt.close(fig)

    sr = report["score_resolution"]
    ns = sorted(int(n) for n in sr["gap_by_n"])
    lo = [sr["gap_by_n"][str(n)][0] for n in ns]
    hi = [sr["gap_by_n"][str(n)][1] for n in ns]
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.vlines(ns, lo, hi, color=BLUE, linewidth=1.2)
    ax.scatter(ns, lo, s=6, color=BLUE)
    ax.scatter(ns, hi, s=6, color=BLUE)
    ax.axvline(129, color=GREY, linestyle="--", linewidth=0.8)
    ax.text(131, max(hi) - 0.5, "129 public dev tasks", color=GREY, fontsize=8)
    ax.set_xlabel("Hypothetical number of evaluated tasks N (only N reproducing both 0.18 and 0.15 shown)")
    ax.set_ylabel("v2 - v3 gap (tasks)")
    ax.set_title("Task-count gap implied by displayed scores 0.18 and 0.15 (binary scoring assumed)", loc="left")
    ax.set_xlim(0, max(ns) + 5)
    fig.tight_layout()
    fig.savefig(out_dir / "fig2_score_resolution.png", dpi=200)
    plt.close(fig)


def main() -> None:
    report = build_report()
    (ROOT / "evidence" / "analysis_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    make_figures(report, ROOT / "paper" / "figures")
    a, s = report["instruction_audit"], report["score_resolution"]
    print(f"units: {a['units_retained']}/{a['units_total']} retained; "
          f"rationales dropped {a['by_kind']['rationale']['dropped']}/{a['by_kind']['rationale']['v2']}; "
          f"directives dropped {a['by_kind']['directive']['dropped']}/{a['by_kind']['directive']['v2']}")
    print(f"score resolution: smallest N={s['smallest_consistent_n']}, gap for N<=129 = "
          f"{s['task_gap_min_max_for_n_le_129']} tasks, 2-sigma independent N={s['required_n_two_sigma_independent']}")


if __name__ == "__main__":
    main()
