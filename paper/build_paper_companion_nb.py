"""Generate a self-contained, fail-closed Kaggle reproducibility notebook."""
import ast
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.adk_bundle import SUBMISSION_FILES

def build():
    v2 = json.loads((ROOT/'artifacts/v2_files.json').read_text(encoding='utf-8'))
    cells=[]
    def md(s): cells.append(dict(cell_type='markdown', metadata={}, source=s.splitlines(True)))
    def code(s):
        ast.parse(s)
        cells.append(dict(cell_type='code',metadata={},source=s.splitlines(True),execution_count=None,outputs=[]))
    md('''# Gemma 4: a smaller prompt did not improve the observed score
Reproducibility companion. Kaggle API checked 2026-11-12: v2 submission 58201114 COMPLETE, 0.18; v3 submission 58250000 COMPLETE, 0.15.
This notebook measures prompt bytes and audits official development data. It does not measure model tokens, GPU latency, compaction delay, or statistical significance. The API snapshot is historical evidence, not a fresh query from this offline notebook.
''')
    code('import json, hashlib, zipfile\nfrom pathlib import Path\nimport numpy as np\nV2_FILES = '+repr(v2)+'\nV3_FILES = '+repr(SUBMISSION_FILES))
    code('''candidates=sorted(Path('/kaggle/input/competitions/gemma-4-developer-agent').glob('**/tasks.jsonl'))
if not candidates:
    candidates=sorted(Path('/kaggle/input').glob('**/tasks.jsonl'))
assert len(candidates)==1, f'Need exactly one official tasks.jsonl; got {candidates}'
p=candidates[0]
raw=p.read_bytes()
tasks=[json.loads(line) for line in raw.decode().splitlines() if line.strip()]
problems=[str(t.get('problem_statement') or t.get('problem_description') or t.get('description') or '') for t in tasks]
assert tasks and all(problems), 'Missing problem statements'
audit={'tasks_path':str(p),'tasks_sha256':hashlib.sha256(raw).hexdigest(),'task_count':len(tasks),'problem_bytes_quantiles':np.percentile([len(x.encode()) for x in problems],[0,50,90,100]).tolist()}
print(json.dumps(audit,indent=2))
''')
    code('''rows=[]
for label,files in [('v2',V2_FILES),('v3',V3_FILES)]:
    prompt=files['prompts/system.md']
    sizes=[len(prompt.replace('{problem_description}',x).encode('utf-8')) for x in problems]
    rows.append({'variant':label,'prompt_template_bytes':len(prompt.encode('utf-8')),'expanded_prompt_bytes_p50':float(np.median(sizes)),'expanded_prompt_bytes_p90':float(np.percentile(sizes,90))})
reduction=rows[0]['prompt_template_bytes']-rows[1]['prompt_template_bytes']
print(json.dumps(rows,indent=2))
print('Measured template byte reduction:',reduction)
print('No tokenizer or serialized tool-schema measurements are claimed.')
report={'provenance':audit,'prompt_measurements':rows,'template_bytes_saved':reduction,'verified_historical_scores':{'58201114':0.18,'58250000':0.15},'score_delta':0.15-0.18,'limitations':['One evaluation per variant','Multiple configuration changes','No paired task outcomes','No causal solve-rate attribution','No inference executed by CPU companion']}
Path('/kaggle/working/evidence_report.json').write_text(json.dumps(report,indent=2))
''')
    md('''## Configuration validation
The following cells reproduce the v3 bundle and run the official compiler. The tool implementations used for compilation are signature stubs, not executed repair tools. Compilation success establishes configuration compatibility only.
''')
    agent=json.loads((ROOT/'kaggle_notebook/gemma_4_developer_agent_baseline.ipynb').read_text(encoding='utf-8'))
    cells.extend(c for c in agent['cells'] if c['cell_type']=='code')
    md('''## Interpretation
The smaller v3 prompt accompanied a lower observed public score (0.15 versus 0.18). Prompt size, tool selection, temperature and time budget changed together. These runs cannot identify the effect of prompt compression alone. No p-value or estimated reversal probability is justified without additional assumptions and paired outcomes. Keep v2 as the best observed candidate; evaluate one-factor variants before replacing it.
''')
    nb=dict(nbformat=4,nbformat_minor=4,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},cells=cells)
    out=ROOT/'paper/paper_companion/gemma_4_adk_roofline_and_power_companion.ipynb'
    out.write_text(json.dumps(nb,indent=2),encoding='utf-8')
    for c in cells:
        if c['cell_type']=='code': ast.parse(''.join(c['source']))
    print('Built and AST-checked',out)
if __name__=='__main__': build()
