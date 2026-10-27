"""Independent adversarial fixtures; never interpreted as user attempts."""
import sys,json,sqlite3,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from xingce_project.tests_backend.test_backend import BackendTest
class IndependentBackend(BackendTest):
 def seed(self,v):
  super().seed(v)
  c=sqlite3.connect(self.root/v/'content.sqlite')
  q=json.loads(c.execute('select data from questions where id="q1"').fetchone()[0]);q['variant_family_id']='same-cluster';c.execute('update questions set data=? where id="q1"',(json.dumps(q),))
  q['question_id']='q5';q['material_id']=None;c.execute('insert into questions values(?,?,?,?,?,?,?)',('q5',json.dumps(q),'data','verified',1,None,'增长率变式'))
  card={'card_id':'leaky-card','title':'测试卡','question_ids':['q1'],'concept_ids':['growth'],'body_markdown':'SECRET_GROUP_ANSWER_A'}
  c.execute('insert into cards values(?,?)',('leaky-card',json.dumps(card)));c.commit();c.close()
 def test_search_short_and_sql(self):
  r=self.client.get("/api/search",params={"q":"增长"});self.assertEqual({x["question_id"] for x in r.json()["items"]},{"q1","q2","q5"});self.assertNotIn("SECRET_EXPLANATION",r.text)
  explicit=self.client.get("/api/search",params={"q":"增长","allow_source_only":"true"});self.assertEqual({x["question_id"] for x in explicit.json()["items"]},{"q1","q2","q3","q5"});self.assertNotIn("q4",{x["question_id"] for x in explicit.json()["items"]})
  self.assertEqual(self.client.get("/api/search",params={"q": "' OR 1=1--"}).json()["items"],[])
 def test_active_group_cards_do_not_leak(self):
  self.session('group')
  for path in ['/api/cards','/api/cards/leaky-card','/api/search?kind=cards']:
   self.assertNotIn('SECRET_GROUP_ANSWER_A',self.client.get(path).text,path)
 def test_transfer_excludes_same_cluster(self):
  s=self.session();self.submit(s);r=self.client.get('/api/attempts/'+s['attempts'][0]['id']+'/review')
  self.assertNotIn('q5',[x['question_id'] for x in r.json()['transfer']])
 def test_bad_package_retains_current(self):
  before=self.client.get('/api/catalog').json()['release']; bad=self.user/'imports'/'bad';bad.mkdir();(bad/'manifest.json').write_text(json.dumps({'schema_version':'1.0'}))
  response=self.client.post('/api/imports',json={'path':'bad'})
  self.assertEqual(response.status_code,422,response.text)
  self.assertEqual(self.client.get('/api/catalog').json()['release'],before)
 def test_review_card_examples_not_recommended_same_response(self):
  c=sqlite3.connect(self.root/'r1'/'content.sqlite');q=json.loads(c.execute('select data from questions where id="q5"').fetchone()[0]);q['question_id']='q6';q['variant_family_id']='different-family';c.execute('insert into questions values(?,?,?,?,?,?,?)',('q6',json.dumps(q),'data','verified',1,None,'增长迁移题'))
  card={'card_id':'exposing-card','concept_ids':['growth'],'example_qids':['q6'],'body_markdown':'q6 answer A'};c.execute('insert into cards values(?,?)',('exposing-card',json.dumps(card)));c.commit();c.close()
  session=self.session();self.submit(session);r=self.client.get('/api/attempts/'+session['attempts'][0]['id']+'/review')
  self.assertNotIn('q6',[x['question_id'] for x in r.json()['transfer']])
 def test_holdout_material_hidden(self):
  c=sqlite3.connect(self.root/'r1'/'content.sqlite');q=json.loads(c.execute('select data from questions where id="q5"').fetchone()[0]);q['holdout_reserved']=True;q['candidate_material_ids']=['reserved-m'];c.execute('update questions set data=? where id="q5"',(json.dumps(q),));c.execute('insert into materials values(?,?)',('reserved-m',json.dumps({'material_id':'reserved-m','stem_markdown':'HELD_OUT_MATERIAL_SECRET','assets':[]})));c.commit();c.close()
  self.assertNotIn('HELD_OUT_MATERIAL_SECRET',self.client.get('/api/search?kind=materials').text)
  self.assertEqual(self.client.post('/api/sessions',json={'question_ids':['q5'],'allow_source_only':True}).status_code,422)
 def test_invalid_option_rejected(self):
  s=self.session();a=s['attempts'][0]
  r=self.client.post('/api/attempts',json={'session_id':s['id'],'question_id':a['question_id'],'attempt_id':a['id'],'selected_option_ids':['NOT_AN_OPTION'],'action':'submit'})
  self.assertEqual(r.status_code,422)
if __name__=='__main__':
 suite=unittest.TestSuite(IndependentBackend(name) for name in ['test_active_group_cards_do_not_leak','test_transfer_excludes_same_cluster','test_invalid_option_rejected','test_bad_package_retains_current','test_review_card_examples_not_recommended_same_response','test_holdout_material_hidden'])
 result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())
