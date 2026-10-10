"""Kiểm dữ liệu, liên kết và dấu vết xuất bản của bộ nghiên cứu."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).parent
PUB=ROOT/'publication'
VAULT=Path(r'D:\Obsidian Vault')
COLLECTION='DYLIGHT Bridge Evolution/Literature/SAGE-EvoBridge Research 2026-09-23'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
c=json.loads((ROOT/'corpus.json').read_text(encoding='utf-8'))
errors=[];notes=[]
ids=[s['id'] for s in c['sources']]
assert len(ids)==len(set(ids))==104
assert json.loads((PUB/'Data/corpus.json').read_text(encoding='utf-8'))==c
required=['title','publisher','url','reading_level','read_locator','summary_vi','key_points_vi','limitations_vi','project_use_vi','accessed_on']
max_words=0
for s in c['sources']:
 for k in required:
  if not s.get(k):errors.append(f"{s['id']}: missing {k}")
 if s['engineering_rule_approved'] is not False:errors.append(f"{s['id']}: rule promoted")
 words=len((' '.join([s['summary_vi'],*s['key_points_vi'],*s['limitations_vi'],s['project_use_vi']])).split());max_words=max(max_words,words)
 if words>200:errors.append(f"{s['id']}: derived prose {words} words")
 if s.get('attachment'):
  a=s['attachment'];p=PUB/a['file']
  if not p.read_bytes().startswith(b'%PDF') or sha(p)!=a['sha256']:errors.append(f"{s['id']}: PDF/hash invalid")
  if len(PdfReader(str(p)).pages)!=a['page_count']:errors.append(f"{s['id']}: page count mismatch")
 if s.get('existing_attachment'):
  a=s['existing_attachment'];p=VAULT/a['vault_path']
  if not p.exists() or sha(p)!=a['sha256']:errors.append(f"{s['id']}: existing PDF missing/drifted")

links_checked=0;frontmatter=0
for p in PUB.rglob('*.md'):
 text=p.read_text(encoding='utf-8')
 if '\ufffd' in text:errors.append(f'{p.name}: replacement character')
 if text.startswith('---\n'):
  fm=text.split('---\n',2)[1];frontmatter+=1
  keys=[]
  for line in fm.splitlines():
   # Gói chỉ dùng scalar một dòng và danh sách tag ASCII, kiểm đúng tập con này.
   match=re.fullmatch(r"([a-z_]+): (?:'(?:[^']|'')*'|[A-Z_]+|\[[a-z0-9, -]+\])",line)
   if not match:errors.append(f'{p.name}: unsupported/invalid YAML field {line}')
   else:keys.append(match.group(1))
  if len(keys)!=len(set(keys)):errors.append(f'{p.name}: duplicate YAML keys')
 for raw in re.findall(r'\[\[(.*?)\]\]',text):
  target=raw.split('|')[0].rstrip('\\').split('#')[0]
  if target.startswith(COLLECTION+'/'):q=PUB/target[len(COLLECTION)+1:]
  else:q=VAULT/target
  candidates=[q,q.with_suffix('.md')] if q.suffix not in ['.md','.pdf','.json'] else [q]
  if not any(x.is_file() for x in candidates):errors.append(f'{p.name}: broken wikilink {target}')
  links_checked+=1
 for label,raw in re.findall(r'\[([^\[\]]+)\]\(([^)]+)\)',text):
  target=raw.strip('<>').split('#')[0]
  if not target.startswith(('http:','https:')) and not (p.parent/target).exists():errors.append(f'{p.name}: broken Markdown link {target}')
stats=c['stats']
assert stats['by_reading_level']==dict(Counter(s['reading_level'] for s in c['sources']))
legacy=ROOT.parents[2]/c['prior_index']['path']
if sha(legacy)!=c['prior_index']['sha256']:errors.append('legacy index drift')
file_records=[dict(path=p.relative_to(PUB).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(PUB.rglob('*')) if p.is_file() and p.name!='manifest.json']
manifest={'schema_version':'1.0','collection':COLLECTION,'files':file_records}
(ROOT/'publication_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(PUB/'Data/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report=dict(task_id='BRD-055',checked_on='2026-09-23',status='PASS' if not errors else 'FAIL',
    source_records=len(ids),source_note_files=len(list((PUB/'Sources').glob('*.md'))),all_markdown_files=len(list(PUB.rglob('*.md'))),
    yaml_frontmatters_syntax_validated=frontmatter,wikilinks_resolved=links_checked,downloaded_pdfs=stats['downloaded_pdfs'],
    local_existing_pdfs_checked=stats['existing_local_pdfs'],max_source_derived_words=max_words,
    legacy_index_unchanged=sha(legacy)==c['prior_index']['sha256'],errors=errors,
    boundaries=['No engineering approval','No full-corpus full-text reading claim','No algorithm implementation or model training','No periodic automation enabled'],
    publication_status='STAGED_PENDING_COPY',independent_review='Separate reviewer evidence in independent_review.json')
(ROOT/'qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(1 if errors else 0)
