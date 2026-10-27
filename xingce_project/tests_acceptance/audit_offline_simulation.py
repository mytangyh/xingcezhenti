"""Process-local outbound denial; never changes machine/firewall/browser settings."""
import socket,runpy,json,re,sys
from pathlib import Path
from urllib.parse import urlsplit
from html.parser import HTMLParser
P=Path(__file__).resolve().parents[1];attempted=[]
old_connect=socket.socket.connect;old_dns=socket.getaddrinfo;old_create=socket.create_connection
def permitted(host):return host in (None,'','localhost','127.0.0.1','::1')
def deny_connect(sock,address):
 if isinstance(address,tuple) and not permitted(address[0]):attempted.append(str(address));raise OSError('QA process external connect blocked')
 return old_connect(sock,address)
def deny_dns(host,*args,**kwargs):
 if not permitted(host):attempted.append(str(host));raise OSError('QA process external DNS blocked')
 return old_dns(host,*args,**kwargs)
def deny_create(address,*args,**kwargs):
 if not permitted(address[0]):attempted.append(str(address));raise OSError('QA process external connect blocked')
 return old_create(address,*args,**kwargs)
socket.socket.connect=deny_connect;socket.getaddrinfo=deny_dns;socket.create_connection=deny_create
probe=False;app_pass=False
try:
 try:socket.create_connection(('example.invalid',443),timeout=.1)
 except OSError:probe=True
 attempted.clear()
 try:runpy.run_path(str(P/'tests_acceptance/audit_real_release_api.py'),run_name='__main__');app_pass=True
 except SystemExit as e:app_pass=e.code in (0,False,None)
finally:socket.socket.connect=old_connect;socket.getaddrinfo=old_dns;socket.create_connection=old_create
class Refs(HTMLParser):
 def __init__(self):super().__init__();self.refs=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='script' and a.get('src'):self.refs.append(a['src'])
  if t=='link' and a.get('href') and a.get('rel') in ('stylesheet','modulepreload','preload','icon'):self.refs.append(a['href'])
dist=P/'apps/workbench/frontend/dist';r=Refs();r.feed((dist/'index.html').read_text());bad=[];checked=[]
for ref in r.refs:
 uri=urlsplit(ref);local=dist/ref.lstrip('/')
 if uri.scheme or uri.netloc or not local.is_file():bad.append(ref)
 checked.append(ref)
for css in dist.glob('assets/*.css'):
 for ref in re.findall(r'url\([\"\']?([^\"\')]+)',css.read_text()):
  if ref.startswith('data:'):continue
  uri=urlsplit(ref)
  if uri.scheme or uri.netloc:bad.append(ref)
  checked.append(ref)
report={'scope':'应用层断外联模拟＋构建资源本地性检查；非浏览器公网断连实测','process_guard_probe_pass':probe,'real_api_flow_under_guard_pass':app_pass,'external_attempts_by_application':attempted,'static_resource_refs':checked,'bad_static_resources':bad,'all_checked_resources_local':not bad,'global_machine_network_changed':False,'browser_public_network_disconnect_tested':False,'remaining':'实际浏览器在机器公网断开而localhost仍可用场景未实测；不把本报告当A09完整通过'}
(P/'acceptance/offline_simulation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));raise SystemExit(not(probe and app_pass and not attempted and not bad))
