"""Durable idempotent production queue. No network or paid provider implemented."""
import hashlib,json,sqlite3,time,os
from pathlib import Path
STATES=('pending','running','response_received','persisted','validated','published','retryable_error','blocked_input','needs_review')
class Queue:
 def __init__(self,path):
  self.path=Path(path);self.spool=Path(str(path)+'.responses');self.spool.mkdir(parents=True,exist_ok=True);self.memory_responses={}
  self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
  self.db.executescript('''CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,request TEXT NOT NULL,state TEXT NOT NULL,attempts INTEGER DEFAULT 0,response TEXT,error TEXT,updated REAL NOT NULL,next_retry_at REAL DEFAULT 0); CREATE TABLE IF NOT EXISTS outputs(id TEXT PRIMARY KEY,payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT,state TEXT,details TEXT,created REAL); CREATE TABLE IF NOT EXISTS usage_ledger(call_id INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT,attempt INTEGER,started REAL,finished REAL,provider_kind TEXT,status TEXT,cost_status TEXT,cost_usd REAL);''')
  if 'next_retry_at' not in {r[1] for r in self.db.execute('PRAGMA table_info(jobs)')}:self.db.execute('ALTER TABLE jobs ADD COLUMN next_retry_at REAL DEFAULT 0')
  self.db.commit()
 def enqueue(self,request):
  required=('question_id','question_revision','material_id','material_revision','prompt_version','taxonomy_version','model_config')
  if any(k not in request for k in required):raise ValueError('incomplete cache key')
  s=json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(',',':'));key=hashlib.sha256(s.encode()).hexdigest()
  self.db.execute('INSERT OR IGNORE INTO jobs(id,request,state,updated) VALUES(?,?,?,?)',(key,s,'pending',time.time()));self.db.commit();return key
 def get(self,key):
  r=self.db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone();return dict(r) if r else None
 def _spool_write(self,key,payload):
  target=self.spool/(key+'.json');tmp=self.spool/(key+'.tmp')
  with open(tmp,'w') as f:f.write(payload);f.flush();os.fsync(f.fileno())
  os.replace(tmp,target)
  fd=os.open(self.spool,os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
 def recover(self,older_than_seconds=600):
  # An ambiguous in-flight request is never blindly repeated. Receipt spool repairs DB persistence.
  jobs=list(self.db.execute("SELECT id,response FROM jobs WHERE state='running' AND updated<?",(time.time()-older_than_seconds,)))
  for job in jobs:
   p=self.spool/(job['id']+'.json')
   if p.exists():self._set(job['id'],'response_received',response=p.read_text(),error=None)
   elif job['response']:self._set(job['id'],'response_received',error=None)
   else:self._set(job['id'],'needs_review',error='ambiguous_provider_outcome_no_receipt; do not repeat automatically')
 def run(self,key,provider=None,validator=None,fail_after=None,max_attempts=3,retry_delay=30):
  job=self.get(key)
  if not job:raise KeyError(key)
  if job['state'] in ('published','needs_review','blocked_input'):return job
  receipt=self.spool/(key+'.json')
  if job['response'] is None and (receipt.exists() or key in self.memory_responses):
   payload=receipt.read_text() if receipt.exists() else self.memory_responses[key]
   if not receipt.exists():self._spool_write(key,payload)
   with self.db:self.db.execute('UPDATE usage_ledger SET finished=?,status=? WHERE job_id=? AND status=?',(time.time(),'response_received',key,'started'))
   self._set(key,'response_received',response=payload,error=None);self.memory_responses.pop(key,None);job=self.get(key)
  if job['state']=='running':return job
  if job['state']=='retryable_error' and job['next_retry_at']>time.time():return job
  if job['response'] is None:
   if provider is None:
    self._set(key,'blocked_input',error='real_model_configuration_missing; no paid fallback');return self.get(key)
   if job['attempts']>=max_attempts:self._set(key,'needs_review',error='retry_budget_exhausted');return self.get(key)
   with self.db:
    changed=self.db.execute("UPDATE jobs SET state='running',attempts=attempts+1,updated=? WHERE id=? AND state IN ('pending','retryable_error')",(time.time(),key)).rowcount
   if not changed:return self.get(key)
   with self.db:
    cur=self.db.execute('INSERT INTO usage_ledger(job_id,attempt,started,provider_kind,status,cost_status,cost_usd) VALUES(?,?,?,?,?,?,?)',(key,job['attempts']+1,time.time(),'mock' if isinstance(provider,MockProvider) else 'explicit_callback','started','simulation_zero' if isinstance(provider,MockProvider) else 'not_reported',0 if isinstance(provider,MockProvider) else None));call_id=cur.lastrowid
   try:response=provider(json.loads(job['request']))
   except Exception as e:
    with self.db:self.db.execute('UPDATE usage_ledger SET finished=?,status=? WHERE call_id=?',(time.time(),'provider_error',call_id))
    self._set(key,'retryable_error',error=str(e),next_retry_at=time.time()+min(600,retry_delay*(2**job['attempts'])));return self.get(key)
   # Persistence errors are NOT provider errors. Keep running/ambiguous, never mark retryable.
   payload=json.dumps(response,ensure_ascii=False);self.memory_responses[key]=payload
   self._spool_write(key,payload)
   with self.db:self.db.execute('UPDATE usage_ledger SET finished=?,status=? WHERE job_id=? AND status=?',(time.time(),'response_received',key,'started'))
   self._set(key,'response_received',response=payload,error=None);self.memory_responses.pop(key,None)
  if fail_after=='response_received':raise RuntimeError('injected persistence failure')
  job=self.get(key);response=json.loads(job['response'])
  with self.db:self.db.execute('INSERT OR IGNORE INTO outputs VALUES(?,?)',(key,job['response']))
  self._set(key,'persisted')
  if fail_after=='persisted':raise RuntimeError('injected validation interruption')
  try:
   if not response.get('simulation') and validator is None:raise ValueError('validator_required_for_real_result')
   if validator:validator(response)
  except Exception as e:self._set(key,'needs_review',error=str(e));return self.get(key)
  self._set(key,'validated');return self.get(key)
 def publish(self,key):
  job=self.get(key)
  if job['state']!='validated':raise ValueError('not validated')
  response=json.loads(job['response'])
  if response.get('simulation') or not response.get('real_model_distillation'):raise ValueError('mock or unproven result cannot be published')
  self._set(key,'published')
 def _set(self,key,state,**fields):
  if state not in STATES:raise ValueError(state)
  if not set(fields)<={'response','error','next_retry_at'}:raise ValueError('invalid fields')
  with self.db:
   self.db.execute('UPDATE jobs SET state=?,updated=?'+''.join(','+k+'=?' for k in fields)+' WHERE id=?',[state,time.time(),*fields.values(),key])
   self.db.execute('INSERT INTO events(job_id,state,details,created) VALUES(?,?,?,?)',(key,state,json.dumps(fields,ensure_ascii=False),time.time()))
class MockProvider:
 """Tests only; response always advertises simulation."""
 def __init__(self,failures=0):self.calls=0;self.failures=failures
 def __call__(self,request):
  self.calls+=1
  if self.calls<=self.failures:raise RuntimeError('simulated provider failure')
  return {'simulation':True,'real_model_distillation':False,'question_id':request['question_id'],'status':'mock_only'}
