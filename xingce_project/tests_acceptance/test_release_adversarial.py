"""Synthetic contract adversaries. Not real learning/content validation."""
import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.release import TABLES,dump,make_database,write_manifest,validate_release
class ReleaseAdversaries(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name)
  q={'question_id':'q-test','revision':1,'normalized_module':'数量关系','answer_status':'source_only','practice_ready':False,'material_id':None,'stem_markdown':'合成测试题','stem_html':'合成测试题','options':[{'option_id':'o-A','label':'A','text':'1','html':'1'}],'source_answer':{'option_ids':['o-A']},'verified_answer':None,'material_binding_status':'unknown','practice_blockers':['test_fixture'],'concept_ids':[],'source_refs':[],'classification_status':'unknown'}
  for t in TABLES:dump(self.p/(t+'.jsonl'),[q] if t=='questions' else [])
  make_database(self.p);write_manifest(self.p,{'version':'synthetic-contract-test'})
 def tearDown(self):self.temp.cleanup()
 def test_valid_fixture_accepted(self):
  validate_release(self.p)
 def test_manifest_cannot_omit_required_hash(self):
  p=self.p/'manifest.json';m=json.loads(p.read_text());m['files'].pop('content.sqlite');p.write_text(json.dumps(m))
  with self.assertRaises((ValueError,KeyError)):validate_release(self.p)
 def test_jsonl_and_database_must_agree(self):
  p=self.p/'questions.jsonl';q=json.loads(p.read_text());q['stem_html']='不同题干';dump(p,[q]);write_manifest(self.p,{'version':'synthetic-contract-test'})
  with self.assertRaises((ValueError,KeyError)):validate_release(self.p)
 def test_unknown_question_status_rejected(self):
  import sqlite3
  # Only the synthetic TemporaryDirectory fixture is deliberately tampered; never a real release.
  (self.p/'content.sqlite').chmod(0o600)
  con=sqlite3.connect(self.p/'content.sqlite');row=con.execute('select data from questions').fetchone();q=json.loads(row[0]);q['answer_status']='made_up';con.execute('update questions set data=?',(json.dumps(q),));con.commit();con.close();dump(self.p/'questions.jsonl',[q]);write_manifest(self.p,{'version':'synthetic-contract-test'})
  with self.assertRaises((ValueError,KeyError)):validate_release(self.p)
if __name__=='__main__':unittest.main()
