"""
Unit tests for the Gemma Developer Agent Harness.
Verifies toolkit execution, AST safety, and agent search loop.
"""

import os
import shutil
import tempfile
import pytest
from harness.tools import AgentToolkit
from harness.agent import GemmaDeveloperAgent


@pytest.fixture
def temp_workspace():
    tmp_dir = tempfile.mkdtemp()
    # Create sample codebase structure
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
    old = "rate: float = 0.05"
    new = "rate: float = 0.08"
    success, msg = toolkit.apply_patch("pkg/calculator.py", old, new)
    assert success is True
    assert "Successfully patched" in msg

    updated = toolkit.read_file("pkg/calculator.py")
    assert "0.08" in updated


def test_toolkit_rejects_syntax_error(temp_workspace):
    toolkit = AgentToolkit(temp_workspace)
    old = "rate: float = 0.05"
    # Deliberate syntax break: unclosed bracket
    new = "rate: float = (0.08"
    success, msg = toolkit.apply_patch("pkg/calculator.py", old, new)
    assert success is False
    assert "Syntax error" in msg


def test_agent_solve_loop(temp_workspace):
    agent = GemmaDeveloperAgent(temp_workspace)
    res = agent.solve_issue("Fix the calculate_tax logic when rate is default")
    assert "calculate_tax" in res["extracted_keywords"]
    assert "pkg/calculator.py" in res["target_files"]
