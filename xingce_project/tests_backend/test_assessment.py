import unittest,tempfile,json,sqlite3,shutil,hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from xingce_project.tests_backend import test_backend
from xingce_project.apps.workbench.backend.app import create_app
class AssessmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'releases';self.root.mkdir();test_backend.BackendTest.seed(self,'r1');(self.root/'current.json').write_text('{"version":"r1"}')
  self.aroot=self.base/'assessments';self.pack=self.aroot/'test-pack';self.pack.mkdir(parents=True);shutil.copyfile(self.root/'r1'/'content.sqlite',self.pack/'content.sqlite');c=sqlite3.connect(self.pack/'content.sqlite')
  for t in ['occurrences','annotations','assessments']:c.execute(f'CREATE TABLE {t}(id TEXT PRIMARY KEY,data TEXT)')
  c.execute('DELETE FROM questions WHERE id NOT IN ("q1","q2")')
  for id in ['q1','q2']:
   q=json.loads(c.execute('SELECT data FROM questions WHERE id=?',(id,)).fetchone()[0]);q.update(prompt_ready=True,practice_ready=False,holdout_reserved=True,assessment_ready=id=='q1',source_answer=None,answer_status='verified' if id=='q1' else 'unresolved')
   if id=='q2':q['verified_answer']=None
   c.execute('UPDATE questions SET data=?,practice_ready=0,status=? WHERE id=?',(json.dumps(q),q['answer_status'],id))
  c.commit();c.close();self.manifest={'schema_version':'assessment-1','pack_id':'test-pack','title':'合成评测测试，不是真题','question_ids':['q1','q2'],'scorable_count':1,'unscored_count':1,'files':{'content.sqlite':hashlib.sha256((self.pack/'content.sqlite').read_bytes()).hexdigest()}};(self.pack/'manifest.json').write_text(json.dumps(self.manifest));self.user=self.base/'user';self.client=TestClient(create_app(self.root,self.user,self.aroot))
 def tearDown(self):self.tmp.cleanup()
 def start(self,**kwargs):
  r=self.client.post('/api/assessments/test-pack/start',json={'confirm':True,**kwargs});self.assertEqual(r.status_code,200,r.text);return r.json()
 def test_explicit_confirmation_and_metadata_no_exposure(self):
  r=self.client.get('/api/assessments').json();self.assertEqual(r['items'][0]['scorable_count'],1)
  self.assertEqual(self.client.post('/api/assessments/test-pack/start',json={}).status_code,422)
  with sqlite3.connect(self.user/'personal.sqlite') as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM exposures').fetchone()[0],0)
 def test_abandon_never_reveals_pending_key(self):
  s=self.start();a=s['attempts'][0];self.client.post('/api/attempts',json={'session_id':s['id'],'question_id':a['question_id'],'attempt_id':a['id'],'selected_option_ids':['A'],'action':'submit'})
  self.assertEqual(self.client.get('/api/attempts/'+a['id']+'/review').status_code,409);self.client.post('/api/sessions/'+s['id']+'/abandon',json={});self.assertEqual(self.client.get('/api/attempts/'+a['id']+'/review').status_code,409)
  grades=[json.loads(a['grade']) for a in self.client.get('/api/exports?format=json').json()['attempts'] if a['grade']];self.assertTrue(all(g.get('pending') and g.get('answer') is None for g in grades))
 def test_whole_submit_unscored_excluded_and_stats_separate(self):
  s=self.start();a=s['attempts'][0];self.client.post('/api/attempts',json={'session_id':s['id'],'question_id':a['question_id'],'attempt_id':a['id'],'selected_option_ids':['A'],'action':'save'});self.client.post('/api/sessions/'+s['id']+'/submit',json={});stats=self.client.get('/api/stats').json();self.assertEqual(stats['total_submitted'],0);r=stats['assessment_sessions'][0];self.assertEqual((r['scored_count'],r['correct_count'],r['ungraded_count']),(1,1,1))
  unknown=self.client.get('/api/attempts/'+s['attempts'][1]['id']+'/review').json();self.assertIsNone(unknown['attempt']['grade']['correct']);self.assertIsNone(unknown['answer'])
 def test_started_exposure_and_retake(self):
  first=self.start();self.client.post('/api/sessions/'+first['id']+'/abandon',json={});second=self.start(seen_before=True,hint_used=True);self.assertEqual(second['assessment']['previous_starts'],1);self.assertEqual(second['assessment']['known_question_count'],2);self.assertIn('重做',second['assessment']['attempt_label']);self.assertTrue(second['attempts'][0]['hint'])
 def test_hash_pin_rejects_mutation(self):
  s=self.start();self.manifest['title']='changed';(self.pack/'manifest.json').write_text(json.dumps(self.manifest));self.assertEqual(self.client.get('/api/sessions/'+s['id']+'/items').status_code,409)
 def test_extra_file_rejected_before_start(self):
  (self.pack/'unexpected.txt').write_text('not manifested');self.assertEqual(self.client.post('/api/assessments/test-pack/start',json={'confirm':True}).status_code,422);self.assertEqual(self.client.get('/api/sessions').json()['items'],[])
if __name__=='__main__':unittest.main()
