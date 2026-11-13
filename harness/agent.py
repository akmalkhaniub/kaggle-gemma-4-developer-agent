"""Offline issue locator used while designing prompts.

It extracts identifiers from an issue description and lists the workspace files
that mention them. It does not call a model, plan, or write patches; the
competition agent is the declarative ADK bundle executed by Kaggle.
"""

import re
from typing import Any, Dict, List, Optional

from harness.tools import AgentToolkit

STOP_WORDS = {"this", "that", "with", "from", "when", "error", "issue", "problem", "function", "class"}


class IssueLocator:
    """Maps an issue description to candidate files by literal identifier search."""

    def __init__(self, workspace_root: str, max_keywords: int = 4, max_files: int = 3):
        self.toolkit = AgentToolkit(workspace_root)
        self.max_keywords = max_keywords
        self.max_files = max_files

    def locate(self, issue_description: str, test_cmd: Optional[str] = None) -> Dict[str, Any]:
        keywords = extract_keywords(issue_description)
        hits = [hit for kw in keywords[: self.max_keywords] for hit in self.toolkit.search_code(kw)]
        files = list(dict.fromkeys(hit["file"] for hit in hits))
        report: Dict[str, Any] = {
            "extracted_keywords": keywords,
            "target_files": files,
            "file_previews": {f: self.toolkit.read_file(f, 1, 150) for f in files[: self.max_files]},
        }
        if test_cmd:
            report["baseline_test"] = self.toolkit.run_tests(test_cmd)
        return report


def extract_keywords(text: str, limit: int = 10) -> List[str]:
    """Identifier-like tokens of length >= 4, in order of first appearance, minus stop words."""
    identifiers = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b", text)
    return list(dict.fromkeys(i for i in identifiers if i.lower() not in STOP_WORDS))[:limit]
