"""Real content integration, temporary PERSONAL state, never fabricates student results."""
import json,tempfile,time,sqlite3,statistics
from pathlib import Path
from fastapi.testclient import TestClient
from xingce_project.apps.workbench.backend.app import create_app,PROJECT

def run():
 report={'kind':'automated_real_release_integration_not_student_performance','checks':{},'latency_ms':{}}
 with tempfile.TemporaryDirectory() as tmp:
  client=TestClient(create_app(PROJECT/'releases',tmp))
  def get(url):
   t=time.perf_counter();r=client.get(url);report['latency_ms'].setdefault(url,[]).append(round((time.perf_counter()-t)*1000,2));assert r.status_code==200,(url,r.text);return r
  cat=get('/api/catalog').json();report['release']=cat['release'];report['counts']=cat['counts'];report['checks']['catalog_real']=True
  for q in ['增长','增长率','资料分析']:
   x=get('/api/search?q='+q).json();report['checks']['search_'+q]=x['search_mode']
  c=sqlite3.connect(PROJECT/'releases'/cat['release']/'content.sqlite');qs=[json.loads(r[0]) for r in c.execute('SELECT data FROM questions WHERE practice_ready=1 AND status="verified"')];report['ready_questions']=len(qs)
  # CUA regression: D11 example is exposure before transfer recommendations.
  probe_client=TestClient(create_app(PROJECT/'releases',Path(tmp)/'cua-probe'))
  probe=probe_client.post('/api/sessions',json={'mode':'practice','question_ids':['q-19283747']})
  if probe.status_code==200:
   ss=probe.json();aa=ss['attempts'][0];probe_client.post('/api/attempts',json={'session_id':ss['id'],'question_id':aa['question_id'],'attempt_id':aa['id'],'selected_option_ids':[],'action':'submit'})
   rr=probe_client.get('/api/attempts/'+aa['id']+'/review').json();assert any(x.get('id')=='D11' for x in rr['cards']);assert 'q-19526226' not in [x['question_id'] for x in rr['transfer']]
   personal=sqlite3.connect(Path(tmp)/'cua-probe'/'personal.sqlite');assert personal.execute('SELECT 1 FROM exposures WHERE question_id=?',('q-19526226',)).fetchone();personal.close();report['checks']['cua_d11_exposure_before_transfer']=True
  exercised=0;asset_count=0;group_count=0;supplement_count=0;seen=set()
  for q in qs:
   if q['material_id'] in seen:continue
   seen.add(q['material_id']);r=client.post('/api/sessions',json={'mode':'group','question_ids':[q['question_id']]})
   if r.status_code==422:continue
   assert r.status_code==200,r.text;s=r.json();data=get('/api/sessions/'+s['id']+'/items').json();assert all('explanation' not in i and 'verified_answer' not in i and 'concept_ids' not in i for i in data['items']);group_count+=1
   for i in data['items']:
    exercised+=1
    if i.get('material_id'):
     original=json.loads(c.execute('SELECT data FROM materials WHERE id=?',(i['material_id'],)).fetchone()[0])
     if original.get('supplementary_context'):
      assert '非原题原文' in i['material']['text'];supplement_count+=1
    for asset in i['assets']+(i.get('material') or {}).get('assets',[])+[a for o in i['options'] for a in o.get('assets',[])]:get(asset['url']);asset_count+=1
   a=s['attempts'][0];body={'session_id':s['id'],'question_id':a['question_id'],'attempt_id':a['id'],'selected_option_ids':[],'action':'submit'}
   r=client.post('/api/attempts',json=body);assert r.status_code==200;assert client.get('/api/attempts/'+a['id']+'/review').status_code==409
   assert client.post('/api/sessions/'+s['id']+'/submit',json={}).status_code==200
   rev=get('/api/attempts/'+a['id']+'/review').json();assert rev['answer'];assert rev['attempt']['grade']['release']==cat['release']
   client.post('/api/attempts/'+a['id']+'/review',json={'error_type':'数据疑点','interval_days':1})
  report['checks'].update(group_gate=True,answer_blind=True,real_material_groups=group_count,questions_in_groups=exercised,image_requests_succeeded=asset_count,supplementary_context_visible_count=supplement_count)
  stats=get('/api/stats').json();report['temporary_test_attempts']=stats['total_submitted'];exp=get('/api/exports?format=sqlite');name=exp.headers['content-disposition'].split('filename="')[1].split('"')[0]
  assert client.post('/api/restore',json={'path':name}).status_code==200;assert get('/api/stats').json()['total_submitted']==stats['total_submitted'];report['checks']['backup_restore']=True
  get('/api/today');get('/api/cards');get('/api/releases');report['checks']['p1_endpoints']=True
 path=PROJECT/'tests_backend/real_release_report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
