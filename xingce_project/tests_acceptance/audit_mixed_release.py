import json,tempfile,sqlite3,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from xingce_project.apps.workbench.backend.app import create_app
P=Path(__file__).resolve().parents[1];root=P/'releases';v=json.loads((root/'current.json').read_text())['version'];c=sqlite3.connect(root/v/'content.sqlite');qs={r[0]:json.loads(r[1]) for r in c.execute('select id,data from questions')};c.close();checks={};cases={}
with tempfile.TemporaryDirectory() as d:
 client=TestClient(create_app(root,d))
 risks=[q for q in qs.values() if q['material_binding_status']=='verified' and q['answer_status'] in ('disputed','unresolved')]
 for q in risks:
  status=client.post('/api/sessions',json={'question_ids':[q['question_id']],'allow_source_only':True}).status_code;cases[q['question_id']]={'status':q['answer_status'],'http':status}
 checks['all_new_unresolved_disputed_denied']=all(x['http']==422 for x in cases.values())
 checks['complete_long_article_group_starts']=client.post('/api/sessions',json={'mode':'group','question_ids':['q-19526409']}).status_code==200
 rr=client.post('/api/sessions',json={'mode':'practice','question_ids':['q-19526404']});checks['verified_long_article_single_starts']=rr.status_code==200
 if rr.status_code==200:
  item=client.get('/api/sessions/'+rr.json()['id']+'/items').json()['items'][0];checks['full_long_article_present']=len(item['material']['text'])>800;checks['formula_asset_present']=bool(item['material']['assets']);checks['formula_asset_fetchable']=all(client.get(a['url']).status_code==200 for a in item['material']['assets'])
 checks['unsafe_long_group_not_misrepresented_complete']=client.post('/api/sessions',json={'mode':'group','question_ids':['q-19526404']}).status_code==422 if qs['q-19526407']['answer_status']=='unresolved' else True
 checks['new_math_replacement_ready']=client.post('/api/sessions',json={'question_ids':['q-2264411']}).status_code==200
out={'release':v,'new_quarantine_count':len(cases),'quarantine_cases':cases,'checks':checks,'scope':'当前真实发布数据的长文/公式/数学替补/全部新增未决API检查；不是盲抽或用户行为'};(P/'acceptance/mixed_release_api.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False));raise SystemExit(not all(checks.values()))
