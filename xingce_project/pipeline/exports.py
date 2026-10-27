"""Separate teacher/learner exports; no answer metadata in practice."""
import hashlib,re,html,collections,json
from .release import dump

def fingerprint(q,materials):
 mids=q.get('candidate_material_ids',[])
 material_hashes=sorted(hashlib.sha256(materials[m]['raw_text'].encode()).hexdigest() for m in mids if m in materials)
 payload=[q['stem_markdown'],[(o['label'],o['text']) for o in q['options']],q['source_answer']['option_ids'] and [x.rsplit('-opt-',1)[-1] for x in q['source_answer']['option_ids']],material_hashes]
 return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def duplicate_candidates(questions,materials):
 exact=collections.defaultdict(list);near=collections.defaultdict(list)
 for q in questions.values():
  fp=fingerprint(q,materials);exact[fp].append(q['question_id']);text=re.sub(r'\W','',html.unescape(re.sub('<[^>]+>','',q['stem_markdown'])))
  # Conservative candidate blocking, not an equivalence assertion.
  if len(text)>25:near[text[:24]].append(q['question_id'])
 candidates=[]
 for fp,ids in exact.items():
  if len(ids)>1:
   family='vf-'+fp[:24]
   for qid in ids:questions[qid]['variant_family_id']=family
   candidates.append({'candidate_id':family,'kind':'exact_content_with_candidate_material','question_ids':ids,'merge_status':'needs_review','reason':'candidate material binding does not prove identity; no automatic ID merge'})
 for prefix,ids in near.items():
  if len(ids)>1 and len({questions[x]['variant_family_id'] for x in ids})>1:candidates.append({'candidate_id':'near-'+hashlib.sha256(prefix.encode()).hexdigest()[:24],'kind':'shared_stem_prefix','question_ids':ids,'merge_status':'needs_review','reason':'prefix similarity only; may be entirely different questions'})
 return candidates

def export_separated(out,data):
 for folder in ('reading','practice','answers'):(out/folder).mkdir()
 with open(out/'reading/cards.md','w') as f:
  f.write('# 方法参考卡（AI整理，待人工验收，不是正式卡）\n\n')
  for c in data['cards'].values():
   f.write('## '+c.get('title',c['card_id'])+'\n\n卡号：'+c['card_id']+'；状态：待人工验收\n\n')
   if c.get('body_markdown'):f.write(c['body_markdown']+'\n\n')
   else:
    for k in ('trigger','steps','boundary','boundaries','example','skip'):
     if c.get(k):
      f.write(k+'：\n')
      if isinstance(c[k],list):f.write('\n'.join('- '+str(x) for x in c[k])+'\n\n')
      else:f.write(str(c[k])+'\n\n')
 practice=[];answers=[]
 for q in data['questions'].values():
  if not q['practice_ready']:continue
  practice.append({'id':q['question_id'],'revision':q['revision'],'stem':q['stem_markdown'],'options':[{k:o[k] for k in ('option_id','label','text','html','assets') if k in o} for o in q['options']],'assets':q['assets'],'material_id':q['material_id']})
  answers.append({'question_id':q['question_id'],'answer_status':q['answer_status'],'answer':q['verified_answer'] or q['source_answer'],'explanation':q.get('explanation',''),'warning':'AI核验，非用户人工验收' if q['answer_status']=='verified' else '仅源答案，未独立核验'})
 dump(out/'practice/questions.jsonl',practice);dump(out/'practice/materials.jsonl',[{k:m[k] for k in ('material_id','stem_markdown','stem_html','assets')} for m in data['materials'].values() if m['material_id'] in {q['material_id'] for q in practice}]);dump(out/'answers/answers.jsonl',answers)
 (out/'practice/README.md').write_text('本目录只含可练题面，答案单独answers。source_only与verified成绩不能合并。未核题仅在规范全库存在，不进入本目录。\n')
