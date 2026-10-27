"""Small strict validator for the schema subset shipped here (no remote refs)."""
import json,re
from pathlib import Path
TYPES={'object':dict,'array':list,'string':str,'integer':int,'boolean':bool}
def validate(instance,schema,path='$'):
 kind=schema.get('type')
 if kind and (not isinstance(instance,TYPES[kind]) or (kind=='integer' and isinstance(instance,bool))):raise ValueError(path+' invalid type')
 if 'pattern' in schema and not re.fullmatch(schema['pattern'],instance):raise ValueError(path+' invalid pattern')
 if 'enum' in schema and instance not in schema['enum']:raise ValueError(path+' invalid enum')
 if 'minimum' in schema and instance<schema['minimum']:raise ValueError(path+' below minimum')
 if isinstance(instance,dict):
  for k in schema.get('required',[]):
   if k not in instance:raise ValueError(path+' missing '+k)
  for k,v in instance.items():
   if k in schema.get('properties',{}):validate(v,schema['properties'][k],path+'.'+k)
 if isinstance(instance,list) and 'items' in schema:
  for i,v in enumerate(instance):validate(v,schema['items'],path+f'[{i}]')
def load_schemas():
 base=Path(__file__).resolve().parent.parent/'schemas';return {p.name.removesuffix('.schema.json'):json.loads(p.read_text()) for p in base.glob('*.schema.json')}
