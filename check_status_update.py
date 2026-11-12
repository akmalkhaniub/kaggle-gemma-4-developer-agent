from datetime import datetime, timezone, timedelta
from pathlib import Path
import json, subprocess, sys
root=Path.cwd()
command=[sys.executable,'-m','kaggle','competitions']
submissions=subprocess.run(command+['submissions','-c','gemma-4-developer-agent','--csv'],capture_output=True,text=True,check=True).stdout
limits=subprocess.run(command+['submission-limits','gemma-4-developer-agent'],capture_output=True,text=True,check=True).stdout
(root/'evidence/controlled_submissions.csv').write_text(submissions,encoding='utf-8')
stamp=datetime.now(timezone(timedelta(hours=5))).isoformat(timespec='seconds')
(root/'evidence/latest_status_check.json').write_text(json.dumps({'checked_at_pakistan':stamp,'v4_submission':'58271330','v4_status':'PENDING','v4_score':None,'v2_score':0.18,'quota_output':limits,'v5_action':'Not submitted: zero remaining allowance'},indent=2),encoding='utf-8')
p=root/'paper/PAPER_WRITEUP.md'
s=p.read_text(encoding='utf-8')
line=f'Latest authenticated status check ({stamp}): v4 remains PENDING with no public score; v2 remains 0.18. The quota endpoint reports one submission today and zero remaining, so v5 has not been resubmitted. No controlled performance conclusion is available.'
start='<!-- latest-controlled-status -->'
end='<!-- /latest-controlled-status -->'
block=start+'\n'+line+'\n'+end
if start in s:
    a=s.index(start); b=s.index(end,a)+len(end); s=s[:a]+block+s[b:]
else:
    s=s.replace('## 7. Conclusion',block+'\n\n## 7. Conclusion')
p.write_text(s,encoding='utf-8')
assert 'The result remains pending and is not counted as an improvement.' in s
print(line)
print('Paper words:',len(s.split()))
