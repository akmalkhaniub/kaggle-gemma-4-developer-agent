import csv, io, json, subprocess, sys, time
from pathlib import Path
root=Path(__file__).resolve().parent
manifest=root/'experiments/manifest.json'
rows=json.loads(manifest.read_text())
rows[0].update(submission_ref='58271330',status='PENDING')
rows[1].update(status='NOT_SUBMITTED_DAILY_QUOTA',submission_ref=None)
manifest.write_text(json.dumps(rows,indent=2))
last=None
while True:
    result=subprocess.run([sys.executable,'-m','kaggle','competitions','submissions','-c','gemma-4-developer-agent','--csv'],capture_output=True,text=True)
    if result.returncode:
        print('Polling failed; retrying',flush=True)
    else:
        (root/'evidence/controlled_submissions.csv').write_text(result.stdout)
        entries=list(csv.DictReader(io.StringIO(result.stdout)))
        target=next((x for x in entries if x['ref']=='58271330'),None)
        if target:
            state=(target['status'],target['publicScore'])
            if state!=last: print(json.dumps(target),flush=True);last=state
            rows[0].update(status=target['status'],public_score=target['publicScore'])
            manifest.write_text(json.dumps(rows,indent=2))
            if any(x in target['status'].upper() for x in ('COMPLETE','ERROR','CANCEL')): break
    time.sleep(45)
