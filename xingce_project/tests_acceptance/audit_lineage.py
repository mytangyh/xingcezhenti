import ast,json,decimal,hashlib
from pathlib import Path
P=Path(__file__).resolve().parents[1];folder=P/'content_review/snapshots/lineage190-final-v2';decimal.getcontext().prec=50;D=decimal.Decimal
def calc(expr,values):
 def go(n):
  if isinstance(n,ast.Name):return values[n.id]
  if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool):return D(ast.get_source_segment(expr,n))
  if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return go(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
  if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
   a,b=go(n.left),go(n.right)
   if isinstance(n.op,ast.Add):return a+b
   if isinstance(n.op,ast.Sub):return a-b
   if isinstance(n.op,ast.Mult):return a*b
   return a/b
  raise ValueError('Nonwhitelisted AST')
 return go(ast.parse(expr,mode='eval').body)
rows=list(map(json.loads,(folder/'variable_lineage.jsonl').open()));exprs=0;issues=[];varcount=0
for row in rows:
 values={}
 for v in row['variables']:
  varcount+=1
  for key in ['symbol','value','unit','period','statistical_object','source_path','source_locator']:
   if not v.get(key):issues.append({'question_id':row['question_id'],'missing':key})
  values[v['symbol']]=D(v['value'])
  if v.get('source_sha256'):
   file=P.parent/'repos/xingcezhenti'/v['source_path']
   if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=v['source_sha256']:issues.append({'question_id':row['question_id'],'bad_source_hash':v['source_path']})
 for ex in row['symbolic_expressions']:
  exprs+=1;a=calc(ex['symbolic_expression'],values);b=calc(ex['original_numeric_expression'],{});reported=D(ex['decimal_result']);tol=max(D('1e-30'),abs(a)*D('1e-30'))
  if abs(a-b)>tol or abs(a-reported)>tol:issues.append({'question_id':row['question_id'],'expression_index':ex['expression_index'],'a':str(a),'b':str(b),'reported':str(reported)})
byqid={r['question_id']:r for r in rows};checks={}
a=byqid['q-4639655'];twins=[v for v in a['variables'] if v['value']=='37.5'];checks['37_5_eight_and_eleven_month_distinct']=len(twins)==2 and len({v['symbol'] for v in twins})==2 and any('8月' in v['source_locator'] for v in twins) and any('11月' in v['source_locator'] for v in twins)
a=byqid['q-5445741'];checks['mask_decline_minus76_not_apparel24']=any(v['value']=='-76' and '口罩' in v['statistical_object'] for v in a['variables']) and not any(v['value']=='24' for v in a['variables'])
a=byqid['q-5445759'];checks['safety_belt_q3_q4_16_separate_cells']=len(a['variables'])==16 and sum('三季度' in v['source_locator'] for v in a['variables'])==8 and sum('四季度' in v['source_locator'] for v in a['variables'])==8
report={'input_sha256':hashlib.sha256((folder/'variable_lineage.jsonl').read_bytes()).hexdigest(),'questions':len(rows),'variables':varcount,'expressions':exprs,'issues':issues,'targeted_semantic_wiring_checks':checks,'scope':'全具名式与原数字式50位Decimal同值/字段及图hash；3个定向同数异义case经AI原图/原文复核，不是全操作数人工语义签字','all_pass':not issues and all(checks.values())}
(P/'acceptance/lineage_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));raise SystemExit(not report['all_pass'])
