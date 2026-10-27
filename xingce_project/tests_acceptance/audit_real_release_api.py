"""Real content plus isolated synthetic QA attempts, never user performance."""
import json,sqlite3,sys,tempfile,time,statistics
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from xingce_project.apps.workbench.backend.app import create_app
P=Path(__file__).resolve().parents[1];root=P/'releases';version=json.loads((root/'current.json').read_text())['version'];checks={};durations={}
with tempfile.TemporaryDirectory() as d:
 client=TestClient(create_app(root,Path(d)));t=time.perf_counter();r=client.get('/api/catalog');durations['catalog_ms']=(time.perf_counter()-t)*1000;checks['catalog_real']=r.status_code==200
 r=client.post('/api/sessions',json={'mode':'group','question_ids':['q-19283752']});checks['group_start']=r.status_code==200;s=r.json();sid=s['id']
 checks['group_five']=len(s['question_ids'])==5
 r=client.get('/api/sessions/'+sid+'/items');checks['items_no_answer']=r.status_code==200 and all(x not in r.text for x in ['verified_answer','source_answer','explanation','concept_ids'])
 items=r.json()['items'];checks['real_material_present']=all(x.get('material',{}).get('text') or x.get('material',{}).get('assets') for x in items)
 q=next(x for x in items if x['question_id']=='q-19283765');checks['image_options_assigned']=all(x.get('assets') for x in q['options'])
 for x in q['options']:
  for asset in x.get('assets',[]):checks['asset_'+x['label']]=client.get(asset['url']).status_code==200
 first=s['attempts'][0];q0=next(x for x in items if x['question_id']==first['question_id']);payload={'session_id':sid,'question_id':first['question_id'],'attempt_id':first['id'],'selected_option_ids':[q0['options'][0]['option_id']],'action':'submit'}
 a=client.post('/api/attempts',json=payload).json();payload['selected_option_ids']=[q0['options'][1]['option_id']];b=client.post('/api/attempts',json=payload).json();checks['double_submit_frozen']=a==b
 checks['group_review_blocked']=client.get('/api/attempts/'+first['id']+'/review').status_code==409
 checks['reload_restores']=TestClient(create_app(root,Path(d))).get('/api/sessions/'+sid).json()['attempts'][0]['selected_option_ids']==a['selected_option_ids']
 checks['whole_group_submit']=client.post('/api/sessions/'+sid+'/submit',json={}).status_code==200
 checks['review_after_submit']=client.get('/api/attempts/'+first['id']+'/review').status_code==200
 for qid in ['q-19526229','q-19526231']:
  rr=client.post('/api/sessions',json={'question_ids':[qid],'allow_source_only':True})
  cc=sqlite3.connect(root/version/'content.sqlite');source_q=json.loads(cc.execute('select data from questions where id=?',(qid,)).fetchone()[0]);cc.close()
  if source_q['answer_status']=='unresolved':checks['unresolved_blocked_'+qid]=rr.status_code==422
  else:
   checks['supplemented_verified_'+qid]=rr.status_code==200 and source_q['answer_status']=='verified'
   shown=client.get('/api/sessions/'+rr.json()['id']+'/items').json()['items'][0]['material']['text'] if rr.status_code==200 else ''
   checks['external_calendar_visible_'+qid]=all(x in shown for x in ['2024','3','5']) and ('补充' in shown or '外部' in shown)
 checks['chinese_search']=client.get('/api/search',params={'q':'增长率'}).status_code==200
 checks['due_endpoint']=client.get('/api/reviews/due').status_code==200
 stats=client.get('/api/stats').json();checks['only_qa_group_counted']=stats['total_submitted']==5
 def persisted():
  c=sqlite3.connect(Path(d)/'personal.sqlite');result={t:[list(r) for r in c.execute('select * from '+t+' order by 1')] for (t,) in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'")};c.close();return result
 before_persisted=persisted()
 rr=client.get('/api/exports?format=sqlite');checks['sqlite_export']=rr.status_code==200;filename=rr.headers['content-disposition'].split('filename="')[1].split('"')[0]
 checks['restore']=client.post('/api/restore',json={'path':filename}).status_code==200
 checks['restore_persisted_records_exact']=persisted()==before_persisted
out={'release':version,'checks':checks,'passed':sum(checks.values()),'total':len(checks),'cloud_inprocess_timing_ms':durations,'scope':'真实发布内容+独立临时个人库的API集成；作答是QA合成，不是用户迁移；尚非浏览器断网/人工图像映射验收'}
(P/'acceptance/real_release_api.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False));raise SystemExit(not all(checks.values()))
