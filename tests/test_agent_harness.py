"""Unit tests for the Gemma Developer Agent Harness and Declarative ADK Submission."""

import ast
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
import pytest

from harness.adk_bundle import build_submission_zip, validate_submission_bundle, write_submission_bundle
from harness.tools import AgentToolkit
from harness.agent import GemmaDeveloperAgent


@pytest.fixture
def temp_workspace():
    tmp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(tmp_dir, "pkg")
    os.makedirs(src_dir, exist_ok=True)
    sample_file = os.path.join(src_dir, "calculator.py")
    with open(sample_file, "w", encoding="utf-8") as f:
        f.write("def calculate_tax(amount: float, rate: float = 0.05) -> float:\n    return amount * rate\n")
    yield tmp_dir
    shutil.rmtree(tmp_dir)


def test_toolkit_list_and_read(temp_workspace):
    toolkit = AgentToolkit(temp_workspace)
    files = toolkit.list_files()
    assert "pkg/calculator.py" in files
    content = toolkit.read_file("pkg/calculator.py", 1, 10)
    assert "calculate_tax" in content


def test_toolkit_search(temp_workspace):
    toolkit = AgentToolkit(temp_workspace)
    hits = toolkit.search_code("calculate_tax")
    assert len(hits) >= 1
    assert hits[0]["file"] == "pkg/calculator.py"


def test_toolkit_apply_valid_patch(temp_workspace):
    toolkit = AgentToolkit(temp_workspace)
    success, msg = toolkit.apply_patch("pkg/calculator.py", "rate: float = 0.05", "rate: float = 0.08")
    assert success is True
    assert "Successfully patched" in msg
    assert "0.08" in toolkit.read_file("pkg/calculator.py")


def test_toolkit_rejects_syntax_error(temp_workspace):
    toolkit = AgentToolkit(temp_workspace)
    success, msg = toolkit.apply_patch("pkg/calculator.py", "rate: float = 0.05", "rate: float = (0.08")
    assert success is False
    assert "Syntax error" in msg


def test_agent_solve_loop(temp_workspace):
    agent = GemmaDeveloperAgent(temp_workspace)
    res = agent.solve_issue("Fix the calculate_tax logic when rate is default")
    assert "calculate_tax" in res["extracted_keywords"]
    assert "pkg/calculator.py" in res["target_files"]


def test_adk_submission_bundle_and_zip(tmp_path):
    import yaml

    bundle_dir = write_submission_bundle(tmp_path / "submission")
    models = validate_submission_bundle(bundle_dir)
    assert models == {"gemma-4-31b-it-qat-w4a16-ct"}

    class _Inc(yaml.SafeLoader):
        pass

    _Inc.add_constructor("!include", lambda loader, node: loader.construct_scalar(node))
    agent_cfg = yaml.load((bundle_dir / "agent.yaml").read_text(encoding="utf-8"), Loader=_Inc)
    assert agent_cfg["tools"] == [
        "run_command",
        "read_file",
        "edit_file",
        "write_file",
        "get_status",
        "submit_patch",
    ]
    sampling_cfg = yaml.safe_load((bundle_dir / "configs" / "sampling.yaml").read_text(encoding="utf-8"))
    assert sampling_cfg["temperature"] == 0.4
    eval_cfg = yaml.safe_load((bundle_dir / "eval_config.yaml").read_text(encoding="utf-8"))
    assert eval_cfg["evaluation"]["max_time_minutes"] == 8
    prompt_text = (bundle_dir / "prompts" / "system.md").read_text(encoding="utf-8")
    assert "{problem_description}" in prompt_text
    assert len(prompt_text) <= 3800

    zip_path = build_submission_zip(bundle_dir, tmp_path / "submission.zip")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = set(zf.namelist())
        assert names == {
            "agent.yaml",
            "configs/sampling.yaml",
            "eval_config.yaml",
            "prompts/system.md",
        }
        assert zf.testzip() is None


def test_generated_notebook_valid_ast():
    repo_root = Path(__file__).resolve().parents[1]
    nb_path = repo_root / "kaggle_notebook" / "gemma_4_developer_agent_baseline.ipynb"
    assert nb_path.is_file()
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    code_cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) >= 3
    for src in code_cells:
        ast.parse(src)

def test_toolkit_rejects_sibling_prefix(tmp_path):
    root = tmp_path / 'repo'
    sibling = tmp_path / 'repo-other'
    root.mkdir()
    sibling.mkdir()
    (sibling / 'secret.py').write_text('secret = 1')
    with pytest.raises(PermissionError):
        AgentToolkit(str(root)).read_file(str(sibling / 'secret.py'))


def test_patch_rejects_top_level_return(temp_workspace):
    toolkit = AgentToolkit(temp_workspace)
    before = toolkit.read_file('pkg/calculator.py')
    ok, message = toolkit.apply_patch('pkg/calculator.py', 'def calculate_tax(amount: float, rate: float = 0.05):', 'return 1')
    # Use the exact original file to ensure the compiler, not matching, rejects it.
    source = Path(temp_workspace, 'pkg/calculator.py').read_text()
    ok, message = toolkit.apply_patch('pkg/calculator.py', source, 'return 1\n')
    assert not ok and 'Syntax error' in message
    assert toolkit.read_file('pkg/calculator.py') == before
