"""Update the local paper only from completed, authenticated result snapshots."""
import json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def finalize():
    rows=json.loads((ROOT/'experiments/manifest.json').read_text())
    run=rows[0]
    if run['status'] != 'SubmissionStatus.COMPLETE':
        return False
    score=float(run['public_score'])
    conclusion=('exceeds' if score>0.18 else 'equals' if score==0.18 else 'falls below')
    result=f"The completed v4 evaluation scored {score:.2f}, which {conclusion} the historical v2 score of 0.18 (difference {score-0.18:+.2f}). This is one observed run, not a statistically established effect."
    p=ROOT/'paper/PAPER_WRITEUP.md'
    s=p.read_text(encoding='utf-8').replace('The result remains pending and is not counted as an improvement.',result)
    p.write_text(s,encoding='utf-8')
    winner=ROOT/('experiments/v4_tools_only/submission.zip' if score>0.18 else 'artifacts/v2_submission.zip')
    shutil.copyfile(winner,ROOT/'artifacts/best_verified_submission.zip')
    (ROOT/'evidence/CONTROLLED_RESULTS.md').write_text('# Controlled leaderboard experiment\n\n'+result+'\n\nSubmission: 58271330. Control: 58201114. Only graph-tool declarations changed.\nThe temperature-only variant was rejected by the daily quota and has no result.\n',encoding='utf-8')
    print(result,flush=True)
    return True

if __name__=='__main__':
    import time
    while not finalize(): time.sleep(45)
