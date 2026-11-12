"""Declarative Google ADK submission builder and validator for Kaggle's Gemma 4 Developer Agent."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Dict, Set

import yaml

ALLOWED_MODELS = (
    "gemma-4-31b-it-qat-w4a16-ct",
    "gemma-4-12b-it-qat-w4a16-ct",
    "gemma-4-e4b-it-qat-w4a16-ct",
    "gemma-4-e2b-it-qat-w4a16-ct",
)
ROOT_CONFIGS = ("agent.yaml", "agent.yml", "root_agent.yaml", "root_agent.yml")
ALLOWED_SUFFIXES = {".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}
ALLOWED_STATE_VARS = {"problem_description", "hints"}
MAX_UNPACKED_BYTES = 3 * 2**30

SYSTEM_PROMPT = """You are an autonomous software engineer. Make the smallest correct fix to SOURCE code in /workspace so hidden tests pass. Treat exact symbol names, types, exception classes, and messages in the issue as literal contracts.

# HARD LIMITS
- Budget: 28 tool calls and 8 minutes (`submit_patch` and `get_status` are free). When either expires, `git add -N . && git diff HEAD` is graded; an unedited tree always scores 0.
- Never create, edit, or delete test files (`test_*.py`, `*_test.py`, `tests/`, `test/`, `testing/`) or runner configs (`pytest.ini`, `conftest.py`, `pyproject.toml`, `setup.cfg`, `tox.ini`, `sitecustomize.py`, `usercustomize.py`).
- Put scratch scripts and logs strictly under `/tmp` via `run_command`; any untracked file inside `/workspace` enters your graded patch.
- Never run a full test suite (`pytest`, `pytest .`, `unittest discover`). Target one test file with `-x -q -k`, saving output to `/tmp`: `python3 -m pytest tests/path/test_x.py -x -q -k kw > /tmp/t.log 2>&1; tail -n 35 /tmp/t.log` (`run_command` keeps only the first 5,000 chars).
- Never inspect outside `/workspace` or install packages (offline container).

# CALL PLAN
- Calls 1-8: locate and inspect exact target source + caller/test lines.
- Calls 9-12: edit SOURCE code. You MUST make at least one source edit by call 12 even if uncertain; an imperfect patch can be refined, pure reading scores 0.
- Calls 13-20: run `/tmp` repro + one targeted test file; fix edge cases across all parallel code paths.
- Call 21+: stop exploring, verify `git status --short && git diff`, and call `submit_patch`.

# WORKFLOW
1. **Spec (no tool call)**: List exact files/symbols, error types/messages, return values, and edge cases (`None`, empty, unicode, bounds, defaults, async).
2. **Locate**: Start with paths mentioned in the issue. Batch known fixed-string searches in one `run_command` using `git grep -n -F` and `git ls-files` (`head -n 30`). Read 40-120 line slices via `read_file` or `sed -n 'S,Ep'`, including one caller or sibling test. Keep brief plain-text notes between turns so key facts survive context compaction.
3. **Edit**: Use `edit_file` with a short unique `old_string` verbatim from the file. Never repeat an identical failed edit; after 2 match failures, reread exact line numbers and apply one atomic Python replacement via `run_command` quoted heredoc asserting `content.count(old) == 1`. Propagate fixes across ALL parallel implementations (sync/async, `Client`/`AsyncClient`, alternate backends, typing overloads, `__init__.py`/`__all__`, `docs_src/`). Keep unrelated code and signatures intact.
4. **Verify**: Run `python3 -m py_compile <edited_file>`, a `/tmp/repro.py` script, and the single closest test file via `/tmp/t.log`. Ignore pre-existing failures from missing optional fixtures or unrelated modules.
5. **Submit**: Run `git status --short && git diff`, delete any stray `/workspace` files, revert accidental non-source edits with `git checkout --`, then call `submit_patch` and confirm `patch_size > 0` and `files_changed > 0`. Finish with a one-sentence summary.

# DECISION RULES
- Ambiguous spec: follow the most literal interpretation and act; never stall.
- Stuck on empty searches: try one alternate symbol, then apply your best-reasoned small fix. Never conclude no edit is needed.

# Issue
{problem_description}
"""

SUBMISSION_FILES: Dict[str, str] = {
    "agent.yaml": """name: swe_agent
model: gemma-4-31b-it-qat-w4a16-ct
description: Resolves a repository issue with a minimal, verified source patch.
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - get_status
  - submit_patch
generate_content_config: !include configs/sampling.yaml
""",
    "configs/sampling.yaml": """temperature: 0.4
top_p: 0.95
top_k: 64
max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true
""",
    "eval_config.yaml": """evaluation:
  timeout_seconds: 240
  max_tool_calls: 28
  max_time_minutes: 8
  max_turns: 80
""",
    "prompts/system.md": SYSTEM_PROMPT,
}


def _safe_yaml_load(text: str) -> dict:
    class _IncludeLoader(yaml.SafeLoader):
        pass

    _IncludeLoader.add_constructor("!include", lambda loader, node: loader.construct_scalar(node))
    return yaml.load(text, Loader=_IncludeLoader) or {}


def write_submission_bundle(target_dir: Path) -> Path:
    """Materializes SUBMISSION_FILES cleanly with Unix LF line endings."""
    target_dir = Path(target_dir)
    for rel_path, content in SUBMISSION_FILES.items():
        dest = target_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content.replace("\r\n", "\n").encode("utf-8"))
    return target_dir


def validate_submission_bundle(bundle_dir: Path) -> Set[str]:
    """Validates directory layout, YAML includes, single allowed model, and ADK template safety."""
    bundle_dir = Path(bundle_dir)
    files = sorted(p for p in bundle_dir.rglob("*") if p.is_file())
    assert files, "bundle contains no files"
    assert not any(p.is_symlink() for p in bundle_dir.rglob("*")), "symlinks are rejected"

    roots = [name for name in ROOT_CONFIGS if (bundle_dir / name).is_file()]
    assert len(roots) == 1, f"expected exactly 1 root config, found {roots}"

    bad_suffixes = [p.name for p in files if p.suffix not in ALLOWED_SUFFIXES]
    assert not bad_suffixes, f"disallowed file suffixes: {bad_suffixes}"
    assert sum(p.stat().st_size for p in files) < MAX_UNPACKED_BYTES, "bundle exceeds 3 GiB unpacked"

    declared_models: Set[str] = set()
    for cfg in (p for p in files if p.suffix in (".yaml", ".yml")):
        raw_text = cfg.read_text(encoding="utf-8")
        data = _safe_yaml_load(raw_text)
        for inc_rel in re.findall(r"!include\s+(\S+)", raw_text):
            inc_path = (cfg.parent / inc_rel).resolve()
            assert bundle_dir.resolve() in inc_path.parents, f"include traversal outside root: {inc_rel}"
            assert inc_path.is_file(), f"{cfg.name}: missing !include target {inc_rel}"
        assert "adapter" not in data, f"{cfg.name}: adapter key unexpectedly set"
        if "model" in data:
            declared_models.add(str(data["model"]).strip())

    assert len(declared_models) == 1, f"single model rule failed: {declared_models}"
    model = next(iter(declared_models))
    assert model in ALLOWED_MODELS, f"model {model!r} not in {ALLOWED_MODELS}"

    for md_path in (p for p in files if p.suffix in (".md", ".txt")):
        txt = md_path.read_text(encoding="utf-8")
        placeholders = set(re.findall(r"\{([^}]*)\}", txt))
        unknown = placeholders - ALLOWED_STATE_VARS
        assert not unknown, f"{md_path.name}: unrecognised ADK state template placeholders: {unknown}"

    return declared_models


def build_submission_zip(bundle_dir: Path, zip_path: Path) -> Path:
    """Packages a deterministic, files-only zip archive compatible with adk-submission."""
    bundle_dir = Path(bundle_dir)
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for p in sorted(f for f in bundle_dir.rglob("*") if f.is_file()):
            rel = p.relative_to(bundle_dir).as_posix()
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, p.read_bytes())

    with zipfile.ZipFile(zip_path, "r") as zf:
        assert zf.testzip() is None, "zip CRC integrity check failed"
        names = zf.namelist()
        assert "agent.yaml" in names, "agent.yaml must sit at archive root"
        assert not any(n.endswith("/") for n in names), "directory entries are disallowed"
    return zip_path
