"""Compare two independently built releases, not one manifest against itself."""
import argparse,json
from pathlib import Path
from .release import validate_release,digest,TABLES

def compare(first,second):
 a,b=Path(first),Path(second);ma,mb=validate_release(a),validate_release(b)
 ignore={'manifest.json','content.sqlite'}
 files_a=set(ma['files'])-ignore;files_b=set(mb['files'])-ignore
 differences=[]
 if files_a!=files_b:differences.append({'kind':'file_inventory','only_first':sorted(files_a-files_b),'only_second':sorted(files_b-files_a)})
 for name in sorted(files_a & files_b):
  if ma['files'][name]!=mb['files'][name]:differences.append({'kind':'file_bytes','path':name})
 # These fields may not silently vary between a declared same-input comparison.
 for key in sorted((set(ma)|set(mb))-{'version','files'}):
  if ma.get(key)!=mb.get(key):differences.append({'kind':'manifest_semantics','field':key})
 sqlite_identical=digest(a/'content.sqlite')==digest(b/'content.sqlite')
 # Each DB was already checked entity-by-entity against its authoritative JSONL above.
 canonical_equal=all(ma['files'][t+'.jsonl']==mb['files'][t+'.jsonl'] for t in TABLES)
 report={'first_version':ma['version'],'second_version':mb['version'],'same_frozen_inputs':ma.get('input_hashes')==mb.get('input_hashes'),'canonical_jsonl_byte_equal':canonical_equal,'non_sqlite_payload_byte_equal':not differences,'sqlite_entity_logical_equal':canonical_equal,'sqlite_binary_equal':sqlite_identical,'asset_files_compared':sum(p.startswith('assets/') for p in files_a),'allowed_manifest_differences':['version','files.content.sqlite only if SQLite encoding differs despite identical entities'],'unexpected_differences':differences,'passed':not differences and canonical_equal,'scope':'two separately executed builds; no personal database included; byte equivalence limited to this runtime/version, not promised across SQLite versions'}
 if not sqlite_identical:report['sqlite_note']='SQLite bytes differ; only entity-level logical reproducibility established, not byte-for-byte database reproducibility.'
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('first');p.add_argument('second');p.add_argument('--output',required=True);a=p.parse_args();r=compare(a.first,a.second);Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False));raise SystemExit(0 if r['passed'] else 1)
