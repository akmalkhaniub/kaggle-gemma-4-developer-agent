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
        s=s.replace('from __future__ import annotations\n','')
        ast.parse(s)
        cells.append(dict(cell_type='code',metadata={},source=s.splitlines(True),execution_count=None,outputs=[]))
    md('''# What Prompt Compression Removes: reproducibility companion
Kaggle API snapshot (2026-11-12): v2 submission 58201114 COMPLETE, 0.18; v3 submission 58250000 COMPLETE, 0.15.
This notebook (1) audits the official development tasks, (2) measures prompt bytes, (3) re-runs the instruction-unit audit of the v2 -> v3 compression,
(4) computes which evaluation sizes are consistent with the two displayed scores, and (5) validates and compiles the v3 bundle with the official wheelhouse.
It runs no model inference and makes no token, latency or significance claims. The API scores are historical evidence, not a fresh query.
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
    md('''## Instruction-unit audit
Each v2 guidance unit cites a verbatim v2 excerpt and, if it survives, a verbatim v3 excerpt. The audit fails if any excerpt is not found.
''')
    code((ROOT/'analysis/prompt_units.py').read_text(encoding='utf-8'))
    code('''audit=audit_units(V2_FILES['prompts/system.md'],V3_FILES['prompts/system.md'])
print(json.dumps({k:audit[k] for k in ('units_total','units_retained','units_dropped','by_kind','section_bytes')},indent=2))
for u in audit['dropped']: print(u['id'],u['kind'],'-',u['summary'])
print('Sensitivity of the rationale-vs-directive contrast to alternative labellings:')
for name,sc in audit['sensitivity']['scenarios'].items():
    print(' ',name,'| rationales dropped',sc['rationale']['dropped'],'/',sc['rationale']['total'],'| directives dropped',sc['directive']['dropped'],'/',sc['directive']['total'],'| rate ratio',sc['rate_ratio'])
print('Rate-ratio range across scenarios:',audit['sensitivity']['rate_ratio_range_scenarios'],'| leave-one-unit-out:',audit['sensitivity']['rate_ratio_range_leave_one_out'])
''')
    md('''## Score resolution
Assuming binary per-task outcomes and two-decimal rounding, which evaluation sizes N reproduce both displayed scores, and how many tasks does the gap represent?
''')
    code((ROOT/'analysis/score_resolution.py').read_text(encoding='utf-8'))
    code('''res=summarize(0.18,0.15)
gap=res.pop('gap_by_n')
print(json.dumps(res,indent=2))
print('Gap (tasks) at selected N:',{n:gap[str(n)] for n in (33,62,100,120,129) if str(n) in gap})
report.update(instruction_audit=audit,score_resolution=res)
Path('/kaggle/working/evidence_report.json').write_text(json.dumps(report,indent=2))
''')
    md('''## Figures and configuration checksums
Regenerates the paper's Figures 1 and 2 from the values computed above, and identifies each configuration by a SHA-256 over its file contents (ZIP bytes vary with the DEFLATE implementation, so they are not used as identity).
''')
    import inspect
    from analysis import run_all
    from harness.variants import content_digest
    FIG_SRC = (
        'from typing import Mapping' + '\n' + '\n'
        + 'BLUE, AMBER, GREY = ' + repr((run_all.BLUE, run_all.AMBER, run_all.GREY)) + '\n'
        + 'SECTIONS = ' + repr(run_all.SECTIONS) + '\n'
        + 'KIND_COLORS = ' + repr(run_all.KIND_COLORS) + '\n'
        + 'MAP_SECTIONS = ' + repr(run_all.MAP_SECTIONS) + '\n' + '\n'
        + inspect.getsource(run_all._unit_map) + '\n' + '\n'
        + inspect.getsource(run_all.make_figures) + '\n' + '\n'
        + inspect.getsource(content_digest)
    )
    code(FIG_SRC)
    code('''from IPython.display import Image, display
fig_dir=Path('/kaggle/working/figures')
make_figures({'instruction_audit':audit,'score_resolution':{**res,'gap_by_n':gap}},fig_dir)
for name in ('fig1_prompt_audit.png','fig2_score_resolution.png'):
    display(Image(filename=str(fig_dir/name)))
digests={'v2':content_digest(V2_FILES),'v3':content_digest(V3_FILES)}
print(json.dumps(digests,indent=2))
report.update(bundle_content_digest=digests)
Path('/kaggle/working/evidence_report.json').write_text(json.dumps(report,indent=2))
''')
    md('''## Configuration validation
The following cells reproduce the v3 bundle and run the official compiler. The tool implementations used for compilation are signature stubs, not executed repair tools. Compilation success establishes configuration compatibility only.
''')
    agent=json.loads((ROOT/'kaggle_notebook/gemma_4_developer_agent_baseline.ipynb').read_text(encoding='utf-8'))
    cells.extend(c for c in agent['cells'] if c['cell_type']=='code')
    md('''## Interpretation
The smaller v3 prompt accompanied a lower observed public score (0.15 versus 0.18). Prompt size, tool selection, temperature and time budget changed together, so these runs cannot identify the effect of prompt compression alone. The compression removed rationale units far more often than directives; whether that matters is a hypothesis for one-factor experiments, not a finding of this notebook. Keep v2 as the best observed candidate.
''')
    nb=dict(nbformat=4,nbformat_minor=4,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},cells=cells)
    out=ROOT/'paper/paper_companion/gemma_4_adk_roofline_and_power_companion.ipynb'
    out.write_text(json.dumps(nb,indent=2),encoding='utf-8')
    for c in cells:
        if c['cell_type']=='code': ast.parse(''.join(c['source']))
    print('Built and AST-checked',out)
if __name__=='__main__': build()
