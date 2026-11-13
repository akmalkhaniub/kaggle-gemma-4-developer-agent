"""Local diagnostic toolkit used to inspect repositories during configuration work.

This is NOT the competition's executing agent: submissions are declarative ADK
bundles run by Kaggle's own tool implementations. Paths are confined to the
workspace; commands are executed without a shell but are not otherwise sandboxed.
"""

import os
import shlex
import subprocess
from typing import Dict, List, Sequence, Tuple, Union

SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".pytest_cache"}


class AgentToolkit:
    """Local diagnostic helpers; shell commands are not sandboxed."""

    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.realpath(workspace_root)

    def _resolve_path(self, file_path: str) -> str:
        full_path = os.path.realpath(os.path.join(self.workspace_root, file_path))
        if os.path.commonpath([self.workspace_root, full_path]) != self.workspace_root:
            raise PermissionError(f"Access denied outside workspace boundary: {file_path}")
        return full_path

    def list_files(self, sub_dir: str = "", max_files: int = 100) -> List[str]:
        """Lists repository files relative to workspace root."""
        target_dir = self._resolve_path(sub_dir)
        matches = []
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), self.workspace_root).replace("\\", "/")
                matches.append(rel)
                if len(matches) >= max_files:
                    return matches
        return matches

    def read_file(self, file_path: str, start_line: int = 1, end_line: int = 200) -> str:
        """Reads specific line window from a file."""
        abs_path = self._resolve_path(file_path)
        if not os.path.isfile(abs_path):
            return f"ERROR: File not found: {file_path}"
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            start = max(1, start_line)
            end = min(len(lines), end_line)
            numbered_lines = [f"{i}: {lines[i - 1]}" for i in range(start, end + 1)]
            return "".join(numbered_lines)
        except OSError as e:
            return f"ERROR: {str(e)}"

    def search_code(self, query: str, file_ext: str = ".py", max_results: int = 25) -> List[Dict[str, object]]:
        """Case-insensitive literal search across files with the given extension."""
        results = []
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith(file_ext):
                    path = os.path.join(root, f)
                    rel = os.path.relpath(path, self.workspace_root).replace("\\", "/")
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as src_file:
                            for idx, line in enumerate(src_file, 1):
                                if query.lower() in line.lower():
                                    results.append({
                                        "file": rel,
                                        "line": idx,
                                        "content": line.strip()
                                    })
                                    if len(results) >= max_results:
                                        return results
                    except OSError:
                        continue
        return results

    def apply_patch(self, file_path: str, old_str: str, new_str: str) -> Tuple[bool, str]:
        """Applies an exact surgical string replacement with Python AST validation."""
        abs_path = self._resolve_path(file_path)
        if not os.path.isfile(abs_path):
            return False, f"File does not exist: {file_path}"
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            if old_str not in content:
                return False, f"Target string not found in {file_path}"
            
            # Check unique occurrence
            count = content.count(old_str)
            if count > 1:
                return False, f"Ambiguous match: target appears {count} times in {file_path}. Include more context."
            
            updated = content.replace(old_str, new_str)
            
            # Syntax validation if Python file
            if file_path.endswith(".py"):
                try:
                    compile(updated, file_path, "exec")
                except SyntaxError as syn_err:
                    return False, f"Syntax error in replacement: {syn_err.msg} at line {syn_err.lineno}"
            
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(updated)
            return True, f"Successfully patched {file_path}"
        except (OSError, UnicodeDecodeError, ValueError) as e:
            return False, f"Patch failed: {str(e)}"

    def run_tests(self, test_cmd: Union[str, Sequence[str]], timeout: int = 30) -> Dict[str, object]:
        """Runs a test command (argv list, or a string split with POSIX rules) without a shell."""
        argv = shlex.split(test_cmd) if isinstance(test_cmd, str) else list(test_cmd)
        if not argv:
            return {"exit_code": -1, "stdout": "", "stderr": "empty command", "status": "ERROR"}
        try:
            res = subprocess.run(
                argv,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout[:2000],
                "stderr": res.stderr[:2000],
                "status": "PASSED" if res.returncode == 0 else "FAILED"
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": f"Test timed out after {timeout}s", "status": "TIMEOUT"}
        except OSError as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e), "status": "ERROR"}

    def get_git_diff(self) -> str:
        """Emits git diff representation of current changes."""
        try:
            res = subprocess.run(
                ["git", "diff"],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            return res.stdout
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"Error retrieving git diff: {e}"
