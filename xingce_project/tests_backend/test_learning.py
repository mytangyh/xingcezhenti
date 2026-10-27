"""Synthetic-only coverage and planning regressions."""
import json, sqlite3, time, unittest
from test_backend import BackendTest

class LearningTest(BackendTest):
 def seed(self,v):
  super().seed(v)
  with sqlite3.connect(self.root/v/'content.sqlite') as c:
   c.execute('CREATE TABLE occurrences(id TEXT PRIMARY KEY,data TEXT)')
   for pid,name,year,kind in [('p1','合成考试甲',2020,'A'),('p2','合成考试甲',2020,'A'),('p3','合成考试乙',None,'未区分')]:
    c.execute('INSERT INTO papers VALUES(?,?)',(pid,json.dumps(dict(paper_id=pid,name=name,exam_year_label=year,paper_type=kind))))
   for n,pid in enumerate(['p1','p1','p2','p3']):
    c.execute('INSERT INTO occurrences VALUES(?,?)',(str(n),json.dumps(dict(occurrence_id=str(n),question_id='q1',paper_id=pid,source_path='synthetic.md',source_line=1))))
 def test_whole_index_denominators_and_unknowns(self):
  r=self.client.get('/api/coverage').json();s=r['summary']
  self.assertEqual((s['identities'],s['occurrences'],s['source_groups'],s['question_source_pairs']),(4,4,2,2))
  self.assertEqual(s['verified'],3);self.assertEqual(s['practice_ready'],2)
  u=self.client.get('/api/coverage',params={'year':'未知','paper_type':'未知'}).json()
  self.assertEqual(u['summary']['identities'],4);self.assertEqual(u['summary']['occurrences'],1)
  self.assertEqual(self.client.get('/api/coverage?year=1900').json()['summary']['identities'],0)
 def test_representative_blind_exposure_and_lock(self):
  r=self.client.get('/api/coverage/evidence/q1');self.assertEqual(r.status_code,200)
  for key in ['SECRET_EXPLANATION','source_answer','verified_answer']:self.assertNotIn(key,r.text)
  with sqlite3.connect(self.user/'personal.sqlite') as c:self.assertEqual(c.execute('select count(*) from exposures').fetchone()[0],2)
  self.assertEqual(self.client.get('/api/coverage/evidence/q4').status_code,404)
  self.session('group');self.assertEqual(self.client.get('/api/coverage/evidence/q1').status_code,409)
 def test_budget_cold_start_exact_ids_and_stale_version(self):
  p=self.client.get('/api/today?budget_minutes=20').json()
  self.assertTrue(p['cold_start']);self.assertLessEqual(p['estimated_minutes'],16)
  ids=[q for t in p['items'] for q in t['question_ids']];self.assertEqual(len(ids),len(set(ids)))
  self.assertEqual(set(ids),{'q1','q2'});self.assertEqual(self.client.get('/api/today?budget_minutes=1').status_code,422)
  self.assertEqual(self.client.post('/api/sessions',json={'question_ids':ids,'planned_release':'stale'}).status_code,409)
 def test_first_attempt_uncertainty_and_due(self):
  s=self.session();a=s['attempts'][0]
  self.client.post('/api/attempts',json={'session_id':s['id'],'question_id':'q1','attempt_id':a['id'],'action':'submit','selected_option_ids':['B'],'guessed':True})
  with sqlite3.connect(self.user/'personal.sqlite') as c:
   c.execute('UPDATE reviews SET due_at=?',(time.time()-1,))
  p=self.client.get('/api/today').json();self.assertEqual(p['items'][0]['id'],'due');self.assertEqual(p['items'][0]['question_ids'],['q1'])
  e=p['items'][1]['evidence'][0];self.assertEqual(e['first_count'],1);self.assertEqual(e['first_correct'],0);self.assertFalse(e['candidate_unseen'])
 def test_alias_chain_and_material_prevent_false_new(self):
  with sqlite3.connect(self.root/'r1'/'content.sqlite') as c:
   for i,old,new in [('1','old','middle'),('2','middle','q1')]:c.execute('INSERT INTO id_aliases VALUES(?,?)',(i,json.dumps({'old_id':old,'new_id':new})))
  with sqlite3.connect(self.user/'personal.sqlite') as c:c.execute('INSERT INTO exposures VALUES(?,?,?)',('old','fixture',time.time()))
  p=self.client.get('/api/today').json();self.assertEqual(p['items'][0]['candidate_unseen_count'],0)
 def test_base_tags_preserved_against_deep_relabel(self):
  with sqlite3.connect(self.root/'r1'/'content.sqlite') as c:
   c.execute('CREATE TABLE annotations(id TEXT PRIMARY KEY,data TEXT)')
   c.execute('INSERT INTO annotations VALUES(?,?)',('base',json.dumps({'question_id':'q1','status':'reference_not_human_approved','concept_ids':['growth']})))
   q=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0]);q['concept_ids']=['refined'];c.execute('UPDATE questions SET data=? WHERE id="q1"',(json.dumps(q),))
  topics=self.client.get('/api/coverage').json()['topics']
  self.assertEqual([r['identities'] for r in topics if r['concept_id']=='growth'],[4])
  self.assertFalse(any(r['concept_id']=='refined' for r in topics))
 def test_raw_file_containing_holdout_never_linked(self):
  with sqlite3.connect(self.root/'r1'/'content.sqlite') as c:
   q=json.loads(c.execute('SELECT data FROM questions WHERE id="q4"').fetchone()[0]);q['holdout_reserved']=True;c.execute('UPDATE questions SET data=? WHERE id="q4"',(json.dumps(q),))
   c.execute('INSERT INTO occurrences VALUES(?,?)',('reserved',json.dumps({'question_id':'q4','paper_id':'p1','source_path':'synthetic.md'})))
  r=self.client.get('/api/coverage/evidence/q1').json();self.assertTrue(r['sources']);self.assertTrue(all(not s['raw_link_allowed'] for s in r['sources']))
  self.assertEqual(self.client.get('/api/coverage/evidence/q4').status_code,404)
 def test_weak_topic_precedes_correct_topic_and_timer_is_explained(self):
  with sqlite3.connect(self.root/'r1'/'content.sqlite') as c:
   base=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0])
   for qid,cid in [('strong-first','strong'),('weak-first','weak'),('a-strong-new','strong'),('z-weak-new','weak')]:
    q={**base,'question_id':qid,'material_id':None,'concept_ids':[cid]}
    c.execute('INSERT INTO questions VALUES(?,?,?,?,?,?,?)',(qid,json.dumps(q),'data','verified',1,None,'原创优先级夹具'))
  strong=self.session(ids=['strong-first']);self.submit(strong,'A')
  weak=self.session(ids=['weak-first'])
  self.client.post('/api/sessions/'+weak['id']+'/events',json={'type':'question_time','question_id':'weak-first','duration_seconds':180})
  self.submit(weak,'B')
  p=self.client.get('/api/today').json();row=p['items'][0];self.assertLess(row['question_ids'].index('z-weak-new'),row['question_ids'].index('a-strong-new'))
  e=next(x for x in row['evidence'] if x['question_id']=='z-weak-new');self.assertEqual(e['median_question_seconds'],180);self.assertEqual(e['first_correct'],0)
 def test_unknown_ratio_and_filter_denominator_consistency(self):
  all_data=self.client.get('/api/coverage').json()['summary']
  known=self.client.get('/api/coverage?paper_type=A').json()['summary']
  unknown=self.client.get('/api/coverage?paper_type=未知').json()['summary']
  self.assertEqual(all_data['unknown_type_ratio'],1/4)
  self.assertEqual(known['unknown_type_ratio'],0)
  self.assertEqual(unknown['unknown_type_ratio'],1)
  self.assertEqual(known['occurrences']+unknown['occurrences'],all_data['occurrences'])
  empty=self.client.get('/api/coverage?year=1900').json()['summary'];self.assertIsNone(empty['unknown_type_ratio'])
 def test_duplicate_and_fine_tags_do_not_inflate_identity_denominators(self):
  with sqlite3.connect(self.root/'r1'/'content.sqlite') as c:
   q=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0]);q['concept_ids']=['growth','growth','fine'];c.execute('UPDATE questions SET data=? WHERE id="q1"',(json.dumps(q),))
  r=self.client.get('/api/coverage').json();self.assertEqual(r['summary']['identities'],4);self.assertEqual(r['summary']['tagged'],4)
  growth=next(t for t in r['topics'] if t['concept_id']=='growth');self.assertEqual(growth['identities'],4);self.assertEqual(growth['occurrences'],4)
  # Multi-label topic membership may overlap; aggregate identity counts never sum these rows.
  self.assertEqual(next(t for t in r['topics'] if t['concept_id']=='fine')['identities'],1)
 def test_raw_link_blocks_cross_file_protected_material_sibling(self):
  with sqlite3.connect(self.root/'r1'/'content.sqlite') as c:
   # q1 is allowed. Its source file also contains q2, which shares the held-out
   # material with q4 in a different source file. No direct holdout is in q1's file.
   for qid,changes in [('q2',{'material_id':'protected'}),('q4',{'holdout_reserved':True,'material_id':'protected'})]:
    q=json.loads(c.execute('SELECT data FROM questions WHERE id=?',(qid,)).fetchone()[0]);q.update(changes);c.execute('UPDATE questions SET data=?,material_id=? WHERE id=?',(json.dumps(q),q['material_id'],qid))
   for oid,qid,path in [('sibling','q2','synthetic.md'),('held','q4','other-file.md')]:
    c.execute('INSERT INTO occurrences VALUES(?,?)',(oid,json.dumps({'question_id':qid,'paper_id':'p1','source_path':path})))
  r=self.client.get('/api/coverage/evidence/q1');self.assertEqual(r.status_code,200)
  self.assertTrue(all(not s['raw_link_allowed'] for s in r.json()['sources']))
  self.assertEqual(self.client.get('/api/coverage/evidence/q2').status_code,404)
  with sqlite3.connect(self.user/'personal.sqlite') as c:
   self.assertFalse(c.execute("SELECT 1 FROM exposures WHERE question_id IN ('q2','q4')").fetchone())
 def test_raw_link_blocks_candidate_material_and_reference_only_sources(self):
  with sqlite3.connect(self.root/'r1'/'content.sqlite') as c:
   for qid,changes in [('q2',{'material_id':None,'candidate_material_ids':['protected'],'source_refs':[{'source_path':'synthetic.md'}]}),('q4',{'holdout_reserved':True,'material_id':'protected','source_refs':[{'source_path':'other-file.md'}]})]:
    q=json.loads(c.execute('SELECT data FROM questions WHERE id=?',(qid,)).fetchone()[0]);q.update(changes);c.execute('UPDATE questions SET data=?,material_id=? WHERE id=?',(json.dumps(q),q['material_id'],qid))
  r=self.client.get('/api/coverage/evidence/q1');self.assertEqual(r.status_code,200)
  self.assertTrue(all(not s['raw_link_allowed'] for s in r.json()['sources']))
 def test_old_revision_first_not_replaced_by_hinted_new_revision_redo(self):
  old=self.session();self.submit(old,'B');self.seed('r2')
  with sqlite3.connect(self.root/'r2'/'content.sqlite') as c:
   q=json.loads(c.execute('SELECT data FROM questions WHERE id="q1"').fetchone()[0]);q['revision']=2;c.execute('UPDATE questions SET data=? WHERE id="q1"',(json.dumps(q),))
  (self.root/'current.json').write_text(json.dumps({'version':'r2'}))
  new=self.session();a=new['attempts'][0]
  self.client.post('/api/attempts',json={'session_id':new['id'],'question_id':'q1','attempt_id':a['id'],'action':'submit','selected_option_ids':['A'],'hint_used':True,'guessed':True})
  p=self.client.get('/api/today').json();self.assertTrue(p['cold_start']);self.assertEqual(p['excluded_first_count'],1)
  for item in p['items']:
   for e in item.get('evidence',[]):self.assertEqual(e['first_count'],0);self.assertFalse(e['candidate_unseen'])
  self.assertIn('历史曝光仍保留',p['notice'])
 def test_current_revision_real_first_keeps_hint_guess_evidence(self):
  s=self.session();a=s['attempts'][0]
  self.client.post('/api/attempts',json={'session_id':s['id'],'question_id':'q1','attempt_id':a['id'],'action':'submit','selected_option_ids':['A'],'hint_used':True,'guessed':True})
  p=self.client.get('/api/today').json();self.assertFalse(p['cold_start']);self.assertEqual(p['excluded_first_count'],0)
  e=p['items'][0]['evidence'][0];self.assertEqual(e['first_count'],1);self.assertEqual(e['first_correct'],1);self.assertEqual(e['hint_or_guess_count'],1);self.assertFalse(e['candidate_unseen'])
 def test_unscorable_first_remains_cold_but_exposed(self):
  s=self.session();self.submit(s)
  with sqlite3.connect(self.user/'personal.sqlite') as c:
   c.execute('UPDATE attempts SET grade=? WHERE id=?',(json.dumps({'correct':None,'answer_status':'unresolved','question_revision':1}),s['attempts'][0]['id']))
  p=self.client.get('/api/today').json();self.assertTrue(p['cold_start']);self.assertEqual(p['excluded_first_count'],1)
  self.assertEqual(p['items'][0]['candidate_unseen_count'],0)
