import re,html,hashlib,shutil
from html.parser import HTMLParser
from pathlib import Path
LEAK=re.compile(r'(?:正确|参考|标准)?答案\s*(?:为|是|[:：])\s*[A-HＡ-Ｈ]|故(?:本题)?(?:选|正确)|本题(?:考查|考察)|【解析】|答案解析|解析\s*[:：]',re.I)
MARK=re.compile('[✅✔✓☑]')
class Cleaner(HTMLParser):
 def __init__(self,asset):super().__init__(convert_charrefs=True);self.out=[];self.hidden=0;self.asset=asset;self.assets=[];self.issues=[]
 def handle_starttag(self,t,a):
  if t in ('script','style','iframe','object'):self.hidden+=1;self.issues.append('unsafe_html');return
  if self.hidden:return
  if t=='img':
   x=self.asset(dict(a).get('src',''))
   if x:self.assets.append(x);self.out.append('<img src="'+html.escape(x['path'],quote=True)+'" />')
   else:self.issues.append('missing_or_unsafe_image')
  elif t in ('br','p','div','tr'):self.out.append('\n')
  elif t in ('u','sub','sup','b','strong','em','table','td','th'):self.out.append('<'+t+'>')
 def handle_endtag(self,t):
  if t in ('script','style','iframe','object'):self.hidden=max(0,self.hidden-1)
  elif not self.hidden and t in ('u','sub','sup','b','strong','em','table','td','th'):self.out.append('</'+t+'>')
 def handle_data(self,d):
  if not self.hidden:self.out.append(html.escape(MARK.sub('',d)))
def sanitize(text,asset):
 text=str(text);text=re.sub(r'!\[[^\]]*\]\(([^ )]+)(?:[^)]*)\)',lambda m:'<img src="'+html.escape(m[1],quote=True)+'">',text)
 p=Cleaner(asset);p.feed(text);p.close();clean=''.join(p.out).strip()
 if LEAK.search(text) or LEAK.search(html.unescape(clean)):p.issues.append('suspected_answer_leak')
 return clean,p.assets,sorted(set(p.issues))
class Assets:
 def __init__(self,repo,out):self.repo=Path(repo).resolve();self.out=Path(out);self.records={};self.cache={};self.missing={}
 def resolve(self,src,source_path,role='prompt'):
  if not src or re.match(r'(?i)(https?:|data:|javascript:|//)',src):return None
  p=(self.repo/Path(source_path).parent/src).resolve()
  if not p.is_relative_to(self.repo) or not p.is_file() or p.suffix.lower() not in ('.png','.jpg','.jpeg','.gif','.webp','.jfif'):
   key=source_path+'|'+src+'|'+role;self.missing[key]={'source_path':source_path,'reference':src,'role':role,'availability':'missing_or_unsupported'};return None
  k=str(p)
  if k not in self.cache:
   raw=p.read_bytes()
   if p.suffix.lower()=='.jfif' and not raw.startswith(b'\xff\xd8'):return None
   digest=hashlib.sha256(raw).hexdigest();ext='.jpg' if p.suffix.lower()=='.jfif' else p.suffix.lower();rel='assets/'+digest+ext;dest=self.out/rel;dest.parent.mkdir(exist_ok=True)
   if not dest.exists():shutil.copyfile(p,dest)
   self.cache[k]=self.records.get('a-'+digest) or {'asset_id':'a-'+digest,'path':rel,'sha256':digest,'availability':'available','source_paths':[],'roles':[],'license_status':'source_license_unconfirmed_private_study_only'}
  a=self.cache[k];sp=str(p.relative_to(self.repo))
  if sp not in a['source_paths']:a['source_paths'].append(sp)
  if role not in a['roles']:a['roles'].append(role)
  self.records[a['asset_id']]=a
  return {'asset_id':a['asset_id'],'path':a['path'],'role':role}

class StrictMarkup(HTMLParser):
 def handle_startendtag(self,t,attrs):
  self.handle_starttag(t,attrs)
  if t not in ('img','br'):self.handle_endtag(t)
 def __init__(self,root):super().__init__(convert_charrefs=True);self.root=Path(root)
 def handle_starttag(self,t,attrs):
  if t not in ('img','u','sub','sup','b','strong','em','table','td','th','br'):raise ValueError('unsafe tag '+t)
  if t!='img' and attrs:raise ValueError('unsafe attributes')
  if t=='img':
   if len(attrs)!=1 or attrs[0][0]!='src':raise ValueError('unsafe image attributes')
   src=attrs[0][1]
   if not re.fullmatch(r'assets/[a-f0-9]{64}\.(png|jpg|jpeg|gif|webp)',src):raise ValueError('unsafe image path')
   if not (self.root/src).is_file():raise ValueError('missing image')
 def handle_endtag(self,t):
  if t not in ('u','sub','sup','b','strong','em','table','td','th'):raise ValueError('unsafe closing tag')
def validate_safe_markup(text,root):
 p=StrictMarkup(root);p.feed(str(text));p.close()
 if MARK.search(text):raise ValueError('answer marker in practice')
