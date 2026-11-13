"""Tests for bundle construction, validation, packaging, and archived-artifact integrity."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from harness.adk_bundle import BundleError, build_submission_zip, validate_submission_bundle, write_submission_bundle
from harness.variants import BUNDLE_FILES, changed_files, load_variants

ROOT = Path(__file__).resolve().parents[1]


class _Include(yaml.SafeLoader):
    pass


_Include.add_constructor("!include", lambda loader, node: loader.construct_scalar(node))


def _write(dir_: Path, files: dict) -> Path:
    for rel, text in files.items():
        dest = dir_ / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(text.encode("utf-8"))
    return dir_


def test_v3_bundle_contents_and_zip(tmp_path):
    bundle = write_submission_bundle(tmp_path / "submission")
    assert validate_submission_bundle(bundle) == {"gemma-4-31b-it-qat-w4a16-ct"}
    agent = yaml.load((bundle / "agent.yaml").read_text(encoding="utf-8"), Loader=_Include)
    assert agent["tools"] == ["run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch"]
    assert yaml.safe_load((bundle / "configs/sampling.yaml").read_text())["temperature"] == 0.4
    assert yaml.safe_load((bundle / "eval_config.yaml").read_text())["evaluation"]["max_time_minutes"] == 8

    zip_path = build_submission_zip(bundle, tmp_path / "submission.zip")
    with zipfile.ZipFile(zip_path) as zf:
        assert set(zf.namelist()) == set(BUNDLE_FILES)
    # Deterministic packaging: rebuilding yields identical bytes.
    again = build_submission_zip(bundle, tmp_path / "again.zip")
    assert zip_path.read_bytes() == again.read_bytes()


@pytest.mark.parametrize("mutate, message", [
    (lambda f: f.update({"agent.yaml": f["agent.yaml"].replace("gemma-4-31b-it-qat-w4a16-ct", "gpt-4o")}), "not in"),
    (lambda f: f.update({"prompts/system.md": f["prompts/system.md"] + "\n{secret_state}\n"}), "placeholders"),
    (lambda f: f.update({"agent.yaml": f["agent.yaml"].replace("prompts/system.md", "../system.md")}), "traversal"),
    (lambda f: f.update({"agent.yaml": f["agent.yaml"] + "adapter: lora/\n"}), "adapter"),
    (lambda f: f.update({"notes.exe": "x"}), "suffixes"),
    (lambda f: f.update({"root_agent.yaml": f["agent.yaml"]}), "root config"),
])
def test_validator_rejects_contract_violations(tmp_path, mutate, message):
    files = dict(load_variants()["v2"].files)
    mutate(files)
    with pytest.raises(BundleError, match=message):
        validate_submission_bundle(_write(tmp_path / "b", files))


def test_all_variants_validate(tmp_path):
    for name, variant in load_variants().items():
        assert validate_submission_bundle(_write(tmp_path / name, dict(variant.files)))


def test_one_factor_variants_change_exactly_one_file():
    v = load_variants()
    assert changed_files(v["v2"].files, v["v4"].files) == ["agent.yaml"]
    assert changed_files(v["v2"].files, v["v5"].files) == ["configs/sampling.yaml"]
    assert len(changed_files(v["v2"].files, v["v3"].files)) == 4


def test_archived_v2_zip_matches_manifest():
    files = load_variants()["v2"].files
    with zipfile.ZipFile(ROOT / "artifacts" / "v2_submission.zip") as zf:
        assert zf.testzip() is None
        assert {n: zf.read(n).decode("utf-8") for n in zf.namelist()} == dict(files)


def test_experiment_zips_match_bundles_and_recorded_hashes():
    manifest = {row["variant"]: row for row in json.loads((ROOT / "experiments" / "manifest.json").read_text())}
    variants = load_variants()
    for variant, short in (("v4_tools_only", "v4"), ("v5_temperature_only", "v5")):
        zip_bytes = (ROOT / "experiments" / variant / "submission.zip").read_bytes()
        assert hashlib.sha256(zip_bytes).hexdigest() == manifest[variant]["sha256"]
        with zipfile.ZipFile(ROOT / "experiments" / variant / "submission.zip") as zf:
            assert {n: zf.read(n).decode("utf-8") for n in zf.namelist()} == dict(variants[short].files)
