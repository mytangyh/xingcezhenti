"""Prepare answer-hidden language audit; parent mapping kept out of input."""
import json,random,collections,hashlib,re
from pathlib import Path
P=Path(__file__).resolve().parents[1];R=P/'releases/content-v5-reviewed290';S=P/'content_review_language/snapshots/batch-160-v2'
base={q['question_id']:q for q in map(json.loads,(R/'questions.jsonl').open())};mats={m['material_id']:m for m in map(json.loads,(R/'materials.jsonl').open())};anns={a['question_id']:a for a in map(json.loads,(S/'annotations.jsonl').open())};patches=list(map(json.loads,(S/'questions.jsonl').open()));holdout={q['question_id'] for q in map(json.loads,(P/'acceptance/holdout/reserved_ids.jsonl').open())}
strata=collections.defaultdict(list)
for q in patches:
 if q['answer_status']!='verified' or q['question_id'] in holdout:continue
 mid=q.get('material_id');methods=anns[q['question_id']].get('method_ids',[])
 kind='long_article' if mid else 'sentence_order_cohesion' if set(methods)&{'R06','R07'} else 'fill_blank' if set(methods)&{'R01','R02'} else 'short_paragraph'
 strata[kind].append(q)
rng=random.Random(2026102616);chosen=[]
for kind in ['fill_blank','short_paragraph','sentence_order_cohesion']:
 chosen.extend((kind,q) for q in rng.sample(strata[kind],4))
longgroups=collections.defaultdict(list)
for q in strata['long_article']:longgroups[q['material_id']].append(q)
assert len(longgroups)==2
for mid,qs in sorted(longgroups.items()):chosen.extend(('long_article',q) for q in rng.sample(qs,2))
rng.shuffle(chosen);out=P/'acceptance/language_blind16/input';out.mkdir(parents=True,exist_ok=True);(out/'assets').mkdir(exist_ok=True);mapping=[];materials=[];mids={};assets={}
def clean(text):
 for match in list(re.finditer(r'<img\s+src="([^"]+)"\s*/?>',text)):
  src=match[1];file=R/src;digest=hashlib.sha256(file.read_bytes()).hexdigest();name=digest+file.suffix.lower();dest=out/'assets'/name
  if not dest.exists():dest.write_bytes(file.read_bytes())
  assets[name]=digest;text=text.replace(src,'assets/'+name)
 return text
qs=[]
for i,(kind,patch) in enumerate(chosen,1):
 q={**base[patch['question_id']],**patch};neutral=f'Q{i:02d}';mid=q.get('material_id');material_label=None
 if mid:
  if mid not in mids:
   material_label='M'+str(len(mids)+1).zfill(2);mids[mid]=material_label;materials.append({'id':material_label,'text':clean(mats[mid]['stem_html'])})
  material_label=mids[mid]
 qs.append({'id':neutral,'material_id':material_label,'stem':clean(q['stem_html']),'options':[{'label':o['label'],'text':clean(o['html'])} for o in q['options']]})
 mapping.append({'id':neutral,'question_id':q['question_id'],'stratum':kind,'material_id':mid,'expected':[a.rsplit('-opt-',1)[-1] for a in q['verified_answer']['option_ids']]})
payload={'materials':materials,'questions':qs};(out/'questions.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(out/'README.txt').write_text('仅读取本目录questions.json及assets。共16题；若material_id非空须完整阅读对应长文。不要读取父目录、题库、答案、映射、其他生成/审计文件或网络搜题。按Q01等编号独立给A/B/C/D、简要依据和排除理由；不确定可标unresolved，不能猜既有答案。不要把文中法律科技表述当当前现实事实，按文本作答。遇图片请实际查看。输出由父任务指定路径，封存后再由父任务比较。此为AI独立审计，非个人测验。\n')
parent=out.parent;(parent/'parent_mapping.json').write_text(json.dumps({'seed':2026102616,'population_verified':147,'source_snapshot':'batch-160-v2','items':mapping},ensure_ascii=False,indent=2)+'\n');text=(out/'questions.json').read_text();report={'count':len(qs),'strata':dict(collections.Counter(k for k,q in chosen)),'full_long_articles':len(materials),'asset_count':len(assets),'no_holdout':not any(x['question_id'] in holdout for x in mapping),'no_qids':not any(x['question_id'] in text for x in mapping),'no_answer_keys':not any(x in text for x in ['verified_answer','source_answer','independent_answer','concept_ids','method_ids','✅']),'input_sha256':hashlib.sha256(text.encode()).hexdigest(),'scope':'stratified random within147 verified, long articles2each; original13 quarantined excluded for separate review'};(parent/'preparation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
