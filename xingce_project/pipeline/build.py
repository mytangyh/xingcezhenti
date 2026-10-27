"""python -m pipeline.build --root .. --version v1 [--overlay path]"""
import argparse,collections,hashlib,json,os,re,shutil
from pathlib import Path
from .safety import Assets,sanitize
from .exports import duplicate_candidates,export_separated
from .calculation import evaluate
from .provenance import is_independent_annotation
from .release import TABLES,KEYS,dump,make_database,write_manifest,validate_release,activate_release,check_revision_migration

def sid(prefix,s):return prefix+hashlib.sha256(s.encode()).hexdigest()[:24]
def lines(p):
 if Path(p).exists():
  with open(p) as f:
   for l in f:
    if l.strip():yield json.loads(l)
def build(root,version,overlays=(),activate=True,allowed_new_card_ids=()):
 import fcntl
 approved={'card-R19','card-R20','card-R21'}
 if not set(allowed_new_card_ids)<=approved:raise ValueError('new card ID not explicitly authorized')
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}',version):raise ValueError('unsafe release version')
 releases=Path(root).resolve()/'xingce_project/releases';releases.mkdir(parents=True,exist_ok=True)
 with open(releases/'.build.lock','a+') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError('another content build is running; do not remove its staging directory')
  try:return _build(root,version,overlays,activate,allowed_new_card_ids)
  finally:fcntl.flock(lock,fcntl.LOCK_UN)

def _build(root,version,overlays=(),activate=True,allowed_new_card_ids=()):
 root=Path(root).resolve();analysis=root/'xingce_analysis';repo=root/'repos/xingcezhenti';dest=root/'xingce_project/releases';out=dest/('.building-'+version)
 if (dest/version).exists():raise ValueError('immutable release already exists')
 if out.exists():shutil.rmtree(out)
 out.mkdir(parents=True);assets=Assets(repo,out);data={t:{} for t in TABLES};variants=collections.defaultdict(dict)
 producer_hashes={}
 for directory,pattern in (('pipeline','*.py'),('schemas','*.json')):
  for source in sorted((root/'xingce_project'/directory).glob(pattern)):
   raw=source.read_bytes();relative='producer/'+directory+'/'+source.name;target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);producer_hashes[relative]=hashlib.sha256(raw).hexdigest()
 # Capture exact bytes before the long corpus pass; hashes describe consumed bytes.
 overlay_records={};overlay_hashes={}
 for overlay in overlays:
  overlay_records[overlay]={}
  for t in TABLES:
   inp=Path(overlay)/(t+'.jsonl')
   if inp.exists():
    raw=inp.read_bytes();overlay_hashes[str(inp)]=hashlib.sha256(raw).hexdigest();overlay_records[overlay][t]=[json.loads(line) for line in raw.decode().split('\n') if line.strip()]
   else:overlay_records[overlay][t]=[]
 topics={r['qid']:r for r in lines(analysis/'v2/index/canonical_topic_index.jsonl')}
 material_lookup={}
 for r in lines(analysis/'materials_candidates.jsonl'):
  mid=sid('m-',r['source_path']+'#'+str(r['source_material_number']));safe,aa,issues=sanitize(r['raw_text'],lambda s:assets.resolve(s,r['source_path'],'material'))
  data['materials'][mid]={'material_id':mid,'revision':1,'raw_text':r['raw_text'],'stem_markdown':safe,'stem_html':safe,'assets':aa,'binding_status':'source_inferred','issues':issues,'source_refs':[{'source_path':r['source_path'],'source_material_number':r['source_material_number']}]};material_lookup[(r['source_path'],r['source_material_number'])]=mid
 for r in lines(analysis/'records.jsonl'):
  qid='q-'+r['qid'];pid=sid('p-',r['paper_name']);oid=r['occurrence_id'];ref={k:r.get(k) for k in ('source_commit','source_path','source_line','source_local_number')}
  data['papers'].setdefault(pid,{'paper_id':pid,'name':r['paper_name'],'exam_year_label':r['year'],'exam_date':None,'region':r['region'],'paper_type':r['paper_type'],'paper_completeness':'unverified','original_order_verified':False})
  mid=material_lookup.get((r['source_path'],r.get('candidate_material_number')))
  data['occurrences'][oid]={'occurrence_id':oid,'question_id':qid,'paper_id':pid,'source_qid':r['qid'],**ref,'source_module':r['module'],'candidate_material_id':mid,'material_binding_status':'source_inferred' if mid else 'unknown','source_analysis_sha256':hashlib.sha256(r['source_analysis'].encode()).hexdigest()}
  fingerprint=hashlib.sha256(json.dumps([r['stem'],r['options'],r['source_answer']],sort_keys=True,ensure_ascii=False).encode()).hexdigest();variants[qid][fingerprint]=oid
  if qid in data['questions']:
   q=data['questions'][qid];q['source_refs'].append(ref)
   if mid and mid not in q['candidate_material_ids']:q['candidate_material_ids'].append(mid)
   continue
  stem,aa,issues=sanitize(r['stem'],lambda s:assets.resolve(s,r['source_path'],'stem'));options=[];label_counts=collections.Counter(o['label'] for o in r['options']);label_seen=collections.Counter()
  for o in r['options']:
   label_seen[o['label']]+=1;option_id=qid+'-opt-'+o['label']+(('-'+str(label_seen[o['label']])) if label_counts[o['label']]>1 else '')
   text,oa,oi=sanitize(o['text'],lambda s:assets.resolve(s,r['source_path'],'option'));oa=[{**a,'option_id':option_id} for a in oa];aa+=oa;issues+=oi;options.append({'option_id':option_id,'label':o['label'],'text':text,'html':text,'assets':oa})
  labels={o['label'] for o in options};answer=[o['option_id'] for o in options if o['label'] in str(r['source_answer'])]
  if len(options)!=4 or len(labels)!=4:issues.append('nonstandard_options')
  if not stem:issues.append('empty_stem')
  if not answer:issues.append('missing_source_answer')
  if len(answer)!=1:issues.append('ambiguous_answer_cardinality')
  safe_analysis,analysis_assets,analysis_issues=sanitize(r['source_analysis'],lambda s:assets.resolve(s,r['source_path'],'analysis_only'))
  topic=topics.get(r['qid'],{});name=topic.get('reviewed_primary_fine') or topic.get('candidate_primary_fine');cids=[]
  if name:
   cid=sid('c-',name);cids=[cid];data['concepts'].setdefault(cid,{'concept_id':cid,'name':name,'parent_id':None,'definition':None,'aliases':[],'taxonomy_version':'v2-ai-1','status':'ai_reference'})
  normalized='数量关系' if r['qid'] in ('5445878','5893530') else r['module']
  q={'question_id':qid,'revision':1,'source_qid':r['qid'],'stem_markdown':stem,'stem_html':stem,'options':options,'source_answer':{'option_ids':answer,'status':'source_only'},'verified_answer':None,'answer_status':'source_only' if answer else 'unresolved','explanation_origin':'source_reference','explanation':safe_analysis,'source_analysis':r['source_analysis'],'analysis_assets':analysis_assets,'source_analysis_issues':analysis_issues,'question_type':'single_choice' if len(options)==4 else 'nonstandard','material_id':None,'candidate_material_ids':[mid] if mid else [],'material_binding_status':'source_inferred' if mid else 'unknown','source_module':r['module'],'normalized_module':normalized,'classification_status':topic.get('status','unknown'),'concept_ids':cids,'assets':aa,'source_refs':[ref],'practice_ready':False,'practice_blockers':sorted(set(issues+['material_or_independence_not_verified'])),'content_issues':sorted(set(issues)),'review_status':'unreviewed','exposure_status':'not_assessed','prior_public_example':False,'exposure_assessment_complete':False}
  data['questions'][qid]=q
  aid='ann-'+qid;data['annotations'][aid]={'annotation_id':aid,'question_id':qid,'question_revision':1,'concept_ids':cids,'classification_status':q['classification_status'],'reviewer_type':'ai','status':'reference_not_human_approved','evidence_refs':topic.get('review_evidence',[]),'method_card_ids':topic.get('method_card_evidence_ids',[])}
  aid='assess-'+qid;data['assessments'][aid]={'assessment_id':aid,'question_id':qid,'question_revision':1,'status':'quarantined','stage':'pre_overlay_source_import','check_type':'mechanical_prompt_integrity','reviewer_type':'program','findings':q['practice_blockers']}
 for qid,vs in variants.items():
  q=data['questions'][qid];q['content_variants']=[{'sha256':k,'occurrence_id':v} for k,v in vs.items()];q['variant_family_id']=qid
  if len(vs)>1:q['answer_status']='disputed';q['practice_blockers'].append('source_content_conflict')
  q['candidate_material_variants']=[{'material_id':mid,'raw_sha256':hashlib.sha256(data['materials'][mid]['raw_text'].encode()).hexdigest(),'status':'candidate_not_semantically_equated'} for mid in q['candidate_material_ids']]
  q['occurrence_material_consistency']='multiple_candidates_need_review' if len({m['raw_sha256'] for m in q['candidate_material_variants']})>1 else 'not_independently_compared'
 # Existing cards are references, never human-approved official cards.
 for r in json.load(open(analysis/'v2/quant/method_cards.json')):
  cid='card-'+r['id'];data['cards'][cid]={'card_id':cid,**r,'concept_ids':[],'approval_status':'ai_reference_pending_human','is_official':False}
 for r in json.load(open(analysis/'v2/index/method_card_catalog.json')):
  cid='card-'+r['id']
  if cid not in data['cards']:data['cards'][cid]={'card_id':cid,**r,'concept_ids':[],'approval_status':'ai_reference_pending_human','is_official':False}
 # Attach the 18 actual reasoning cards, not headings or duplicate catalog entries.
 p=analysis/'v2/reasoning/reasoning_language.md';body=p.read_text();section=body.split('## 18张方法卡',1)[1]
 for match in re.finditer(r'(?ms)^### (\d{2})｜([^\n]+)\n(.*?)(?=^### |^## |\Z)',section):
  cid='card-R'+match[1];data['cards'][cid]['body_markdown']='### '+match[1]+'｜'+match[2]+'\n'+match[3]
 p=analysis/'v2/knowledge/knowledge_cards.md'
 for match in re.finditer(r'(?ms)^## (\d+)｜([^\n]+)\n(.*?)(?=^## |\Z)',p.read_text()):
  cid='card-K'+match[1].zfill(2);data['cards'][cid]={'card_id':cid,'title':match[2],'body_markdown':'## '+match[1]+'｜'+match[2]+'\n'+match[3],'concept_ids':[],'approval_status':'ai_reference_pending_human','is_official':False,'source_path':str(p.relative_to(root))}
 for overlay in overlays:
  for t in TABLES:
   for patch in overlay_records[overlay][t]:
    key=patch[KEYS[t]]
    if t=='cards' and key not in data[t]:
     if key not in allowed_new_card_ids:raise ValueError('new card admission requires explicit scope approval: '+key)
     if patch.get('is_official') or patch.get('approval_status')!='ai_reference_pending_human':raise ValueError('new card authorized only as AI reference, not formal approval')
    if t=='questions' and 'source_answer' in patch and key in data[t] and patch['source_answer']!=data[t][key]['source_answer']:raise ValueError('overlay may not rewrite source answer '+key)
    data[t][key]={**data[t].get(key,{}),**patch}
    if t=='questions' and 'explanation' in patch and patch.get('review_status')=='ai_verified_not_human':data[t][key]['explanation_origin']='native_independent_review'
 # Re-sanitize material patches from their raw source with localized images.
 for m in data['materials'].values():
  source_path=next((r['source_path'] for r in m['source_refs'] if r.get('source_path','').endswith('.md')),None)
  if source_path:
   safe,aa,issues=sanitize(m['raw_text'],lambda src:assets.resolve(src,source_path,'material'));m.update(stem_markdown=safe,stem_html=safe,assets=aa,issues=issues)
  else:m['issues']=['missing_material_source_path']
  supplements=m.get('supplementary_context',[])
  if supplements:
   added='\n\n外部补充核验信息（非原题原文）：\n'+'\n'.join(str(x.get('text',''))+' 来源：'+str(x.get('source_url','')) for x in supplements)
   safe,extra_assets,extra_issues=sanitize(added,lambda src:None);m['stem_markdown']+=safe;m['stem_html']+=safe;m['issues']+=extra_issues
 # Attach independent native reasoning, never relabel a retained source explanation as AI work.
 for ann in data['annotations'].values():
  q=data['questions'].get(ann.get('question_id'))
  if q and q.get('review_status')=='ai_verified_not_human' and q.get('explanation_origin')=='source_reference' and ann.get('steps'):
   parts=['独立推导：']+[str(x) for x in ann['steps']]
   if ann.get('option_elimination'):parts.append('选项辨析：'+str(ann['option_elimination']))
   if ann.get('boundaries'):parts.append('边界：'+str(ann['boundaries']))
   q['explanation']='\n'.join(parts);q['explanation_origin']='native_independent_review'
 # Question overlay must not bypass safe prompt validation; strict validator runs before publication.
 for q in data['questions'].values():
  q['practice_blockers']=sorted(set(q.get('practice_blockers',[])+q.get('content_issues',[])))
  if q['material_binding_status']=='verified':
   q['practice_blockers']=[x for x in q['practice_blockers'] if x!='material_or_independence_not_verified']
   if not q.get('binding_evidence_refs'):q['practice_blockers'].append('binding_evidence_missing')
  if q.get('material_id') and data['materials'][q['material_id']].get('issues'):q['practice_blockers'].append('material_content_issues')
  if q.get('holdout_reserved'):q['practice_blockers'].append('holdout_reserved')
  q['practice_ready']=not q['practice_blockers'] and q['material_binding_status']=='verified' and q['answer_status'] in ('source_only','verified')
 calculation_checks=[]
 for annotation in data['annotations'].values():
  for expr in annotation.get('expressions',[]):
   exact=evaluate(expr['expression']);reported=float(evaluate(str(expr['result'])));ok=abs(float(exact)-reported)<=max(1e-9,abs(reported)*1e-9)
   calculation_checks.append({'annotation_id':annotation['annotation_id'],'question_id':annotation['question_id'],'expression':expr['expression'],'exact_fraction':str(exact),'reported_result':reported,'matches_reported':ok,'scope':'arithmetic_only_not_source_reading_or_choice_proof'})
   if not ok:raise ValueError('calculation mismatch '+annotation['annotation_id'])
 dump(out/'calculation_checks.jsonl',calculation_checks)
 data['assets']=assets.records
 dump(out/'duplicate_candidates.jsonl',duplicate_candidates(data['questions'],data['materials']))
 dump(out/'label_proposals.jsonl',[])
 export_separated(out,data)
 dump(out/'assets_manifest.jsonl',data['assets'].values())
 dump(out/'missing_asset_references.jsonl',assets.missing.values())
 for t in TABLES:dump(out/(t+'.jsonl'),data[t].values())
 make_database(out)
 native_review_ids={a['question_id'] for a in data['annotations'].values() if is_independent_annotation(a)}
 if any(data['questions'][qid].get('holdout_reserved') for qid in native_review_ids):raise ValueError('independent review overlaps reserved holdout; freeze a clean split before publication')
 exposure_counts=dict(collections.Counter(data['questions'][qid].get('exposure_status','not_assessed') for qid in sorted(native_review_ids)))
 stats={'native_assistant_reviewed_unique':len(native_review_ids),'reviewed_exposure_status':exposure_counts,'known_public_examples_rechecked':sum(bool(data['questions'][qid].get('prior_public_example')) for qid in native_review_ids),'questions':len(data['questions']),'occurrences':len(data['occurrences']),'practice_ready':sum(q['practice_ready'] for q in data['questions'].values()),'verified_answers':sum(q['answer_status']=='verified' for q in data['questions'].values()),'answer_status':dict(collections.Counter(q['answer_status'] for q in data['questions'].values())),'material_binding':dict(collections.Counter(q['material_binding_status'] for q in data['questions'].values())),'official_cards':sum(c.get('is_official',False) for c in data['cards'].values())}
 (out/'coverage.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
 input_hashes=dict(overlay_hashes)
 for inp in [analysis/'records.jsonl',analysis/'materials_candidates.jsonl',analysis/'v2/index/canonical_topic_index.jsonl']:
  if inp.exists():input_hashes[str(inp.relative_to(root)) if inp.is_relative_to(root) else str(inp)]=hashlib.sha256(inp.read_bytes()).hexdigest()
 write_manifest(out,{'admitted_ai_reference_card_ids':sorted(allowed_new_card_ids),'producer_hashes':producer_hashes,'input_hashes':input_hashes,'version':version,'taxonomy_version':'v2-ai-1','question_count_basis':'source_qid identities; cross-qid candidate duplicates remain unresolved, not a claim of complete semantic deduplication','source_commit':next(iter(data['questions'].values()))['source_refs'][0]['source_commit'],'coverage':stats,'external_model_api_used':False,'native_assistant_reviewed_unique':len(native_review_ids),'native_model_identifier':None,'limitations':['未核材料与独立性题目隔离','AI卡待人工验收','700题目标仍需真实逐题产物与人审/迁移验收，不以原解析或mock凑数','源图许可不明，仅私有学习，不对外发布']})
 validate_release(out)
 if (dest/'current.json').exists():
  previous=json.loads((dest/'current.json').read_text())['path'];check_revision_migration(dest/previous,out)
 os.rename(out,dest/version)
 if activate:activate_release(dest,version)
 return stats
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='..');p.add_argument('--version',required=True);p.add_argument('--overlay',action='append',default=[]);p.add_argument('--no-activate',action='store_true');p.add_argument('--allow-new-card',action='append',choices=['card-R19','card-R20','card-R21'],default=[]);a=p.parse_args();print(json.dumps(build(a.root,a.version,a.overlay,not a.no_activate,a.allow_new_card),ensure_ascii=False))
