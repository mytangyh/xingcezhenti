import hashlib,json,os,sqlite3
from pathlib import Path
from .store import TABLES
KEYS={'questions':'question_id','occurrences':'occurrence_id','papers':'paper_id','materials':'material_id','assets':'asset_id','concepts':'concept_id','cards':'card_id','annotations':'annotation_id','assessments':'assessment_id','id_aliases':'alias_id'}
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(path,records):
 with open(path,'w') as f:
  for r in records:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
def make_database(path):
 con=sqlite3.connect(path/'content.sqlite')
 for t in TABLES:
  extra=', question_id TEXT, revision INTEGER, module TEXT, status TEXT, practice_ready INTEGER, material_id TEXT, stem TEXT' if t=='questions' else ''
  con.execute(f'CREATE TABLE {t}(id TEXT PRIMARY KEY,data TEXT NOT NULL{extra})')
  with open(path/(t+'.jsonl')) as f:
   for line in f:
    r=json.loads(line);v=[r[KEYS[t]],line.strip()]
    if t=='questions':v += [r['question_id'],r['revision'],r['normalized_module'],r['answer_status'],int(r['practice_ready']),r.get('material_id'),r['stem_markdown']]
    con.execute(f'INSERT INTO {t} VALUES ({",".join("?" for _ in v)})',v)
 con.execute('CREATE INDEX questions_filter ON questions(module,status,practice_ready)')
 con.execute('CREATE VIRTUAL TABLE question_search USING fts5(question_id UNINDEXED,stem,tokenize="trigram")')
 con.execute('INSERT INTO question_search SELECT question_id,stem FROM questions');con.commit();con.close();os.chmod(path/'content.sqlite',0o444)
def write_manifest(path,metadata):
 counts={}
 for t in TABLES:
  with open(path/(t+'.jsonl')) as f:counts[t]=sum(1 for _ in f)
 files={str(p.relative_to(path)):digest(p) for p in sorted(path.rglob('*')) if p.is_file() and p.name!='manifest.json'}
 m={**metadata,'schema_version':'1.0','counts':counts,'files':files};(path/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2));return m
def validate_release(path):
 from .schema import load_schemas,validate
 schemas=load_schemas()
 path=Path(path).resolve();m=json.loads((path/'manifest.json').read_text())
 if m.get('schema_version')!='1.0':raise ValueError('unsupported schema')
 required={t+'.jsonl' for t in TABLES}|{'content.sqlite'}
 if not required<=set(m['files']):raise ValueError('manifest omits required file')
 actual={str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p.name!='manifest.json'}
 if actual!=set(m['files']):raise ValueError('manifest file inventory mismatch')
 for name,sha in m['files'].items():
  p=(path/name).resolve()
  if not p.is_relative_to(path) or not p.is_file() or digest(p)!=sha:raise ValueError('hash mismatch '+name)
 from .safety import validate_safe_markup
 con=sqlite3.connect('file:'+str(path/'content.sqlite')+'?mode=ro',uri=True)
 try:
  if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('database integrity')
  ids={t:{r[0] for r in con.execute(f'SELECT id FROM {t}')} for t in TABLES}
  for t in TABLES:
   if len(ids[t])!=m['counts'][t]:raise ValueError('count mismatch '+t)
   seen=set()
   with open(path/(t+'.jsonl')) as f:
    for line in f:
     r=json.loads(line);validate(r,schemas[t]);key=r[KEYS[t]]
     if key in seen:raise ValueError('duplicate JSONL entity')
     seen.add(key);dbrow=con.execute(f'SELECT data FROM {t} WHERE id=?',(key,)).fetchone()
     if not dbrow or json.loads(dbrow[0])!=r:raise ValueError('JSONL SQLite mismatch '+t)
   if seen!=ids[t]:raise ValueError('JSONL IDs mismatch')
  for row in con.execute('SELECT data FROM questions'):
   q=json.loads(row[0]);mid=q.get('material_id')
   if q['answer_status'] not in ('source_only','verified','disputed','unresolved'):raise ValueError('invalid answer status')
   if q['material_binding_status'] not in ('unknown','source_inferred','verified','rejected'):raise ValueError('invalid binding status')
   if not isinstance(q['revision'],int) or q['revision']<1:raise ValueError('invalid revision')
   from .safety import validate_safe_markup
   for field in ('stem_markdown','stem_html'):validate_safe_markup(q[field],path)
   for opt in q['options']:
    validate_safe_markup(opt['text'],path);validate_safe_markup(opt['html'],path)
   if len({o['option_id'] for o in q['options']})!=len(q['options']):raise ValueError('duplicate option ID')
   indexed=con.execute('SELECT question_id,revision,module,status,practice_ready,material_id,stem FROM questions WHERE id=?',(q['question_id'],)).fetchone()
   if indexed!=(q['question_id'],q['revision'],q['normalized_module'],q['answer_status'],int(q['practice_ready']),q.get('material_id'),q['stem_markdown']):raise ValueError('question index columns mismatch')
   if mid and mid not in ids['materials']:raise ValueError('missing material')
   if any(x not in ids['concepts'] for x in q.get('concept_ids',[])):raise ValueError('missing concept')
   opts={o['option_id'] for o in q['options']}
   for answer in ('source_answer','verified_answer'):
    if q.get(answer) and not set(q[answer]['option_ids'])<=opts:raise ValueError('invalid option reference')
   if q['practice_ready'] and (q['material_binding_status']!='verified' or q['practice_blockers'] or not q.get('binding_evidence_refs')):raise ValueError('unsafe practice')
   if q['practice_ready'] and q.get('holdout_reserved'):raise ValueError('holdout exposed as practice')
   if q['practice_ready'] and q['answer_status'] not in ('source_only','verified'):raise ValueError('unscorable question exposed')
   if q['answer_status']=='verified' and not (q.get('verified_answer') or {}).get('evidence_refs'):raise ValueError('unsubstantiated verified answer')
   if mid and q['practice_ready']:
    mat=json.loads(con.execute('SELECT data FROM materials WHERE id=?',(mid,)).fetchone()[0])
    if mat.get('binding_status')!='verified':raise ValueError('unverified material')
  for row in con.execute('SELECT data FROM materials'):
   mat=json.loads(row[0])
   if mat['binding_status']=='verified' and not mat.get('evidence_refs'):raise ValueError('material verification evidence absent')
   for field in ('stem_markdown','stem_html'):validate_safe_markup(mat[field],path)
  for row in con.execute('SELECT data FROM occurrences'):
   r=json.loads(row[0])
   if r['question_id'] not in ids['questions'] or r['paper_id'] not in ids['papers']:raise ValueError('dangling occurrence')
  for t in ('annotations','cards','assessments'):
   for row in con.execute(f'SELECT data FROM {t}'):
    r=json.loads(row[0])
    if r.get('question_id') and r['question_id'] not in ids['questions']:raise ValueError('dangling question reference')
    if any(c not in ids['concepts'] for c in r.get('concept_ids',[])):raise ValueError('dangling concept reference')
    if r.get('is_official') and r.get('approval_status')!='human_approved':raise ValueError('official card requires human approval')
    for field,target in (('evidence_question_ids','questions'),('evidence_material_ids','materials'),('evidence_annotation_ids','annotations')):
     if any(k not in ids[target] for k in r.get(field,[])):raise ValueError('dangling card evidence '+field)
  for row in con.execute('SELECT data FROM assets'):
   a=json.loads(row[0]);f=(path/a['path']).resolve()
   if not f.is_relative_to(path/'assets') or not f.is_file() or digest(f)!=a['sha256']:raise ValueError('invalid asset')
  for t in ('questions','materials'):
   for row in con.execute(f'SELECT data FROM {t}'):
    entity=json.loads(row[0])
    for a in entity.get('assets',[])+entity.get('analysis_assets',[]):
     if a['asset_id'] not in ids['assets']:raise ValueError('missing asset reference')
     asset=json.loads(con.execute('SELECT data FROM assets WHERE id=?',(a['asset_id'],)).fetchone()[0])
     if a['path']!=asset['path']:raise ValueError('asset path mismatch')
  for row in con.execute('SELECT data FROM id_aliases'):
   a=json.loads(row[0])
   if a.get('target_id') not in ids['questions']:raise ValueError('invalid alias target')
 finally:con.close()
 return m
def check_revision_migration(old_path,new_path):
 old=sqlite3.connect('file:'+str(Path(old_path)/'content.sqlite')+'?mode=ro',uri=True);new=sqlite3.connect('file:'+str(Path(new_path)/'content.sqlite')+'?mode=ro',uri=True)
 try:
  for row in new.execute('SELECT id,data FROM questions'):
   previous=old.execute('SELECT data FROM questions WHERE id=?',(row[0],)).fetchone()
   if not previous:continue
   before=json.loads(previous[0]);after=json.loads(row[1])
   before_prompt=[before['stem_markdown'],[(o['option_id'],o['text']) for o in before['options']]]
   after_prompt=[after['stem_markdown'],[(o['option_id'],o['text']) for o in after['options']]]
   if before_prompt!=after_prompt and after['revision']<=before['revision']:raise ValueError('prompt changed without revision migration '+row[0])
  for row in new.execute('SELECT id,data FROM materials'):
   previous=old.execute('SELECT data FROM materials WHERE id=?',(row[0],)).fetchone()
   if not previous:continue
   before=json.loads(previous[0]);after=json.loads(row[1])
   if before['stem_markdown']!=after['stem_markdown'] and after['revision']<=before['revision']:raise ValueError('material changed without revision migration '+row[0])
 finally:old.close();new.close()

def activate_release(root,version):
 root=Path(root).resolve();p=(root/version).resolve()
 if p.parent!=root:raise ValueError('unsafe version')
 m=validate_release(p);cur={'version':version,'path':version,'manifest_sha256':digest(p/'manifest.json')}
 import tempfile
 fd,tmp=tempfile.mkstemp(prefix='.current-',dir=root)
 try:
  with os.fdopen(fd,'w') as f:f.write(json.dumps(cur));f.flush();os.fsync(f.fileno())
  os.replace(tmp,root/'current.json')
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 return cur
def list_releases(root):
 return [json.loads(p.read_text()) for p in sorted(Path(root).glob('*/manifest.json')) if not p.parent.name.startswith('.')]

def import_release(source,root,activate=False):
 """Import a directory without touching current on any validation/copy error."""
 import shutil,tempfile
 source=Path(source).resolve();root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
 m=validate_release(source);version=m['version']
 if not version or '/' in version or '\\' in version or version.startswith('.'):raise ValueError('unsafe release version')
 target=root/version
 if target.exists():raise ValueError('release exists; immutable')
 staging=Path(tempfile.mkdtemp(prefix='.import-',dir=root))
 try:
  # Reject symbolic links before copying so an archive cannot escape its package.
  if any(p.is_symlink() for p in source.rglob('*')):raise ValueError('symlink in release')
  shutil.copytree(source,staging,dirs_exist_ok=True);validate_release(staging);os.rename(staging,target)
  if activate:activate_release(root,version)
  return target
 except Exception:
  shutil.rmtree(staging,ignore_errors=True);raise
