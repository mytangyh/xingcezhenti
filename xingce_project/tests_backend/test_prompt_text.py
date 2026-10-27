import unittest
from xingce_project.apps.workbench.backend.app import plain

class PromptTextTests(unittest.TestCase):
 def test_functional_marks(self):
  self.assertEqual(plain('<p>向<u>参会的人</u>致谢，<u>人家</u>来支持。</p>'),'向【划线：参会的人】致谢，【划线：人家】来支持。')
  self.assertEqual(plain('10<sup>3</sup>与a<sub>1</sub>'),'10^(3)与a_(1)')
  self.assertEqual(plain('填入<u> &nbsp; </u>合适句子'),'填入【划线：（空白）】合适句子')
 def test_no_active_content_or_image_metadata(self):
  self.assertEqual(plain('<script>answer=A</script><img src="x" alt="answer=B"><u onclick="bad()">必要条件</u>'),'【划线：必要条件】')
 def test_escaped_text_remains_text(self):
  self.assertEqual(plain('a&lt;b &amp; c&gt;d'),'a<b & c>d')

if __name__=='__main__':unittest.main()
