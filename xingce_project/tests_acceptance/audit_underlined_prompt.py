import json,sqlite3,tempfile,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from xingce_project.apps.workbench.backend.app import create_app
P=Path(__file__).resolve().parents[1];root=P/'releases';v=json.load((root/'current.json').open())['version'];db=sqlite3.connect('file:'+str(root/v/'content.sqlite')+'?mode=ro',uri=True);q=json.loads(db.execute('select data from questions where id=?',('q-4637365',)).fetchone()[0]);db.close();checks={'release_all_four_options_preserve_u':all('<u>' in o['html'] for o in q['options'])};projected=[]
with tempfile.TemporaryDirectory() as d:
 client=TestClient(create_app(root,d));r=client.post('/api/sessions',json={'question_ids':[q['question_id']]});checks['session_starts']=r.status_code==200
 if r.status_code==200:
  item=client.get('/api/sessions/'+r.json()['id']+'/items').json()['items'][0];projected=item['options'];text=json.dumps(projected,ensure_ascii=False);checks['semantics_projected']=all(s in text for s in ['【划线：前来参会的人】','【划线：人家】','【划线：三轮车】','【划线：车夫】','【划线：这房子】','【划线：门】','【划线：餐馆】','【划线：服务员】']);checks['no_active_markup']=all(s not in text for s in ['<u>','onclick','<script','✅'])
 for qid,tokens in [('q-19526392',['听说','庆幸','知道','幻想']),('q-19526245',['松','石','鸡','杨','丹','白','枸'])]:
  r=client.post('/api/sessions',json={'question_ids':[qid]});checks[qid+'_start']=r.status_code==200
  if r.status_code==200:
   it=client.get('/api/sessions/'+r.json()['id']+'/items').json()['items'][0];tx=json.dumps(it['options'],ensure_ascii=False);checks[qid+'_markers']=all('【划线：'+x+'】' in tx for x in tokens)
 r=client.post('/api/sessions',json={'question_ids':['q-19526404']});checks['article_start']=r.status_code==200
 if r.status_code==200:
  it=client.get('/api/sessions/'+r.json()['id']+'/items').json()['items'][0];tx=it['material']['text'];checks['article_blank_marked']='【划线：（空白）】' in tx
report={'release':v,'question_id':q['question_id'],'checks':checks,'options':projected,'scope':'source-confirmed underline survives release safe markup and actual student API equivalent text; React remains text rendering'};(P/'acceptance/underline_api.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));assert all(checks.values())
