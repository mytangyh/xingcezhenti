"""Answer-hidden inputs for a fresh, context-free independent AI audit.
Parent mapping stays outside blind input folder. This is NOT personal holdout80.
"""
import json,re,hashlib,random,collections,html
from pathlib import Path
P=Path(__file__).resolve().parents[1];A=P.parent/'xingce_analysis';R=P/'releases/content-v2-190';snap=P/'content_review/snapshots/batch-v4-190'
questions={x['question_id']:x for x in map(json.loads,(R/'questions.jsonl').open())};materials={x['material_id']:x for x in map(json.loads,(R/'materials.jsonl').open())}; reviewed=list(map(json.loads,(snap/'questions.jsonl').open()))
pub=set()
for p in [A/'deliverables/行测高收益知识与解题方法手册_20261026.md',A/'quant/method_cards.json',A/'quant_methods.md',A/'v2/quant/method_cards.json',A/'v2/quant/quant_methods.md']:
 if p.exists():pub.update(re.findall(r'\b\d{6,9}\b',p.read_text()))
bad_materials={q['material_id'] for q in reviewed if q['question_id'].removeprefix('q-') in pub};holdout={x['question_id'] for x in map(json.loads,(P/'acceptance/holdout/reserved_ids.jsonl').open())}
groups=collections.defaultdict(list)
for patch in reviewed:
 if patch['material_id'] not in bad_materials and patch['question_id'] not in holdout:groups[patch['material_id']].append(questions[patch['question_id']])
byyear=collections.defaultdict(list)
for mid,qs in groups.items():
 year=int(re.search(r'20\d\d',qs[0]['source_refs'][0]['source_path'])[0]);is_image=bool(materials[mid]['assets']);byyear[year].append((mid,is_image))
rng=random.Random(2026102650); chosen=[];strata=[]
for y in sorted(byyear):
 options=sorted(byyear[y]);rng.shuffle(options);image=[x for x in options if x[1]];text=[x for x in options if not x[1]]
 take=[image[0],text[0]] if image and text else options[:2]
 assert len(take)==2
 chosen.extend(mid for mid,_ in take);strata.append({'year':y,'groups':len(take),'questions':sum(len(groups[mid]) for mid,_ in take),'material_image_groups':sum(v for _,v in take)})
rng.shuffle(chosen)
out=P/'acceptance/blind50/input';out.mkdir(parents=True,exist_ok=True);(out/'assets').mkdir(exist_ok=True);mapping=[];payload=[];allassets={}
def clean(text):
 # Render-safe HTML kept only to position neutral local image assets. No annotations/answers included.
 for match in re.finditer(r'<img\s+src="([^"]+)"\s*/?>',text):
  src=match[1];p=R/src;digest=hashlib.sha256(p.read_bytes()).hexdigest();name=digest+p.suffix.lower();dest=out/'assets'/name
  if not dest.exists():dest.write_bytes(p.read_bytes())
  allassets[name]=digest;text=text.replace(src,'assets/'+name)
 return text
for gi,mid in enumerate(chosen,1):
 material=materials[mid];entries=[];members=list(groups[mid]);rng.shuffle(members)
 for q in members:
  neutral=f'Q{len(mapping)+1:02d}';entry={'id':neutral,'stem':clean(q['stem_html']),'options':[{'label':o['label'],'text':clean(o['html'])} for o in q['options']]};entries.append(entry);mapping.append({'blind_id':neutral,'question_id':q['question_id'],'material_id':mid,'expected_option_ids':q['verified_answer']['option_ids']})
 payload.append({'group_id':f'M{gi:02d}','material':clean(material['stem_html']),'questions':entries})
assert len(mapping)==50
(out/'questions.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
(out/'README.txt').write_text('独立解题审计：只读取本目录questions.json和assets图片，不读取上级目录、源仓库、答案、解析、其他审计输出或网络搜题。逐题从材料推导答案，输出id、A/B/C/D选择、简要数值/证据和有无缺条件。遇图片请实际看图；不可读或不能确定如实填unresolved。不要猜既有答案，不需要题号/年份/考点标签。结果请写到父任务指定文件，完成后才允许父任务比对。共10组50题。此为AI审计，不是用户考试成绩。\n')
(P/'acceptance/blind50/parent_mapping.json').write_text(json.dumps({'seed':2026102650,'release':'content-v2-190','strata':strata,'items':mapping},ensure_ascii=False,indent=2)+'\n')
text=(out/'questions.json').read_text();check={'count':50,'group_count':10,'no_qid_metadata':not any(x['question_id'] in text for x in mapping),'no_answer_fields':not any(x in text for x in ['verified_answer','source_answer','explanation','concept_ids','method_ids','✅']),'no_holdout_overlap':not any(x['question_id'] in holdout for x in mapping),'no_published_example_or_material_overlap':not any(x['material_id'] in bad_materials for x in mapping),'assets':len(allassets),'questions_sha256':hashlib.sha256(text.encode()).hexdigest(),'strata':strata,'limits':['material-group random stratification by year+image form; not a fully difficulty-balanced sample','AI independent audit only; not personal unseen transfer or human approval']}
(P/'acceptance/blind50/preparation_report.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n');print(json.dumps(check,ensure_ascii=False))
