import sys
import ast,json,decimal,hashlib
from pathlib import Path
P=Path(__file__).resolve().parents[1];decimal.getcontext().prec=50
D=decimal.Decimal
def compute(expr):
 def visit(node):
  if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)) and not isinstance(node.value,bool):return D(ast.get_source_segment(expr,node))
  if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):return visit(node.operand)*(-1 if isinstance(node.op,ast.USub) else 1)
  if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
   a,b=visit(node.left),visit(node.right)
   if isinstance(node.op,ast.Add):return a+b
   if isinstance(node.op,ast.Sub):return a-b
   if isinstance(node.op,ast.Mult):return a*b
   return a/b
  raise ValueError('Unsupported expression '+expr)
 return visit(ast.parse(expr,mode='eval').body)
checks=[];refs=[]
input_dir=Path(sys.argv[1]) if len(sys.argv)>1 else P/'content_review'
for ann in map(json.loads,(input_dir/'annotations.jsonl').open()):
 for x in ann.get('expressions',[]):
  actual=compute(x['expression']);expected=D(str(x['result'])); tolerance=max(D('1e-8'),abs(actual)*D('1e-10'))
  checks.append({'question_id':ann['question_id'],'expression':x['expression'],'decimal_50':str(actual),'reported':str(expected),'pass':abs(actual-expected)<=tolerance})
 for ref in ann.get('binding_evidence_refs',[]):
  if ref.get('sha256'):
   p=P.parent/'repos/xingcezhenti'/ref['source_path'];refs.append(p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256'])
out={'input_dir':str(input_dir),'annotations_sha256':hashlib.sha256((input_dir/'annotations.jsonl').read_bytes()).hexdigest(),'scope':'独立白名单AST+50位Decimal复算；不独自证明取数/公式选择/近似边界正确','expression_count':len(checks),'all_numeric_match':all(x['pass'] for x in checks),'hashed_refs':len(refs),'hashes_pass':all(refs),'checks':checks}
(P/'acceptance/calculation_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='checks'},ensure_ascii=False));raise SystemExit(not(out['all_numeric_match'] and out['hashes_pass']))
