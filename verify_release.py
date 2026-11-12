from pathlib import Path
import json, hashlib, zipfile
root=Path.cwd()
p=root/'paper/PAPER_WRITEUP.md'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('## 4. Results','''## 4. Results

The revised companion completed on Kaggle CPU as version 7 on November 12, 2026. It audited 129 official development tasks (median problem length 420 bytes; P90 1,806.2 bytes). Expanded system prompts had medians of 5,750 bytes for v2 and 3,739 bytes for v3. Both official directory validation and compilation passed for v3. The emitted ZIP was 2,608 bytes, SHA-256 `4029424ef9242aa53d0e32752b2f89c1064dd82b57d85b80145135426587496b`. This rerun performed no model inference.
''')
p.write_text(s,encoding='utf-8')
print('Paper whitespace word count:',len(s.split()))
# Verify the selected archive against its portable manifest and local structural checks.
from harness.adk_bundle import validate_submission_bundle
files=json.loads((root/'artifacts/v2_files.json').read_text())
bundle=root/'artifacts/v2_bundle'
for name,content in files.items():
    dest=bundle/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content.encode())
validate_submission_bundle(bundle)
with zipfile.ZipFile(root/'artifacts/v2_submission.zip') as z:
    assert z.testzip() is None
    assert set(z.namelist())==set(files)
    assert all(z.read(n)==files[n].encode() for n in files)
print('v2 archive matches manifest and passes structural validation')
