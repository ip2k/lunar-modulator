// Bounded UI interactions with a mock canonical-project host; no DSP acceptance.
import { launch } from './launch.mjs';
import { serve } from './serve.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
const out = process.argv[3] || 'scratch/sequencer-ui';
await mkdir(out, {recursive:true});
const {server,url}=await serve(process.argv[2] || 'sim/web/www',18873);
const {browser}=await launch();
const page=await browser.newPage({viewport:{width:1440,height:1100}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try {
 await page.route('**/harness.html',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html><head><link rel="stylesheet" href="/editor/editor.css"><style>body{margin:24px;background:#15141c;color:#ddd;font-family:sans-serif}main{max-width:1300px;margin:auto}</style></head><body><main class="ed"></main></body></html>'}));
 await page.goto(url.replace('index.html','harness.html'));
 await page.evaluate(async()=>{
  const {makeSequencer}=await import('/editor/sequencer.js');
  const {emptySet,emptyClip,writeSet,parseSet}=await import('/editor/sequence-model.js');
  const m=emptySet();m.sceneNames[0]='INTRO';m.sceneNames[1]='CHORUS';m.song=[0,0,1];
  m.tracks.forEach((t,i)=>{t.route={kind:1,index:i%4};t.clips[0]=emptyClip(32);t.clips[1]=emptyClip(64)});
  m.tracks[0].clips[0].notes=[{tick:0,gate:36,pitch:60,vel:96,step:0}];
  window.doc={set:writeSet(m),sounds:['Punch','Acid','Trio','FM6'].map(engine=>({engine,level:75,inserts:[null,null]}))};window.calls=[];window.reject=false;
  window.seq=makeSequencer({fetchProject:async()=>structuredClone(window.doc),applyProject:async(d,label)=>{if(window.reject)throw Error('test refusal');window.doc=d;window.calls.push(label)},getTransport:()=>({playing:false}),metadata:{engine:()=>({params:[{name:'Cutoff',flags:[]},{name:'Voices',flags:['nolock']}]})},watchTrack:t=>window.calls.push('watch '+t),playScene:s=>window.calls.push('scene '+s),inspector:key=>{const e=document.createElement('p');e.textContent='Inspector '+key;return e}});
  document.querySelector('main').append(window.seq.render());await window.seq.refresh();window.model=()=>parseSet(window.doc.set);
 });
 await page.getByRole('button',{name:'Add note',exact:true}).click();
 await page.waitForFunction(()=>window.model().tracks[0].clips[0].notes.length===2);
 async function set(label,value){await page.getByLabel(label,{exact:true}).fill(String(value));await page.getByLabel(label,{exact:true}).dispatchEvent('change');await page.waitForFunction(()=>document.querySelector('.sq').getAttribute('aria-busy')==='false')}
 await set('Velocity',72);await set('Gate · ticks',48);await set('Microtiming · ticks',3);await set('Probability %',70);
 const note=await page.evaluate(()=>window.model().tracks[0].clips[0]);
 if(!note.notes.some(n=>n.vel===72&&n.gate===48&&n.tick===3)||note.trigs[0].prob!==70)throw Error('Note properties did not persist');
 await page.getByRole('button',{name:'Assign parameter',exact:true}).click();await page.waitForFunction(()=>!!window.model().tracks[0].lanes[0]);
 await set('Lane 1, step 1 lock',91);if(await page.evaluate(()=>window.model().tracks[0].clips[0].locks[0].value)!==91)throw Error('lock');
 await page.getByLabel('Track 8 output',{exact:true}).selectOption('m16');await page.waitForFunction(()=>window.model().tracks[7].route.index===16);
 await set('Repeats',3);if(await page.evaluate(()=>window.model().song.length)!==4)throw Error('repeat');
 await page.getByTestId('launch-scene').click();
 await page.evaluate(()=>{window.reject=true});await set('BPM',130);
 if(!await page.getByRole('status').textContent().then(t=>t.includes('test refusal')))throw Error('refusal not visible');
 if(await page.evaluate(()=>window.model().bpmX100)!==12000)throw Error('refusal mutated model');
 await page.evaluate(()=>{window.reject=false;window.seq.update({playing:true,scene:0,step:4,songIndex:0,tracks:[{active:0,posTick:96}]})});
 if(await page.locator('[data-roll-playhead]').isHidden())throw Error('playhead hidden');
 await page.screenshot({path:`${out}/desktop.png`,fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${out}/mobile.png`,fullPage:true});
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)throw Error('mobile document overflow');
 if(errors.length)throw Error(errors.join('\n'));
 await writeFile(`${out}/results.json`,JSON.stringify({passed:true,errors,note,checks:['note fields','probability','locks','routing','song repeats','scene launch','refusal rollback','playhead','mobile overflow']},null,2));
 console.log('PASS sequencer mock-host desktop/mobile checks');
} finally {await browser.close();await new Promise(r=>server.close(r))}
