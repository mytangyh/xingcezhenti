"""Full-index/eligible-prompt integration; private input, temporary QA state only."""
import json,sqlite3,tempfile,time
from pathlib import Path
from fastapi.testclient import TestClient
from xingce_project.apps.workbench.backend.app import create_app,PROJECT

def run():
 with tempfile.TemporaryDirectory() as tmp:
  client=TestClient(create_app(PROJECT/'releases',tmp));start=time.perf_counter()
  response=client.get('/api/coverage');assert response.status_code==200,response.text
  cov=response.json();v=cov['release']
  with sqlite3.connect((PROJECT/'releases'/v/'content.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as c:
   assert cov['summary']['identities']==c.execute('SELECT COUNT(*) FROM questions').fetchone()[0]
   assert cov['summary']['occurrences']==c.execute('SELECT COUNT(*) FROM occurrences').fetchone()[0]
   ids=[r[0] for r in c.execute('SELECT id FROM questions WHERE practice_ready=1 AND status="verified"')]
  plans={}
  for budget in (20,40):
   p=client.get('/api/today',params={'budget_minutes':budget}).json();assert p['cold_start'];assert p['estimated_minutes']<=budget*.8
   planned=[i for t in p['items'] for i in t['question_ids']];assert len(planned)==len(set(planned));assert set(planned)<=set(ids);plans[budget]={'count':len(planned),'minutes':p['estimated_minutes']}
  urls=set();count=0
  for start_index in range(0,len(ids),150):
   r=client.post('/api/sessions',json={'mode':'practice','question_ids':ids[start_index:start_index+150],'planned_release':v});assert r.status_code==200,r.text
   r=client.get('/api/sessions/'+r.json()['id']+'/items');assert r.status_code==200
   for q in r.json()['items']:
    assert not {'verified_answer','source_answer','explanation','concept_ids'} & set(q)
    count+=1
    urls.update(a['url'] for a in q['assets']+(q.get('material') or {}).get('assets',[])+[a for o in q['options'] for a in o.get('assets',[])])
  for url in urls:assert client.get(url).status_code==200,url
  assert count==len(ids)
  result={'release':v,'summary':cov['summary'],'plans':plans,'eligible_prompts_checked':count,'unique_assets_loaded':len(urls),'seconds':round(time.perf_counter()-start,2),'scope':'temporary QA records; no semantic image review, no user learning results'}
 (PROJECT/'tests_backend/real_learning_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
