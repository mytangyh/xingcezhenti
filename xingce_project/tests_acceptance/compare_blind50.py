"""Only run after independent_answers.json is sealed. Does not edit audit answers."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'acceptance/blind50';a_path=P/'independent_answers.json';a=json.loads(a_path.read_text());mapping=json.loads((P/'parent_mapping.json').read_text());assert a['sealed'] is True
rows={r['id']:r for r in a['answers']};out=[]
for r in mapping['items']:
 x=rows[r['blind_id']];expected=[s.rsplit('-opt-',1)[-1] for s in r['expected_option_ids']];got=x['answer'];got=[got] if isinstance(got,str) else got
 out.append({'blind_id':r['blind_id'],'question_id':r['question_id'],'expected':expected,'independent_answer':got,'status':x['status'],'matches':sorted(expected)==sorted(got),'uncertainty':x.get('uncertainty'),'calculation':x.get('calculation')})
report={'independent_answers_sha256':hashlib.sha256(a_path.read_bytes()).hexdigest(),'sealed_before_comparison':True,'count':len(out),'matches':sum(x['matches'] for x in out),'disagreements':[x for x in out if not x['matches']],'unresolved':[x for x in out if x['status']!='resolved'],'scope':'fresh context-free AI independent answer-hidden sample; agreement with production is not proof of correctness or human approval; not personal learning score','process_note':'Authoritative sealed JSON is used; retain a separate reviewed audit log for any pre-seal corrections','strata':mapping['strata'],'results':out}
(P/'comparison_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['results','strata']},ensure_ascii=False))
