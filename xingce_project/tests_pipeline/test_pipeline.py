import tempfile,unittest
from pathlib import Path
from pipeline.queue import Queue,MockProvider
from pipeline.safety import sanitize,Assets
from pipeline.calculation import evaluate
from pipeline.release import dump,make_database,write_manifest,activate_release,TABLES
REQ=dict(question_id='q-1',question_revision=1,material_id=None,material_revision=None,prompt_version='1',taxonomy_version='1',model_config={'provider':'mock'})
class QueueTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.q=Queue(Path(self.tmp.name)/'queue.sqlite')
 def tearDown(self):self.q.db.close();self.tmp.cleanup()
 def test_idempotency(self):self.assertEqual(self.q.enqueue(REQ),self.q.enqueue(REQ));self.assertNotEqual(self.q.enqueue(REQ),self.q.enqueue({**REQ,'question_revision':2}))
 def test_response_cache_after_disk_failure(self):
  key=self.q.enqueue(REQ);p=MockProvider()
  with self.assertRaises(RuntimeError):self.q.run(key,p,fail_after='response_received')
  self.assertEqual(self.q.get(key)['state'],'response_received');self.q.run(key,p);self.assertEqual(p.calls,1);self.assertEqual(self.q.get(key)['state'],'validated')
 def test_retry_and_resume(self):
  key=self.q.enqueue(REQ);p=MockProvider(1);self.assertEqual(self.q.run(key,p,retry_delay=0)['state'],'retryable_error');self.assertEqual(self.q.run(key,p)['state'],'validated');self.assertEqual(p.calls,2)
 def test_missing_model_no_simulation(self):
  key=self.q.enqueue(REQ);r=self.q.run(key);self.assertEqual(r['state'],'blocked_input');self.assertIsNone(r['response'])
 def test_mock_not_real(self):self.assertTrue(MockProvider()(REQ)['simulation'])
 def test_recovery(self):
  key=self.q.enqueue(REQ);self.q._set(key,'running');self.q.recover(0);self.assertEqual(self.q.get(key)['state'],'needs_review')
 def test_validation_quarantine(self):
  key=self.q.enqueue(REQ)
  def fail(x):raise ValueError('bad evidence')
  self.assertEqual(self.q.run(key,MockProvider(),fail)['state'],'needs_review')
 def test_mock_cannot_publish(self):
  key=self.q.enqueue(REQ);self.q.run(key,MockProvider())
  with self.assertRaises(ValueError):self.q.publish(key)
 def test_actual_db_receipt_write_failure(self):
  key=self.q.enqueue(REQ);p=MockProvider();original=self.q._set
  def fail(k,state,**fields):
   if state=='response_received':raise OSError('disk database write failure')
   return original(k,state,**fields)
  self.q._set=fail
  with self.assertRaises(OSError):self.q.run(key,p)
  self.assertEqual(self.q.get(key)['state'],'running');self.q._set=original;self.q.run(key,p);self.assertEqual(p.calls,1)
 def test_spool_failure_does_not_retry_provider(self):
  key=self.q.enqueue(REQ);p=MockProvider();original=self.q._spool_write
  def fail(*args):raise OSError('disk full')
  self.q._spool_write=fail
  with self.assertRaises(OSError):self.q.run(key,p)
  self.assertEqual(self.q.get(key)['state'],'running');self.q._spool_write=original;self.q.run(key,p);self.assertEqual(p.calls,1)
 def test_exponential_backoff(self):
  import time
  key=self.q.enqueue(REQ);p=MockProvider(2);r=self.q.run(key,p);self.assertGreater(r['next_retry_at'],time.time()+25);self.q.run(key,p);self.assertEqual(p.calls,1)
 def test_real_result_requires_validation(self):
  key=self.q.enqueue(REQ)
  result=self.q.run(key,lambda _: {'simulation':False,'real_model_distillation':True})
  self.assertEqual(result['state'],'needs_review')
 def test_publish_requires_validated(self):
  key=self.q.enqueue(REQ)
  with self.assertRaises(ValueError):self.q.publish(key)
class SafetyTests(unittest.TestCase):
 def test_html_and_marks(self):
  text,assets,issues=sanitize('<script>alert(1)</script>A✅ <b onclick="x">X</b><img src="https://evil/x.png" alt="答案A">',lambda s:None)
  self.assertNotIn('alert',text);self.assertNotIn('onclick',text);self.assertNotIn('✅',text);self.assertTrue(issues)
 def test_leak(self):self.assertIn('suspected_answer_leak',sanitize('正确答案：A',lambda s:None)[2])
 def test_traversal(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'repo').mkdir();(p/'out').mkdir();(p/'secret.png').write_bytes(b'x');a=Assets(p/'repo',p/'out');self.assertIsNone(a.resolve('../secret.png','x.md'))
 def test_arithmetic(self):self.assertEqual(str(evaluate('0.1+0.2')),'3/10')
 def test_no_code(self):
  for s in ['__import__("os").system("x")','2**100000','a[0]']:
   with self.assertRaises(ValueError):evaluate(s)
class ReleaseTests(unittest.TestCase):
 def fixture(self,p):
  p.mkdir()
  for t in TABLES:dump(p/(t+'.jsonl'),[])
  make_database(p);write_manifest(p,{'version':p.name})
 def test_rollback_and_failed_switch(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.fixture(root/'v1');self.fixture(root/'v2');activate_release(root,'v1');activate_release(root,'v2');activate_release(root,'v1');before=(root/'current.json').read_bytes();(root/'v2/questions.jsonl').write_text('tampered')
   with self.assertRaises(ValueError):activate_release(root,'v2')
   self.assertEqual(before,(root/'current.json').read_bytes())
 def test_two_build_reproducibility(self):
  from pipeline.reproducibility import compare
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.fixture(root/'v1');self.fixture(root/'v2');r=compare(root/'v1',root/'v2');self.assertTrue(r['passed']);self.assertTrue(r['canonical_jsonl_byte_equal']);self.assertTrue(r['sqlite_entity_logical_equal'])
 def test_reproducibility_detects_payload_change(self):
  from pipeline.reproducibility import compare
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.fixture(root/'v1');self.fixture(root/'v2');(root/'v2'/'extra.txt').write_text('changed');write_manifest(root/'v2',{'version':'v2'});self.assertFalse(compare(root/'v1',root/'v2')['passed'])
 def test_unsafe_release(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):activate_release(d,'../bad')
if __name__=='__main__':unittest.main()
