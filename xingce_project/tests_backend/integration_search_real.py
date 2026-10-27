"""Read/search actual release via API, only temporary personal exposure state."""
import json,sqlite3,tempfile,time
from pathlib import Path
from fastapi.testclient import TestClient
from xingce_project.apps.workbench.backend.app import create_app,PROJECT

def run():
 root=PROJECT/'releases';v=json.loads((root/'current.json').read_text())['version'];c=sqlite3.connect(root/v/'content.sqlite')
 q=json.loads(c.execute('SELECT data FROM questions WHERE practice_ready=1 AND status="verified" AND material_id IS NOT NULL LIMIT 1').fetchone()[0]);qid=q['question_id'];occ=json.loads(c.execute('SELECT data FROM occurrences WHERE json_extract(data,"$.question_id")=? LIMIT 1',(qid,)).fetchone()[0]);p=json.loads(c.execute('SELECT data FROM papers WHERE id=?',(occ['paper_id'],)).fetchone()[0])
 report={'release':v,'scope':'real release search integration; not user study results','checks':{},'timings_ms':{}}
 with tempfile.TemporaryDirectory() as temp:
  client=TestClient(create_app(root,temp))
  def get(path,params=None):
   t=time.perf_counter();r=client.get(path,params=params);report['timings_ms'][path+str(params or '')]=round((time.perf_counter()-t)*1000,2);assert r.status_code==200,r.text;return r.json()
  metadata=get('/api/search/filters');assert str(p['exam_year_label']) in metadata['years'];report['checks']['metadata']=True
  filters={'q':qid.removeprefix('q-'),'module':q['normalized_module'],'year':p['exam_year_label'],'paper_type':p['paper_type'],'concept_id':(q.get('concept_ids') or [''])[0]}
  data=get('/api/search',filters);assert [x['question_id'] for x in data['items']]==[qid];report['checks']['qid_module_year_type_concept_combined']=True
  assert all(x not in json.dumps(data) for x in ['verified_answer','source_answer','explanation','concept_ids']);report['checks']['answer_blind']=True
  sid=client.post('/api/sessions',json={'mode':'practice','question_ids':[qid]}).json()['id'];assert client.get('/api/sessions/'+sid+'/items').status_code==200;report['checks']['explicit_single_question_start']=True
  filters['year']='1900';assert not get('/api/search',filters)['items'];report['checks']['impossible_filter_empty']=True
  if q.get('material_id'):
   mats=get('/api/search',{'kind':'materials','q':qid,'year':p['exam_year_label'],'paper_type':p['paper_type']});assert any(x['id']==q['material_id'] for x in mats['items']);assert all('raw_text' not in x for x in mats['items']);report['checks']['material_context']=True
   urls=[a['url'] for m in mats['items'] for a in m['assets']]
   for url in urls:assert client.get(url).status_code==200
   report['checks']['material_image_count']=len(urls)
  expected=set()
  for x, in c.execute('SELECT data FROM questions WHERE practice_ready=1 AND status="verified"'):
   r=json.loads(x)
   if not r.get('holdout_reserved'):expected.add(r['question_id'])
  result=get('/api/search',{'limit':100});assert all(x['question_id'] in expected for x in result['items']);report['checks']['default_practice_ready_verified']=True
  for module in ['资料分析','判断推理','言语理解与表达']:
   a=get('/api/cards',{'module':module});b=get('/api/search',{'kind':'cards','module':module,'limit':100});assert {x['card_id'] for x in a['items']}=={x['card_id'] for x in b['items']};assert a['items'];report['checks']['cards_filter_'+module]=len(a['items'])
  assert not get('/api/cards',{'module':'不存在的模块'})['items'];report['checks']['cards_invalid_module_empty']=True
  with sqlite3.connect(Path(temp)/'personal.sqlite') as d:assert d.execute('SELECT 1 FROM exposures WHERE question_id=?',(qid,)).fetchone()
  report['checks']['search_records_exposure']=True
 (PROJECT/'tests_backend/real_search_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
