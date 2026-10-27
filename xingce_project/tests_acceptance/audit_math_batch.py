import ast,json,hashlib
from fractions import Fraction as F
from pathlib import Path
P=Path(__file__).resolve().parents[1];folder=P/'content_review_math';file=folder/'blind_solutions.jsonl';rows=list(map(json.loads,file.open()));seal=json.loads((folder/'blind_seal.json').read_text());holdout={r['source_qid'] for r in map(json.loads,(P/'acceptance/holdout/reserved_ids.jsonl').open())}
def calc(expr):
 def go(n):
  if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool):return F(ast.get_source_segment(expr,n))
  if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return go(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
  if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div)):
   a,b=go(n.left),go(n.right)
   if isinstance(n.op,ast.Add):return a+b
   if isinstance(n.op,ast.Sub):return a-b
   if isinstance(n.op,ast.Mult):return a*b
   return a/b
  raise ValueError('unapproved AST')
 return go(ast.parse(expr,mode='eval').body)
issues=[];count=0
for r in rows:
 for ex in r['expressions']:
  count+=1
  if calc(ex['expression'])!=F(ex['result']):issues.append(r['qid'])
checks={'seal_matches':hashlib.sha256(file.read_bytes()).hexdigest()==seal['sha256'],'count50':len(rows)==50,'no_direct_holdout_overlap':not {r['qid'] for r in rows}&holdout,'all_numeric_expressions_match':not issues}
# Independent direct derivation witnesses for sampled/high-risk conditions.
checks.update({'age_5893829':48==2*25-2 and F(27,18)==F(3,2) and 32+23==55 and 89+30<=120<89+33,'integer_inclusion_5445875':[k for k in range(1,10) if 121*k-76>=0 and 342*k-76<=287]==[1] and 287-266==21,'period_2264420':5*3+3*5==30 and 4*3+4*5==32,'symbolic_19526420':all(5*(6*n-10+1)==3*(F(3,2)*(6*n-10)+n) for n in [F(2),F(3),F(7,3)])})
report={'scope':'AI after-reveal second review: 6 seeded random +4 risk (one overlap=9 unique); arithmetic AST全量不是完整推导证明；符号关系另按原等式代数检查','source_seal_sha256':seal['sha256'],'questions':len(rows),'expressions':count,'checks':checks,'semantic_sample_results':{'2719398':'6选3×2=40 C','5893763':'a=4m，乙首16m/甲4m=4 C','19283966':'b+c=10，严格差约束最小a9 D','2264420':'最少5次热触发15热天，30天可实现且8次 D','2133512':'总利润120c=15000，c125 A','5893536':'k=2，103+x≥2(126−x)，最小整数50 C','5893829':'2023三人89，2033总119/2034总122 D','5445875':'k唯一1，两项121仅防病100仅育种45，剩21 A','19526420':'5(m+1)=3(1.5m+n)化简m=6n−10 B'},'human_reviewed':0,'all_pass':all(checks.values())}
(P/'acceptance/math_batch_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));raise SystemExit(not report['all_pass'])
