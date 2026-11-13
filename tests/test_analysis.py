"""Tests for the analyses whose numbers the paper reports."""

import json
from pathlib import Path

import pytest

from analysis.prompt_units import UNITS, Unit, audit_units, section_bytes
from analysis.run_all import build_report
from analysis.score_resolution import consistent_sizes, displayed, pass_counts, required_n_independent, summarize
from harness.variants import load_variants

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def prompts():
    v = load_variants()
    return v["v2"].files["prompts/system.md"], v["v3"].files["prompts/system.md"]


def test_section_bytes_sum_to_prompt_bytes(prompts):
    for prompt in prompts:
        assert sum(section_bytes(prompt).values()) == len(prompt.encode("utf-8"))


def test_unit_audit_counts(prompts):
    audit = audit_units(*prompts)
    assert audit["units_total"] == 51 and audit["units_dropped"] == 14
    assert audit["by_kind"]["rationale"] == {"v2": 8, "dropped": 6}
    assert audit["by_kind"]["directive"] == {"v2": 34, "dropped": 5}


def test_unit_audit_rejects_non_verbatim_excerpt(prompts):
    bogus = UNITS + [Unit("U99", "preamble", "directive", "fake", "this text is not in v2", None)]
    with pytest.raises(ValueError, match="U99"):
        audit_units(*prompts, units=bogus)


def test_dropped_units_really_absent_from_v3(prompts):
    """Spot-check that dropped guidance has no surviving key phrase in v3."""
    v3 = prompts[1].lower()
    for phrase in ("root cause", "`rg`", "phase 2", "merely observed", "verdict at the end", "hides untracked",
                   "genuinely requires", "search_similar_code"):
        assert phrase not in v3, phrase


def test_displayed_rounding():
    assert displayed(10, 58) == 0.17 and displayed(11, 58) == 0.19
    assert pass_counts(0.18, 58) == []
    assert pass_counts(0.18, 100) == [18]


def test_score_resolution_summary():
    s = summarize(0.18, 0.15)
    assert s["smallest_consistent_n"] == 33
    assert 58 in s["inconsistent_n_up_to_129"] and 129 not in s["inconsistent_n_up_to_129"]
    assert s["task_gap_min_max_for_n_le_129"] == [1, 4]
    assert consistent_sizes(0.18, 0.15, 129, 129)[129] == ([23], [19])
    assert required_n_independent(0.165, 0.03) == s["required_n_two_sigma_independent"] == 1177


def test_committed_report_is_current():
    """evidence/analysis_report.json must equal a fresh recomputation."""
    committed = json.loads((ROOT / "evidence" / "analysis_report.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(build_report()))


def test_parse_kaggle_submissions_csv():
    from scripts.kaggle_status import parse_submissions

    csv_text = (
        "ref,fileName,date,description,status,publicScore,privateScore\n"
        "58271330,submission.zip,2026-11-12,v4,SubmissionStatus.PENDING,,\n"
        "58201114,submission.zip,2026-11-10,v2,SubmissionStatus.COMPLETE,0.18,\n"
        "99999999,submission.zip,2026-11-09,other,SubmissionStatus.COMPLETE,0.50,\n"
    )
    parsed = parse_submissions(csv_text)
    assert parsed == {
        "v4": {"ref": "58271330", "status": "PENDING", "public_score": None},
        "v2": {"ref": "58201114", "status": "COMPLETE", "public_score": 0.18},
    }


def test_sensitivity_headline_survives_alternative_labellings(prompts):
    from analysis.prompt_units import BORDERLINE_RATIONALES, PARTLY_RETAINED, sensitivity

    s = sensitivity()
    sc = s["scenarios"]
    assert sc["as_labelled"]["rationale"] == {"dropped": 6, "total": 8, "rate": 0.75}
    assert sc["borderline_environment_facts_as_rationales"]["rationale"]["total"] == 8 + len(BORDERLINE_RATIONALES)
    assert sc["partly_retained_units_counted_as_kept"]["rationale"]["dropped"] == 5
    assert sc["graph_tool_units_excluded"]["rationale"] == {"dropped": 5, "total": 7, "rate": 0.714}
    assert sc["graph_tool_units_excluded"]["directive"]["total"] == 33
    assert set(PARTLY_RETAINED) <= {u.uid for u in UNITS}
    # The qualitative claim: rationales are dropped several times as often as directives, however labelled.
    assert all(v["rate_ratio"] > 3 for v in sc.values())
    assert s["rate_ratio_range_scenarios"] == [3.71, 5.9]
    assert min(s["rate_ratio_range_leave_one_out"]) > 3


def test_audit_exposes_per_unit_records_for_the_figure(prompts):
    audit = audit_units(*prompts)
    assert len(audit["units"]) == 51
    assert sum(u["dropped"] for u in audit["units"]) == audit["units_dropped"] == 14
    assert {u["section"] for u in audit["units"]} == {"preamble", "hard limits", "call plan", "procedure", "decision rules"}


def _perfect_second_rater():
    return {"labels": {u.uid: {"kind": u.kind, "borderline": False,
                               "retained": "no" if u.v3_excerpt is None else "yes"} for u in UNITS},
            "uncovered": []}


def test_cohens_kappa_known_values():
    from analysis.interrater import cohens_kappa

    assert cohens_kappa(list("aabb"), list("aabb")) == 1.0
    assert cohens_kappa(list("abab"), list("baba")) == -1.0
    assert cohens_kappa(list("aaaa"), list("aaaa")) == 1.0
    # 3 of 4 agree; expected agreement 0.5 -> kappa 0.5
    assert abs(cohens_kappa(list("aabb"), list("aaba")) - 0.5) < 1e-9
    with pytest.raises(ValueError):
        cohens_kappa(["a"], ["a", "b"])


def test_interrater_perfect_agreement_reproduces_first_rater_headline():
    from analysis.interrater import compare

    report = compare(second=_perfect_second_rater())
    assert report["kind"]["agreement"] == 51 and report["kind"]["kappa"] == 1.0
    assert report["retention"]["partly_counts_as_kept"]["agreement"] == 51
    assert report["headline_under_second_rater"]["partly_counts_as_kept"] == report["headline_under_first_rater"]


def test_interrater_detects_disagreement_and_validates_input():
    from analysis.interrater import compare

    second = _perfect_second_rater()
    second["labels"]["U02"]["kind"] = "directive"       # first rater: rationale
    second["labels"]["U07"]["retained"] = "partly"      # first rater: dropped
    report = compare(second=second)
    assert report["kind"]["disagreements"] == [{"id": "U02", "first": "rationale", "second": "directive"}]
    assert report["retention"]["partly_counts_as_kept"]["disagreements"] == ["U07"]
    assert report["retention"]["partly_counts_as_dropped"]["disagreements"] == []
    del second["labels"]["U51"]
    with pytest.raises(ValueError, match="U51"):
        compare(second=second)
    second["labels"]["U51"] = {"kind": "opinion", "retained": "yes"}
    with pytest.raises(ValueError, match="invalid kind"):
        compare(second=second)


def test_committed_interrater_report_is_current():
    from analysis.interrater import REPORT_PATH, compare

    committed = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(compare()))
    assert committed["kind"]["agreement"] == 47 and committed["kind"]["kappa"] == 0.845
    # Every disagreement is on the rationale / environment boundary.
    assert {frozenset((d["first"], d["second"])) for d in committed["kind"]["disagreements"]} == {frozenset(("rationale", "environment"))}
    # Under the second rater the contrast shrinks but keeps its direction.
    for scenario in committed["headline_under_second_rater"].values():
        assert scenario["rate_ratio"] > 2
