# 🤖 Google — The Gemma 4 Developer Agent Competition ($75,000 USD)

[![Competition](https://img.shields.io/badge/Kaggle-Gemma%204%20Developer%20Agent-20BEFF?style=flat&logo=kaggle)](https://www.kaggle.com/competitions/gemma-4-developer-agent)
[![Prizes](https://img.shields.io/badge/Prize%20Pool-%2475%2C000%20USD-gold?style=flat)](https://www.kaggle.com/competitions/gemma-4-developer-agent)
[![Category](https://img.shields.io/badge/Category-Featured%20%7C%20Points%20%26%20Medals-success?style=flat)](https://www.kaggle.com/competitions/gemma-4-developer-agent)
[![Tests](https://img.shields.io/badge/Pytest-5%2F5%20Passing-brightgreen?style=flat)](tests/)

Autonomous Software Engineering Agent architecture engineered for the **[Google — The Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent)** on Kaggle (Deadline: **December 2, 2026**).

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    Issue["📝 Issue Description / Bug Report"] --> Agent["🤖 Gemma Developer Agent Harness"]
    
    subgraph DiagnosticLoop ["Surgical Diagnostics & Fault Localization"]
        Agent -->|"1. Extract Identifiers"| KW["Key Term / Symbol Indexer"]
        KW -->|"2. Grep & Codebase Search"| Search["Code Search Toolkit (harness/tools.py)"]
        Search -->|"3. Window Reading"| Context["Context Reader (Lines 1-200)"]
    end
    
    subgraph PatchSynthesis ["Surgical Patch Synthesis & AST Safety"]
        Context -->|"4. Synthesize Diff"| Gemma["Gemma Model (Reasoning & Code Infilling)"]
        Gemma -->|"5. String Replacement"| AST["Python AST Syntax Validator"]
        AST -->|"Rejects Malformed Syntax"| Retry["Self-Correction Loop"]
        Retry --> Gemma
        AST -->|"Syntax Valid"| TestRunner["6. Pytest Execution Sandbox"]
    end
    
    TestRunner -->|"All Tests Passed"| GitDiff["7. Export Clean Git Diff (.patch)"]
```

---

## 🛠️ Components

- [`harness/tools.py`](harness/tools.py): Safe execution boundary providing `list_files`, `read_file`, `search_code`, surgical `apply_patch` with Python AST pre-compilation checks, and sandboxed test execution.
- [`harness/agent.py`](harness/agent.py): Multi-step agent orchestrator that coordinates keyword discovery, fault localization, and test verification.
- [`tests/test_agent_harness.py`](tests/test_agent_harness.py): End-to-end pytest test suite (**5/5 passing**).

---

## 🚀 How to Enter & Compete

### Step 1: Accept Competition Rules
Accept the official rules on the competition page:
👉 **[kaggle.com/competitions/gemma-4-developer-agent/rules](https://www.kaggle.com/competitions/gemma-4-developer-agent/rules)**

### Step 2: Run Verification Tests Locally
```powershell
pytest -v tests/
```

### Step 3: Push Baseline to Kaggle GPU
```powershell
Set-Location "kaggle_notebook"
kaggle kernels push -p .
```
