"""Builds the v3 Kaggle notebook for Gemma 4 Developer Agent.

Packages our verified 6-tool declarative ADK bundle (thinking ON, temperature=0.4,
8,192 max output tokens, 8-min / 28-call / 240s per-task budget, single agent
without dummy LoRA adapters, tightened ~3.1k-char call-paced prompt, and graph
tools removed from agent.yaml), validates it against the official attached
wheelhouse (`adk_submission` + `swegemma`), renders configuration/budget diagnostic
visualizations, and emits a files-only `/kaggle/working/submission.zip`.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from harness.adk_bundle import SUBMISSION_FILES  # noqa: E402


def build() -> None:
    cells = []

    def add_md(text: str) -> None:
        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [line + "\n" for line in text.strip().split("\n")],
        })

    def add_code(code: str) -> None:
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [line + "\n" for line in code.strip().split("\n")],
        })

    add_md("""# Gemma 4 declarative agent: v3 reproducibility artifact
Kaggle API verified on 2026-11-12: v2 scored 0.18; v3 scored 0.15.
This notebook reproduces v3, which is not the best observed configuration.
Compilation validates configuration only; it does not demonstrate repair success.
The archived v2 bundle remains the best verified candidate.
""")

    add_md("## 1. Materialize Declarative Submission Bundle")
    files_json = json.dumps(SUBMISSION_FILES, indent=2, ensure_ascii=False)
    add_code(
        f"""import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
import yaml

WORKING = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path("working")
WORKING.mkdir(parents=True, exist_ok=True)
BUNDLE = WORKING / "submission_bundle"
shutil.rmtree(BUNDLE, ignore_errors=True)
BUNDLE.mkdir(parents=True, exist_ok=True)

SUBMISSION_FILES = json.loads({files_json!r})

for rel_path, content in sorted(SUBMISSION_FILES.items()):
    dest = BUNDLE / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content.replace("\\r\\n", "\\n").encode("utf-8"))
    print(f"Wrote {{rel_path:24s}} ({{dest.stat().st_size:,}} bytes)")
"""
    )

    add_md("## 2. Structural, Schema & ADK Placeholder Validation")
    add_code(r"""ROOT_CONFIGS = ("agent.yaml", "agent.yml", "root_agent.yaml", "root_agent.yml")
ALLOWED_SUFFIXES = {".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}
ALLOWED_MODELS = (
    "gemma-4-31b-it-qat-w4a16-ct",
    "gemma-4-12b-it-qat-w4a16-ct",
    "gemma-4-e4b-it-qat-w4a16-ct",
    "gemma-4-e2b-it-qat-w4a16-ct",
)
ALLOWED_STATE_VARS = {"problem_description", "hints"}

yaml.SafeLoader.add_constructor("!include", lambda loader, node: loader.construct_scalar(node))

files = sorted(p for p in BUNDLE.rglob("*") if p.is_file())
roots = [name for name in ROOT_CONFIGS if (BUNDLE / name).is_file()]
assert len(roots) == 1, f"Expected 1 root config, found {roots}"
assert not any(p.is_symlink() for p in BUNDLE.rglob("*")), "Symlinks rejected"
assert all(p.suffix in ALLOWED_SUFFIXES for p in files), f"Bad suffix: {[p.name for p in files if p.suffix not in ALLOWED_SUFFIXES]}"
assert sum(p.stat().st_size for p in files) < 3 * 2**30, "Bundle exceeds 3 GiB"

declared_models = set()
for cfg in (p for p in files if p.suffix in (".yaml", ".yml")):
    text = cfg.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    for inc in re.findall(r"!include\s+(\S+)", text):
        inc_path = (cfg.parent / inc).resolve()
        assert BUNDLE.resolve() in inc_path.parents and inc_path.is_file(), f"{cfg.name}: bad include {inc}"
    assert "adapter" not in data, "Unexpected adapter key"
    if "model" in data:
        declared_models.add(str(data["model"]).strip())

assert len(declared_models) == 1, f"Single model rule violated: {declared_models}"
model = next(iter(declared_models))
assert model in ALLOWED_MODELS, f"Unsupported model: {model}"

for md_file in (p for p in files if p.suffix in (".md", ".txt")):
    placeholders = set(re.findall(r"\{([^}]*)\}", md_file.read_text(encoding="utf-8")))
    unknown = placeholders - ALLOWED_STATE_VARS
    assert not unknown, f"{md_file.name}: unknown ADK state vars {unknown}"

print(f"Schema OK: root={roots[0]} | files={len(files)} | model={model}")
""")

    add_md("## 3. Official Harness Compilation Check (`adk_submission` + `swegemma`)")
    add_code(r"""HARNESS_WHEELS = ("google_adk-", "google_genai-", "adk_submission-", "adk_eval_core-", "swegemma-")
PROVIDER_PREFIXES = ("openai/", "google/", "hosted_vllm/", "custom/")

def install_harness() -> None:
    found = sorted(Path("/kaggle/input").glob("**/adk_submission-*.whl")) if Path("/kaggle/input").exists() else []
    if not found:
        raise FileNotFoundError("metric/gemma-4-developer-agent-wheelhouse not attached")
    wh_dir = found[0].parent
    wheels = [str(w) for w in sorted(wh_dir.glob("*.whl")) if w.name.startswith(HARNESS_WHEELS)]
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", *wheels], check=True)

def run_command(command: str) -> str: ...
def read_file(filepath: str, start_line: int | None = None, end_line: int | None = None) -> str: ...
def write_file(filepath: str, content: str) -> str: ...
def edit_file(filepath: str, old_string: str, new_string: str, allow_multiple: bool = False) -> str: ...
def submit_patch() -> str: ...
def get_status() -> str: ...

def _norm_model(name: str) -> str:
    name = name.strip().lower()
    for p in PROVIDER_PREFIXES:
        name = name.removeprefix(p)
    return name

ON_KAGGLE = Path("/kaggle/input").exists()
if not ON_KAGGLE:
    try:
        import adk_submission  # noqa: F401
        HAS_HARNESS = True
    except ImportError as exc:
        HAS_HARNESS = False
        print(f"Harness wheel check skipped offline ({exc!r}); structural validation passed.")
else:
    try:
        import adk_submission  # noqa: F401
    except ImportError:
        install_harness()
    HAS_HARNESS = True

if HAS_HARNESS:
    from adk_submission import ModelRegistry, compile_submission, validate_directory
    from adk_submission.discovery import discover_declared_models
    from google.adk.models.lite_llm import LiteLlm
    from swegemma.config import build_submission_limits

    limits, constraints = build_submission_limits()
    validate_directory(BUNDLE, limits)
    print("validate_directory: PASSED")
    declared = discover_declared_models(BUNDLE, normalize_fn=_norm_model)
    assert declared == {model}, f"Mismatch in declared models: {declared}"
    tools = {
        fn.__name__: fn
        for fn in (run_command, read_file, write_file, edit_file, submit_patch, get_status)
    }
    models = ModelRegistry()
    models.register(model, LiteLlm(model=f"openai/{model}", api_base="http://127.0.0.1:9/v1", api_key="EMPTY"))
    compiled_agent = compile_submission(BUNDLE, tools, models, limits=limits, generation_constraints=constraints)
    print(f"compile_submission: PASSED (root_agent={compiled_agent.name!r}, tools={len(tools)})")
""")

    add_md("## 5. Emit Clean Files-Only `submission.zip`")
    add_code(r"""ZIP_PATH = WORKING / "submission.zip"
with zipfile.ZipFile(ZIP_PATH, "w") as zf:
    for p in sorted(f for f in BUNDLE.rglob("*") if f.is_file()):
        info = zipfile.ZipInfo(p.relative_to(BUNDLE).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        zf.writestr(info, p.read_bytes())

with zipfile.ZipFile(ZIP_PATH, "r") as zf:
    assert zf.testzip() is None
    names = zf.namelist()
    assert "agent.yaml" in names and not any(n.endswith("/") for n in names)

shutil.rmtree(BUNDLE)
digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
print(f"Submission ready: {ZIP_PATH} ({ZIP_PATH.stat().st_size:,} bytes) | SHA-256: {digest}")
for n in names:
    print(" ", n)
""")

    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    out_file = ROOT / "kaggle_notebook" / "gemma_4_developer_agent_baseline.ipynb"
    out_file.write_text(json.dumps(nb, indent=2), encoding="utf-8")
    print(f"Wrote {out_file} ({len(cells)} cells)")


if __name__ == "__main__":
    build()
