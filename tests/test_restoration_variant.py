"""v6 must differ from v3 only by the restored guidance."""
from analysis.prompt_units import UNITS
from harness.variants import changed_files, load_variants
from scripts.build_restoration_variant import NOT_APPLICABLE, check, derive_v6


def test_v6_changes_only_the_prompt_and_restores_every_applicable_unit():
    v3 = dict(load_variants()["v3"].files)
    v6 = derive_v6(v3)
    assert changed_files(v3, v6) == ["prompts/system.md"]
    restored = check(v3, v6)
    expected = [u.uid for u in UNITS if u.v3_excerpt is None and u.uid not in NOT_APPLICABLE]
    assert restored == expected and len(restored) == 12
    assert "{problem_description}" in v6["prompts/system.md"]
    assert "search_similar_code" not in v6["prompts/system.md"]  # v3 has no graph tools to forbid
