"""Import genuine native-assistant artifacts, not mock/external API responses."""
import argparse,json,sqlite3,hashlib
from pathlib import Path
from .queue import Queue
from .release import validate_release
from .provenance import is_independent_annotation

def import_native(release,queue_path):
 release=Path(release).resolve();manifest=validate_release(release);db=sqlite3.connect('file:'+str(release/'content.sqlite')+'?mode=ro',uri=True);queue=Queue(queue_path)
 imported=[];reviewed=[];quarantined=[]
 try:
  annotations={}
  for row in db.execute('SELECT data FROM annotations'):
   a=json.loads(row[0])
   # Base semantic labels/source-analysis copies do not qualify as new independent review.
   if a.get('status')=='reference_not_human_approved':continue
   if is_independent_annotation(a):
    annotations.setdefault(a['question_id'],[]).append(a)
  for row in db.execute('SELECT data FROM questions'):
   q=json.loads(row[0]);aa=annotations.get(q['question_id'],[])
   if not aa or q.get('holdout_reserved') or q.get('review_status') not in ('ai_verified_not_human','ai_disagreement_pending','awaiting_adjudication'):continue
   reviewed.append(q['question_id'])
   mid=q.get('material_id');mr=None
   if mid:mr=json.loads(db.execute('SELECT data FROM materials WHERE id=?',(mid,)).fetchone()[0])['revision']
   request={'question_id':q['question_id'],'question_revision':q['revision'],'material_id':mid,'material_revision':mr,'prompt_version':'native-independent-review-v1','taxonomy_version':manifest['taxonomy_version'],'model_config':{'provider':'native_assistant_artifact','model_identifier':None},'release':manifest['version']}
   response={'simulation':False,'real_model_distillation':True,'producer':'native_assistant_artifact','model_identifier':None,'model_identifier_status':'not_provided','external_api_calls':0,'token_usage':None,'cost_usd':None,'cost_status':'not_a_billed_external_api_call','question_id':q['question_id'],'question_revision':q['revision'],'answer_status':q['answer_status'],'source_release':manifest['version'],'artifact_sha256':manifest['files']['annotations.jsonl'],'annotation_ids':[a['annotation_id'] for a in aa],'verified_answer':q['verified_answer'],'binding_evidence_refs':q['binding_evidence_refs'],'scope':'native assistant original-material review and independent reasoning; AI, not human approved'}
   key=queue.enqueue(request)
   if queue.get(key)['state']=='published':imported.append(q['question_id']);continue
   payload=json.dumps(response,ensure_ascii=False,sort_keys=True);queue._spool_write(key,payload);queue._set(key,'response_received',response=payload,error=None)
   def validator(r):
    if r['simulation'] or r['producer']!='native_assistant_artifact' or not r['annotation_ids'] or not r['verified_answer']['evidence_refs']:raise ValueError('invalid native review artifact')
   if q['answer_status']!='verified' or not q['practice_ready']:
    with queue.db:queue.db.execute('INSERT OR REPLACE INTO outputs VALUES(?,?)',(key,payload))
    queue._set(key,'needs_review',error='native_review_completed_but_answer_or_practice_is_quarantined');quarantined.append(q['question_id'])
   else:
    queue.run(key,validator=validator);queue.publish(key);imported.append(q['question_id'])
  states=dict(queue.db.execute('SELECT state,count(*) FROM jobs GROUP BY state'));completed=set();requested=set()
  for r in queue.db.execute('SELECT request,state FROM jobs'):
   qid=json.loads(r['request'])['question_id'];requested.add(qid)
   if r['state']=='published':completed.add(qid)
  report={'release':manifest['version'],'native_artifacts_reviewed':len(reviewed),'native_artifacts_quarantined':len(quarantined),'native_quarantined_question_ids':quarantined,'native_artifacts_imported':len(imported),'native_question_ids':imported,'all_queue_states':states,'distinct_completed_questions':len(completed),'distinct_queued_questions':len(requested),'distinct_unfulfilled_questions':len(requested-completed),'external_api_calls':0,'model_identifier':'not provided','human_approved':False,'note':'legacy unconfigured requests keep immutable keys; completed coverage is deduplicated by question ID, not summed job states'}
  return report
 finally:queue.db.close();db.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--queue',required=True);p.add_argument('--report');a=p.parse_args();r=import_native(a.release,a.queue);text=json.dumps(r,ensure_ascii=False,indent=2)
 if a.report:Path(a.report).write_text(text)
 print(text)
