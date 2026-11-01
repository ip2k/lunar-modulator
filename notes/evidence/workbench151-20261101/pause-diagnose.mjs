import { serve } from '../../../sim/web/test/serve.mjs';
import { launch } from '../../../sim/web/test/launch.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
const out='scratch/pause151/diagnose'; await mkdir(out,{recursive:true});
const {server,url}=await serve('sim/web/www',18919); const {browser}=await launch();
let failed=false;
try {for(let n=0;n<48;n++) {
const page=await browser.newPage({viewport:{width:1440,height:900}});
await page.goto(url+'?view=sequencer');
await page.getByRole('button',{name:'Power on',exact:true}).click();
await page.waitForFunction(()=>fm1?.editor?.state?.mirror && document.querySelector('.sq-transport'));
await page.evaluate(()=>{
 window.pauseTrace=[]; let count=0; const ids=new WeakMap();
 const id=e=>{if(!e)return null;if(!ids.has(e))ids.set(e,++count);return ids.get(e)};
 const record=(kind,target)=>{const b=document.querySelector('[data-transport-play-pause]');pauseTrace.push({at:performance.now(),kind,target:id(target),button:id(b),label:b?.getAttribute('aria-label'),disabled:b?.matches(':disabled'),busy:document.querySelector('.sq')?.getAttribute('aria-busy'),playing:fm1.seq?.playing,paused:fm1.seq?.paused});if(pauseTrace.length>160)pauseTrace.shift()};
 for(const name of ['pointerdown','mousedown','pointerup','mouseup','click','dblclick','focus','blur'])document.addEventListener(name,e=>record(name,e.target),true);
 const p=fm1.node.port;const send=p.postMessage.bind(p);p.postMessage=(message,...args)=>{if(message.type==='seq-line')record(new TextDecoder().decode(message.bytes));return send(message,...args)};
 let button=document.querySelector('[data-transport-play-pause]'); new MutationObserver(()=>{const next=document.querySelector('[data-transport-play-pause]');if(next!==button){button=next;record('button-replaced')}}).observe(document.body,{childList:true,subtree:true});
});
const keys=page.locator('.ed-keys');await keys.click();await keys.click();
const play=page.locator('[data-transport-play-pause]');
try {
await play.click();await page.waitForFunction(()=>document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label')==='Pause',{},{timeout:5000});
await play.click();await page.waitForFunction(()=>document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label')==='Resume',{},{timeout:5000});
await play.click();await page.waitForFunction(()=>document.querySelector('[data-transport-play-pause]')?.getAttribute('aria-label')==='Pause',{},{timeout:5000});
console.log('PASS',n); if(n===0)await writeFile(out+'/first-pass.json',JSON.stringify(await page.evaluate(()=>pauseTrace),null,2));
} catch(e) {failed=true; console.log('FAIL',n,String(e));await writeFile(out+'/failure-'+n+'.json',JSON.stringify(await page.evaluate(()=>pauseTrace),null,2));}
await page.close();
if(failed)break;
}} finally {await browser.close();server.close()}
if(failed)process.exitCode=1;
