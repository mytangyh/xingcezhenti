import unittest,tempfile,json,sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from xingce_project.apps.workbench.backend.app import create_app

class BackendTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'releases';self.root.mkdir();self.seed('r1');(self.root/'current.json').write_text(json.dumps({'version':'r1','path':'r1'}));self.user=self.base/'user';self.client=TestClient(create_app(self.root,self.user))
 def tearDown(self):self.tmp.cleanup()
 def seed(self,v):
  p=self.root/v;p.mkdir();c=sqlite3.connect(p/'content.sqlite')
  for t in ['materials','cards','concepts','papers','assets','id_aliases']:c.execute(f'CREATE TABLE {t}(id TEXT PRIMARY KEY,data TEXT)')
  c.execute('CREATE TABLE questions(id TEXT PRIMARY KEY,data TEXT,module TEXT,status TEXT,practice_ready INTEGER,material_id TEXT,stem TEXT)')
  for i in range(1,5):
   q={'question_id':f'q{i}','revision':1,'stem_markdown':f'增长率问题{i}','options':[{'option_id':'A','label':'A','text':'10'},{'option_id':'B','label':'B','text':'20'}],'answer_status':'source_only' if i==3 else 'verified','source_answer':{'option_ids':['A']},'verified_answer':{'option_ids':['A'],'evidence_refs':['fixture-only']} if i!=3 else None,'material_id':'m1' if i<3 else None,'practice_ready':i!=4,'concept_ids':['growth'],'explanation':'SECRET_EXPLANATION','assets':[]}
   c.execute('INSERT INTO questions VALUES(?,?,?,?,?,?,?)',(f'q{i}',json.dumps(q), 'data',q['answer_status'],i!=4,q['material_id'],q['stem_markdown']))
  c.execute('INSERT INTO materials VALUES(?,?)',('m1',json.dumps({'id':'m1','stem_markdown':'原创测试材料','assets':[]})));c.commit();c.close()
 def session(self,mode='practice',ids=None,**kw):
  r=self.client.post('/api/sessions',json={'mode':mode,'question_ids':ids or ['q1'],**kw});self.assertEqual(r.status_code,200,r.text);return r.json()
 def submit(self,s,answer='A'):
  a=s['attempts'][0];return self.client.post('/api/attempts',json={'session_id':s['id'],'question_id':a['question_id'],'attempt_id':a['id'],'selected_option_ids':[answer],'action':'submit'})
 def test_no_leak_and_group_gate(self):
  s=self.session('group');self.assertEqual(len(s['question_ids']),2)
  text=self.client.get(f"/api/sessions/{s['id']}/items").text
  for secret in ['SECRET_EXPLANATION','verified_answer','source_answer','concept_ids']:self.assertNotIn(secret,text)
  self.submit(s);aid=s['attempts'][0]['id'];self.assertEqual(self.client.get(f'/api/attempts/{aid}/review').status_code,409)
  self.client.post(f"/api/sessions/{s['id']}/submit",json={});self.assertEqual(self.client.get(f'/api/attempts/{aid}/review').json()['explanation'],'SECRET_EXPLANATION')
 def test_idempotence_freeze_redo(self):
  s=self.session();a=self.submit(s).json();b=self.submit(s,'B').json();self.assertEqual(a,b)
  r=self.client.post('/api/attempts',json={'session_id':s['id'],'question_id':'q1','attempt_id':a['id'],'action':'redo'}).json();self.assertNotEqual(a['id'],r['id']);self.assertEqual(r['status'],'draft');self.assertEqual(self.client.get('/api/stats').json()['total_submitted'],1)
 def test_source_only(self):
  self.assertEqual(self.client.post('/api/sessions',json={'question_ids':['q3']}).status_code,422)
  s=self.session(ids=['q3'],allow_source_only=True);self.submit(s);stat=self.client.get('/api/stats').json();self.assertEqual(stat['source_only']['count'],1);self.assertEqual(stat['verified']['count'],0)
 def test_unready_denied(self):self.assertEqual(self.client.post('/api/sessions',json={'question_ids':['q4']}).status_code,422)
 def test_pause_mock_restore_pinned(self):
  s=self.session('mock');self.assertEqual(self.client.post(f"/api/sessions/{s['id']}/events",json={'type':'pause'}).status_code,409)
  self.seed('r2');(self.root/'current.json').write_text(json.dumps({'version':'r2'}));self.assertEqual(self.client.get(f"/api/sessions/{s['id']}/items").json()['session']['release'],'r1')
  self.client.post(f"/api/sessions/{s['id']}/events",json={'type':'interrupt'});self.assertTrue(self.client.get(f"/api/sessions/{s['id']}").json()['interrupted'])
 def test_search_short_and_sql(self):
  r=self.client.get('/api/search',params={'q':'增长'});self.assertEqual(len(r.json()['items']),2);self.assertNotIn('SECRET_EXPLANATION',r.text)
  self.assertEqual(self.client.get('/api/search',params={'q':"' OR 1=1--"}).json()['items'],[])
 def test_backup_restore(self):
  s=self.session();self.submit(s);before=self.client.get('/api/stats').json();r=self.client.get('/api/exports?format=sqlite');self.assertEqual(r.status_code,200)
  name=r.headers['content-disposition'].split('filename="')[1].split('"')[0];self.session(ids=['q2']);r=self.client.post('/api/restore',json={'path':name});self.assertEqual(r.status_code,200,r.text);self.assertEqual(before,self.client.get('/api/stats').json());self.assertEqual(len(self.client.get('/api/sessions').json()['items']),1)
 def test_paths_and_cross_origin(self):
  self.assertEqual(self.client.get('/api/assets/r1/assets/%2e%2e/content.sqlite').status_code,403)
  self.assertEqual(self.client.post('/api/restore',json={'path':'../personal.sqlite'}).status_code,400)
  self.assertEqual(self.client.post('/api/sessions',json={},headers={'Origin':'https://evil.invalid'}).status_code,403)
 def test_review_due(self):
  s=self.session();self.submit(s);a=s['attempts'][0]['id'];r=self.client.post(f'/api/attempts/{a}/review',json={'error_type':'计算错误','interval_days':3});self.assertEqual(r.status_code,200);self.assertEqual(self.client.get('/api/reviews/due').json()['items'],[])

 def test_personal_json_import_roundtrip(self):
  s=self.session();self.submit(s);r=self.client.get('/api/exports?format=json');data=r.json()
  # Import into independent private data store sharing the pinned content release.
  other=self.base/'other';cl=TestClient(create_app(self.root,other));(other/'imports'/'history.json').write_text(json.dumps(data))
  result=cl.post('/api/imports',json={'kind':'userdata','path':'history.json'});self.assertEqual(result.status_code,200,result.text);self.assertEqual(cl.get('/api/stats').json()['total_submitted'],1)
  self.assertEqual(cl.post('/api/imports',json={'kind':'userdata','path':'history.json'}).status_code,200)
  data['attempts'][0]['selected']='["B"]';(other/'imports'/'bad.json').write_text(json.dumps(data));self.assertEqual(cl.post('/api/imports',json={'kind':'userdata','path':'bad.json'}).status_code,409);self.assertEqual(cl.get('/api/stats').json()['verified']['correct'],1)
 def test_phase_one_jsonl(self):
  r={'attempt_id':'first-phase-001','question_id':'q1','revision':1,'release_id':'r1','selected_options':['A'],'elapsed_ms':12300,'mode':'practice','hint_used':False,'correct':True}
  (self.user/'imports'/'attempts.jsonl').write_text(json.dumps(r)+'\n')
  result=self.client.post('/api/imports',json={'kind':'attempts_jsonl','path':'attempts.jsonl'});self.assertEqual(result.status_code,200,result.text);stat=self.client.get('/api/stats').json();self.assertEqual(stat['ungraded']['count'],1);self.assertEqual(stat['verified']['count'],0)
  self.assertEqual(self.client.post('/api/imports',json={'kind':'attempts_jsonl','path':'attempts.jsonl'}).status_code,409)
 def test_holdout_cannot_select(self):
  c=sqlite3.connect(self.root/'r1'/'content.sqlite');q=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0]);q['holdout_reserved']=True;c.execute('UPDATE questions SET data=? WHERE id="q1"',(json.dumps(q),));c.commit();c.close()
  self.assertEqual(self.client.post('/api/sessions',json={'question_ids':['q1'],'allow_source_only':True}).status_code,422)
  self.assertNotIn('q1',[x['question_id'] for x in self.client.get('/api/search?q=增长').json()['items']])
 def test_abandon_unlock_and_freeze(self):
  s=self.session('group');r=self.client.post(f"/api/sessions/{s['id']}/abandon",json={});self.assertEqual(r.json()['status'],'abandoned');self.assertEqual(self.submit(s).status_code,409);self.assertEqual(self.client.post(f"/api/sessions/{s['id']}/submit",json={}).status_code,409)
 def test_bad_restore_preserves_state(self):
  s=self.session();bad=self.user/'exports'/'bad.sqlite';c=sqlite3.connect(bad);c.execute('CREATE TABLE fake(x)');c.close();self.assertEqual(self.client.post('/api/restore',json={'path':'bad.sqlite'}).status_code,422);self.assertEqual(self.client.get(f"/api/sessions/{s['id']}").status_code,200)
 def test_today_adjust_skip(self):
  t=self.client.get('/api/today').json();task=t['items'][0]['id'];self.assertEqual(self.client.post('/api/today/'+task,json={'count':2}).status_code,200);self.assertEqual(self.client.get('/api/today').json()['items'][0]['count'],2);self.client.post('/api/today/'+task,json={'skip':True});self.assertEqual(self.client.get('/api/today').json()['items'],[])

 def test_default_groups_unseen_and_skip_incomplete(self):
  c=sqlite3.connect(self.root/'r1'/'content.sqlite');base=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0]);c.execute('DELETE FROM questions WHERE id NOT IN ("q1","q2")')
  for qid,mid,ready,status in [('q5','m2',1,'verified'),('q6','m2',1,'verified'),('q0','m0',1,'verified'),('q00','m0',0,'unresolved')]:
   q={**base,'question_id':qid,'material_id':mid,'practice_ready':bool(ready),'answer_status':status,'variant_family_id':qid};c.execute('INSERT INTO questions VALUES(?,?,?,?,?,?,?)',(qid,json.dumps(q),'data',status,ready,mid,'增长'))
  for mid in ['m0','m2']:c.execute('INSERT INTO materials VALUES(?,?)',(mid,json.dumps({'stem_markdown':'合成测试材料','assets':[]})))
  c.commit();c.close()
  first=self.client.post('/api/sessions',json={'mode':'group'}).json();second=self.client.post('/api/sessions',json={'mode':'group'}).json();third=self.client.post('/api/sessions',json={'mode':'group'}).json()
  self.assertEqual(first['question_ids'],['q1','q2']);self.assertEqual(second['question_ids'],['q5','q6']);self.assertNotIn('q0',first['question_ids']+second['question_ids']);self.assertIn('复习/已见',third['selection_notice'])

 def test_group_backup_no_answer_leak_and_final_grade(self):
  s=self.session('group');self.submit(s);payload=self.client.get('/api/exports?format=json').json();a=payload['attempts'][0];g=json.loads(a['grade']);self.assertTrue(g['pending']);self.assertIsNone(g['answer']);self.assertIsNone(g['correct'])
  self.client.get('/api/exports?format=sqlite');listing=self.client.get('/api/backups').json()['items'];self.assertEqual(len(listing),1);self.assertNotIn('/',listing[0]['filename']);self.assertGreater(listing[0]['size_bytes'],0)
  self.assertEqual(self.client.post('/api/restore',json={'path':listing[0]['filename']}).status_code,200)
  self.client.post('/api/sessions/'+s['id']+'/submit',json={});r=self.client.get('/api/attempts/'+s['attempts'][0]['id']+'/review').json();self.assertTrue(r['attempt']['grade']['correct']);self.assertEqual(r['answer']['option_ids'],['A'])

 def test_today_uses_user_module_priority_not_alphabetical_order(self):
  expected=['资料分析','判断推理','言语理解与表达','数量关系']
  with sqlite3.connect(self.root/'r1'/'content.sqlite') as c:
   original=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0])
   for index,module in enumerate(reversed(expected)):
    q={**original,'question_id':'priority-'+str(index),'normalized_module':module,'material_id':None}
    c.execute('INSERT INTO questions VALUES(?,?,?,?,?,?,?)',(q['question_id'],json.dumps(q),module,'verified',1,None,'合成排序测试'))
  response=self.client.get('/api/today').json()
  self.assertEqual([x['module'] for x in response['items'] if x.get('module')][:4],expected)
  self.assertIn('未建立个人基线',response['notice'])

if __name__=='__main__':unittest.main()
