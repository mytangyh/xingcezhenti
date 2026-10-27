"""Validate sealed assessment packs; no publication or user answer synthesis."""
import hashlib,json,re,sqlite3
from pathlib import Path

def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()

def inspect_pack(root,pack_id):
 root=Path(root).resolve()
 if not re.fullmatch(r'[A-Za-z0-9_.-]+',pack_id) or pack_id in ('.','..'):raise ValueError('非法评测包ID')
 raw=root/pack_id
 if raw.is_symlink():raise ValueError('不允许评测目录符号链接')
 p=raw.resolve()
 if p.parent!=root:raise ValueError('非法评测路径')
 m=json.loads((p/'manifest.json').read_text())
 if m.get('schema_version')!='assessment-1' or m.get('pack_id')!=pack_id:raise ValueError('评测包版本/ID不匹配')
 files=m.get('files',{})
 if not isinstance(files,dict) or 'content.sqlite' not in files:raise ValueError('缺内容库hash')
 actual={str(x.relative_to(p)) for x in p.rglob('*') if x.is_file() and x.name!='manifest.json'}
 if actual!=set(files):raise ValueError('文件清单不完整或含未登记文件')
 for name,sha in files.items():
  if (p/name).is_symlink() or any(parent.is_symlink() for parent in (p/name).parents if parent.is_relative_to(p)):raise ValueError('不允许资产符号链接')
  target=(p/name).resolve()
  if not target.is_relative_to(p) or not target.is_file() or digest(target)!=sha:raise ValueError('评测包hash校验失败：'+name)
 ids=m.get('question_ids')
 if not isinstance(ids,list) or not ids or len(ids)>150 or not all(isinstance(x,str) for x in ids) or len(set(ids))!=len(ids):raise ValueError('题序无效')
 c=sqlite3.connect((p/'content.sqlite').as_uri()+'?mode=ro',uri=True)
 try:
  if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('评测库损坏')
  for table in ['questions','materials','assets','cards','concepts','papers','id_aliases','annotations','assessments','occurrences']:c.execute(f'SELECT id,data FROM {table} LIMIT 1')
  qs={r[0]:json.loads(r[1]) for r in c.execute('SELECT id,data FROM questions')}
  if set(qs)!=set(ids):raise ValueError('题序与实体不一致')
  materials={r[0]:json.loads(r[1]) for r in c.execute('SELECT id,data FROM materials')};mats=set(materials);asset_records={r[0]:json.loads(r[1]) for r in c.execute('SELECT id,data FROM assets')};assetpaths={x['path'] for x in asset_records.values()}
  from xingce_project.pipeline.safety import validate_safe_markup
  def validate_prompt(x):
   for field in ('stem_markdown','stem_html','text','html'):
    if field in x:validate_safe_markup(x[field],p)
   for a in x.get('assets',[]):
    if a.get('asset_id') not in asset_records or asset_records[a['asset_id']]['path']!=a.get('path') or a.get('path') not in files:raise ValueError('题面资产引用无效')
   for path in re.findall(r'assets/[a-f0-9]{64}\.(?:png|jpg|jpeg|gif|webp)',json.dumps(x,ensure_ascii=False)):
    if path not in assetpaths or path not in files:raise ValueError('HTML资产未登记')
  for material in materials.values():validate_prompt(material)
  for path in assetpaths:
   if path not in files or not path.startswith('assets/'):raise ValueError('未登记或未hash资产')
  scored=0
  for qid in ids:
   q=qs[qid];validate_prompt(q)
   for option in q.get('options',[]):validate_prompt(option)
   if q.get('question_id')!=qid or not q.get('prompt_ready') or q.get('practice_ready') or not q.get('holdout_reserved'):raise ValueError('评测题面状态不合约')
   if q.get('material_id') and q['material_id'] not in mats:raise ValueError('评测材料缺失')
   opts=q.get('options',[]);option_ids={x['option_id'] for x in opts}
   if len(option_ids)<2 or len(option_ids)!=len(opts):raise ValueError('选项无效')
   if q.get('assessment_ready'):
    ans=q.get('verified_answer') or {}
    if q.get('answer_status')!='verified' or not ans.get('option_ids') or not set(ans['option_ids'])<=option_ids or not ans.get('evidence_refs'):raise ValueError('评测密钥证据无效')
    scored+=1
   elif q.get('answer_status') not in ('unresolved','disputed') or q.get('verified_answer'):raise ValueError('未决题不可按来源答案评分')
  if scored!=m.get('scorable_count') or len(ids)-scored!=m.get('unscored_count'):raise ValueError('可评分数量不符')
 finally:c.close()
 return p,{**m,'manifest_sha256':digest(p/'manifest.json')}
