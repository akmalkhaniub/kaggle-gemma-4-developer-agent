"""Instruction-level audit of the v2 -> v3 system-prompt compression.

The v2 prompt is decomposed by hand into atomic guidance units. Each unit cites a
verbatim excerpt of v2 and, when the guidance survives, a verbatim excerpt of v3.
``audit_units`` refuses to run if any excerpt is not found in the corresponding
prompt, so the coding cannot silently drift from the submitted bytes.

Kinds:
  directive    - tells the model what to do or not do
  rationale    - explains why a directive exists
  environment  - states a fact about the sandbox or tools
  example      - a concrete illustration of a directive
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, NamedTuple, Optional


class Unit(NamedTuple):
    uid: str
    section: str
    kind: str
    summary: str
    v2_excerpt: str
    v3_excerpt: Optional[str]  # None means the guidance is absent from v3


UNITS: List[Unit] = [
    Unit("U01", "preamble", "directive", "Smallest correct source change",
         "smallest correct change to the SOURCE code", "smallest correct fix to SOURCE code"),
    Unit("U02", "preamble", "rationale", "Hidden tests derive from the issue text",
         "Hidden tests were written from the issue specification", None),
    Unit("U03", "preamble", "directive", "Treat issue names and messages as contracts",
         "edge cases in the issue are the contract", "as literal contracts"),
    Unit("U04", "hard limits", "environment", "Tool-call and time budget",
         "28 tool calls and 7 minutes total", "28 tool calls and 8 minutes"),
    Unit("U05", "hard limits", "environment", "submit_patch and get_status are free",
         "do not consume tool calls", "are free"),
    Unit("U06", "hard limits", "environment", "Working tree is graded when budget expires",
         "the working tree is graded as-is", "`git add -N . && git diff HEAD` is graded"),
    Unit("U07", "hard limits", "rationale", "An edit on disk counts even without submission",
         "An edit on disk counts", None),
    Unit("U08", "hard limits", "directive", "Never touch tests or runner configs",
         "Never create, modify, or delete test files", "Never create, edit, or delete test files"),
    Unit("U09", "hard limits", "rationale", "Test files are reset before grading",
         "Phase 2 resets them before grading", None),
    Unit("U10", "hard limits", "directive", "Scratch files only under /tmp",
         "Scratch scripts, test logs, and backups go strictly under `/tmp`",
         "Put scratch scripts and logs strictly under `/tmp`"),
    Unit("U11", "hard limits", "example", "Heredoc example for /tmp scripts",
         "for example `cat > /tmp/repro.py << 'EOF'`", None),
    Unit("U12", "hard limits", "environment", "File tools only accept /workspace paths",
         "only accept paths inside `/workspace`", None),
    Unit("U13", "hard limits", "environment", "Untracked workspace files enter the patch",
         "any untracked file left under `/workspace` becomes part of your graded patch",
         "any untracked file inside `/workspace` enters your graded patch"),
    Unit("U14", "hard limits", "directive", "Never run a full test suite",
         "Never run a full test suite", "Never run a full test suite"),
    Unit("U15", "hard limits", "directive", "Target one test file, log to /tmp, read the tail",
         "Always target one test file", "Target one test file"),
    Unit("U16", "hard limits", "environment", "run_command keeps only the first 5,000 characters",
         "truncated at its FIRST 5,000 characters", "keeps only the first 5,000 chars"),
    Unit("U17", "hard limits", "rationale", "pytest prints its verdict at the end",
         "pytest prints its verdict at the end", None),
    Unit("U18", "hard limits", "directive", "Never call the three graph tools",
         "Never call `search_similar_code`, `get_code_neighbors`, or `get_code_subgraph`", None),
    Unit("U19", "hard limits", "rationale", "Graph tools omit async code and can overflow context",
         "Code graphs omit async functions", None),
    Unit("U20", "hard limits", "directive", "Stay inside /workspace; install nothing",
         "Never look outside `/workspace` or install packages",
         "Never inspect outside `/workspace` or install packages"),
    Unit("U21", "hard limits", "environment", "Container is offline",
         "the container is offline", "offline container"),
    Unit("U22", "call plan", "directive", "Calls 1-8: locate and read",
         "Calls 1-8: locate and read focused line ranges", "Calls 1-8: locate and inspect"),
    Unit("U23", "call plan", "directive", "Edit source by call 12",
         "You MUST edit a source file by call 12", "You MUST make at least one source edit by call 12"),
    Unit("U24", "call plan", "rationale", "A wrong edit can be revised; reading alone scores zero",
         "pure reading scores zero", "pure reading scores 0"),
    Unit("U25", "call plan", "directive", "Calls 13-20: reproduce and test",
         "Calls 13-20: verify with `/tmp` reproduction and targeted tests",
         "Calls 13-20: run `/tmp` repro + one targeted test file"),
    Unit("U26", "call plan", "directive", "Call 21+: stop exploring and submit",
         "Call 21 onward: no new exploration", "Call 21+: stop exploring"),
    Unit("U27", "procedure", "directive", "Extract a specification before tool calls",
         "Extract the Specification (no tool call)", "**Spec (no tool call)**"),
    Unit("U28", "procedure", "directive", "Start from paths named in the issue",
         "Jump straight to paths named in the issue", "Start with paths mentioned in the issue"),
    Unit("U29", "procedure", "directive", "Batch fixed-string searches with git grep",
         "batch known fixed-string searches in one `run_command` using `git grep -n -F`",
         "Batch known fixed-string searches in one `run_command` using `git grep -n -F`"),
    Unit("U30", "procedure", "environment", "rg and tree are not installed",
         "`rg` and `tree` are not installed", None),
    Unit("U31", "procedure", "directive", "Read 40-120 line slices",
         "Read focused slices (40-120 lines)", "Read 40-120 line slices"),
    Unit("U32", "procedure", "directive", "Inspect one caller or sibling test before editing",
         "one existing caller or sibling test", "including one caller or sibling test"),
    Unit("U33", "procedure", "directive", "Keep brief plain-text notes",
         "Keep notes in brief plain text between tool calls", "Keep brief plain-text notes between turns"),
    Unit("U34", "procedure", "rationale", "Older tool outputs may be compacted",
         "older tool outputs may be compacted", "survive context compaction"),
    Unit("U35", "procedure", "directive", "Prefer edit_file with a short unique old_string",
         "Prefer `edit_file` with a short, unique `old_string`", "Use `edit_file` with a short unique `old_string`"),
    Unit("U36", "procedure", "directive", "Use write_file only for genuinely new modules",
         "Use `write_file` only if the issue genuinely requires a new source module", None),
    Unit("U37", "procedure", "directive", "Never repeat a failed edit; heredoc fallback",
         "Never repeat an identical failing edit", "Never repeat an identical failed edit"),
    Unit("U38", "procedure", "directive", "Fix the root cause",
         "Fix the root cause cleanly", None),
    Unit("U39", "procedure", "directive", "Preserve existing signatures",
         "without breaking existing signatures", "Keep unrelated code and signatures intact"),
    Unit("U40", "procedure", "directive", "Propagate fixes to all parallel implementations",
         "Propagate the fix to ALL parallel implementations", "Propagate fixes across ALL parallel implementations"),
    Unit("U41", "procedure", "directive", "py_compile, repro script and one test file",
         "Run `python3 -m py_compile <edited_file>`", "Run `python3 -m py_compile <edited_file>`"),
    Unit("U42", "procedure", "directive", "Ignore unrelated pre-existing failures",
         "Pre-existing failures from missing optional fixtures", "Ignore pre-existing failures from missing optional fixtures"),
    Unit("U43", "procedure", "directive", "Judge by tests covering the modified path",
         "judge by the tests covering the modified code path", None),
    Unit("U44", "procedure", "directive", "Check git status and diff before submitting",
         "Run `git status --short && git diff`", "Run `git status --short && git diff`"),
    Unit("U45", "procedure", "rationale", "git diff alone hides untracked files",
         "`git diff` alone hides untracked files", None),
    Unit("U46", "procedure", "directive", "Remove scratch files; revert test/config edits",
         "Remove any stray `/workspace` scratch files", "delete any stray `/workspace` files"),
    Unit("U47", "procedure", "directive", "Confirm a non-empty submitted patch",
         "confirm `patch_size > 0` and `files_changed > 0`", "confirm `patch_size > 0` and `files_changed > 0`"),
    Unit("U48", "decision rules", "directive", "Ambiguity: take the most literal reading",
         "pick the most literal reading and edit", "follow the most literal interpretation and act"),
    Unit("U49", "decision rules", "directive", "Edit where wrong behaviour is produced, not observed",
         "edit where wrong behaviour is produced rather than where it is merely observed", None),
    Unit("U50", "decision rules", "directive", "When stuck, try one alternate symbol then edit",
         "try one alternate symbol", "try one alternate symbol"),
    Unit("U51", "decision rules", "directive", "Never conclude no change is needed",
         "never conclude no change is needed", "Never conclude no edit is needed"),
]

# Labelling choices that a different rater could reasonably make differently.
# Environment facts that also explain a nearby rule (U13 explains why scratch files
# belong in /tmp, U16 why test output is read from its tail, U21 why nothing is installed).
BORDERLINE_RATIONALES = ("U13", "U16", "U21")
# Units that v3 keeps in part: U07 (v3 keeps "an unedited tree scores 0" but not
# "an edit on disk counts"), U43 (v3 keeps "ignore pre-existing failures" but not
# "judge by the tests covering the modified path").
PARTLY_RETAINED = ("U07", "U43")
# Guidance about tools that v3 removed, so it became moot rather than lost.
MOOT_AFTER_TOOL_REMOVAL = ("U18", "U19")

SECTION_ALIASES = {
    "hard limits": "hard limits",
    "call plan": "call plan",
    "procedure": "procedure",
    "workflow": "procedure",
    "decision rules": "decision rules",
    "the issue, kept in view": "issue",
    "issue": "issue",
}


def section_bytes(prompt: str) -> Dict[str, int]:
    """UTF-8 bytes per top-level ``# `` section; text before the first heading is 'preamble'."""
    sizes: Dict[str, int] = Counter()
    current = "preamble"
    for line in prompt.splitlines(keepends=True):
        match = re.match(r"# (?!#)(.+)", line)
        if match:
            current = SECTION_ALIASES[match.group(1).strip().lower()]
        sizes[current] += len(line.encode("utf-8"))
    return dict(sizes)


def _rates(units, kinds, dropped, excluded=()):
    out = {}
    for kind in ("rationale", "directive"):
        ids = [u.uid for u in units if kinds[u.uid] == kind and u.uid not in excluded]
        gone = [i for i in ids if i in dropped and i not in excluded]
        out[kind] = {"dropped": len(gone), "total": len(ids), "rate": round(len(gone) / len(ids), 3)}
    out["rate_ratio"] = round(out["rationale"]["rate"] / out["directive"]["rate"], 2)
    return out


def sensitivity(units: List[Unit] = UNITS) -> Dict[str, object]:
    """How the headline (rationales dropped far more often than directives) responds to
    defensible alternative labellings, and to leaving out any single unit."""
    kinds = {u.uid: u.kind for u in units}
    dropped = {u.uid for u in units if u.v3_excerpt is None}
    reclassified = {**kinds, **{i: "rationale" for i in BORDERLINE_RATIONALES}}
    still_dropped = dropped - set(PARTLY_RETAINED)
    scenarios = {
        "as_labelled": _rates(units, kinds, dropped),
        "borderline_environment_facts_as_rationales": _rates(units, reclassified, dropped),
        "partly_retained_units_counted_as_kept": _rates(units, kinds, still_dropped),
        "both_changes": _rates(units, reclassified, still_dropped),
        "graph_tool_units_excluded": _rates(units, kinds, dropped, MOOT_AFTER_TOOL_REMOVAL),
    }
    leave_one_out = [_rates([u for u in units if u.uid != x.uid], kinds, dropped) for x in units]
    ratios = [s["rate_ratio"] for s in scenarios.values()]
    return {
        "scenarios": scenarios,
        "rate_ratio_range_scenarios": [min(ratios), max(ratios)],
        "rate_ratio_range_leave_one_out": [min(r["rate_ratio"] for r in leave_one_out),
                                           max(r["rate_ratio"] for r in leave_one_out)],
    }


def audit_units(v2_prompt: str, v3_prompt: str, units: List[Unit] = UNITS) -> Dict[str, object]:
    """Validates every excerpt against the prompts and summarises what v3 dropped."""
    missing = [u.uid for u in units if u.v2_excerpt not in v2_prompt]
    missing += [u.uid for u in units if u.v3_excerpt is not None and u.v3_excerpt not in v3_prompt]
    if missing:
        raise ValueError(f"excerpts not found verbatim in the prompts: {missing}")
    ids = [u.uid for u in units]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate unit ids")

    dropped = [u for u in units if u.v3_excerpt is None]
    by_kind = {
        kind: {"v2": sum(u.kind == kind for u in units), "dropped": sum(u.kind == kind for u in dropped)}
        for kind in ("directive", "rationale", "environment", "example")
    }
    return {
        "units_total": len(units),
        "units_retained": len(units) - len(dropped),
        "units_dropped": len(dropped),
        "by_kind": by_kind,
        "dropped": [{"id": u.uid, "kind": u.kind, "section": u.section, "summary": u.summary} for u in dropped],
        "units": [{"id": u.uid, "section": u.section, "kind": u.kind, "dropped": u.v3_excerpt is None} for u in units],
        "sensitivity": sensitivity(units),
        "section_bytes": {"v2": section_bytes(v2_prompt), "v3": section_bytes(v3_prompt)},
    }
