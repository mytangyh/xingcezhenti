import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.safety import sanitize,Assets
class Safety(unittest.TestCase):
 def test_active_html_not_preserved(self):
  for text in ['<script>alert(1)</script>安全','<iframe src=x></iframe>安全','<svg onload=alert(1)>安全</svg>','<a href="javascript:alert(1)">安全</a>','<div onclick="alert(1)">安全</div>','<img src="javascript:alert(1)">']:
   out,assets,issues=sanitize(text,lambda src:None)
   self.assertNotIn('javascript:',out);self.assertNotIn('onclick',out);self.assertNotIn('<svg',out);self.assertNotIn('<script',out);self.assertNotIn('<iframe',out)
 def test_semantic_underline_kept_without_active_attributes(self):
  out,_,_=sanitize('<u onclick="alert(1)" style="background:url(javascript:x)">先行语</u>',lambda src:None)
  self.assertIn("<u>先行语</u>",out)
  self.assertNotIn("onclick",out);self.assertNotIn("style",out);self.assertNotIn("javascript",out)
 def test_answer_leak_flagged(self):
  for text in ['正确答案：A','参考答案为 B','【解析】先求差','<div>答案是C</div>']:
   self.assertIn('suspected_answer_leak',sanitize(text,lambda src:None)[2])
 def test_mark_removed(self):
  self.assertNotIn('✅',sanitize('选项✅',lambda src:None)[0])
 def test_html_encoded_payload_escaped(self):
  out,_,_=sanitize('&lt;script&gt;alert(1)&lt;/script&gt;',lambda src:None)
  self.assertNotIn('<script>',out)
 def test_assets_cannot_escape(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'repo';root.mkdir();out=Path(d)/'out';out.mkdir();(Path(d)/'outside.png').write_bytes(b'test');(root/'link.png').symlink_to(Path(d)/'outside.png')
   a=Assets(root,out)
   for path in ['../outside.png','link.png','https://example.com/x.png','javascript:x','data:image/png,abc','//example.com/x.png']:
    self.assertIsNone(a.resolve(path,'file.md'),path)
if __name__=='__main__':unittest.main()
