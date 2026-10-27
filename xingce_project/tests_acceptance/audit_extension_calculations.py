import json,decimal,ast,hashlib,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];S=P/(sys.argv[1] if len(sys.argv)>1 else 'content_review/snapshots/extension-batch1-20');decimal.getcontext().prec=50;D=decimal.Decimal
# Independent whitelist: reject functions/indexing/attributes and arbitrary code.
def calc(s,v):
 def ev(n):
  if isinstance(n,ast.Name):return v[n.id]
  if isinstance(n,ast.Constant) and type(n.value) in (int,float):return D(ast.get_source_segment(s,n))
  if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return -ev(n.operand) if isinstance(n.op,ast.USub) else ev(n.operand)
  if isinstance(n,ast.BinOp):
   a,b=ev(n.left),ev(n.right)
   if isinstance(n.op,ast.Add):return a+b
   if isinstance(n.op,ast.Sub):return a-b
   if isinstance(n.op,ast.Mult):return a*b
   if isinstance(n.op,ast.Div):return a/b
   if isinstance(n.op,ast.Pow) and b==int(b) and abs(b)<=20:return a**int(b)
  raise ValueError(ast.dump(n))
 return ev(ast.parse(s,mode='eval').body)
rows=list(map(json.loads,(S/'annotations.jsonl').open()));n=0;issues=[]
for r in rows:
 line=r['source_variable_lineage'];v={x['symbol']:D(x['value']) for x in line['variables']}
 for x in line['variables']:
  for k in ['unit','period','statistical_object','source_path','source_locator']:
   if not x.get(k):issues.append([r['question_id'],'missing',k])
 for e in line['symbolic_expressions']:
  n+=1;a=calc(e['expression'],{});b=calc(e['symbolic_expression'],v);c=D(e['decimal_result']);tol=max(D('1e-30'),abs(a)*D('1e-37'))
  if a!=b or abs(a-c)>tol:issues.append([r['question_id'],'mismatch',str(a),str(b),str(c)])
report={'input':str(S.relative_to(P)),'sha256':hashlib.sha256((S/'annotations.jsonl').read_bytes()).hexdigest(),'questions':len(rows),'expressions':n,'issues':issues,'all_pass':not issues,'scope':'independent50digitDecimal numerical-symbolic equivalence and field presence, not full source operand/answer semantics'};(P/'acceptance'/('calculation_'+S.name+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));assert not issues
