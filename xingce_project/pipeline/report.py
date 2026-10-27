import json,sqlite3,argparse
from pathlib import Path
from .store import resolve_current,connect_readonly

def report(root,queue=None):
 release=resolve_current(root);m=json.loads((release/'manifest.json').read_text());db=connect_readonly(release/'content.sqlite')
 try:
  qs=[json.loads(r[0]) for r in db.execute('SELECT data FROM questions')]
  result={'current_release':m['version'],'counts':m['counts'],'coverage':m['coverage'],'holdout_reserved':sum(q.get('holdout_reserved',False) for q in qs),'source_only_practice_ready':sum(q['practice_ready'] and q['answer_status']=='source_only' for q in qs),'verified_practice_ready':sum(q['practice_ready'] and q['answer_status']=='verified' for q in qs),'human_approved_cards':sum(json.loads(r[0]).get('is_official',False) for r in db.execute('SELECT data FROM cards')),'limitations':m.get('limitations',[])}
 finally:db.close()
 if queue and Path(queue).exists():
  db=connect_readonly(queue);states=dict(db.execute('SELECT state,count(*) FROM jobs GROUP BY state'));complete=set();reviewed=set();current_published=set();current_quarantined=set()
  for row in db.execute("SELECT request,response,state FROM jobs WHERE response IS NOT NULL"):
   request,response=json.loads(row[0]),json.loads(row[1]);state=row[2]
   if not response.get('simulation') and response.get('producer')=='native_assistant_artifact':
    reviewed.add(request['question_id'])
    if state=='published':complete.add(request['question_id'])
    if response.get('source_release')==m['version']:
     if state=='published':current_published.add(request['question_id'])
     elif state=='needs_review':current_quarantined.add(request['question_id'])
  result['production_queue']={'states':states,'unique_real_artifact_questions_reviewed':len(reviewed),'unique_real_artifact_questions_published':len(complete),'current_release_native_published':len(current_published),'current_release_native_needs_review':len(current_quarantined),'native_model_identifier':'not provided','external_api_configured':False};db.close()
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='releases');p.add_argument('--queue');p.add_argument('--output');a=p.parse_args();r=json.dumps(report(a.root,a.queue),ensure_ascii=False,indent=2)
 if a.output:Path(a.output).write_text(r)
 print(r)
