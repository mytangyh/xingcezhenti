import json,sqlite3,shutil,tempfile,unittest,sys,hashlib
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P.parent));from xingce_project.apps.workbench.backend.assessment import inspect_pack
class AssessmentSecurity(unittest.TestCase):
 def setUp(self):
  if not (P/'assessments/personal-holdout-80-v1').is_dir():
   self.skipTest('Requires separately authorized sealed assessment package; not included in public source')
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.name='personal-holdout-80-v1';self.p=self.root/self.name;shutil.copytree(P/'assessments'/self.name,self.p)
 def tearDown(self):self.tmp.cleanup()
 def manifest(self):return json.loads((self.p/'manifest.json').read_text())
 def save(self,m):(self.p/'manifest.json').write_text(json.dumps(m))
 def test_omitted_asset_hash_rejected(self):
  m=self.manifest();m['files'].pop(next(x for x in m['files'] if x.startswith('assets/')));self.save(m)
  with self.assertRaises(ValueError):inspect_pack(self.root,self.name)
 def test_unsafe_prompt_rejected_after_rehash(self):
  db=self.p/'content.sqlite';db.chmod(0o600);c=sqlite3.connect(db);qid,raw=c.execute('select id,data from questions limit 1').fetchone();q=json.loads(raw);q['stem_markdown']=q['stem_html']='<script>leak()</script>';c.execute('update questions set data=? where id=?',(json.dumps(q),qid));c.commit();c.close();m=self.manifest();m['files']['content.sqlite']=hashlib.sha256(db.read_bytes()).hexdigest();self.save(m)
  with self.assertRaises(ValueError):inspect_pack(self.root,self.name)
 def test_symbolic_link_rejected(self):
  m=self.manifest();name=next(x for x in m['files'] if x.startswith('assets/'));p=self.p/name;raw=p.read_bytes();target=self.root/'outside.png';target.write_bytes(raw);p.unlink();p.symlink_to(target)
  with self.assertRaises(ValueError):inspect_pack(self.root,self.name)
if __name__=='__main__':unittest.main()
