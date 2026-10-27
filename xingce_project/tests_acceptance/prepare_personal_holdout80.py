"""Prepare candidate verification inputs, NOT an approved user test or production overlay."""
import json,sys,hashlib,collections
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));from pipeline.safety import Assets,sanitize
R=P/'releases/content-v6-reviewed550';H=P/'acceptance/holdout';out=H/'verification_input';out.mkdir(exist_ok=True);repo=P.parent/'repos/xingcezhenti';assets=Assets(repo,out)
ids=list(map(json.loads,(H/'reserved_ids.jsonl').open()));base={q['question_id']:q for q in map(json.loads,(R/'questions.jsonl').open())};mats={m['material_id']:m for m in map(json.loads,(R/'materials.jsonl').open())};sources=collections.defaultdict(list)
for r in map(json.loads,(P.parent/'xingce_analysis/records.jsonl').open()):sources['q-'+r['qid']].append(r)
material_labels={};materials=[];questions=[];parent=[];issues=[]
for i,h in enumerate(ids,1):
 q=base[h['question_id']];neutral=f'H{i:02d}';r=sources[q['question_id']][0];sp=r['source_path']
 def clean(s,path=sp):
  text,_,errors=sanitize(s,lambda src:assets.resolve(src,path));issues.extend({'id':neutral,'issue':e} for e in errors);return text
 candidates=[]
 for mid in q.get('candidate_material_ids',[]):
  if mid not in material_labels:
   label=f'M{len(material_labels)+1:02d}';material_labels[mid]=label;m=mats[mid];msp=m['source_refs'][0]['source_path'];materials.append({'id':label,'text':clean(m['raw_text'],msp),'status':'candidate_material_not_binding_verified'})
  candidates.append(material_labels[mid])
 questions.append({'id':neutral,'stem':clean(r['stem']),'options':[{'label':o['label'],'text':clean(o['text'])} for o in r['options']],'candidate_material_ids':candidates,'instruction':'须独立判断是否需要候选材料；无候选不等于独立性已核验'})
 parent.append({'id':neutral,'question_id':q['question_id'],'source_path':sp,'source_line':r['source_line'],'module':q['normalized_module'],'source_answer':q['source_answer'],'answer_status':q['answer_status'],'binding_status':q['material_binding_status'],'candidate_material_ids':q.get('candidate_material_ids',[])})
(out/'questions.json').write_text(json.dumps({'materials':materials,'questions':questions},ensure_ascii=False,indent=2)+'\n');(out/'README.txt').write_text('这是80道个人迁移留出候选的评测准备输入，不是已核准的训练卷。只读本目录题面、候选材料与assets，不读父目录映射/源答案，不联网搜题。先核每题必要材料完整性及对应关系，再独立解答、保存推导/选项排除/图像取数证据；图必须实际查看。全部独解封存后才由父任务揭示来源比较。结果只能保存在单独评测评分依据，不得反哺生产卡、训练池或默认推荐。任何缺图/歧义标unresolved。此准备不代表用户实际做过题，不声称用户站外未见。\n');(H/'verification_parent_mapping.json').write_text(json.dumps(parent,ensure_ascii=False,indent=2)+'\n');rep={'count':80,'answer_statuses':dict(collections.Counter(x['answer_status'] for x in parent)),'binding_statuses':dict(collections.Counter(x['binding_status'] for x in parent)),'candidate_materials':len(materials),'assets':len(assets.records),'sanitize_issues':issues,'source_u_preserved':True,'input_sha256':hashlib.sha256((out/'questions.json').read_bytes()).hexdigest(),'ready_for_actual_user_blind_test':False,'required_work':['80独立答案及四选项排除','35资料题候选材料逐题核验','45题独立性及题面完整性核验','所有图实际查看/算式复核','独解封存后source对比争议隔离','独立密封评分依据和无答案可用卷，仍不得写回生产','真实用户作答与迁移统计未做'],'scope':'identity holdout protection is separate from content approval'};(H/'verification_readiness.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rep,ensure_ascii=False))
