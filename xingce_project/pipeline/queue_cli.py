"""Prepare durable production requests without making network calls."""
import argparse,json,sqlite3
from pathlib import Path
from .queue import Queue
from .release import validate_release

def prepare(release,queue_path,limit=700):
 m=validate_release(release);db=sqlite3.connect('file:'+str((Path(release)/'content.sqlite').resolve())+'?mode=ro',uri=True);queue=Queue(queue_path);count=0
 try:
  # Priority goes to existing AI semantic annotations, never conflated with completed distillation.
  rows=db.execute('SELECT data FROM questions ORDER BY practice_ready DESC,question_id')
  for row in rows:
   q=json.loads(row[0]);request={'question_id':q['question_id'],'question_revision':q['revision'],'material_id':q['material_id'],'material_revision':None,'prompt_version':'distillation-draft-v1','taxonomy_version':m['taxonomy_version'],'model_config':{'provider':'unconfigured','real_model':False},'release':m['version']}
   if q['material_id']:
    mat=json.loads(db.execute('SELECT data FROM materials WHERE id=?',(q['material_id'],)).fetchone()[0]);request['material_revision']=mat['revision']
   key=queue.enqueue(request)
   if not q['practice_ready']:queue._set(key,'blocked_input',error='material_or_prompt_not_verified')
   else:queue.run(key,provider=None)
   count+=1
   if count>=limit:break
  return {'prepared':count,'real_model_calls':0,'states':dict(queue.db.execute('SELECT state,count(*) FROM jobs GROUP BY state'))}
 finally:db.close();queue.db.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--release',required=True);p.add_argument('--queue',required=True);p.add_argument('--limit',type=int,default=700);a=p.parse_args();print(json.dumps(prepare(a.release,a.queue,a.limit),ensure_ascii=False))
