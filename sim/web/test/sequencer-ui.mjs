// Bounded UI interactions with a mock canonical-project host; no DSP acceptance.
import { launch } from './launch.mjs';
import { serve } from './serve.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
const out = process.argv[3] || 'scratch/sequencer-ui';
await mkdir(out, {recursive:true});
const {server,url}=await serve(process.argv[2] || 'sim/web/www',18873);
const {browser}=await launch();
const page=await browser.newPage({viewport:{width:1440,height:1100},hasTouch:true});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
async function tab(name){await page.getByRole('tab',{name,exact:true}).click()}
try {
 await page.route('**/harness.html',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html><head><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/editor/editor.css"><style>body{display:block;margin:24px;padding:0}main{max-width:1300px;margin:auto}</style></head><body><main class="ed"></main></body></html>'}));
 await page.goto(url.replace('index.html','harness.html'));
 await page.evaluate(async()=>{
  const {makeSequencer}=await import('/editor/sequencer.js');
  const {emptySet,emptyClip,writeSet,parseSet}=await import('/editor/sequence-model.js');
  const m=emptySet();m.sceneNames[0]='INTRO';m.sceneNames[1]='CHORUS';m.song=[0,0,1];
  m.tracks.forEach((t,i)=>{t.route={kind:1,index:i%4};t.clips[0]=emptyClip(32);t.clips[1]=emptyClip(64)});
  m.tracks[0].clips[0].notes=[{tick:0,gate:36,pitch:57,vel:96,step:0}];
  window.doc={set:writeSet(m),sounds:['Punch','Acid','Trio','FM6'].map(engine=>({engine,level:75,inserts:[null,null]}))};window.doc.master=[{engine:'Hall'},{engine:'Limit'}];window.doc.sounds[0].inserts[0]={engine:'Echo'};window.calls=[];window.reject=false;window.output=.8;window.soundLevels=[75,75,75,75];window.levelGestures=[];
  const telemetry={sections:[{name:'meters',offset:0,mask:0,rows:['snd1.post_fader','out.post_master'],fields:['peak','rms']},{name:'levels',offset:4,mask:8,rows:['s1.level','master.level'],fields:['peak','rms']}]};
  window.seq=makeSequencer({fetchProject:async()=>structuredClone(window.doc),applyProject:async(d,label)=>{if(window.reject)throw Error('test refusal');window.doc=d;window.calls.push(label)},getMaster:()=>window.output,setMaster:v=>{window.output=v},getSoundLevel:s=>window.soundLevels[s],setSoundLevel:(s,v,mode)=>{window.soundLevels[s]=v;window.levelGestures.push({sound:s,value:v,mode})},beginLevelDrag:s=>window.levelGestures.push({begin:s}),endLevelDrag:()=>window.levelGestures.push({end:true}),getTransport:()=>({playing:false}),metadata:{doc:{telemetry},engine:name=>name?({params:[{name:'Cutoff',type:'float',min:0,max:1,def:.5,flags:[]},{name:'Voices',flags:['nolock']}]}):null},watchTrack:t=>window.calls.push('watch '+t),playScene:s=>window.calls.push('scene '+s),playClip:(t,s)=>window.calls.push('clip '+t+' '+s),inspector:key=>{const e=document.createElement('p');e.textContent='Inspector '+key;return e}});
  document.querySelector('main').append(window.seq.render());await window.seq.refresh();window.model=()=>parseSet(window.doc.set);
 });
 // Names edit independently of track selection, using the native set field.
 const name=page.getByLabel('Track 1 name',{exact:true});
 await name.dblclick();await name.fill(' Bass 1 ');await name.press('Enter');
 await page.waitForFunction(()=>window.model().tracks[0].name===' Bass 1 ');
 if(!await page.evaluate(()=>window.doc.set.includes('tn 0 2042617373203120'))||await page.evaluate(()=>window.model().sceneNames[0])!=='INTRO')throw Error('Track rename did not persist natively or changed scene name');
 if(await name.inputValue()!==' Bass 1 '||await name.evaluate(e=>!e.readOnly))throw Error('Track title did not settle readonly');
 await name.press('F2');await name.fill('Cancel');await name.press('Escape');
 if(await name.inputValue()!==' Bass 1 '||await page.evaluate(()=>window.model().tracks[0].name)!==' Bass 1 ')throw Error('Escape did not cancel rename');
 await name.dblclick();await name.fill('Bass 2');
 await page.getByRole('button',{name:'Select track 1',exact:true}).focus();
 await page.waitForFunction(()=>window.model().tracks[0].name==='Bass 2');
 // Hold the destination pointer down: blur must not lock it before click.
 await name.press('Enter');await name.fill('Click Bass');
 const destination=page.getByRole('button',{name:'Select track 2',exact:true});
 const destBox=await destination.boundingBox();await page.mouse.move(destBox.x+10,destBox.y+10);await page.mouse.down();
 await page.waitForTimeout(120);await page.mouse.up();
 await page.waitForFunction(()=>window.model().tracks[0].name==='Click Bass');
 if(!await page.evaluate(()=>window.calls.includes('watch 1')))throw Error('Blur save swallowed destination click');
 await page.getByRole('button',{name:'Select track 1',exact:true}).click();
 await name.dblclick();await name.fill('Bass 2');
 const tapBox=await destination.boundingBox();await page.touchscreen.tap(tapBox.x+10,tapBox.y+10);
 await page.waitForFunction(()=>window.model().tracks[0].name==='Bass 2');
 if(await page.locator('.sq-scene-edit[aria-pressed="true"]').first().getAttribute('aria-label')!=='Edit track 2 scene 1')throw Error('Blur save swallowed destination touch tap');
 await page.getByRole('button',{name:'Select track 1',exact:true}).click();
 await name.press('Enter');await name.fill('12345678901234567');await name.press('Enter');
 if(await page.evaluate(()=>window.model().tracks[0].name)!=='Bass 2'||await name.evaluate(e=>e.readOnly))throw Error('Invalid rename was truncated or saved');
 await name.press('Escape');
 await page.evaluate(()=>window.reject=true);await name.press('Enter');await name.fill('Refused');await name.press('Enter');
 await page.waitForFunction(()=>document.querySelector('.sq-status').textContent.includes('test refusal'));
 if(await page.evaluate(()=>window.model().tracks[0].name)!=='Bass 2'||await name.inputValue()!=='Bass 2')throw Error('Refused rename did not restore canonical name');
 await page.evaluate(()=>window.reject=false);
 await page.screenshot({path:`${out}/track-names-scenes.png`,fullPage:true});
 await tab('Arrangement');if(await name.inputValue()!=='Bass 2')throw Error('Arrangement title lost track name');
 await tab('Mixer');if(await name.inputValue()!=='Bass 2')throw Error('Mixer title lost track name');
 await page.screenshot({path:`${out}/track-names-mixer.png`,fullPage:true});
 await tab('Clip');
 if(await page.getByLabel('Edit track',{exact:true}).locator('option').first().textContent()!=='Bass 2'||!await page.getByRole('heading',{name:'Bass 2 · INTRO',exact:true}).isVisible())throw Error('Clip label or selector lost track name');
 await name.dblclick();await name.fill('');await name.press('Enter');
 await page.waitForFunction(()=>window.model().tracks[0].name==='');
 if(await name.getAttribute('placeholder')!=='Track 1'||await page.evaluate(()=>window.doc.set.some(l=>l.startsWith('tn '))))throw Error('Clear rename did not restore numbered fallback');
 await tab('Clip');
 // Selecting another track uses its current pitch; restore this test fixture.
 await page.getByLabel('New note pitch',{exact:true}).fill('60');await page.getByLabel('New note pitch',{exact:true}).dispatchEvent('change');
 const clipActions=page.locator('.sq-clip-actions');
 if(!await clipActions.getByRole('button',{name:'Add note',exact:true}).isVisible()||!await clipActions.getByLabel('New note pitch',{exact:true}).isVisible())throw Error('New note pitch must sit beside Add note');
 await page.getByLabel('New note pitch',{exact:true}).fill('60');await page.getByLabel('New note pitch',{exact:true}).dispatchEvent('change');
 await page.getByRole('button',{name:'Add note',exact:true}).click();
 await page.waitForFunction(()=>window.model().tracks[0].clips[0].notes.length===2);
 for(const label of ['MIDI pitch','Step','Gate · ticks','Velocity'])if(!await page.getByLabel(label,{exact:true}).isVisible())throw Error(`Essential note field hidden: ${label}`);
 const advanced=page.locator('.sq-note-details details.sq-note-advanced');
 if(await advanced.evaluate(e=>e.open)||await page.getByLabel('Probability %',{exact:true}).isVisible())throw Error('Advanced note controls should start collapsed');
 const advancedSummary=advanced.locator(':scope > summary');
 await advancedSummary.focus();await advancedSummary.press('Enter');
 if(!await advanced.evaluate(e=>e.open)||!await page.getByLabel('Probability %',{exact:true}).isVisible())throw Error('Keyboard did not open Advanced note controls');
 async function set(label,value){await page.getByLabel(label,{exact:true}).fill(String(value));await page.getByLabel(label,{exact:true}).dispatchEvent('change');await page.waitForFunction(()=>document.querySelector('.sq').getAttribute('aria-busy')==='false')}
 await set('Velocity',72);
 if(await page.evaluate(()=>document.activeElement.getAttribute('aria-label'))!=='Velocity')throw Error('Focus lost on edit');
 await set('Gate · ticks',48);await set('Microtiming · ticks',3);await set('Probability %',70);
 if(!await advanced.evaluate(e=>e.open)||await page.evaluate(()=>document.activeElement.getAttribute('aria-label'))!=='Probability %')throw Error('Advanced disclosure state or field focus lost on edit');
 const note=await page.evaluate(()=>window.model().tracks[0].clips[0]);
 if(!note.notes.some(n=>n.vel===72&&n.gate===48&&n.tick===3)||note.trigs[0].prob!==70)throw Error('Note properties did not persist');
 await page.locator('[data-note="1"]').scrollIntoViewIfNeeded();
 const nb=await page.locator('[data-note="1"]').boundingBox();
 await page.mouse.move(nb.x+12,nb.y+8);await page.mouse.down();const stepWidth=await page.locator('.sq-note-lane').first().evaluate(e=>e.clientWidth/Number(e.closest('.sq-roll').style.getPropertyValue('--steps')));await page.mouse.move(nb.x+12+stepWidth*2,nb.y-15,{steps:4});await page.mouse.up();
 await page.waitForFunction(()=>window.model().tracks[0].clips[0].notes.some(n=>n.pitch===61&&n.step===2));
 const handle=await page.locator('[data-resize-note="1"]').boundingBox();
 await page.mouse.move(handle.x+3,handle.y+8);await page.mouse.down();await page.mouse.move(handle.x+3+stepWidth,handle.y+8,{steps:4});await page.mouse.up();
 await page.waitForFunction(()=>window.model().tracks[0].clips[0].notes.some(n=>n.pitch===61&&n.gate===72));
 await tab('Automation');
 await page.getByRole('button',{name:'Assign parameter',exact:true}).click();await page.waitForFunction(()=>!!window.model().tracks[0].lanes[0]);
 await page.getByLabel('Automation target',{exact:true}).selectOption('in1');await page.waitForFunction(()=>window.model().tracks[0].lanes[0]?.label==='in1:Cutoff');
 await page.getByLabel('Automation target',{exact:true}).selectOption('m1');await page.waitForFunction(()=>window.model().tracks[0].lanes[0]?.label==='m1:Cutoff');
 await page.getByLabel('Automation target',{exact:true}).selectOption('mix');await page.waitForFunction(()=>window.model().tracks[0].lanes[0]?.label==='mix:Level');
 await tab('Mixer');
 const routingFx=page.getByRole('button',{name:'Routing & FX',exact:true});
 if(await routingFx.getAttribute('aria-expanded')!=='true'||!await page.locator('.sq-track-routing').isVisible()||!await page.locator('.sq-device-rack').first().isVisible())throw Error('Desktop mixer routing and effects should be expanded by default');
 await page.setViewportSize({width:844,height:390});
 await page.waitForFunction(()=>document.querySelector('[aria-controls="sq-mixer-board"]')?.getAttribute('aria-expanded')==='false');
 if(await routingFx.getAttribute('aria-expanded')!=='false'||await page.locator('.sq-track-routing').isVisible())throw Error(`Mixer disclosure accessibility state did not follow landscape resize: expanded=${await routingFx.getAttribute('aria-expanded')} details=${await page.locator('.sq').getAttribute('data-mixer-details')} visible=${await page.locator('.sq-track-routing').isVisible()} narrow=${await page.evaluate(()=>matchMedia('(max-height: 500px) and (orientation: landscape)').matches)}`);
 await page.setViewportSize({width:1440,height:1100});
 await page.waitForFunction(()=>document.querySelector('[aria-controls="sq-mixer-board"]')?.getAttribute('aria-expanded')==='true');
 if(await routingFx.getAttribute('aria-expanded')!=='true'||!await page.locator('.sq-track-routing').isVisible())throw Error(`Mixer disclosure accessibility state did not follow desktop resize: expanded=${await routingFx.getAttribute('aria-expanded')} details=${await page.locator('.sq').getAttribute('data-mixer-details')} visible=${await page.locator('.sq-track-routing').isVisible()}`);
 const fader=page.getByRole('slider',{name:'S1 level',exact:true});
 if(await fader.inputValue()!=='75'||await fader.getAttribute('aria-valuetext')!=='-2.5 dB')throw Error('Sound fader initial value/dB');
 await fader.focus();await fader.press('ArrowDown');await page.waitForFunction(()=>window.soundLevels[0]===74);
 if(!(await page.locator('.sq-fader-value').first().textContent()).includes('-2.6 dB'))throw Error('Sound fader dB display');
 if(!await page.evaluate(()=>window.levelGestures.some(x=>x.sound===0&&x.value===74&&x.mode==='key')))throw Error('Keyboard fader edit was not incremental');
 await fader.dispatchEvent('pointerdown',{pointerId:1,pointerType:'mouse',button:0});await fader.evaluate(e=>{e.value='61';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))});await fader.dispatchEvent('pointerup',{pointerId:1,pointerType:'mouse',button:0});
 await page.waitForFunction(()=>window.soundLevels[0]===61);
 if(!await page.evaluate(()=>window.levelGestures.some(x=>x.begin===0)&&window.levelGestures.some(x=>x.sound===0&&x.value===61&&x.mode==='drag')&&window.levelGestures.some(x=>x.end)))throw Error('Sound fader drag lifecycle');
 const master=page.getByRole('slider',{name:'Master output level',exact:true});await master.evaluate(e=>{e.value='45';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))});
 if(await page.evaluate(()=>window.output)!==.45||await master.getAttribute('aria-valuetext')!=='-13.9 dB')throw Error('Master output preference or dB display');
 const wanted=await page.evaluate(()=>window.seq.wantRows());if(wanted.length!==4)throw Error('Mixer telemetry did not subscribe to meter and level rows');
 await page.evaluate(()=>window.seq.onTelemetry(new Float32Array([.5,.25,1,.5,.25,.125,.75,.25])));
 const meter=page.locator('[data-sq-meter="snd1.post_fader"]');
 if(await meter.getAttribute('aria-valuenow')!=='-6.0'||!await meter.getAttribute('aria-valuetext').then(t=>t.includes('Peak -6.0 dB'))||await meter.evaluate(e=>parseFloat(e.style.getPropertyValue('--peak'))<=0))throw Error('Sound telemetry meter did not update');
 const masterMeter=page.getByRole('meter',{name:'Final master output level',exact:true});if(await masterMeter.getAttribute('aria-valuenow')!=='0.0'||!await masterMeter.evaluate(e=>e.classList.contains('is-clipping')))throw Error('Master telemetry meter did not update/clipping');
 const insert=page.getByRole('button',{name:'S1 insert 1',exact:true});await insert.click();
 const inspector=page.getByRole('dialog',{name:'Device controls',exact:true});await inspector.waitFor({state:'visible'});
 if(!await inspector.getByText('Inspector s1.in1',{exact:true}).isVisible()||await inspector.getByRole('button',{name:'Close inspector',exact:true}).evaluate(e=>e!==document.activeElement))throw Error('Device inspector did not open with focus');
 const inspectorFiles=inspector.locator('.sq-device-dialog-footer .sq-file-tools');
 if(await inspectorFiles.count()!==1||await inspector.locator('.sq-transport > .sq-file-tools').count())throw Error('Files & export should move into the device inspector footer');
 await inspector.getByRole('button',{name:'Close inspector',exact:true}).click();
 if(await insert.getAttribute('aria-expanded')!=='false'||await page.evaluate(()=>document.activeElement.getAttribute('aria-label'))!=='S1 insert 1')throw Error('Device inspector did not return focus to its trigger');
 await tab('Automation');
 await set('Lane 1, step 1 lock',91);if(await page.evaluate(()=>window.model().tracks[0].clips[0].locks[0].value)!==91)throw Error('lock');
 await tab('Arrangement');
 if(!await page.getByRole('button',{name:/Track 1, INTRO, 2 notes, 2 bars/}).isVisible())throw Error('Arrangement note/bar plural summary');
 await page.getByLabel('Track 8 output',{exact:true}).selectOption('m16');await page.waitForFunction(()=>window.model().tracks[7].route.index===16);
 await page.locator('.sq-section-tools > summary').filter({hasText:'Section tools'}).click();
 await set('Repeats',3);if(await page.evaluate(()=>window.model().song.length)!==4)throw Error('repeat');
 // Native shared-scene names edit inline, with a single commit per gesture.
 const entryName=page.getByLabel('Scene 1 name in song entry 1',{exact:true});
 await entryName.dblclick();await entryName.fill('ORBIT');await entryName.press('Enter');
 await page.waitForFunction(()=>window.model().sceneNames[0]==='ORBIT');
 if(await page.getByLabel('Scene 1 name in song entry 1',{exact:true}).inputValue()!=='ORBIT')throw Error('Inline scene rename did not redraw');
 const renameCount=await page.evaluate(()=>window.calls.filter(x=>x==='Rename scene').length);
 await page.getByLabel('Scene 1 name in song entry 1',{exact:true}).dblclick();await page.getByLabel('Scene 1 name in song entry 1',{exact:true}).fill('NOPE');await page.getByLabel('Scene 1 name in song entry 1',{exact:true}).press('Escape');
 if(await page.evaluate(()=>window.model().sceneNames[0])!=='ORBIT'||await page.getByLabel('Scene 1 name in song entry 1',{exact:true}).inputValue()!=='ORBIT')throw Error('Escape did not cancel scene rename');
 await page.getByLabel('Scene 1 name in song entry 1',{exact:true}).dblclick();await page.getByLabel('Scene 1 name in song entry 1',{exact:true}).fill('INTRO');await page.getByRole('button',{name:'Select song entry 2: CHORUS',exact:true}).focus();
 await page.waitForFunction(()=>window.model().sceneNames[0]==='INTRO');
 if(await page.evaluate(()=>window.calls.filter(x=>x==='Rename scene').length)!==renameCount+1)throw Error('Blur rename committed more than once');
 if(await page.getByLabel('Add scene',{exact:true}).count())throw Error('Permanent Add scene selector remains');
 const addSection=page.locator('.sq-add-section');
 if(await addSection.evaluate(e=>e.open))throw Error('Scene insertion chooser starts open');
 await addSection.locator('summary').click();await page.getByRole('button',{name:'Append scene 2: CHORUS',exact:true}).click();
 await page.waitForFunction(()=>window.model().song.length===5);
 if(await page.evaluate(()=>window.model().song[4])!==1)throw Error('Insertion chooser did not append chosen scene');
 // Sections page at readable widths with no horizontal scroll surface.
 await page.evaluate(async()=>{const m=window.model();window.savedSong=m.song;m.song=Array.from({length:64},(_,i)=>i%2);window.doc.set=(await import('/editor/sequence-model.js')).writeSet(m);window.seq.invalidate();await window.seq.refresh()});
 await page.setViewportSize({width:844,height:390});
 await page.waitForTimeout(100);
 let sections=0;
 do {sections+=await page.locator('.sq-entry').count();if(await page.getByRole('button',{name:'Next sections page',exact:true}).isDisabled())break;await page.getByRole('button',{name:'Next sections page',exact:true}).click();}while(true);
 if(sections!==64||await page.locator('[data-scroll="song"]').evaluate(e=>e.scrollWidth>e.clientWidth+1))throw Error('Paged arrangement lost native entries or overflows');
 if(await page.getByRole('slider',{name:/horizontal position/}).count())throw Error('Horizontal slider remains');
 await page.setViewportSize({width:1440,height:1100});
 await page.evaluate(async()=>{const m=window.model();m.song=window.savedSong;window.doc.set=(await import('/editor/sequence-model.js')).writeSet(m);window.seq.invalidate();await window.seq.refresh()});
 await tab('Scenes');
 await page.getByLabel('Scene 1 name',{exact:true}).dblclick();await page.getByLabel('Scene 1 name',{exact:true}).fill('HELLO');await page.getByLabel('Scene 1 name',{exact:true}).press('Enter');
 await page.waitForFunction(()=>window.model().sceneNames[0]==='HELLO');
 await page.getByLabel('Scene 1 name',{exact:true}).press('F2');await page.getByLabel('Scene 1 name',{exact:true}).fill('INTRO');await page.getByRole('button',{name:'Edit scene 2',exact:true}).focus();
 await page.waitForFunction(()=>window.model().sceneNames[0]==='INTRO');
 await page.getByRole('button',{name:'Launch scene 1',exact:true}).click();
 await page.evaluate(()=>{window.reject=true});await set('BPM',130);
 if(!await page.locator('.sq-status').textContent().then(t=>t.includes('test refusal')))throw Error('refusal not visible');
 if(await page.evaluate(()=>window.model().bpmX100)!==12000)throw Error('refusal mutated model');
 await tab('Clip');
 await page.evaluate(()=>{window.reject=false;window.seq.update({playing:true,scene:0,step:4,songIndex:0,tracks:[{active:1,playing:0,posTick:96}]})});
 if(await page.locator('[data-roll-playhead]').isHidden())throw Error('playhead hidden for playing clip while another clip queued');
 if(!await page.locator('[data-play-position]').textContent().then(t=>t.includes('Scene 1 · Step 5')))throw Error('Queued scene shown as playing');
 const midi = Buffer.from([77,84,104,100,0,0,0,6,0,0,0,1,0,96,77,84,114,107,0,0,0,12,0,144,67,100,96,128,67,0,0,255,47,0]);
 await page.locator('.sq-file-tools > summary').click();
 const beforeBatch = await page.evaluate(() => ({ doc: JSON.stringify(window.doc), calls: window.calls.length }));
 await page.getByLabel('Import MIDI files',{exact:true}).setInputFiles(Array.from({length:17},(_,i)=>({name:`Part${i}.mid`,mimeType:'audio/midi',buffer:midi})));
 await page.waitForFunction(()=>document.querySelector('.sq-status').textContent.includes('at most 16 MIDI files'));
 if(await page.getByTestId('midi-import-preview').count()||await page.evaluate(()=>JSON.stringify(window.doc))!==beforeBatch.doc||await page.evaluate(()=>window.calls.length)!==beforeBatch.calls)throw Error('Oversized MIDI batch changed the preview or native project');
 await page.getByLabel('Import MIDI files',{exact:true}).setInputFiles([{name:'Lead.mid',mimeType:'audio/midi',buffer:midi},{name:'Bass.mid',mimeType:'audio/midi',buffer:midi}]);
 await page.getByTestId('midi-import-preview').waitFor();
 await page.getByLabel('Existing clips',{exact:true}).selectOption('replace');
 await page.getByTestId('apply-midi-import').click();
 await page.waitForFunction(()=>document.querySelector('.sq').getAttribute('aria-busy')==='false');
 if(!await page.locator('.sq-status').textContent().then(t=>t.includes('unmapped longer clip')))throw Error('Unsafe import was not refused');
 await tab('Scenes');
 await page.getByRole('button',{name:'Edit scene 3',exact:true}).click();
 await page.getByTestId('apply-midi-import').click();
 await page.waitForFunction(()=>window.model().tracks[1].clips[2]?.notes.length===1);
 if(await page.evaluate(()=>window.model().tracks[1].clips[2].notes[0].pitch)!==67)throw Error('MIDI mapping');
 await tab('Scenes');
 await page.getByRole('button',{name:'Edit scene 1',exact:true}).click();
 await tab('Clip');
 if(await page.locator('.sq-note').first().evaluate(e=>e.getBoundingClientRect().height>24))throw Error('Note exceeds piano row');
 await tab('Scenes');
 let slots=0;do{slots+=await page.locator('[data-live-track]').count();if(await page.getByRole('button',{name:'Next scenes page',exact:true}).isDisabled())break;await page.getByRole('button',{name:'Next scenes page',exact:true}).click();}while(true);if(slots!==64)throw Error('Scene paging lost native slots');
 while(!await page.getByRole('button',{name:'Previous scenes page',exact:true}).isDisabled())await page.getByRole('button',{name:'Previous scenes page',exact:true}).click();
 await page.getByRole('button',{name:'Launch clip 1 scene 1',exact:true}).click();
 await page.getByRole('button',{name:'Launch scene 2',exact:true}).click();
 while(!await page.getByRole('button',{name:'Next scenes page',exact:true}).isDisabled())await page.getByRole('button',{name:'Next scenes page',exact:true}).click();
 await page.getByRole('button',{name:'Stop track 8 scene 8',exact:true}).click();
 while(!await page.getByRole('button',{name:'Previous scenes page',exact:true}).isDisabled())await page.getByRole('button',{name:'Previous scenes page',exact:true}).click();
 if(!await page.evaluate(()=>window.calls.includes('clip 0 0')&&window.calls.includes('scene 1')&&window.calls.includes('clip 7 7')))throw Error('Native scene/clip callbacks');
 const sceneEdit=page.getByRole('button',{name:'Edit track 2 scene 2',exact:true});await sceneEdit.focus();await sceneEdit.press('Enter');
 if(await page.getByLabel('Edit scene',{exact:true}).inputValue()!=='1')throw Error('Matrix edit did not select scene');
 if(await page.getByRole('tab',{name:'Clip',exact:true}).getAttribute('aria-selected')!=='true')throw Error('Clip click must open editor');
 if(await page.evaluate(()=>document.activeElement.getAttribute('data-view'))!=='Clip')throw Error('Keyboard scene edit did not focus the Clip tab');
 await tab('Scenes');
 await page.screenshot({path:`${out}/matrix-desktop.png`,fullPage:true});
 await page.setViewportSize({width:390,height:844});
 if(!await page.getByTestId('song-rotate-prompt').isVisible())throw Error('Missing rotate prompt');
 if(await page.getByRole('tab',{name:'Scenes',exact:true}).isVisible())throw Error('Portrait workspace visible');
 await page.screenshot({path:`${out}/portrait.png`,fullPage:true});
 await page.setViewportSize({width:844,height:390});
 if(await page.getByTestId('song-rotate-prompt').isVisible())throw Error('Landscape blocked');
 for(const view of ['Scenes','Arrangement','Clip','Automation','Mixer']){
  await tab(view);
  if(['Scenes','Arrangement','Mixer'].includes(view)&&(await page.getByRole('combobox',{name:'Edit scene',exact:true}).count()||await page.getByRole('combobox',{name:'Edit track',exact:true}).count()))throw Error(`${view} view retained redundant edit selectors`);
  if(view==='Mixer'){
   const toggle=page.getByRole('button',{name:'Routing & FX',exact:true});
   if(await toggle.getAttribute('aria-expanded')!=='false'||await page.locator('.sq-track-routing').isVisible()||await page.locator('.sq-device-rack').first().isVisible())throw Error('Landscape mixer routing and effects should start collapsed');
   await toggle.click();
   if(await toggle.getAttribute('aria-expanded')!=='true'||!await page.locator('.sq-track-routing').isVisible()||!await page.locator('.sq-device-rack').first().isVisible())throw Error('Landscape Routing & FX disclosure did not restore mixer controls');
   if(await page.evaluate(()=>document.activeElement.getAttribute('aria-label'))!=='Routing & FX')throw Error('Routing & FX focus was lost when the disclosure redrew');
   await toggle.click();
  }
  if(await page.getByRole('tabpanel').count()!==1)throw Error('Stacked workspace views');
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Landscape document overflow');
  await page.screenshot({path:`${out}/landscape-${view.toLowerCase()}.png`,fullPage:true});
 }
 await tab('Clip');await page.getByRole('button',{name:'Add note',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.sq').getAttribute('aria-busy')==='false');
 await set('Velocity',63);
 if(!await page.evaluate(()=>window.model().tracks[1].clips[1].notes.some(n=>n.vel===63)))throw Error('Landscape editing');
 await page.setViewportSize({width:1440,height:1100});
 for(const view of ['Scenes','Arrangement','Clip','Automation','Mixer']){
  await tab(view);await page.screenshot({path:`${out}/desktop-${view.toLowerCase()}.png`,fullPage:true});
 }
 await page.getByRole('tab',{name:'Mixer',exact:true}).press('Home');
 if(await page.getByRole('tab',{name:'Scenes',exact:true}).getAttribute('aria-selected')!=='true')throw Error('Tab Home navigation');
 await page.getByRole('tab',{name:'Scenes',exact:true}).press('ArrowRight');
 if(await page.getByRole('tab',{name:'Arrangement',exact:true}).getAttribute('aria-selected')!=='true')throw Error('Tab arrow navigation');
 // The real Verse lead begins at step 33. Opening it must find its notes,
 // including in the shorter landscape roll, without changing project data.
 await page.evaluate(async()=>{window.doc=await (await fetch('/examples/satellite-hearts.lunar')).json();window.seq.invalidate();await window.seq.refresh()});
 const songBefore=await page.evaluate(()=>JSON.stringify(window.doc));
 async function noteInRoll(){return page.locator('[data-note="0"]').evaluate(e=>{
  const n=e.getBoundingClientRect(),r=e.closest('[data-scroll="piano"]'),b=r.getBoundingClientRect();
  return n.top>=b.top+r.clientTop&&n.bottom<=b.top+r.clientTop+r.clientHeight&&n.left>=b.left+r.clientLeft&&n.right<=b.left+r.clientLeft+r.clientWidth;
 })}
 for(const size of [{width:1440,height:1100},{width:844,height:390}]){
  await page.setViewportSize(size);await tab('Arrangement');
  await page.getByRole('button',{name:'Track 4, Verse, 12 notes, 12 bars',exact:true}).click();
  if(await page.getByLabel('Edit track',{exact:true}).inputValue()!=='3'||await page.getByLabel('Edit scene',{exact:true}).inputValue()!=='1')throw Error('Verse lead selection');
  if(!await page.locator('[data-note="0"]').count()||!await noteInRoll())throw Error(`Verse notes not framed at ${size.width}px`);
  await page.screenshot({path:`${out}/verse-notes-${size.width}.png`,fullPage:true});
  // Scene-matrix keyboard opening follows the same navigation path.
  await tab('Scenes');await page.getByRole('button',{name:'Edit track 4 scene 2',exact:true}).press('Enter');
  if(!await noteInRoll())throw Error('Matrix keyboard opening did not reveal notes');
  // A subsequent note selection and native refresh preserve manual scrolling.
  await page.locator('[data-scroll="piano"]').evaluate(e=>{e.scrollTop=240;e.scrollLeft=50});
  const scroll=await page.locator('[data-scroll="piano"]').evaluate(e=>[e.scrollLeft,e.scrollTop]);
  await page.locator('[data-note="0"]').dispatchEvent('click');
  await page.evaluate(async()=>{await window.seq.refresh(true)});
  if(JSON.stringify(await page.locator('[data-scroll="piano"]').evaluate(e=>[e.scrollLeft,e.scrollTop]))!==JSON.stringify(scroll))throw Error('Note selection/refresh reset manual scroll');
  await tab('Arrangement');await tab('Clip');
  if(!await noteInRoll())throw Error('Clip tab entry did not reveal existing notes');
 }
 if(await page.evaluate(()=>JSON.stringify(window.doc))!==songBefore)throw Error('Clip navigation mutated the song');
 // Empty offset loops open inside the loop; a late high/low note is framed
 // even when notes are stored out of time order or sustain into the loop.
 for(const pitch of [0,127]){
  await page.evaluate(async pitch=>{
   const {emptyClip,writeSet}=await import('/editor/sequence-model.js');const m=window.model();
   m.tracks[7].clips[1]=emptyClip(32);m.tracks[7].clips[1].loopStart=64;
   m.tracks[7].clips[1].notes=[{tick:72*24,gate:24,pitch,vel:90,step:72},{tick:63*24,gate:48,pitch,vel:80,step:63}];
   window.doc.set=writeSet(m);window.seq.invalidate();await window.seq.refresh();
  },pitch);
  await tab('Scenes');await page.getByRole('button',{name:'Edit track 8 scene 2',exact:true}).click();
  if(!await page.locator('.sq-page-nav .sq-caption').textContent().then(t=>{const r=t.match(/Steps (\d+)–(\d+)/);return +r[1]<=65&&+r[2]>=65}))throw Error('Offset loop opened before its sounding notes');
  if(!await page.locator('[data-note="1"]').evaluate(e=>{const n=e.getBoundingClientRect(),r=e.closest('[data-scroll="piano"]').getBoundingClientRect();return n.top>=r.top&&n.bottom<=r.bottom}))throw Error('Extreme pitch sustain not revealed');
 }
 await page.evaluate(async()=>{const m=window.model();m.tracks[7].clips[1].notes=[];window.doc.set=(await import('/editor/sequence-model.js')).writeSet(m);window.seq.invalidate();await window.seq.refresh()});
 await tab('Scenes');await page.getByRole('button',{name:'Edit track 8 scene 2',exact:true}).click();
 if(await page.locator('.sq-note').count()||!await page.locator('.sq-page-nav .sq-caption').textContent().then(t=>{const r=t.match(/Steps (\d+)–(\d+)/);return +r[1]<=65&&+r[2]>=65}))throw Error('Empty offset loop navigation');
 if(errors.length)throw Error(errors.join('\n'));
 await writeFile(`${out}/results.json`,JSON.stringify({passed:true,errors,note,checks:['native track names across views','rename Enter/blur/Escape and touch button','invalid/refused rename canonical rollback','held mouse and touch blur preserve destination selection','note fields','probability','locks','routing','song repeats','scene launch','refusal rollback','playhead while next scene queued','mobile overflow','input focus','multi-file MIDI mapping','note drag','gate resize','insert/master/mix targets','sound/master fader values and dB display','incremental keyboard level edit','pointer fader drag lifecycle','meter and level telemetry subscription','synthetic sound/master meter updates','device inspector focus and restoration','Files & export disclosure import','desktop routing and FX expanded by default','mobile Routing & FX disclosure toggle','scene selection from scene headings','note row containment','64-slot scene matrix','clip and empty-slot stop callbacks','portrait rotate prompt','844x390 landscape editing','single focused panel','keyboard tab navigation','real Satellite Hearts Verse notes visible at desktop and landscape widths','scene keyboard and Clip tab note framing','manual scroll preserved after note selection and native refresh','navigation leaves project data intact','offset loops with unordered notes, sustaining gates and extreme pitches','empty offset loop navigation']},null,2));
 console.log('PASS sequencer mock-host desktop/mobile checks, real Verse note visibility and offset-loop navigation');
} catch(error) {await page.screenshot({path:`${out}/failure.png`,fullPage:true});console.error({errors});throw error} finally {await browser.close();await new Promise(r=>server.close(r))}
