"""Serve only original synthetic fixtures. No real data or network inputs."""
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'xingce_project')]
from pipeline.release import TABLES,dump,make_database,write_manifest,activate_release
from xingce_project.apps.workbench.backend.app import create_app
import uvicorn

def seed(root,version):
 p=root/version;p.mkdir(parents=True)
 questions=[]
 for i in range(1,9):
  text=f'原创合成测试 {i}：1 加 1 等于多少？'
  questions.append(dict(question_id=f'q-fixture-{i}',revision=1,normalized_module='资料分析',answer_status='verified',practice_ready=True,material_id=None,stem_markdown=text,stem_html=text,
    options=[dict(option_id='A',label='A',text='2',html='2'),dict(option_id='B',label='B',text='3',html='3')],source_answer={'option_ids':['A']},verified_answer={'option_ids':['A'],'evidence_refs':['original synthetic arithmetic']},
    material_binding_status='verified',binding_evidence_refs=['standalone synthetic'],practice_blockers=[],concept_ids=[],source_refs=[],classification_status='unknown',explanation='原创算术测试，1+1=2。',assets=[]))
 for t in TABLES:dump(p/(t+'.jsonl'),questions if t=='questions' else [])
 make_database(p);write_manifest(p,{'version':version})

if __name__=='__main__':
 with tempfile.TemporaryDirectory(prefix='xingce-e2e-') as d:
  root=Path(d)/'releases';seed(root,'synthetic-v1');seed(root,'synthetic-v2');activate_release(root,'synthetic-v1')
  uvicorn.run(create_app(root,Path(d)/'user'),host='127.0.0.1',port=8766)
