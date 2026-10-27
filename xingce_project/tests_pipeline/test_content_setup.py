import json,tempfile,unittest,zipfile
from pathlib import Path
from content_setup import diagnose,import_zip
from pipeline.release import TABLES,dump,make_database,write_manifest,activate_release
class SetupTest(unittest.TestCase):
 def test_missing_diagnostics_no_write(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'missing';self.assertFalse(diagnose(p)[0]['ok']);self.assertFalse(p.exists())
 def test_zip_import_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);source=p/'source';v=source/'synthetic';v.mkdir(parents=True)
   for t in TABLES:dump(v/(t+'.jsonl'),[])
   make_database(v);write_manifest(v,{'version':'synthetic'});activate_release(source,'synthetic')
   z=p/'content.zip'
   with zipfile.ZipFile(z,'w') as f:
    for x in source.rglob('*'):
     if x.is_file():f.write(x,'xingce_project/releases/'+str(x.relative_to(source)))
    f.writestr('xingce_project/DO_NOT_IMPORT.py','private old source')
   target=p/'target';self.assertEqual(import_zip(z,target),'synthetic');self.assertFalse((p/'DO_NOT_IMPORT.py').exists())
   self.assertTrue(all(x['ok'] for x in diagnose(target)))
   with self.assertRaises(ValueError):import_zip(z,target)
 def test_zip_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);z=p/'bad.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('xingce_project/releases/../../escape','bad')
   with self.assertRaises(ValueError):import_zip(z,p/'target')
   self.assertFalse((p/'escape').exists())

 def test_windows_drive_path_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);z=p/'bad.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('xingce_project/releases/C:/escape','bad')
   with self.assertRaises(ValueError):import_zip(z,p/'target')
