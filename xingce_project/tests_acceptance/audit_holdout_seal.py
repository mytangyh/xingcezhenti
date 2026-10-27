import ast,json,hashlib,decimal
from fractions import Fraction as F
from pathlib import Path
P=Path(__file__).resolve().parents[1];H=P/'acceptance/holdout';S=H/'sealed_assessment';a=json.load((S/'sealed_answers_80.json').open());inp=json.load((H/'verification_input/questions.json').open());issues=[];n=0
# AST whitelist for recorded rational calculations, never eval production text.
def calc(expr):
 def ev(x):
  if isinstance(x,ast.Constant) and type(x.value) in (int,str):return x.value
  if isinstance(x,ast.List):return [ev(v) for v in x.elts]
  if isinstance(x,ast.UnaryOp) and isinstance(x.op,ast.USub):return -ev(x.operand)
  if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id in ('F','sum') and not x.keywords:
   args=[ev(v) for v in x.args];return F(*args) if x.func.id=='F' else sum(args[0])
  if isinstance(x,ast.BinOp):
   l,r=ev(x.left),ev(x.right)
   if isinstance(x.op,ast.Add):return l+r
   if isinstance(x.op,ast.Sub):return l-r
   if isinstance(x.op,ast.Mult):return l*r
   if isinstance(x.op,ast.Div):return F(l)/F(r)
  raise ValueError(ast.dump(x))
 return ev(ast.parse(expr,mode='eval').body)
for q in a['questions']:
 for x in q.get('calculations',[]):
  n+=1;v=calc(x['expression']);expect=x['result'];ok=[F(z) for z in expect]==v if isinstance(expect,list) else F(expect['fraction'])==v
  if not ok:issues.append([q['id'],x['expression']])
for f,h in a['component_sha256'].items():
 if hashlib.sha256((S/f).read_bytes()).hexdigest()!=h:issues.append(['component_hash',f])
if hashlib.sha256((H/'verification_input/questions.json').read_bytes()).hexdigest()!=a['input_sha256']:issues.append(['input_hash'])
viewed={f for q in a['questions'] for f in q.get('images_viewed',[])};actual={'assets/'+f.name for f in (H/'verification_input/assets').iterdir()}
if viewed!=actual:issues.append(['image_inventory',sorted(actual-viewed),sorted(viewed-actual)])
r={'sealed_sha256':hashlib.sha256((S/'sealed_answers_80.json').read_bytes()).hexdigest(),'questions':len(a['questions']),'calculations_independently_checked':n,'images_recorded_viewed':len(viewed),'all_components_and_input_hash_valid':not issues,'issues':issues,'scope':'records/hash/65 rational expressions; image-view records corroborate agent process, not this checker personally viewing all73; user_results_none'};(S/'independent_integrity_audit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False));assert not issues
