"""Single-user offline study server. Run on 127.0.0.1 only."""
import json, os, sqlite3, uuid, time, shutil, re, threading, statistics
from pathlib import Path
from contextlib import contextmanager
from html.parser import HTMLParser
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

PROJECT=Path(__file__).resolve().parents[3]
ERROR_TYPES=['看漏条件','模型识别错误','规则错误','计算错误','选项辨析错误','时间分配失当','猜对不确定','数据疑点']
def uid():return uuid.uuid4().hex
def fail(code,msg):raise HTTPException(code,msg)
class PromptText(HTMLParser):
 """Preserve functional formatting without sending executable HTML to React."""
 def __init__(self):
  super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','iframe','object'):
   self.hidden+=1;return
  if self.hidden:return
  if tag=='u':self.parts.append('【划线：')
  elif tag=='sup':self.parts.append('^(')
  elif tag=='sub':self.parts.append('_(')
  elif tag in ('p','div','br','tr'):self.parts.append('\n')
  elif tag in ('td','th'):self.parts.append('\t')
 def handle_endtag(self,tag):
  if tag in ('script','style','iframe','object'):
   self.hidden=max(0,self.hidden-1);return
  if self.hidden:return
  if tag=='u':self.parts.append('】')
  elif tag in ('sup','sub'):self.parts.append(')')
  elif tag in ('p','div','tr'):self.parts.append('\n')
 def handle_data(self,data):
  if not self.hidden:self.parts.append(data.replace('✅',''))
def plain(x):
 parser=PromptText();parser.feed(str(x or ''));parser.close()
 return re.sub(r'【划线：[\s\u00a0]*】','【划线：（空白）】',''.join(parser.parts)).strip()

def create_app(releases=None,userdata=None,assessments=None):
 assessment_root=Path(assessments or os.environ.get('XINGCE_ASSESSMENTS',PROJECT/'assessments')).resolve()
 root=Path(releases or os.environ.get('XINGCE_RELEASES',PROJECT/'releases')).resolve()
 user=Path(userdata or os.environ.get('XINGCE_USERDATA',PROJECT/'userdata')).resolve();user.mkdir(parents=True,exist_ok=True)
 exports=user/'exports';exports.mkdir(exist_ok=True)
 incoming=user/'imports';incoming.mkdir(exist_ok=True)
 dbpath=user/'personal.sqlite'; lock=threading.RLock()
 @contextmanager
 def db():
  with lock:
   c=sqlite3.connect(dbpath);c.row_factory=sqlite3.Row
   try:yield c;c.commit()
   except: c.rollback();raise
   finally:c.close()
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);INSERT OR IGNORE INTO meta VALUES('schema','1');
  CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,release TEXT,mode TEXT,status TEXT,created REAL,submitted REAL,paused REAL,pause_seconds REAL DEFAULT 0,interrupted INTEGER DEFAULT 0,question_ids TEXT);
  CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY,session_id TEXT,question_id TEXT,status TEXT,selected TEXT,created REAL,submitted REAL,grade TEXT,hint INTEGER DEFAULT 0,guessed INTEGER DEFAULT 0,exposed INTEGER DEFAULT 0,active INTEGER DEFAULT 1);
  CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,session_id TEXT,type TEXT,at REAL,question_id TEXT,duration REAL);
  CREATE TABLE IF NOT EXISTS reviews(attempt_id TEXT PRIMARY KEY,error_type TEXT,notes TEXT,due_at REAL,interval_days INTEGER);
  CREATE INDEX IF NOT EXISTS attempt_session ON attempts(session_id); CREATE TABLE IF NOT EXISTS exposures(question_id TEXT PRIMARY KEY,reason TEXT,at REAL); CREATE TABLE IF NOT EXISTS task_settings(id TEXT PRIMARY KEY,data TEXT);''')
 app=FastAPI(title='行测离线工作台',version='1.0.0')
 learning_cache={};coverage_cache={}
 app.state.dbpath=dbpath;asset_registry={};holdout_material_cache={};search_index_cache={};release_summary_cache={}
 @app.middleware('http')
 async def local_guard(request:Request,call_next):
  # Reject cross-site mutations; never bind publicly. Same-origin browser only.
  origin=request.headers.get('origin')
  if request.url.hostname not in ('localhost','127.0.0.1','::1','testserver'):
   from fastapi.responses import JSONResponse
   return JSONResponse({'detail':'仅接受本机Host'},status_code=403)
  if request.method not in ('GET','HEAD','OPTIONS') and origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
   from fastapi.responses import JSONResponse
   return JSONResponse({'detail':'跨站写入被拒绝'},status_code=403)
  response=await call_next(request)
  response.headers['X-Content-Type-Options']='nosniff';response.headers['Cache-Control']='no-store'
  return response
 def release_path(version=None):
  if version is None:
   try:version=json.loads((root/'current.json').read_text())['version']
   except (OSError,KeyError,ValueError):fail(503,'尚无已导入内容版本')
  if not re.fullmatch(r'[A-Za-z0-9_.-]+',version) or version in ('.','..'):fail(400,'非法版本')
  version_root=assessment_root if version.startswith('assessment--') else root
  name=version.removeprefix('assessment--') if version.startswith('assessment--') else version
  p=(version_root/name).resolve()
  if p.parent!=version_root or not (p/'content.sqlite').is_file():fail(404,'内容版本不存在')
  return p
 @contextmanager
 def content(version=None):
  p=release_path(version);c=sqlite3.connect(p.joinpath('content.sqlite').as_uri()+'?mode=ro',uri=True)
  try:yield c,version if version and version.startswith('assessment--') else p.name
  finally:c.close()
 def entity(c,table,id):
  if table not in ['questions','materials','cards','concepts','papers','assets','id_aliases']:fail(400,'非法表')
  row=c.execute(f'SELECT data FROM {table} WHERE id=?',(id,)).fetchone()
  return json.loads(row[0]) if row else None
 def all_entities(c,table):return [json.loads(r[0]) for r in c.execute(f'SELECT data FROM {table}')]
 def assets(xs,version):
  return [{'asset_id':x.get('asset_id'),'url':f"/api/assets/{version}/{x['path']}",'role':x.get('role'),'option_id':x.get('option_id')} for x in xs or [] if isinstance(x,dict) and x.get('role')!='analysis_only' and x.get('path') and not str(x['path']).startswith('/') and '..' not in Path(x['path']).parts]
 def holdout_materials(c,version):
  if version not in holdout_material_cache:
   reserved=[json.loads(r[0]) for r in c.execute('SELECT data FROM questions WHERE json_extract(data,"$.holdout_reserved")=1')]
   holdout_material_cache[version]={mid for q in reserved for mid in [q.get('material_id')]+q.get('candidate_material_ids',[]) if mid}
  return holdout_material_cache[version]
 def expose(qids,reason):
  with db() as d:
   for qid in qids:d.execute('INSERT OR IGNORE INTO exposures VALUES(?,?,?)',(qid,reason,time.time()))
 def safe_question(q,c,version):
  m=entity(c,'materials',q.get('material_id')) if q.get('material_id') else None
  return dict(question_id=q['question_id'],assessment_item_id=q.get('assessment_item_id'),stem=plain(q.get('stem_markdown')),options=[dict(option_id=o['option_id'],label=o.get('label',''),text=plain(o.get('text')),assets=assets(o.get('assets'),version)) for o in q.get('options',[])],material_id=q.get('material_id'),material={'id':q['material_id'],'text':plain(m.get('stem_markdown')),'assets':assets(m.get('assets'),version)} if m else None,assets=assets(q.get('assets'),version),answer_status=q.get('answer_status','unresolved'),review_status=q.get('review_status','unknown'),verification_notice='verified表示附证据的答案核对，AI核对不等同人工审批')
 def session_row(c,id):
  s=c.execute('SELECT * FROM sessions WHERE id=?',(id,)).fetchone()
  if not s:fail(404,'会话不存在')
  s=dict(s)
  if s['release'].startswith('assessment--'):
   from .assessment import digest
   meta=c.execute('SELECT data FROM task_settings WHERE id=?',('assessment-session:'+id,)).fetchone()
   if not meta:fail(409,'评测锁定记录缺失')
   meta=json.loads(meta[0]);p=release_path(s['release'])
   if digest(p/'manifest.json')!=meta['manifest_sha256'] or digest(p/'content.sqlite')!=meta['content_sha256']:fail(409,'评测包已变化；请恢复原始锁定版本，不允许静默重评')
  return s
 def check_assessment_locks(c):
  from .assessment import digest
  for sid,version in c.execute("SELECT id,release FROM sessions WHERE release LIKE 'assessment--%'"):
   row=c.execute('SELECT data FROM task_settings WHERE id=?',('assessment-session:'+sid,)).fetchone()
   if not row:fail(422,'评测历史缺少锁定manifest，拒绝导入/恢复')
   meta=json.loads(row[0]);p=release_path(version)
   if digest(p/'manifest.json')!=meta.get('manifest_sha256') or digest(p/'content.sqlite')!=meta.get('content_sha256'):fail(422,'评测历史锁定hash不匹配，拒绝导入/恢复')
 def attempt_row(c,id):
  a=c.execute('SELECT * FROM attempts WHERE id=?',(id,)).fetchone()
  if not a:fail(404,'作答不存在')
  return dict(a)
 def can_review(c,a):
  s=session_row(c,a['session_id'])
  if s['release'].startswith('assessment--') and s['status']!='submitted':return False
  return a['status']=='submitted' and (s['mode']=='practice' or s['status'] in ('submitted','abandoned'))
 def public_attempt(c,a):
  result={k:a[k] for k in ['id','session_id','question_id','status','created','submitted','hint','guessed','exposed','active']}
  result['attempt_id']=a['id'];result['selected_option_ids']=json.loads(a['selected']);result['review_available']=can_review(c,a)
  return result
 def session_data(c,id):
  s=session_row(c,id)
  last=c.execute('SELECT MAX(at) FROM events WHERE session_id=?',(id,)).fetchone()[0] or s['created']
  if s['status']!='submitted' and not s['paused'] and time.time()-last>90:
   c.execute('UPDATE sessions SET interrupted=1 WHERE id=?',(id,));s['interrupted']=1
  s['question_ids']=json.loads(s['question_ids']);s['attempts']=[public_attempt(c,dict(a)) for a in c.execute('SELECT * FROM attempts WHERE session_id=? AND active=1 ORDER BY created',(id,))]
  end=s['submitted'] or time.time();s['elapsed_seconds']=max(0,end-s['created']);s['active_seconds']=max(0,s['elapsed_seconds']-s['pause_seconds']-((end-s['paused']) if s['paused'] else 0))
  s['started_at']=s['created'];s['paused_at']=s['paused'];s['paused_seconds']=s['pause_seconds']
  s['events']=[dict(e) for e in c.execute('SELECT * FROM events WHERE session_id=? ORDER BY id',(id,))]
  s['label']='重组模拟' if s['mode']=='mock' else '练习';s['selection_notice']='包含复习/已见题，不算全新迁移' if any(e['type']=='selection_repeat' for e in s['events']) else '用户指定题目/重做' if any(e['type']=='selection_explicit' for e in s['events']) else '优先当前记录中未练未曝的候选；非绝对未见保证'
  if s['release'].startswith('assessment--'):
   s['assessment']=json.loads(c.execute('SELECT data FROM task_settings WHERE id=?',('assessment-session:'+id,)).fetchone()[0]);s['label']='个人迁移测验（非原卷）';s['selection_notice']=s['assessment']['attempt_label']+'；非考分预测，未决题不计准确率分母'
  return s
 def grade(a,s):
  with content(s['release']) as (cc,v):
   q=entity(cc,'questions',a['question_id']);status=q.get('answer_status','unresolved');answer=q.get('verified_answer') if status=='verified' else q.get('source_answer') if status=='source_only' else None
   correct=set(json.loads(a['selected']))==set(answer.get('option_ids',[])) if answer and answer.get('option_ids') else None
   return json.dumps({'correct':correct,'answer_status':status,'answer':answer,'question_revision':q.get('revision'),'release':v},ensure_ascii=False)
 def submit_one(c,a,s,finalize=False):
  pending=bool(a.get('grade') and json.loads(a['grade']).get('pending'))
  if a['status']=='submitted' and not (finalize and pending):return
  g=grade(a,s) if s['mode']=='practice' or finalize else json.dumps({'correct':None,'answer_status':'pending','answer':None,'release':s['release'],'pending':True})
  now=time.time();c.execute("UPDATE attempts SET status='submitted',submitted=?,grade=? WHERE id=?",(a.get('submitted') or now,g,a['id']))
  if not s['release'].startswith('assessment--') and (json.loads(g)['correct'] is False or a['hint'] or a['guessed']):
   c.execute('INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?)',(a['id'],'猜对不确定' if a['guessed'] else '', '',now+86400,1))
 def load_assessment(pack_id):
  from .assessment import inspect_pack
  try:return inspect_pack(assessment_root,pack_id)
  except (OSError,ValueError,KeyError,TypeError,sqlite3.Error) as e:fail(422,'评测包校验失败：'+str(e))
 @app.get('/api/assessments')
 def assessments_list():
  result=[]
  for file in sorted(assessment_root.glob('*/manifest.json')):
   try:
    _,m=load_assessment(file.parent.name)
    with db() as c:previous=c.execute('SELECT COUNT(*) FROM sessions WHERE release=?',('assessment--'+m['pack_id'],)).fetchone()[0]
    result.append({'pack_id':m['pack_id'],'title':m.get('title','个人迁移测验'),'question_count':len(m['question_ids']),'scorable_count':m['scorable_count'],'unscored_count':m['unscored_count'],'manifest_sha256':m['manifest_sha256'],'previous_starts':previous})
   except HTTPException:continue
  return {'items':result,'notice':'个人迁移测验，非原卷、非考分预测。只有显式确认启动才展示题面并记录曝光；未决题不评分。'}
 @app.post('/api/assessments/{pack_id}/start')
 def start_assessment(pack_id:str,body:dict):
  if body.get('confirm') is not True:fail(422,'请明确确认启动评测：开始即记录曝光，不可恢复为未见')
  _,m=load_assessment(pack_id);version='assessment--'+pack_id;ids=m['question_ids'];now=time.time()
  with db() as c:
   previous=c.execute('SELECT COUNT(*) FROM sessions WHERE release=?',(version,)).fetchone()[0]
   seen={r[0] for r in c.execute('SELECT DISTINCT question_id FROM attempts')}|{r[0] for r in c.execute('SELECT question_id FROM exposures')}
   known_count=len(set(ids)&seen);sid=uid();declared_seen=bool(body.get('seen_before'));hint=bool(body.get('hint_used'))
   label='重做/再次启动，不能称未见' if previous else '首次启动，但已存在已阅记录或自报熟悉/提示' if known_count or declared_seen or hint else '首次启动（仍不能保证用户此前未见）'
   meta={'pack_id':pack_id,'manifest_sha256':m['manifest_sha256'],'content_sha256':m['files']['content.sqlite'],'question_count':len(ids),'scorable_count':m['scorable_count'],'unscored_count':m['unscored_count'],'previous_starts':previous,'known_question_count':known_count,'declared_seen_before':declared_seen,'declared_hint_used':hint,'attempt_label':label}
   c.execute('INSERT INTO sessions(id,release,mode,status,created,question_ids) VALUES(?,?,?,?,?,?)',(sid,version,'mock','active',now,json.dumps(ids)))
   c.execute('INSERT INTO task_settings VALUES(?,?)',('assessment-session:'+sid,json.dumps(meta)))
   c.execute('INSERT INTO events(session_id,type,at) VALUES(?,?,?)',(sid,'assessment_started',now))
   for qid in ids:
    c.execute('INSERT INTO attempts(id,session_id,question_id,status,selected,created,hint) VALUES(?,?,?,?,?,?,?)',(uid(),sid,qid,'draft','[]',now,int(hint)))
    c.execute('INSERT OR IGNORE INTO exposures VALUES(?,?,?)',(qid,'assessment_started',now))
   return session_data(c,sid)
 @app.get('/api/catalog')
 def catalog():
  with content() as (c,v):
   counts=[{'module':r[0],'answer_status':r[1],'practice_ready':bool(r[2]),'count':r[3]} for r in c.execute('SELECT module,status,practice_ready,COUNT(*) FROM questions GROUP BY module,status,practice_ready')]
   return {'release':v,'counts':counts,'modules':sorted(set(x['module'] or 'unknown' for x in counts)),'concepts':all_entities(c,'concepts'),'quality_notice':'仅核准题面可练；verified可能为AI逐题证据复算，非人工审批；source_only为来源答案，单独统计。未认证题面不进入训练。'}
 def search_index(c,v):
  if v not in search_index_cache:
   papers={x.get('paper_id',x.get('id')):x for x in all_entities(c,'papers')};by_question={}
   if c.execute("SELECT 1 FROM sqlite_master WHERE name='occurrences'").fetchone():
    for row in c.execute('SELECT data FROM occurrences'):
     x=json.loads(row[0]);pid=x.get('paper_id')
     if pid in papers:by_question.setdefault(x['question_id'],set()).add(pid)
   search_index_cache[v]=(papers,by_question)
  return search_index_cache[v]
 def card_modules(card,c):
  result={str(card.get('module') or card.get('normalized_module') or '')}-{''}
  for path in card.get('source_files',[]):
   m=re.search(r'(?:^|/)[0-9]+-([^/]+)/',path)
   if m:result.add(m.group(1))
  refs=[]
  for key in ['evidence_qids','evidence_question_ids','example_qids','question_ids']:refs.extend(card.get(key,[]) or [])
  refs.extend(re.findall(r'(?<![0-9])[0-9]{6,9}(?![0-9])',str(card.get('body_markdown',''))))
  for qid in refs:
   qid=str(qid);q=entity(c,'questions','q-'+qid if qid.isdigit() else qid)
   if q and q.get('normalized_module'):result.add(q['normalized_module'])
  return sorted(result)
 def filtered_cards(c,module=''):
  result=[]
  for card in all_entities(c,'cards'):
   modules=card_modules(card,c)
   if not module or module in modules:result.append({**card,'modules':modules,'module':' · '.join(modules)})
  return result
 @app.get('/api/search/filters')
 def search_filters():
  with content() as (c,v):
   papers,_=search_index(c,v)
   return {'release':v,'years':sorted({str(p['exam_year_label']) for p in papers.values() if p.get('exam_year_label')},reverse=True),'paper_types':sorted({p['paper_type'] for p in papers.values() if p.get('paper_type')}),'concepts':all_entities(c,'concepts'),'notice':'年度与卷型为来源卷标签；不是已确认原卷完整性。'}
 @app.get('/api/search')
 def search(q:str='',module:str='',kind:str='questions',limit:int=20,year:str='',paper_type:str='',concept_id:str='',allow_source_only:bool=False):
  if kind not in ('questions','cards','materials'):fail(400,'不支持的检索范围')
  limit=max(1,min(limit,100));q=q.strip()[:200];search_mode='bounded_substring_fallback'
  with content() as (c,v):
   if kind=='cards':
    matches=[x for x in filtered_cards(c,module) if q.casefold() in json.dumps(x,ensure_ascii=False).casefold()][:limit]
    return {'items':visible_cards(matches),'release':v,'search_mode':'card_metadata_substring'}
   allowed=['verified']+(['source_only'] if allow_source_only else [])
   rows=[json.loads(r[0]) for r in c.execute('SELECT data FROM questions WHERE practice_ready=1 AND status IN ('+','.join('?' for _ in allowed)+') AND (?="" OR module=?)',(*allowed,module,module))]
   papers,by_question=search_index(c,v);protected=holdout_materials(c,v);eligible=[];paper_labels={}
   for x in rows:
    if x.get('holdout_reserved') or x.get('material_id') in protected or concept_id and concept_id not in x.get('concept_ids',[]):continue
    labels=[papers[pid] for pid in sorted(by_question.get(x['question_id'],set())) if (not year or str(papers[pid].get('exam_year_label'))==year) and (not paper_type or papers[pid].get('paper_type')==paper_type)]
    if (year or paper_type) and not labels:continue
    paper_labels[x['question_id']]=[{'paper_id':p.get('paper_id'),'name':p.get('name'),'year':p.get('exam_year_label'),'paper_type':p.get('paper_type')} for p in labels]
    eligible.append(x)
   fts_ids=None
   if kind=='questions' and len(q)>=3 and c.execute("SELECT 1 FROM sqlite_master WHERE name='question_search'").fetchone():
    try:fts_ids={r[0] for r in c.execute('SELECT question_id FROM question_search WHERE question_search MATCH ?',('"'+q.replace('"','""')+'"',))};search_mode='fts5_trigram'
    except sqlite3.OperationalError:pass
   def text_match(x):return not q or q==x['question_id'] or 'q-'+q==x['question_id'] or (x['question_id'] in fts_ids if fts_ids is not None else q.casefold() in str(x.get('stem_markdown','')).casefold())
   def project(x):return {**safe_question(x,c,v),'source_papers':paper_labels[x['question_id']]}
   if kind=='questions':
    matched=[x for x in eligible if text_match(x)];items=[project(x) for x in matched[:limit]];expose([x['question_id'] for x in items],'question_search_seen');total=len(matched)
   else:
    grouped={}
    for x in eligible:
     if x.get('material_id'):grouped.setdefault(x['material_id'],[]).append(x)
    matches=[]
    for mid,questions in grouped.items():
     m=entity(c,'materials',mid)
     if not m:continue
     text=plain(m.get('stem_markdown'));hit=not q or q.casefold() in text.casefold() or any(text_match(x) for x in questions)
     if hit:matches.append({'id':mid,'text':text,'assets':assets(m.get('assets'),v),'questions':[project(x) for x in questions]})
    items=matches[:limit];total=len(matches)
    mids={x['id'] for x in items}
    if mids:
     placeholders=','.join('?' for _ in mids)
     linked=[r[0] for r in c.execute('SELECT id FROM questions WHERE material_id IN ('+placeholders+') OR EXISTS (SELECT 1 FROM json_each(questions.data,"$.candidate_material_ids") j WHERE j.value IN ('+placeholders+'))',list(mids)+list(mids))];expose(linked,'material_search_seen')
   return {'items':items,'total':total,'limit':limit,'search_mode':search_mode,'release':v,'notice':'只展示可练题面；检索显示即记已阅。source_only需主动选择；来源年份/卷型不表示原卷已核完整。'}
 def cards_locked():
  with db() as d:return bool(d.execute("SELECT 1 FROM sessions WHERE mode IN ('group','mock') AND status='active' LIMIT 1").fetchone())
 def visible_cards(items):
  if cards_locked():return [{'card_id':x.get('card_id',x.get('id')),'title':x.get('title'),'status':x.get('status'),'locked':True,'notice':'请先完成组练或模拟，再查看方法例解'} for x in items]
  return [{'card_id':x.get('card_id',x.get('id')),'title':x.get('title'),'status':x.get('status'),'module':x.get('module'),'summary':x.get('summary','')} for x in items]
 def mark_cards(cards):
  with db() as d:
   for card in cards:
    ids=[]
    for key in ['example_qids','boundary_qids','question_ids','evidence_qids','evidence_question_ids']:ids.extend(card.get(key,[]) or [])
    ids.extend(re.findall(r'(?i)qid\s*[:=：]?\s*(\d+)',json.dumps(card,ensure_ascii=False)))
    for qid in ids:
     if isinstance(qid,str):
      qid='q-'+qid if qid.isdigit() else qid
      d.execute('INSERT OR IGNORE INTO exposures VALUES(?,?,?)',(qid,'card',time.time()))
 @app.get('/api/cards')
 def cards(module:str=''):
  with content() as (c,v):
   items=visible_cards(filtered_cards(c,module));return {'items':items,'release':v}
 @app.get('/api/cards/{id}')
 def card(id:str):
  if cards_locked():fail(409,'请先完成组练或模拟，再查看方法例解')
  with content() as (c,v):
   x=entity(c,'cards',id)
   if not x:fail(404,'卡片不存在')
   mark_cards([x]);return x
 @app.post('/api/sessions')
 def new_session(body:dict):
  mode=body.get('mode','practice')
  if mode not in ('practice','group','mock'):fail(400,'非法模式')
  try:count=max(1,min(int(body.get('count',5)),150))
  except (ValueError,TypeError):fail(422,'count必须为整数')
  allowed=['verified']+(['source_only'] if body.get('allow_source_only') is True else [])
  with content() as (cc,v):
   ids=body.get('question_ids');paper_ids=None;selection_repeat=False;automatic=ids is None
   if body.get('planned_release') and body['planned_release']!=v:fail(409,'内容版本已切换，请刷新今日任务')
   if ids is not None and (not isinstance(ids,list) or not all(isinstance(i,str) for i in ids)):fail(422,'题目ID列表无效')
   if body.get('paper_id'):
    if not entity(cc,'papers',body['paper_id']):fail(404,'来源卷不存在')
    paper_ids={json.loads(r[0])['question_id'] for r in cc.execute('SELECT data FROM occurrences WHERE json_extract(data,"$.paper_id")=?',(body['paper_id'],))}
    if ids is not None and not set(ids)<=paper_ids:fail(422,'指定题目不属于来源卷')
   if automatic:
    with db() as d:seen={r[0] for r in d.execute('SELECT DISTINCT question_id FROM attempts')}|{r[0] for r in d.execute('SELECT question_id FROM exposures')}
    for alias in all_entities(cc,'id_aliases'):
     old=alias.get('old_id') or alias.get('from_id') or alias.get('source_id');new=alias.get('new_id') or alias.get('to_id') or alias.get('target_id')
     if old in seen or new in seen:seen.update([old,new])
    seen_q=[x for qid in seen if (x:=entity(cc,'questions',qid))]
    seen_m={x.get('material_id') for x in seen_q if x.get('material_id')};seen_f={x.get('variant_family_id') for x in seen_q if x.get('variant_family_id')}
    candidates=[json.loads(r[0]) for r in cc.execute('SELECT data FROM questions WHERE practice_ready=1 AND status IN ('+','.join('?'*len(allowed))+') AND (?="" OR module=?)',(*allowed,body.get('module',''),body.get('module','')))]
    candidates=[q for q in candidates if not q.get('holdout_reserved') and q.get('material_id') not in holdout_materials(cc,v) and (paper_ids is None or q['question_id'] in paper_ids)]
    def was_seen(q):return bool(q.get('prior_public_example')) or q['question_id'] in seen or bool(q.get('material_id') and q['material_id'] in seen_m) or bool(q.get('variant_family_id') and q['variant_family_id'] in seen_f)
    if mode in ('group','mock'):
     groups={}
     for q in candidates:groups.setdefault(q.get('material_id') or q['question_id'],[]).append(q)
     complete=[];full_groups={}
     mids={q.get('material_id') for q in candidates if q.get('material_id')}
     if mids:
      for row in cc.execute('SELECT data FROM questions WHERE material_id IN ('+','.join('?' for _ in mids)+')',list(mids)):
       item=json.loads(row[0]);full_groups.setdefault(item['material_id'],[]).append(item)
     for key,qs in groups.items():
      mid=qs[0].get('material_id');full=full_groups.get(mid,[]) if mid else qs
      if all(x.get('practice_ready') and x.get('answer_status') in allowed and not x.get('holdout_reserved') and (paper_ids is None or x['question_id'] in paper_ids) for x in full):complete.append(sorted(full,key=lambda x:x['question_id']))
     complete.sort(key=lambda qs:(any(was_seen(q) for q in qs),qs[0]['question_id']))
     chosen=[]
     for qs in complete:
      if chosen and (mode=='group' or len(chosen)>=count):break
      if len(chosen)+len(qs)>150:break
      chosen.extend(qs)
    else:chosen=sorted(candidates,key=lambda q:(was_seen(q),q['question_id']))[:count]
    ids=[q['question_id'] for q in chosen];selection_repeat=any(was_seen(q) for q in chosen)
   if not isinstance(ids,list) or not ids or len(ids)>150 or not all(isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):fail(422,'无可练题或题目列表无效；可显式启用来源答案题')
   for qid in ids:
    q=entity(cc,'questions',qid)
    if not q or q.get('holdout_reserved') or q.get('material_id') in holdout_materials(cc,v) or not q.get('practice_ready') or q.get('answer_status') not in allowed:fail(422,'题面未核准或答案等级不允许：'+str(qid))
   # Group selection expands to all ready questions sharing a verified material.
   if mode=='group':
    mids={entity(cc,'questions',qid).get('material_id') for qid in ids}-{None}
    for mid in mids:
     for row in cc.execute('SELECT data FROM questions WHERE material_id=?',(mid,)):
      q=json.loads(row[0])
      if q.get('holdout_reserved') or not q.get('practice_ready') or q.get('answer_status') not in allowed:fail(422,'材料组存在不可练小题，不能声明完整组练')
      if q['question_id'] not in ids:ids.append(q['question_id'])
   paper=entity(cc,'papers',body['paper_id']) if body.get('paper_id') else None
   label='重组模拟' if mode=='mock' else '练习' # No original-order reconstruction implemented; never claim original mock.
  with db() as c:
   sid=uid();now=time.time();c.execute('INSERT INTO sessions(id,release,mode,status,created,question_ids) VALUES(?,?,?,?,?,?)',(sid,v,mode,'active',now,json.dumps(ids)))
   c.execute('INSERT INTO events(session_id,type,at) VALUES(?,?,?)',(sid,'selection_repeat' if selection_repeat else 'selection_candidate_unseen' if automatic else 'selection_explicit',now))
   for qid in ids:c.execute('INSERT INTO attempts(id,session_id,question_id,status,selected,created) VALUES(?,?,?,?,?,?)',(uid(),sid,qid,'draft','[]',now))
   s=session_data(c,sid);s['label']=label;return s
 @app.get('/api/sessions')
 def sessions():
  with db() as c:return {'items':[session_data(c,r[0]) for r in c.execute('SELECT id FROM sessions ORDER BY created DESC LIMIT 100').fetchall()]}
 @app.get('/api/sessions/{id}')
 def get_session(id:str):
  with db() as c:return session_data(c,id)
 @app.get('/api/sessions/{id}/items')
 def items(id:str):
  with db() as c:s=session_data(c,id)
  with content(s['release']) as (cc,v):return {'session':s,'items':[safe_question(entity(cc,'questions',qid),cc,v) for qid in s['question_ids']],'attempts':s['attempts']}
 @app.post('/api/sessions/{id}/events')
 def events(id:str,body:dict):
  typ=body.get('type')
  try:duration=max(0,min(float(body.get('duration_seconds') or 0),86400))
  except (ValueError,TypeError):fail(422,'duration_seconds必须为数字')
  if typ not in ('pause','resume','heartbeat','interrupt','reading','question_time'):fail(400,'非法计时事件')
  with db() as c:
   s=session_row(c,id);now=time.time()
   if s['status']!='active':fail(409,'已结束会话不能修改')
   if typ=='pause' and s['mode']=='mock':fail(409,'模拟持续计时，不允许暂停')
   if typ=='pause' and not s['paused']:c.execute('UPDATE sessions SET paused=? WHERE id=?',(now,id))
   if typ=='resume' and s['paused']:c.execute('UPDATE sessions SET pause_seconds=pause_seconds+?,paused=NULL WHERE id=?',(now-s['paused'],id))
   if typ=='interrupt':c.execute('UPDATE sessions SET interrupted=1 WHERE id=?',(id,))
   c.execute('INSERT INTO events(session_id,type,at,question_id,duration) VALUES(?,?,?,?,?)',(id,typ,now,body.get('question_id'),duration))
   return session_data(c,id)
 @app.post('/api/attempts')
 def attempts(body:dict):
  with db() as c:
   s=session_row(c,body.get('session_id'));qid=body.get('question_id');aid=body.get('attempt_id')
   if qid not in json.loads(s['question_ids']):fail(400,'题不属于会话')
   if not aid:
    r=c.execute('SELECT id FROM attempts WHERE session_id=? AND question_id=? AND active=1',(s['id'],qid)).fetchone();aid=r[0]
   a=attempt_row(c,aid)
   if a['session_id']!=s['id'] or a['question_id']!=qid:fail(400,'作答归属不符')
   action=body.get('action','save')
   if s['status']=='abandoned' and action!='redo':fail(409,'已放弃的会话不可修改')
   if action=='redo':
    if s['mode']!='practice':fail(409,'组练或模拟请创建新会话重做')
    new_sid=uid();now=time.time();c.execute('INSERT INTO sessions(id,release,mode,status,created,question_ids) VALUES(?,?,?,?,?,?)',(new_sid,s['release'],'practice','active',now,json.dumps([qid])));aid=uid();c.execute('INSERT INTO attempts(id,session_id,question_id,status,selected,created) VALUES(?,?,?,?,?,?)',(aid,new_sid,qid,'draft','[]',now));return public_attempt(c,attempt_row(c,aid))
   if action not in ('save','submit'):fail(400,'非法动作')
   if a['status']=='submitted':return public_attempt(c,a)
   selected=body.get('selected_option_ids',[])
   with content(s['release']) as (cc,v):valid={o['option_id'] for o in entity(cc,'questions',qid).get('options',[])}
   if not isinstance(selected,list) or not all(isinstance(i,str) for i in selected) or len(set(selected))!=len(selected) or not set(selected)<=valid:fail(422,'非法选项')
   c.execute('UPDATE attempts SET selected=?,hint=MAX(hint,?),guessed=MAX(guessed,?) WHERE id=?',(json.dumps(selected),int(bool(body.get('hint_used'))),int(bool(body.get('guessed'))),aid))
   if action=='submit':
    submit_one(c,attempt_row(c,aid),s)
    if s['mode']=='practice' and not c.execute("SELECT 1 FROM attempts WHERE session_id=? AND active=1 AND status='draft'",(s['id'],)).fetchone():
     now=time.time();c.execute("UPDATE sessions SET status='submitted',submitted=?,pause_seconds=pause_seconds+?,paused=NULL WHERE id=?",(now,now-s['paused'] if s['paused'] else 0,s['id']))
     c.execute('INSERT INTO events(session_id,type,at) VALUES(?,?,?)',(s['id'],'submit',now))
   return public_attempt(c,attempt_row(c,aid))
 @app.post('/api/sessions/{id}/abandon')
 def abandon_session(id:str):
  with db() as c:
   s=session_row(c,id)
   if s['status']=='active':
    if not s['release'].startswith('assessment--'):
     for a in c.execute("SELECT * FROM attempts WHERE session_id=? AND status='submitted'",(id,)).fetchall():submit_one(c,dict(a),s,finalize=True)
    now=time.time();c.execute("UPDATE sessions SET status='abandoned',submitted=?,interrupted=1,pause_seconds=pause_seconds+?,paused=NULL WHERE id=?",(now,now-s['paused'] if s['paused'] else 0,id));c.execute('INSERT INTO events(session_id,type,at) VALUES(?,?,?)',(id,'abandon',now))
   return session_data(c,id)
 @app.post('/api/sessions/{id}/submit')
 def submit_session(id:str):
  with db() as c:
   s=session_row(c,id)
   if s['status']=='abandoned':fail(409,'已放弃的会话不可再提交，请新建会话')
   if s['status']!='submitted':
    for a in c.execute('SELECT * FROM attempts WHERE session_id=? AND active=1',(id,)).fetchall():submit_one(c,dict(a),s,finalize=True)
    now=time.time();c.execute("UPDATE sessions SET status='submitted',submitted=?,pause_seconds=pause_seconds+?,paused=NULL WHERE id=?",(now,now-s['paused'] if s['paused'] else 0,id))
    c.execute('INSERT INTO events(session_id,type,at) VALUES(?,?,?)',(id,'submit',now))
   return session_data(c,id)
 @app.get('/api/attempts/{id}/review')
 def review(id:str):
  with db() as c:
   a=attempt_row(c,id)
   if cards_locked():fail(409,'存在尚未提交的组练或模拟，暂不开放解析避免泄漏')
   if not can_review(c,a):fail(409,'请先提交本题；组练与模拟需整组/整卷提交')
   c.execute('UPDATE attempts SET exposed=1 WHERE id=?',(id,));s=session_row(c,a['session_id']);g=json.loads(a['grade']);seen={r[0] for r in c.execute('SELECT DISTINCT question_id FROM attempts')}|{r[0] for r in c.execute('SELECT question_id FROM exposures')}
   c.execute('INSERT OR IGNORE INTO exposures VALUES(?,?,?)',(a['question_id'],'review',time.time()))
  with content(s['release']) as (cc,v):
   q=entity(cc,'questions',a['question_id']);seen_families={x.get('variant_family_id') for qid in seen if (x:=entity(cc,'questions',qid)) and x.get('variant_family_id')};seen_materials={x.get('material_id') for qid in seen if (x:=entity(cc,'questions',qid)) and x.get('material_id')}
   for alias in all_entities(cc,'id_aliases'):
    old=alias.get('old_id') or alias.get('from_id') or alias.get('source_id');new=alias.get('new_id') or alias.get('to_id') or alias.get('target_id')
    if old in seen or new in seen:seen.update([old,new])
   concepts=set(q.get('concept_ids',[]));cards=[x for x in all_entities(cc,'cards') if concepts.intersection(x.get('concept_ids',[])) or x.get('id') in q.get('method_ids',[]) or str(q.get('source_qid')) in x.get('evidence_qids',[])];mark_cards(cards)
   with db() as d:seen|={r[0] for r in d.execute('SELECT question_id FROM exposures')}
   seen_materials|={x.get('material_id') for qid in seen if (x:=entity(cc,'questions',qid)) and x.get('material_id')}
   seen_families|={x.get('variant_family_id') for qid in seen if (x:=entity(cc,'questions',qid)) and x.get('variant_family_id')}
   transfer=[]
   for row in cc.execute('SELECT data FROM questions WHERE practice_ready=1 AND status="verified"'):
    x=json.loads(row[0])
    if not x.get('prior_public_example') and not x.get('holdout_reserved') and x.get('material_id') not in holdout_materials(cc,v) and x['question_id'] not in seen and (not x.get('material_id') or x.get('material_id') not in seen_materials) and (not x.get('variant_family_id') or x.get('variant_family_id') not in seen_families) and concepts.intersection(x.get('concept_ids',[])):transfer.append({'question_id':x['question_id'],'reason':'未作答的同考点候选，非掌握证明'})
    if len(transfer)>=5:break
   verification=[json.loads(r[0]) for r in cc.execute('SELECT data FROM assessments WHERE json_extract(data,"$.question_id")=?',(a['question_id'],))] if cc.execute("SELECT 1 FROM sqlite_master WHERE name='assessments'").fetchone() else []
   return {'verification_records':verification,'explanation_kind':'ai_independent' if q.get('explanation_origin')=='native_independent_review' else 'source_reference','explanation_notice':'以下为AI独立复算/推导，不等同人工审批；证据见答案evidence_refs及核验记录。' if q.get('explanation_origin')=='native_independent_review' else '以下为来源解析，未宣称全文独立核验。','exposure_notice':'已查看解析，原题与同材料题不再算未曝光迁移','attempt':{**a,'selected_option_ids':json.loads(a['selected']),'grade':g},'question':safe_question(q,cc,v),'answer':g.get('answer'),'explanation':plain(q.get('explanation')),'source_refs':q.get('source_refs',[]),'cards':cards,'transfer':transfer}
 @app.post('/api/attempts/{id}/review')
 def save_review(id:str,body:dict):
  interval=body.get('interval_days',1);error=body.get('error_type','')
  if interval not in (1,3,7) or error not in ERROR_TYPES+['']:fail(422,'错因或复习间隔无效')
  with db() as c:
   a=attempt_row(c,id)
   if not can_review(c,a):fail(409,'尚未开放复盘')
   due=time.time()+interval*86400;c.execute('INSERT OR REPLACE INTO reviews VALUES(?,?,?,?,?)',(id,error,str(body.get('notes',''))[:5000],due,interval))
   c.execute('UPDATE attempts SET hint=MAX(hint,?),guessed=MAX(guessed,?) WHERE id=?',(int(bool(body.get('hint_used'))),int(bool(body.get('guessed'))),id))
   return {'attempt_id':id,'due_at':due,'interval_days':interval,'error_type':error}
 @app.get('/api/reviews/due')
 def due():
  with db() as c:return {'items':[dict(r) for r in c.execute('SELECT r.*,a.question_id,a.session_id FROM reviews r JOIN attempts a ON a.id=r.attempt_id WHERE due_at<=? ORDER BY due_at',(time.time(),))],'rule':'可调1/3/7天，不是最优间隔的科学结论'}
 def learning_index(c,v):
  from .coverage import read_index
  if v not in learning_cache:learning_cache[v]=read_index(c)
  return learning_cache[v]
 @app.get('/api/coverage')
 def coverage(year:str='',paper_type:str='',module:str=''):
  from .coverage import build_coverage
  with content() as (c,v):return {'release':v,**build_coverage(learning_index(c,v),year,paper_type,module)}
 @app.get('/api/coverage/evidence/{qid}')
 def coverage_evidence(qid:str):
  if cards_locked():fail(409,'请先完成组练或模拟，再查看考点与来源证据')
  with content() as (c,v):
   q=entity(c,'questions',qid)
   if not q or q.get('holdout_reserved') or q.get('material_id') in holdout_materials(c,v) or not q.get('practice_ready') or q.get('answer_status')!='verified':fail(404,'仅提供已核验可练代表题的证据')
   idx=learning_index(c,v)
   refs=[{k:o.get(k) for k in ('source_commit','source_path','source_line','source_local_number','paper_id')} for o in idx['occurrences'] if o['question_id']==qid]
   reserved_paths={o.get('source_path') for o in idx['occurrences'] if idx['questions'].get(o['question_id'],{}).get('holdout_reserved')}
   for ref in refs:ref['raw_link_allowed']=bool(ref.get('source_path') and ref['source_path'] not in reserved_paths)
   visible_paths={r['source_path'] for r in refs if r['raw_link_allowed']}
   # A source file can reveal more than the representative; conservatively mark all its identities.
   expose([o['question_id'] for o in idx['occurrences'] if o.get('source_path') in visible_paths],'coverage_source_file_available')
   expose([qid],'coverage_representative_seen')
   # Viewing the material also exposes sibling/candidate questions.
   if q.get('material_id'):
    expose([i for i,x in idx['questions'].items() if x.get('material_id')==q['material_id'] or q['material_id'] in x.get('candidate_material_ids',[])],'coverage_material_seen')
   return {'release':v,'question':safe_question(q,c,v),'sources':refs,'notice':'原始证据定位到只读源文件行；代表题不展示答案/解析。可打开的原始文件可能含解析，其全部身份保守记曝光；含留出题的文件不开放原始链接。'}
 @app.get('/api/today')
 def today(budget_minutes:int=40):
  if budget_minutes not in (20,40):fail(422,'预算请选择20或40分钟')
  from .coverage import build_coverage
  from .planning import plan
  with content() as (cc,v):
   idx=learning_index(cc,v)
   if v not in coverage_cache:coverage_cache[v]=build_coverage(idx)
  with db() as c:
   attempts=[dict(r) for r in c.execute("SELECT a.*,s.interrupted FROM attempts a JOIN sessions s ON s.id=a.session_id WHERE s.release NOT LIKE 'assessment--%' ORDER BY a.created")]
   exposures={r[0]:r[1] for r in c.execute('SELECT question_id,at FROM exposures')}
   events=[dict(r) for r in c.execute('SELECT * FROM events')]
   settings={r[0]:json.loads(r[1]) for r in c.execute('SELECT id,data FROM task_settings')}
  return {'release':v,**plan(idx,coverage_cache[v],attempts,exposures,events,due()['items'],settings,time.time(),budget_minutes)}
 @app.post('/api/today/{task_id:path}')
 def adjust_today(task_id:str,body:dict):
  try:count=max(1,min(int(body.get('count',5)),50))
  except (ValueError,TypeError):fail(422,'题量须整数')
  value={'count':count,'skip_until':time.time()+86400 if body.get('skip') else 0}
  with db() as c:c.execute('INSERT OR REPLACE INTO task_settings VALUES(?,?)',(task_id,json.dumps(value)))
  return value
 @app.get('/api/stats')
 def stats():
  with db() as c:
   rows=[dict(r) for r in c.execute("SELECT a.*,s.interrupted FROM attempts a JOIN sessions s ON a.session_id=s.id WHERE a.status='submitted' AND s.release NOT LIKE 'assessment--%' ORDER BY a.created")]
  with db() as c:
   exposure_counts={r[0]:r[1] for r in c.execute('SELECT reason,COUNT(*) FROM exposures GROUP BY reason')};exposures={r[0]:r[1] for r in c.execute('SELECT question_id,at FROM exposures')};session_stats=[session_data(c,r[0]) for r in c.execute("SELECT id FROM sessions WHERE release NOT LIKE 'assessment--%'").fetchall()]
   assessment_stats=[]
   for row in c.execute("SELECT id FROM sessions WHERE release LIKE 'assessment--%' ORDER BY created").fetchall():
    ss=session_data(c,row[0]);grades=[json.loads(r[0]) for r in c.execute("SELECT grade FROM attempts WHERE session_id=? AND status='submitted'",(ss['id'],))];scorable=[g for g in grades if g.get('correct') is not None];assessment_stats.append({'session_id':ss['id'],'status':ss['status'],'assessment':ss['assessment'],'scored_count':len(scorable),'correct_count':sum(g['correct'] is True for g in scorable),'ungraded_count':sum(g.get('correct') is None and not g.get('pending') for g in grades),'active_seconds':ss['active_seconds'],'notice':'评测独立统计；不是标准化考分预测'})
  groups={x:{'count':0,'correct':0} for x in ['verified','source_only','ungraded']};first=[];seen=set();mastery={};evidence={};clean_first=[];seen_families=set();seen_materials=set();question_cache={}
  for a in rows:
   evidence[a['question_id']]=evidence.get(a['question_id'],0)+1
   g=json.loads(a['grade']);key=g['answer_status'] if g['answer_status'] in ('verified','source_only') and g['correct'] is not None else 'ungraded';groups[key]['count']+=1;groups[key]['correct']+=int(g['correct'] is True)
   cache_key=(g['release'],a['question_id'])
   if cache_key not in question_cache:
    with content(g['release']) as (cc,v):question_cache[cache_key]=entity(cc,'questions',a['question_id']) or {}
   q=question_cache[cache_key];family=q.get('variant_family_id');material=q.get('material_id')
   if not q.get('prior_public_example') and a['question_id'] not in seen and not a['hint'] and not a['guessed'] and exposures.get(a['question_id'],float('inf'))>=a['created'] and (not family or family not in seen_families) and (not material or material not in seen_materials):clean_first.append(a['question_id'])
   if family:seen_families.add(family)
   if material:seen_materials.add(material)
   if a['question_id'] not in seen:first.append({'question_id':a['question_id'],'correct':g['correct'],'answer_status':g['answer_status'],'interrupted':bool(a['interrupted']),'hint_used':bool(a['hint']),'guessed':bool(a['guessed']),'label':'首次作答（非保证未曝光）'});seen.add(a['question_id'])
   mastery[a['question_id']]='需纠错' if g['correct'] is False else '待迁移' if g['correct'] and (a['hint'] or a['guessed'] or key!='verified') else '初步掌握' if g['correct'] else '待核验'
  return {'total_submitted':len(rows),'assessment_sessions':assessment_stats,'exposure_counts':exposure_counts,**groups,'first_attempt':first,'mastery':mastery,'evidence_counts':evidence,'first_unexposed_no_hint_candidate_ids':clean_first,'hint_count':sum(bool(a['hint']) for a in rows),'guessed_count':sum(bool(a['guessed']) for a in rows),'redo_count':max(0,len(rows)-len(seen)),'session_timing':[{'session_id':s['id'],'mode':s['mode'],'status':s['status'],'elapsed_seconds':s['elapsed_seconds'],'active_seconds':s['active_seconds'],'interrupted':bool(s['interrupted']),'reading_seconds':sum(e['duration'] or 0 for e in s['events'] if e['type']=='reading'),'question_seconds':sum(e['duration'] or 0 for e in s['events'] if e['type']=='question_time')} for s in session_stats],'normal_completed_session_median_seconds':statistics.median([s['active_seconds'] for s in session_stats if s['status']=='submitted' and not s['interrupted']]) if any(s['status']=='submitted' and not s['interrupted'] for s in session_stats) else None,'speed_excluded_interrupted':sum(bool(a['interrupted']) for a in rows),'notice':'熟题重复不算陌生迁移；标签不是校准掌握概率。卡片仅追踪显式example_qids/boundary_qids/question_ids，文字中隐含题号不作全未见保证。'}
 @app.get('/api/assets/{version}/{path:path}')
 def asset(version:str,path:str):
  p=release_path(version);target=(p/path).resolve()
  if not target.is_relative_to(p/'assets') or '..' in Path(path).parts:fail(403,'非法资产路径')
  with content(version) as (cc,v):
   if version not in asset_registry:asset_registry[version]={x.get('path') for x in all_entities(cc,'assets') if x.get('role')!='analysis_only' and x.get('roles')!=['analysis_only']}
   if path not in asset_registry[version]:fail(404,'未登记资产')
  if target.suffix.lower() not in ('.png','.jpg','.jpeg','.gif','.webp'):fail(403,'不允许可执行图片格式')
  if not target.is_file():fail(404,'资产缺失')
  return FileResponse(target)
 @app.get('/api/backups')
 def backups():
  return {'items':[{'name':p.name,'filename':p.name,'modified_at':p.stat().st_mtime,'created_at':p.stat().st_mtime,'size_bytes':p.stat().st_size,'format':'sqlite'} for p in sorted(exports.glob('*.sqlite'),key=lambda p:p.stat().st_mtime,reverse=True) if p.is_file() and p.resolve().parent==exports]}
 @app.get('/api/exports')
 def export(format:str='json'):
  if format not in ('json','sqlite'):fail(400,'格式必须json或sqlite')
  path=exports/f'personal-{uid()}.{format}'
  with db() as c:
   if format=='sqlite':
    dest=sqlite3.connect(path);c.backup(dest);check=dest.execute('PRAGMA integrity_check').fetchone()[0];dest.close()
    if check!='ok':fail(500,'备份核验失败')
   else:path.write_text(json.dumps({'schema_version':1,'exported_at':time.time(),**{t:[dict(r) for r in c.execute(f'SELECT * FROM {t}')] for t in ['sessions','attempts','events','reviews','exposures','task_settings']}},ensure_ascii=False,indent=2))
  return FileResponse(path,filename=path.name)
 @app.post('/api/restore')
 def restore(body:dict):
  p=(exports/str(body.get('path',''))).resolve()
  if p.parent!=exports or not p.is_file():fail(400,'只允许恢复exports内的备份文件名')
  src=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
  try:
   if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or src.execute("SELECT value FROM meta WHERE key='schema'").fetchone()!=('1',):fail(422,'备份格式或完整性不通过')
   with db() as current:
    for t in ['sessions','attempts','events','reviews','exposures','task_settings']:
     if src.execute(f'PRAGMA table_info({t})').fetchall()!=[tuple(r) for r in current.execute(f'PRAGMA table_info({t})')]:fail(422,'备份表结构不匹配：'+t)
   if src.execute('SELECT COUNT(*) FROM attempts a LEFT JOIN sessions s ON s.id=a.session_id WHERE s.id IS NULL').fetchone()[0]:fail(422,'备份作答引用不存在的会话')
   if src.execute('SELECT COUNT(*) FROM reviews r LEFT JOIN attempts a ON a.id=r.attempt_id WHERE a.id IS NULL').fetchone()[0]:fail(422,'备份复盘引用不存在的作答')
   for v, in src.execute('SELECT DISTINCT release FROM sessions'):release_path(v)
   check_assessment_locks(src)
   if src.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0]:fail(422,'备份不允许触发器/视图')
   for sid,qid,selected,status,grade_text in src.execute('SELECT session_id,question_id,selected,status,grade FROM attempts'):
    ss=src.execute('SELECT question_ids,release FROM sessions WHERE id=?',(sid,)).fetchone()
    if qid not in json.loads(ss[0]) or status not in ('draft','submitted'):fail(422,'备份作答引用/状态不匹配')
    with content(ss[1]) as (cc,v):
     q=entity(cc,'questions',qid)
     if not q or not set(json.loads(selected))<={o['option_id'] for o in q['options']}:fail(422,'备份题目/选项不匹配')
    if status=='submitted' and not isinstance(json.loads(grade_text),dict):fail(422,'备份评分依据缺失')
   with db() as dest:
    snap=sqlite3.connect(exports/f'pre-restore-{uid()}.sqlite');dest.backup(snap);snap.close();src.backup(dest)
  except (sqlite3.Error,ValueError,TypeError,KeyError) as e:fail(422,'备份校验失败：'+str(e))
  finally:src.close()
  return {'restored':True}
 def import_attempts_jsonl(p):
  if p.parent!=incoming or not p.is_file() or p.suffix!='.jsonl':fail(400,'仅接受imports目录中的attempts.jsonl')
  try:
   rows=[json.loads(line) for line in p.read_text().splitlines() if line.strip()]
   if len(rows)>10000:fail(422,'单次最多10000条')
   prepared=[];ids=set()
   for r in rows:
    required={'attempt_id','question_id','revision','release_id','selected_options','elapsed_ms','mode','hint_used'}
    if not required<=set(r):fail(422,'一期作答缺必需字段：'+','.join(sorted(required-set(r))))
    aid=r['attempt_id'];qid=r['question_id'];version=r['release_id']
    if not isinstance(version,str) or version.startswith('assessment--'):fail(422,'一期JSONL不能伪造独立评测；评测仅接受完整原生备份')
    if not isinstance(aid,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',aid) or aid in ids:fail(422,'作答ID无效/重复')
    ids.add(aid)
    if r['mode'] not in ('practice','group','mock') or not isinstance(r['selected_options'],list):fail(422,'模式/选项格式无效')
    duration=float(r['elapsed_ms'])/1000
    if not 0<=duration<=86400:fail(422,'耗时超出允许范围')
    with content(version) as (cc,v):
     q=entity(cc,'questions',qid)
     if not q or q.get('revision')!=r['revision']:fail(422,'题目或revision不匹配，不能猜测历史版本')
     option_map={o.get('label'):o['option_id'] for o in q['options']};valid={o['option_id'] for o in q['options']};selected=[x if x in valid else option_map.get(x) for x in r['selected_options']]
     if any(x is None for x in selected) or len(set(selected))!=len(selected):fail(422,'选项无法映射')
    end=float(r.get('submitted_at',time.time()));start=end-duration
    g=json.dumps({'correct':None,'answer_status':'imported_unverified','answer':None,'question_revision':r['revision'],'release':version,'imported_reported_correct':r.get('correct'),'notice':'一期导入历史未附独立评分快照，不计入准确率'},ensure_ascii=False)
    prepared.append((r,selected,g,start,end))
   with db() as c:
    for r,selected,g,start,end in prepared:
     if c.execute('SELECT 1 FROM attempts WHERE id=?',(r['attempt_id'],)).fetchone():fail(409,'作答ID已存在，拒绝覆盖')
    snap=sqlite3.connect(exports/f'pre-jsonl-{uid()}.sqlite');c.backup(snap);snap.close()
    for r,selected,g,start,end in prepared:
     sid='import-'+r['attempt_id'];c.execute('INSERT INTO sessions(id,release,mode,status,created,submitted,interrupted,question_ids) VALUES(?,?,?,?,?,?,?,?)',(sid,r['release_id'],r['mode'],'submitted',start,end,1,json.dumps([r['question_id']])))
     c.execute('INSERT INTO attempts(id,session_id,question_id,status,selected,created,submitted,grade,hint,guessed,exposed) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r['attempt_id'],sid,r['question_id'],'submitted',json.dumps(selected),start,end,g,int(bool(r['hint_used'])),int(bool(r.get('guessed'))),int(bool(r.get('seen_before')))))
     if r.get('seen_before'):c.execute('INSERT OR IGNORE INTO exposures VALUES(?,?,?)',(r['question_id'],'imported_seen',start-1))
   return {'imported':len(prepared),'notice':'保留历史选项与耗时；缺评分快照的记录归未核评分，导入耗时不混入正常速度'}
  except (ValueError,TypeError,KeyError,sqlite3.Error) as e:fail(422,'一期作答验证失败：'+str(e))
 def import_userdata(p):
  if p.parent!=incoming or not p.is_file() or p.suffix!='.json':fail(400,'个人数据只能导入imports下JSON导出文件')
  try:
   data=json.loads(p.read_text())
   if data.get('schema_version')!=1:fail(422,'个人数据schema版本不支持')
   tables=['sessions','attempts','events','reviews','exposures','task_settings']
   with db() as c:
    # Validate in isolated in-memory DB first, then merge all-or-nothing.
    mem=sqlite3.connect(':memory:');c.backup(mem)
    for t in tables:
     cols=[r[1] for r in c.execute(f'PRAGMA table_info({t})')]
     for row in data.get(t,[]):
      if set(row)!=set(cols):fail(422,'导入字段不符：'+t)
      if t=='events':continue # Event IDs are local sequence numbers, import later.
      key=cols[0];old=mem.execute(f'SELECT * FROM {t} WHERE {key}=?',(row[key],)).fetchone()
      vals=tuple(row[k] for k in cols)
      if old and old!=vals:fail(409,'同ID记录冲突：'+t)
      if not old:mem.execute(f'INSERT INTO {t} VALUES('+','.join('?' for _ in cols)+')',vals)
    if mem.execute('SELECT COUNT(*) FROM attempts a LEFT JOIN sessions s ON s.id=a.session_id WHERE s.id IS NULL').fetchone()[0]:fail(422,'作答会话引用无效')
    if mem.execute('SELECT COUNT(*) FROM reviews r LEFT JOIN attempts a ON a.id=r.attempt_id WHERE a.id IS NULL').fetchone()[0]:fail(422,'复盘作答引用无效')
    for version, in mem.execute('SELECT DISTINCT release FROM sessions'):release_path(version)
    check_assessment_locks(mem)
    for sid,qid,selected,status,grade_text in mem.execute('SELECT session_id,question_id,selected,status,grade FROM attempts'):
     ss=mem.execute('SELECT question_ids,release FROM sessions WHERE id=?',(sid,)).fetchone()
     if qid not in json.loads(ss[0]) or status not in ('draft','submitted'):fail(422,'作答引用或状态无效')
     with content(ss[1]) as (cc,v):
      q=entity(cc,'questions',qid)
      if not q or not set(json.loads(selected))<={o['option_id'] for o in q['options']}:fail(422,'作答题目或选项无效')
     if status=='submitted' and not isinstance(json.loads(grade_text),dict):fail(422,'提交评分依据缺失')
    for row in data.get('events',[]):
     if not mem.execute('SELECT 1 FROM sessions WHERE id=?',(row['session_id'],)).fetchone():fail(422,'计时会话引用无效')
     vals=[row[k] for k in ['session_id','type','at','question_id','duration']]
     if not mem.execute('SELECT 1 FROM events WHERE session_id=? AND type=? AND at=? AND question_id IS ? AND duration IS ?',vals).fetchone():mem.execute('INSERT INTO events(session_id,type,at,question_id,duration) VALUES(?,?,?,?,?)',vals)
    mem.commit();snap=sqlite3.connect(exports/f'pre-import-{uid()}.sqlite');c.backup(snap);snap.close();mem.backup(c);mem.close()
   return {'imported':True,'schema_version':1,'notice':'导入个人历史，不重新计算或覆盖历史评分'}
  except (ValueError,KeyError,TypeError,sqlite3.Error) as e:fail(422,'个人数据验证失败：'+str(e))
 @app.get('/api/releases')
 def releases_list():
  summaries=[]
  for path in sorted(root.glob('*/manifest.json')):
   if path.parent.name.startswith('.'):continue
   key=(str(path),path.stat().st_mtime_ns,path.stat().st_size)
   if key not in release_summary_cache:
    m=json.loads(path.read_text());coverage=m.get('coverage',{})
    release_summary_cache[key]={'version':m.get('version',path.parent.name),'schema_version':m.get('schema_version'),'taxonomy_version':m.get('taxonomy_version'),'source_commit':m.get('source_commit'),'counts':m.get('counts',{}),'coverage':{k:coverage.get(k) for k in ['questions','occurrences','practice_ready','native_assistant_reviewed_unique','official_cards'] if k in coverage}}
   summaries.append(release_summary_cache[key])
  return {'items':summaries,'current':release_path().name,'notice':'仅版本摘要；激活仍严格验证完整manifest和文件hash'}
 @app.post('/api/releases/{version}/activate')
 def activate(version:str):
  from xingce_project.pipeline.release import activate_release
  try:return activate_release(root,version)
  except (ValueError,OSError,KeyError,TypeError,sqlite3.Error) as e:fail(422,str(e))
 @app.post('/api/imports')
 def imports(body:dict):
  from xingce_project.pipeline.release import validate_release,activate_release
  p=(incoming/str(body.get('path',''))).resolve()
  if body.get('kind')=='userdata':return import_userdata(p)
  if body.get('kind')=='attempts_jsonl':return import_attempts_jsonl(p)
  if p.parent!=incoming or not p.is_dir():fail(400,'将release目录放入userdata/imports，path只传目录名')
  try:
   m=validate_release(p);version=m.get('release_version') or m.get('version') or m.get('release') or p.name
   if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',version):fail(422,'非法release版本')
   dest=root/version
   if dest.exists():fail(409,'同版本已存在；禁止覆盖历史内容')
   shutil.copytree(p,dest)
   try:return activate_release(root,version)
   except Exception:shutil.rmtree(dest);raise
  except (ValueError,OSError,sqlite3.Error,KeyError,TypeError) as e:fail(422,str(e))
 dist=PROJECT/'apps/workbench/frontend/dist'
 if dist.is_dir():app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
 return app

app=create_app()
