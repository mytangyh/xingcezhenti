import json,sqlite3,hashlib
from pathlib import Path
TABLES=('questions','occurrences','papers','materials','assets','concepts','cards','annotations','assessments','id_aliases')
def resolve_current(root):
 root=Path(root).resolve(); x=json.loads((root/'current.json').read_text());p=(root/x['path']).resolve()
 if p.parent!=root: raise ValueError('unsafe release path')
 if x.get('manifest_sha256')!=hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest():raise ValueError('current manifest hash mismatch')
 return p
def connect_readonly(path):return sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True)
def load_entity(conn,table,id):
 if table not in TABLES:raise ValueError('invalid table')
 r=conn.execute(f'SELECT data FROM {table} WHERE id=?',(id,)).fetchone()
 return json.loads(r[0]) if r else None
