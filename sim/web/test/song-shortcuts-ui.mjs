// Focus, transaction and keyboard propagation acceptance with a canonical mock host.
// Native transport/undo acceptance is covered by sequencer-native/sync. MIT.
import assert from 'node:assert/strict';
import { launch } from './launch.mjs';
import { serve } from './serve.mjs';
const {server,url}=await serve(process.argv[2] || 'sim/web/www',18876);
const {browser}=await launch();
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
try {
  await page.route('**/harness.html',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html><body><main></main></body></html>'}));
  await page.goto(url.replace('index.html','harness.html'));
  await page.evaluate(async()=>{
    const {makeSequencer}=await import('/editor/sequencer.js');
    const {emptySet,emptyClip,writeSet,parseSet}=await import('/editor/sequence-model.js');
    const m=emptySet();m.tracks[0].route={kind:1,index:0};m.tracks[0].clips[0]=emptyClip(16);m.song=[0,0,1];
    m.tracks[0].clips[0].notes=[{step:0,tick:0,pitch:60,gate:24,vel:90}];
    window.doc={set:writeSet(m),sounds:[{engine:'Test',level:70,inserts:[]}]};window.calls=[];window.nativeKeys=0;window.refuse=false;window.pending=false;
    window.seq=makeSequencer({fetchProject:async()=>structuredClone(window.doc),applyProject:async(d,label)=>{if(window.pending)await new Promise(r=>window.release=r);if(window.refuse)throw Error('native refusal');window.doc=d;calls.push(label)},
      play:()=>calls.push('button play'),playPause:()=>calls.push('transport'),restart:()=>calls.push('restart'),toggleSidebar:()=>calls.push('sidebar'),
      claimKeys:()=>calls.push('claim'),getTransport:()=>({playing:false}),inspector:key=>{const p=document.createElement('p');p.textContent=key;return p}});
    document.querySelector('main').append(seq.render());await seq.refresh();window.model=()=>parseSet(doc.set);
    // Same capture ordering used by the full editor, ahead of app.js's synth keys.
    window.addEventListener('keydown',e=>{if(seq.contains(e.target)||window.editKeys)seq.onKey(e)},true);
    window.addEventListener('keydown',e=>{if([' ','a','d','e','i','0'].includes(e.key))window.nativeKeys++});
  });
  const root=page.locator('.sq');
  async function settled(){await page.waitForFunction(()=>document.querySelector('.sq').getAttribute('aria-busy')!=='true')}
  async function canvas(key){await root.focus();await page.keyboard.press(key);await settled()}
  await canvas('Space');await canvas('Shift+Space');await canvas('i');
  assert.deepEqual(await page.evaluate(()=>calls.filter(x=>x!=='claim')),['transport','restart','sidebar']);
  assert.equal(await page.evaluate(()=>nativeKeys),0,'handled Song keys do not also reach synth');
  await canvas('Tab');assert.equal(await root.getAttribute('data-song-view'),'Mixer');
  await canvas('Tab');assert.equal(await root.getAttribute('data-song-view'),'Arrangement');
  await canvas('Control+d');assert.deepEqual(await page.evaluate(()=>model().song),[0,0,0,0,1]);
  await canvas('Delete');assert.deepEqual(await page.evaluate(()=>model().song),[1]);
  await canvas('e');assert.equal(await root.getAttribute('data-song-view'),'Clip');
  await page.locator('[data-note="0"]').click();await canvas('Control+d');
  assert.equal(await page.evaluate(()=>model().tracks[0].clips[0].notes.length),2);
  await canvas('ArrowUp');assert.equal(await page.evaluate(()=>model().tracks[0].clips[0].notes[1].pitch),61);
  await canvas('ArrowRight');assert.equal(await page.evaluate(()=>model().tracks[0].clips[0].notes[1].tick),48);
  await canvas('0');assert.equal(await page.evaluate(()=>model().tracks[0].muted),1);
  await canvas('Alt+a');assert.equal(await page.evaluate(()=>model().tracks[0].muted),0);
  await canvas('F2');const name=page.getByLabel('Track 1 name',{exact:true});
  assert.equal(await name.evaluate(e=>e.readOnly),false);await name.fill('a d e i 0');await name.press('Space');
  assert.equal(await root.getAttribute('data-song-view'),'Clip');assert.equal(await page.evaluate(()=>model().tracks[0].muted),0);
  await name.press('Escape');
  const nudges=await page.evaluate(()=>calls.filter(x=>x==='Nudge note').length);
  const pitch=page.getByLabel('MIDI pitch',{exact:true});await pitch.focus();await pitch.press('ArrowUp');await settled();
  assert.equal(await page.evaluate(()=>model().tracks[0].clips[0].notes[1].pitch),62,'native number control increments once');
  assert.equal(await page.evaluate(()=>calls.filter(x=>x==='Nudge note').length),nudges,'native number control does not also trigger Song nudge');
  const currentPitch=page.getByLabel('MIDI pitch',{exact:true});
  await currentPitch.fill('61');await currentPitch.dispatchEvent('change');await settled();
  await canvas('d');assert.equal(await page.locator('dialog[open]').count(),1);
  await page.getByRole('button',{name:'Close inspector',exact:true}).focus();await page.keyboard.press('a');
  assert.equal(await root.getAttribute('data-song-view'),'Clip','dialog protects global view keys');
  await page.getByRole('button',{name:'Close inspector',exact:true}).click();
  // Buttons keep normal Space activation and tabs keep native Tab traversal.
  await page.getByRole('tab',{name:'Automation',exact:true}).focus();
  await page.keyboard.press('Tab');assert.equal(await root.getAttribute('data-song-view'),'Clip');
  const transports=await page.evaluate(()=>calls.filter(x=>x==='transport').length);
  await page.getByRole('button',{name:'Play',exact:true}).focus();await page.keyboard.press('Space');await settled();
  assert.equal(await page.evaluate(()=>calls.filter(x=>x==='button play').length),1,'focused button keeps native Space activation');
  assert.equal(await page.evaluate(()=>calls.filter(x=>x==='transport').length),transports);
  await canvas('a');assert.equal(await root.getAttribute('data-song-view'),'Automation');
  await canvas('e');await page.evaluate(()=>window.refuse=true);await canvas('Delete');
  assert.equal(await page.evaluate(()=>model().tracks[0].clips[0].notes.length),2);
  assert.match(await page.locator('.sq-status').textContent(),/native refusal/);
  await page.evaluate(()=>{window.refuse=false;window.pending=true});await root.focus();await page.keyboard.press('Delete');
  await page.waitForFunction(()=>document.querySelector('.sq').getAttribute('aria-busy')==='true');
  const pendingNative=await page.evaluate(()=>nativeKeys);
  await page.keyboard.press('Control+d');await page.keyboard.press('a');
  assert.equal(await root.getAttribute('data-song-view'),'Clip','pending native transaction rejects further shortcuts');
  assert.equal(await page.evaluate(()=>nativeKeys),pendingNative,'pending Song shortcuts remain consumed');
  await page.evaluate(()=>{window.pending=false;window.release()});await settled();
  assert.equal(await page.evaluate(()=>model().tracks[0].clips[0].notes.length),1);
  await page.evaluate(()=>seq.destroy());await page.keyboard.press('Space');
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('PASS Song shortcuts: focus, typing, dialogs, native refusal, pending transactions, note/section operations, synth arbitration');
} finally {await browser.close();server.close()}
