"""Structured search regression fixtures; not actual exam evidence."""
import json,sqlite3,unittest
from xingce_project.tests_backend.test_backend import BackendTest

class SearchFilters(BackendTest):
 def seed(self,v):
  super().seed(v);c=sqlite3.connect(self.root/v/'content.sqlite');c.execute('CREATE TABLE occurrences(id TEXT PRIMARY KEY,data TEXT)')
  for pid,year,typ in [('law25',2025,'行政执法'),('city24',2024,'市地级'),('city25',2025,'市地级')]:c.execute('INSERT INTO papers VALUES(?,?)',(pid,json.dumps({'paper_id':pid,'exam_year_label':year,'paper_type':typ,'name':pid})))
  for i,(qid,pid) in enumerate([('q1','law25'),('q1','city24'),('q2','city24'),('q3','city25')]):c.execute('INSERT INTO occurrences VALUES(?,?)',(str(i),json.dumps({'question_id':qid,'paper_id':pid})))
  for qid in ['q1','q2','q3']:
   q=json.loads(c.execute('SELECT data FROM questions WHERE id=?',(qid,)).fetchone()[0]);q['normalized_module']='data';q['concept_ids']=['other'] if qid=='q2' else ['growth'];c.execute('UPDATE questions SET data=? WHERE id=?',(json.dumps(q),qid))
  for id,card in [('data-card',{'title':'增长方法','evidence_question_ids':['q1']}),('lang-card',{'title':'言语方法','module':'language'})]:c.execute('INSERT INTO cards VALUES(?,?)',(id,json.dumps({'card_id':id,**card})))
  c.commit();c.close()
 def test_qid_and_readiness(self):
  self.assertEqual([x['question_id'] for x in self.client.get('/api/search?q=q1').json()['items']],['q1'])
  self.assertEqual(self.client.get('/api/search?q=q4').json()['items'],[])
  self.assertEqual(self.client.get('/api/search?q=q3').json()['items'],[])
  self.assertEqual(len(self.client.get('/api/search?q=q3&allow_source_only=true').json()['items']),1)
 def test_combined_same_paper_filters(self):
  r=self.client.get('/api/search',params={'year':'2025','paper_type':'行政执法','module':'data','concept_id':'growth'}).json();self.assertEqual([x['question_id'] for x in r['items']],['q1'])
  self.assertEqual(self.client.get('/api/search?year=2025&paper_type=市地级').json()['items'],[])
  self.assertEqual([x['question_id'] for x in self.client.get('/api/search?year=2024&concept_id=other').json()['items']],['q2'])
  for secret in ['SECRET_EXPLANATION','verified_answer','source_answer','concept_ids']:self.assertNotIn(secret,json.dumps(r))
 def test_material_filtered_exposure(self):
  r=self.client.get('/api/search?kind=materials&year=2025&paper_type=行政执法').json();self.assertEqual(len(r['items']),1);self.assertEqual(r['items'][0]['questions'][0]['question_id'],'q1')
  with sqlite3.connect(self.user/'personal.sqlite') as c:self.assertEqual({x[0] for x in c.execute('SELECT question_id FROM exposures')},{'q1','q2'})
 def test_cards_module_actual(self):
  for path in ['/api/cards?module=data','/api/search?kind=cards&module=data']:
   r=self.client.get(path).json();self.assertEqual([x['card_id'] for x in r['items']],['data-card'])
  self.assertEqual(self.client.get('/api/cards?module=missing').json()['items'],[])
 def test_filters_metadata(self):
  r=self.client.get('/api/search/filters').json();self.assertEqual(r['years'],['2025','2024']);self.assertIn('行政执法',r['paper_types'])
 def test_origin_is_not_review_status(self):
  c=sqlite3.connect(self.root/'r1'/'content.sqlite');q=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0]);q['review_status']='ai_verified_not_human';c.execute('UPDATE questions SET data=? WHERE id="q1"',(json.dumps(q),));c.commit();c.close()
  s=self.session();self.submit(s);r=self.client.get('/api/attempts/'+s['attempts'][0]['id']+'/review').json();self.assertEqual(r['explanation_kind'],'source_reference')
 def test_prior_public_not_unseen(self):
  c=sqlite3.connect(self.root/'r1'/'content.sqlite');q=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0]);q['prior_public_example']=True;c.execute('UPDATE questions SET data=? WHERE id="q1"',(json.dumps(q),));c.commit();c.close()
  s=self.session();self.submit(s);self.assertNotIn('q1',self.client.get('/api/stats').json()['first_unexposed_no_hint_candidate_ids'])

if __name__=='__main__':unittest.main()
