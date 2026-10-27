import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.queue import Queue,MockProvider
class QueueIndependent(unittest.TestCase):
 def test_received_response_write_failure_does_not_regenerate(self):
  with tempfile.TemporaryDirectory() as d:
   q=Queue(str(Path(d)/'jobs.sqlite'));req={'question_id':'qa','question_revision':1,'material_id':None,'material_revision':None,'prompt_version':'test','taxonomy_version':'test','model_config':{'provider':'mock'}};key=q.enqueue(req);p=MockProvider();old=q._set;failed=[]
   def fail_once(key,state,**fields):
    if state=='response_received' and not failed:
     failed.append(True);raise OSError('injected actual response state storage failure')
    return old(key,state,**fields)
   q._set=fail_once
   try:q.run(key,p)
   except (OSError,RuntimeError):pass
   q.run(key,p)
   self.assertEqual(p.calls,1,'received response must not call provider again')
   self.assertIsNotNone(q.get(key)['response'])
   q.db.close()
if __name__=='__main__':unittest.main()
