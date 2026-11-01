// Focused browser state regressions against real Worker/AudioWorklet/Wasm.
// LAN Playwright only; no hardware or listening acceptance. MIT.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
const [www, out] = process.argv.slice(2);
await mkdir(out, { recursive: true });
const { server, url } = await serve(www, 18879);
const { browser, name } = await launch();
const report = { browser: name, cases: [], errors: [] };
async function test(label, run) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  try { await run(page); assert.deepEqual(errors, []); report.cases.push({ label, pass: true }); }
  catch (e) { report.cases.push({ label, pass: false, error: e.stack, pageErrors: errors }); }
  finally { await page.close(); }
}
async function start(page) {
  await page.goto(`${url}?load=examples/first-orbit.lunar`);
  await page.click('[data-layout="workbench"]');
  await page.waitForFunction(() => window.fm1?.editor);
  await page.click('#power-on');
  await page.waitForFunction(() => fm1.editor.state.mirror?.blocks.size > 6);
  await page.click('[data-layout="editor"]');
}
async function idle(page) {
  await page.waitForFunction(() => !fm1.editor.state.sequenceBusy && document.querySelector('.sq')?.getAttribute('aria-busy') !== 'true');
}
try {
await test('BAD sound stays dismissible and never mutates live state', async page => {
  await start(page);
  const before = await page.evaluate(() => fm1.files.saveText('project'));
  const verdict = await page.evaluate(async () => {
    fm1.editor.select('s2', { view: 'flow' });
    const bytes = new TextEncoder().encode(JSON.stringify({lunar:'1.0',kind:'sound',sound:{inserts:{}}}));
    const v = await fm1.files.verdict(bytes, 'bad.sound.lunar', 'sound', {into:1,slot:0});
    const dt = new DataTransfer(); dt.items.add(new File([bytes], 'bad.sound.lunar', {type:'application/json'}));
    document.querySelector('.ed-flow .ed-block[data-block="s2"]').dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt}));
    return {ok:v.ok,code:v.report.code};
  });
  assert.equal(verdict.ok, false); assert.equal(verdict.code, 'BAD');
  const dismiss = page.locator('.ed-arrive').getByRole('button',{name:'Dismiss',exact:true});
  await dismiss.waitFor({timeout:3000});
  assert.equal(await page.locator('.ed-arrive button').count(),1);
  await dismiss.click(); assert.equal(await page.locator('.ed-arrive').count(),0);
  assert.equal(await page.evaluate(() => fm1.files.saveText('project')),before);
  // A valid sound still reaches the normal Load/Cancel card after dismissal.
  await page.evaluate(async () => {
    const text=await fm1.files.saveText('sound',1);
    const dt=new DataTransfer();dt.items.add(new File([text],'valid.sound.lunar'));
    document.querySelector('.ed-flow .ed-block[data-block="s2"]').dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:dt}));
  });
  await page.locator('.ed-arrive').getByRole('button',{name:'Load into Sound 2',exact:true}).waitFor();
});
await test('Solo survives own edits and unchanged refresh; replacement and external edits invalidate restoration',async page=>{
  await start(page);
  await page.evaluate(async()=>{
    window.seqApi=await import('/editor/sequence-model.js');
    const d=await fm1.editor.sequencerHost.fetchProject(), m=seqApi.emptySet();
    m.tracks.forEach((t,i)=>{t.route={kind:1,index:i===0?0:1};});
    d.set=seqApi.writeSet(m); await fm1.editor.sequencerHost.applyProject(d,'Fixture A');
    fm1.editor.applyLink({sequencer:true}); await fm1.editor.sequencer.refresh();
  });
  await page.getByRole('tab',{name:'Mixer',exact:true}).click();
  const solo=page.getByRole('button',{name:'S1 solo routed tracks',exact:true});
  await solo.click(); await idle(page); assert.equal(await solo.getAttribute('aria-pressed'),'true');
  await page.evaluate(()=>fm1.editor.sequencer.refresh(true));
  assert.equal(await solo.getAttribute('aria-pressed'),'true');
  // Own sequencer note/tempo edits remain in the same project.
  await page.getByLabel('BPM',{exact:true}).fill('123');
  await page.getByLabel('BPM',{exact:true}).dispatchEvent('change'); await idle(page);
  assert.equal(await solo.getAttribute('aria-pressed'),'true');
  await solo.click(); await idle(page);
  assert.deepEqual(await page.evaluate(async()=>seqApi.parseSet((await fm1.editor.sequencerHost.fetchProject()).set).tracks.map(t=>t.muted)),Array(8).fill(0));
  await solo.click();await idle(page);
  const replaced=await page.evaluate(async()=>{
    const before=fm1.files.pid,d=await fm1.editor.sequencerHost.fetchProject(),m=seqApi.parseSet(d.set);
    m.tracks.forEach(t=>t.muted=0);m.tracks[1].muted=1;d.set=seqApi.writeSet(m);
    const r=await fm1.files.load(new TextEncoder().encode(JSON.stringify(d)),{ask:false,before:false,quiet:true,same:false});
    fm1.editor.applyLink({sequencer:true});await fm1.editor.sequencer.refresh(true);return {ok:r.ok,changed:before!==fm1.files.pid};
  });assert.equal(replaced.ok,true);assert.equal(replaced.changed,true);
  await page.getByRole('tab',{name:'Mixer',exact:true}).click();
  assert.equal(await solo.getAttribute('aria-pressed'),'false');
  await solo.click();await idle(page);await solo.click();await idle(page);
  assert.equal(await page.evaluate(async()=>seqApi.parseSet((await fm1.editor.sequencerHost.fetchProject()).set).tracks[1].muted),1);
  // Same-content reload still creates another browser project identity.
  await solo.click();await idle(page);
  await page.evaluate(async()=>{const d=await fm1.editor.sequencerHost.fetchProject();await fm1.files.load(new TextEncoder().encode(JSON.stringify(d)),{ask:false,before:false,quiet:true,same:false});fm1.editor.applyLink({sequencer:true});await fm1.editor.sequencer.refresh(true);});
  await page.getByRole('tab',{name:'Mixer',exact:true}).click();
  assert.equal(await solo.getAttribute('aria-pressed'),'false');
  await solo.click();await idle(page);
  await page.evaluate(async()=>{const d=await fm1.editor.sequencerHost.fetchProject(),m=seqApi.parseSet(d.set);m.tracks[2].muted=0;d.set=seqApi.writeSet(m);await fm1.editor.sequencerHost.applyProject(d,'External mute');await fm1.editor.sequencer.refresh(true);});
  await page.getByRole('tab',{name:'Mixer',exact:true}).click();
  assert.equal(await solo.getAttribute('aria-pressed'),'false');
  await solo.click();await idle(page);
  await page.evaluate(async()=>{
    fm1.node.port.postMessage({type:'seq-line',bytes:new TextEncoder().encode('mute 3 0')});
    await fm1.files.projectSnapshot();await fm1.editor.sequencer.refresh(true);
  });
  assert.equal(await solo.getAttribute('aria-pressed'),'false');
  const beforeUndo=await page.evaluate(async()=>seqApi.parseSet((await fm1.editor.sequencerHost.fetchProject()).set).tracks.map(t=>t.muted));
  await solo.click();await idle(page);
  await page.evaluate(()=>fm1.editor.undo());await idle(page);
  await page.evaluate(()=>fm1.editor.sequencer.refresh(true));
  assert.equal(await solo.getAttribute('aria-pressed'),'false');
  assert.deepEqual(await page.evaluate(async()=>seqApi.parseSet((await fm1.editor.sequencerHost.fetchProject()).set).tracks.map(t=>t.muted)),beforeUndo);
});
await test('view snapshot refuses an intervening native edit instead of overwriting it',async page=>{
  await page.route('**/view-parent.html',r=>r.fulfill({contentType:'text/html',body:`<!doctype html><iframe src="${url}?embed=1"></iframe>`}));
  await page.goto(new URL('view-parent.html',url).href);
  const frame=page.frames().find(f=>f.url().includes('embed=1')) || await page.waitForEvent('frameattached');
  await frame.waitForSelector('#power-on');await frame.click('#power-on');
  await frame.waitForFunction(()=>fm1.files.powered && fm1.screens>0);
  await page.evaluate(()=>{window.viewReplies=[];addEventListener('message',e=>{if(e.data?.re==='view-race')window.viewReplies.push(e.data);});});
  await frame.evaluate(()=>{
    window.pausePack=true;
    const original=Worker.prototype.postMessage;
    Worker.prototype.postMessage=function(m,transfer){
      if(window.pausePack && m.op==='pack') {window.pausePack=false;window.heldPack=()=>original.call(this,m,transfer);return;}
      return original.call(this,m,transfer);
    };
  });
  await page.evaluate(()=>document.querySelector('iframe').contentWindow.postMessage({lunar:1,id:'view-race',op:'view',view:'seq.track=2'},location.origin));
  await frame.waitForFunction(()=>!!window.heldPack);
  const changed=await frame.evaluate(async()=>{
    const before=await fm1.files.projectSnapshot();
    fm1.node.port.postMessage({type:'seq-line',bytes:new TextEncoder().encode('bpm 123')});
    const after=await fm1.files.projectSnapshot();window.newHash=after.hash;window.heldPack();
    return before.hash!==after.hash;
  });assert.equal(changed,true,'native edit must change the fenced content');
  await page.waitForFunction(()=>window.viewReplies.length===1);
  assert.equal(await page.evaluate(()=>window.viewReplies[0].ok),false);
  assert.equal(await frame.evaluate(async()=>(await fm1.files.projectSnapshot()).hash===window.newHash),true);
});
await test('editor reconnect clears pending work and rejects stale old-port ACKs',async page=>{
  await start(page);
  const result=await page.evaluate(async()=>{
    const st=fm1.editor.state,old=st.port.onmessage;
    st.inflight=1;st.tags.set(4321,{label:'orphan'});let cancelled=false;
    st.snapWait.set(654321,()=>{cancelled=true;});
    window.dispatchEvent(new CustomEvent('fm1-power',{detail:{on:false}}));
    const detached={inflight:st.inflight,tags:st.tags.size,waiters:st.snapWait.size};
    window.dispatchEvent(new CustomEvent('fm1-power',{detail:{on:true}}));
    st.inflight=1;
    old({data:{type:'edited',tag:4321,codes:new Int8Array([0])}});
    const afterOld=st.inflight;st.inflight=0;
    await new Promise(r=>setTimeout(r,300));
    return {detached,afterOld,cancelled};
  });
  assert.deepEqual(result.detached,{inflight:0,tags:0,waiters:0});
  assert.equal(result.cancelled,true);assert.equal(result.afterOld,1);
  await page.waitForFunction(()=>fm1.editor.state.mirror && !fm1.editor.state.loading);
});
} finally { await browser.close(); server.close(); }
report.pass=report.cases.every(c=>c.pass);await writeFile(`${out}/browser-state.json`,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report));process.exitCode=report.pass?0:1;
