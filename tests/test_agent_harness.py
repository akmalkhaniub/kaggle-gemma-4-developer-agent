"""Tests for the local diagnostic toolkit, issue locator, and notebook generation."""

import ast
import json
import sys
from pathlib import Path

import pytest

from harness.agent import IssueLocator, extract_keywords
from harness.tools import AgentToolkit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "def calculate_tax(amount: float, rate: float = 0.05) -> float:\n    return amount * rate\n"


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "calculator.py").write_text(SOURCE, encoding="utf-8")
    return tmp_path


def test_list_and_read(workspace):
    toolkit = AgentToolkit(str(workspace))
    assert "pkg/calculator.py" in toolkit.list_files()
    assert "calculate_tax" in toolkit.read_file("pkg/calculator.py", 1, 10)


def test_search(workspace):
    hits = AgentToolkit(str(workspace)).search_code("calculate_tax")
    assert hits and hits[0]["file"] == "pkg/calculator.py" and hits[0]["line"] == 1


def test_apply_valid_patch(workspace):
    toolkit = AgentToolkit(str(workspace))
    ok, msg = toolkit.apply_patch("pkg/calculator.py", "rate: float = 0.05", "rate: float = 0.08")
    assert ok, msg
    assert "0.08" in toolkit.read_file("pkg/calculator.py")


def test_patch_rejects_syntax_error_and_leaves_file_unchanged(workspace):
    toolkit = AgentToolkit(str(workspace))
    ok, msg = toolkit.apply_patch("pkg/calculator.py", "rate: float = 0.05", "rate: float = (0.08")
    assert not ok and "Syntax error" in msg
    assert (workspace / "pkg" / "calculator.py").read_text(encoding="utf-8") == SOURCE


def test_patch_rejects_top_level_return(workspace):
    ok, msg = AgentToolkit(str(workspace)).apply_patch("pkg/calculator.py", SOURCE, "return 1\n")
    assert not ok and "Syntax error" in msg
    assert (workspace / "pkg" / "calculator.py").read_text(encoding="utf-8") == SOURCE


def test_patch_rejects_ambiguous_match(workspace):
    (workspace / "pkg" / "dup.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    ok, msg = AgentToolkit(str(workspace)).apply_patch("pkg/dup.py", "x = 1", "x = 2")
    assert not ok and "Ambiguous" in msg


def test_rejects_sibling_prefix_escape(tmp_path):
    root, sibling = tmp_path / "repo", tmp_path / "repo-other"
    root.mkdir()
    sibling.mkdir()
    (sibling / "secret.py").write_text("secret = 1")
    with pytest.raises(PermissionError):
        AgentToolkit(str(root)).read_file(str(sibling / "secret.py"))


def test_run_tests_does_not_use_a_shell(workspace):
    toolkit = AgentToolkit(str(workspace))
    ok = toolkit.run_tests([sys.executable, "-c", "print('hi')"])
    assert ok["status"] == "PASSED" and ok["stdout"].strip() == "hi"
    # Shell metacharacters must reach the program as literal arguments.
    literal = toolkit.run_tests([sys.executable, "-c", "import sys; print(sys.argv[1])", "a; echo injected"])
    assert literal["stdout"].strip() == "a; echo injected"
    assert toolkit.run_tests("")["status"] == "ERROR"


def test_issue_locator(workspace):
    report = IssueLocator(str(workspace)).locate("Fix the calculate_tax logic when rate is default")
    assert "calculate_tax" in report["extracted_keywords"]
    assert report["target_files"] == ["pkg/calculator.py"]
    assert "pkg/calculator.py" in report["file_previews"]


def test_extract_keywords_dedupes_and_filters_stop_words():
    assert extract_keywords("Error in parse_date: parse_date fails with ValueError") == ["parse_date", "fails", "ValueError"]


@pytest.mark.parametrize("path", [
    "kaggle_notebook/gemma_4_developer_agent_baseline.ipynb",
    "paper/paper_companion/gemma_4_adk_roofline_and_power_companion.ipynb",
])
def test_generated_notebooks_parse(path):
    nb = json.loads((ROOT / path).read_text(encoding="utf-8"))
    code_cells = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(code_cells) >= 3
    for src in code_cells:
        ast.parse(src)
