from pathlib import Path
p=Path('paper/PAPER_WRITEUP.md')
s=p.read_text(encoding='utf-8')
section='''## 6a. Prospective controlled follow-up (November 12, 2026)

To separate tool-declaration overhead from the earlier bundled changes, we submitted v4 (reference 58271330). It differs from the archived v2 only in agent.yaml: three graph-tool declarations are removed. The full v2 prompt, temperature 0.2, seven-minute limit and 28-call budget are retained byte-for-byte. The prompt already prohibits use of those three tools in v2; this intervention tests the effect of their declarations while retaining that instruction. The candidate ZIP SHA-256 is da33053fc47c61c1208c9b03f168ee4f65766d8a29d805dcf85020db4e1a2be6.

The comparison uses the historical v2 evaluation, not a fresh randomized paired control. A single score difference cannot distinguish an intervention effect from run variability. We predefine success operationally as exceeding the observed v2 score of 0.18; ties do not justify replacing the baseline. The result remains pending and is not counted as an improvement.

A second independently prepared variant changes only v2 temperature from 0.2 to 0.0. Kaggle rejected its submission after reporting zero remaining daily submissions, so it has no evaluation result. Neither the rejected variant nor compilation checks are counted as performance experiments.

'''
assert '## 6a.' not in s
s=s.replace('## 7. Conclusion',section+'## 7. Conclusion')
p.write_text(s,encoding='utf-8')
