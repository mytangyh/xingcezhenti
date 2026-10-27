// Original synthetic fixtures only. Run after building frontend and starting serve.py.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
const context=await browser.newContext();const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const base='http://127.0.0.1:8766';
async function api(path,data){const r=await context.request[data===undefined?'get':'post'](base+'/api'+path,data===undefined?{}:{data});assert(r.ok(),await r.text());return r.json()}
try{
 await page.goto(base);await page.getByRole('heading',{name:'今天，先练一个专题'}).waitFor();
 await page.getByRole('button',{name:'全库覆盖',exact:true}).click();await page.getByRole('heading',{name:'高频考点与覆盖地图'}).waitFor();
 await page.getByText('8 个 source-qid 身份',{exact:false}).waitFor();
 await page.getByRole('button',{name:'今日精练',exact:true}).click();
 await page.getByLabel('计划预算',{exact:true}).selectOption('20');
 await page.getByRole('button',{name:'开始精练',exact:false}).evaluate(b=>{b.click();b.click()});
 await page.getByText('原创合成测试 1：1 加 1 等于多少？',{exact:false}).first().waitFor();
 let sessions=(await api('/sessions')).items;assert.equal(sessions.length,1,'duplicate click created sessions');
 const sid=sessions[0].id;
 // Actual Chromium offline mode: fetch must fail, then online recovery.
 await context.setOffline(true);
 assert.equal(await page.evaluate(async()=>{try{await fetch('/api/catalog');return false}catch{return true}}),true);
 await context.setOffline(false);await page.reload();await page.getByRole('button',{name:'回到训练',exact:false}).click();
 // API integration through browser request transport, persistence and version locking.
 let s=await api('/sessions/'+sid);assert.equal(s.release,'synthetic-v1');
 await page.getByRole('button',{name:'暂停',exact:true}).click();await page.getByRole('heading',{name:'练习已暂停'}).waitFor();await page.reload();await page.getByRole('button',{name:'回到训练',exact:false}).click();assert((await api('/sessions/'+sid)).paused);
 await page.getByRole('button',{name:'继续练习',exact:true}).click();assert.equal((await api('/sessions/'+sid)).paused,null);
 await api('/releases/synthetic-v2/activate',{});assert.equal((await api('/sessions/'+sid+'/items')).session.release,'synthetic-v1');
 s=await api('/sessions/'+sid);const a=s.attempts[0];
 const body={session_id:sid,question_id:a.question_id,attempt_id:a.id,action:'submit',selected_option_ids:['A']};
 page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'提交整组',exact:true}).click();await page.getByText('已提交 · 计时停止',{exact:true}).waitFor();await api('/attempts',body);await api('/sessions/'+sid+'/submit',{});
 await page.reload();assert.equal((await api('/sessions/'+sid)).status,'submitted');
 const exported=await context.request.get(base+'/api/exports?format=sqlite');assert(exported.ok());
 const backup=(await api('/backups')).items[0].filename;
 await api('/sessions',{mode:'practice',count:1});assert.equal((await api('/sessions')).items.length,2);
 await api('/restore',{path:backup});assert.equal((await api('/sessions')).items.length,1);
 await page.reload();assert.equal((await api('/sessions/'+sid)).status,'submitted');
 assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,checks:['coverage UI','budget UI','double-click start','Chromium offline fetch and reconnect','pause/resume controls and reload','version pin (API)','group submit control and repeat API submit','submitted reload','backup restore (API)'],limitations:['offline browser transport only; host network was not disabled','version/backup actions validated through browser request API; not all controls clicked','synthetic content; no Windows or human learning acceptance']}));
} finally {await browser.close()}
