"""Build isolated assessment artifact, never a training release or user attempt."""
import json,re,hashlib,shutil,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P));from pipeline.release import TABLES,dump,make_database,digest
H=P/'acceptance/holdout';S=H/'sealed_assessment';pack='personal-holdout-80-v1';out=P/'assessments'/pack
if out.exists():raise SystemExit('immutable pack already exists')
out.mkdir(parents=True);(out/'assets').mkdir();inp=json.load((H/'verification_input/questions.json').open());answers={q['id']:q for q in json.load((S/'sealed_answers_80.json').open())['questions']};mapping={q['id']:q for q in json.load((H/'verification_parent_mapping.json').open())};base={q['question_id']:q for q in map(json.loads,(P/'releases/content-v7-reviewed753/questions.jsonl').open())};mats={m['id']:m for m in inp['materials']};tables={k:[] for k in TABLES};asset_records={};mat_records={};material_aliases={};seen_text={};checks=[]
def asset_refs(text,role='prompt',option_id=None):
 refs=[]
 for rel in re.findall(r'<img src="([^"]+)"',text):
  file=H/'verification_input'/rel;sha=digest(file);assert file.stem==sha;target=out/rel
  if not target.exists():shutil.copyfile(file,target)
  aid='a-'+sha;asset_records[aid]={'asset_id':aid,'path':rel,'sha256':sha,'availability':'available','roles':['prompt'],'license_status':'source_license_unconfirmed_private_study_only'};ref={'asset_id':aid,'path':rel,'role':role}
  if option_id:ref['option_id']=option_id
  refs.append(ref)
 return refs
for it in inp['questions']:
 a=answers[it['id']];parent=mapping[it['id']];qid=parent['question_id'];old=base[qid];mid=None
 for neutral in a.get('materials_verified',[]):
  text=mats[neutral]['text'];key=hashlib.sha256(text.encode()).hexdigest()
  if key not in seen_text:
   mid_new='am-'+key[:24];seen_text[key]=mid_new;mat_records[mid_new]={'material_id':mid_new,'revision':1,'stem_markdown':text,'stem_html':text,'assets':asset_refs(text),'binding_status':'verified','assessment_only':True}
  material_aliases[neutral]=seen_text[key]
  if mid is not None:assert mid==seen_text[key],'Different required materials need explicit combination'
  mid=seen_text[key]
 opts=[]
 for o in it['options']:
  oid=next(x['option_id'] for x in old['options'] if x['label']==o['label']);opts.append({'option_id':oid,'label':o['label'],'text':o['text'],'html':o['text'],'assets':asset_refs(o['text'],'option',oid)})
 ready=a['chosen_label'] is not None;proof={'kind':'sealed_independent_assessment','sealed_sha256':digest(S/'sealed_answers_80.json'),'assessment_item_id':it['id'],'reviewer_type':'AI','human_approved':False};explanation=a.get('reasoning') or a.get('reason','');uncertainty=a.get('uncertainty',[])
 if uncertainty:explanation+='\n边界/不确定：'+('；'.join(uncertainty) if isinstance(uncertainty,list) else uncertainty)
 if a.get('calculations'):explanation+='\n核验算式：'+json.dumps(a['calculations'],ensure_ascii=False)
 q={'question_id':qid,'revision':1,'normalized_module':parent['module'],'stem_markdown':it['stem'],'stem_html':it['stem'],'options':opts,'assets':asset_refs(it['stem']),'material_id':mid,'candidate_material_ids':[mid] if mid else [],'material_binding_status':'verified','assessment_item_id':it['id'],'prompt_ready':True,'assessment_ready':ready,'practice_ready':False,'holdout_reserved':True,'answer_status':'verified' if ready else 'unresolved','source_answer':None,'verified_answer':{'option_ids':[next(o['option_id'] for o in opts if o['label']==a['chosen_label'])],'evidence_refs':[proof]} if ready else None,'review_status':'ai_verified_not_human' if ready else 'unresolved','explanation':explanation,'explanation_origin':'native_independent_review','concept_ids':[],'method_ids':[],'source_refs':[],'classification_status':'unknown','practice_blockers':['holdout_reserved','assessment_only'],'verification_notice':'独立AI评测核验非人工；不计入生产题/卡，不代表用户成绩。'}
 tables['questions'].append(q)
tables['materials']=list(mat_records.values());tables['assets']=list(asset_records.values())
for t,rows in tables.items():dump(out/(t+'.jsonl'),rows)
make_database(out)
manifest={'schema_version':'assessment-1','pack_id':pack,'title':'个人迁移评测：80题面，79可评分、1待核（非原卷）','question_ids':[q['question_id'] for q in tables['questions']],'scorable_count':79,'unscored_count':1,'reserved_count':80,'human_approved':False,'production_training_allowed':False,'user_result':None,'files':{str(f.relative_to(out)):digest(f) for f in sorted(out.rglob('*')) if f.is_file()},'sealed_answer_sha256':digest(S/'sealed_answers_80.json'),'source_input_sha256':digest(H/'verification_input/questions.json')};(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');report={'pack_path':str(out),'question_count':80,'scorable_count':79,'unscored_items':['H49'],'material_count':len(mat_records),'neutral_material_aliases':material_aliases,'asset_count':len(asset_records),'source_answers_included':False,'production_release_changed':False,'user_session_created':False,'manifest_sha256':digest(out/'manifest.json')};(S/'pack_build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
