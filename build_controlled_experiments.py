import json, hashlib
from pathlib import Path
from harness.adk_bundle import validate_submission_bundle, build_submission_zip
ROOT=Path(__file__).resolve().parent
base=json.loads((ROOT/'artifacts/v2_files.json').read_text())
variants={}
tools=dict(base)
for name in ('get_code_neighbors','search_similar_code','get_code_subgraph'):
    tools['agent.yaml']=tools['agent.yaml'].replace('  - '+name+'\n','')
variants['v4_tools_only']=tools
# A second independent intervention: deterministic sampling, preserving every other byte.
greedy=dict(base)
greedy['configs/sampling.yaml']=greedy['configs/sampling.yaml'].replace('temperature: 0.2','temperature: 0.0')
variants['v5_temperature_only']=greedy
records=[]
for name,files in variants.items():
    out=ROOT/'experiments'/name
    bundle=out/'bundle'
    changed=[n for n in base if files[n]!=base[n]]
    assert len(changed)==1
    for n,s in files.items():
        p=bundle/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode())
    validate_submission_bundle(bundle)
    z=build_submission_zip(bundle,out/'submission.zip')
    records.append({'variant':name,'control_submission':'58201114','changed_files':changed,'sha256':hashlib.sha256(z.read_bytes()).hexdigest(),'status':'prepared','hypothesis':'Remove unused tool schemas' if 'tools' in name else 'Reduce sampling variability','unchanged':'All other bundle files byte-identical to v2'})
(ROOT/'experiments/manifest.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records,indent=2))
