// Viewport paging, editing geometry and native follow in a canonical mock host.
import {launch} from './launch.mjs';
import {serve} from './serve.mjs';
import {mkdir,writeFile} from 'node:fs/promises';
const out=process.argv[3]||'scratch/sequencer-fit-grid';await mkdir(out,{recursive:true});
const {server,url}=await serve(process.argv[2]||'sim/web/www',18875);
const {browser}=await launch();const page=await browser.newPage({viewport:{width:1440,height:1100}});
const errors=[];page.on('pageerror',e=>errors.push(e.message));const check=(ok,msg)=>{if(!ok)throw Error(msg)};
const tab=name=>page.getByRole('tab',{name,exact:true}).click();
try {
 await page.route('**/harness.html',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/editor/editor.css"><style>body{display:block;margin:16px}main{width:100%;max-width:1300px;margin:auto}</style><main class="ed"><header id="transport"></header></main>'}));
 await page.goto(url.replace('index.html','harness.html'));
 await page.evaluate(async()=>{
  const {makeSequencer}=await import('/editor/sequencer.js');const {emptySet,emptyClip,writeSet,parseSet}=await import('/editor/sequence-model.js');
  const m=emptySet();m.song=Array.from({length:64},(_,i)=>i%8);m.tracks.forEach((t,i)=>{t.route={kind:1,index:i%4};t.clips[0]=emptyClip(256)});
  m.tracks[0].clips[0].notes=[{step:32,tick:768,gate:24,pitch:60,vel:90},{step:255,tick:6120,gate:24,pitch:60,vel:80}];m.tracks[0].lanes[0]={label:'Cutoff',base:64};m.tracks[0].lanes[1]={label:'mix:Level',base:90};m.tracks[0].clips[0].locks=[{lane:0,step:0,value:12},{lane:1,step:0,value:101},{lane:0,step:255,value:33},{lane:1,step:255,value:77}];
  window.doc={set:writeSet(m),sounds:[{engine:'Punch'}]};window.transport={playing:false,tracks:[{playing:0,active:0,posTick:0}]};window.model=()=>parseSet(window.doc.set);window.calls=[];
  const telemetry={sections:[{name:'meters',offset:0,mask:0,rows:['out.post_master'],fields:['peak','rms']}]};
  window.seq=makeSequencer({transportHost:document.querySelector('#transport'),fetchProject:async()=>structuredClone(window.doc),applyProject:async d=>{window.doc=d},getTransport:()=>window.transport,metadata:{doc:{telemetry},engine:()=>({params:[{name:'Cutoff',type:'float',min:0,max:1,def:.5,flags:[]} ]})},watchTrack:t=>window.calls.push(['watch',t]),playScene:s=>window.calls.push(['scene',s]),playClip:(t,s)=>window.calls.push(['clip',t,s])});
  document.querySelector('main').append(window.seq.render());await window.seq.refresh();
 });
 check(await page.locator('.sq .sq-transport').count()===0&&await page.locator('#transport .sq-transport').count()===1,'External transport duplicated or detached');
 check(await page.evaluate(()=>window.seq.contains(document.querySelector('#transport button'))),'External transport excluded from shortcuts');
 const metro=page.getByRole('button',{name:'Metronome',exact:true});check(await metro.locator('svg').count()===1&&await metro.textContent()==='','Metronome is not icon-only');
 await metro.click();await page.waitForFunction(()=>window.doc.settings.metronome===1);check(await metro.getAttribute('aria-pressed')==='true','Metronome toggle lost state');
 await page.evaluate(()=>window.seq.onTelemetry(new Float32Array([.5,.25])));check(await page.getByRole('meter',{name:'Master output',exact:true}).getAttribute('aria-valuenow')==='-6.0','External master meter stale');
 const before=await page.evaluate(()=>JSON.stringify(window.doc));
 async function noOverflow(){check(await page.locator('.sq-scroll').evaluateAll(es=>es.every(e=>e.scrollWidth<=e.clientWidth+1)),'Horizontal grid overflow');check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Document overflow')}
 for(const size of [{width:1440,height:1100},{width:1024,height:768},{width:844,height:390},{width:667,height:375}]){
  await page.setViewportSize(size);await page.waitForTimeout(80);
  for(const name of ['Scenes','Arrangement','Clip','Automation']){
   await tab(name);await noOverflow();
   if(name==='Scenes'||name==='Arrangement'){check(await page.getByRole('button',{name:/Select track/}).count()===0,'Visible Select track remains');const header=page.getByRole('group',{name:'Track 2 header',exact:true});await page.evaluate(()=>window.calls=[]);await header.click({position:{x:4,y:4}});check(await header.getAttribute('aria-current')==='true'&&await page.evaluate(()=>window.calls.every(c=>c[0]==='watch')),'Whitespace did not select only the track');check(await page.getByLabel('Track 2 name',{exact:true}).evaluate(e=>e.readOnly),'Header selected name edit');await page.getByRole('group',{name:'Track 1 header',exact:true}).press('Enter');check(await page.getByRole('group',{name:'Track 1 header',exact:true}).getAttribute('aria-current')==='true','Keyboard header selection failed')}
   if(name==='Scenes'||name==='Arrangement'){
    const noun=name==='Scenes'?'scenes':'sections',selector=name==='Scenes'?'[data-live-track]':'.sq-entry';let count=0;
    const pager=page.locator('.sq-section-heading .sq-page-nav.is-compact');
    check(await pager.count()===1&&await page.locator('.sq-timeline > .sq-page-nav').count()===0,'Pager remains in a separate timeline row');
    check(await pager.locator('button svg').count()===2&&await pager.locator('button').evaluateAll(es=>es.every(e=>e.textContent==='')),'Pager arrows are not icon-only');
    check(await page.locator('.sq-section-heading').evaluate(e=>{const h=e.querySelector('h3').getBoundingClientRect(),p=e.querySelector('.sq-page-nav').getBoundingClientRect();return Math.abs((h.top+h.bottom)-(p.top+p.bottom))<2&&p.left-h.right>=6&&p.left-h.right<=12}),'Pager is not immediately beside heading on the same row');
    while(!await page.getByRole('button',{name:`Previous ${noun} page`,exact:true}).isDisabled())await page.getByRole('button',{name:`Previous ${noun} page`,exact:true}).click();
    let expectedFirst=1;do{const visible=await page.locator(selector).count(),columns=name==='Scenes'?visible/8:visible;count+=visible;check(await pager.locator('.sq-caption').textContent()===`${name==='Scenes'?'Scenes':'Sections'} ${expectedFirst}–${expectedFirst+columns-1} / ${name==='Scenes'?8:64}`,'Pager range or total does not match visible columns');expectedFirst+=columns;await noOverflow();if(await page.getByRole('button',{name:`Next ${noun} page`,exact:true}).isDisabled())break;await page.getByRole('button',{name:`Next ${noun} page`,exact:true}).click()}while(true);
    check(count===64,`${name} paging did not reach all native entries`);
   }else{
    check(await page.locator('.sq-clip-heading .sq-page-nav.is-compact button svg').count()===2,'Step paging is not compact');
    check(await page.getByLabel('Scene and clip tools',{exact:true}).textContent()==='','Scene tools disclosure retains visible paragraph label');
    const gridSelector=name==='Clip'?'[data-scroll="piano"]':'[data-scroll="locks"]',gridTop=await page.locator(gridSelector).evaluate(e=>e.getBoundingClientRect().top+scrollY);
    await page.getByLabel('Scene and clip tools',{exact:true}).click();check(await page.getByRole('button',{name:'Copy clip',exact:true}).isVisible()&&await page.locator(gridSelector).evaluate(e=>e.getBoundingClientRect().top+scrollY)===gridTop,'Tools disclosure moved grid or hid copy controls');await noOverflow();await page.getByLabel('Scene and clip tools',{exact:true}).click();
    if(name==='Clip'&&size.width<=844)check(await page.locator('.sq-clip-heading').evaluate((e,top)=>top-e.getBoundingClientRect().top-scrollY<=150,gridTop),'Landscape Clip header consumed too much vertical space');
    const gridBottom=await page.locator(name==='Clip'?'[data-scroll="steps"]':'[data-scroll="locks"]').evaluate(e=>e.getBoundingClientRect().bottom);
    check(await page.getByLabel('Edit track',{exact:true}).evaluate((e,b)=>e.getBoundingClientRect().top>=b,gridBottom)&&await page.getByLabel('Edit scene',{exact:true}).evaluate((e,b)=>e.getBoundingClientRect().top>=b,gridBottom),'Edit selectors are above numbered grid');
    if(name==='Clip'){check(await page.locator('.sq-ruler .sq-octaves button svg').count()===2,'Clef octave controls are outside pitch label column');check(await page.getByRole('button',{name:'Octave ↑',exact:true}).textContent()===''&&await page.getByRole('button',{name:'Octave ↓',exact:true}).textContent()==='','Octave controls are not icon-only');const low=await page.locator('.sq-pitch-row').last().textContent();await page.getByRole('button',{name:'Octave ↑',exact:true}).click();check(await page.locator('.sq-pitch-row').last().textContent()!==low,'Treble control did not shift octave');await page.getByRole('button',{name:'Octave ↓',exact:true}).click();check(await page.locator('.sq-pitch-row').last().textContent()===low,'Bass control did not restore octave');}
    while(!await page.getByRole('button',{name:'Previous steps page',exact:true}).isDisabled())await page.getByRole('button',{name:'Previous steps page',exact:true}).click();
    if(name==='Automation'){check(await page.locator('[data-automation-lane]').count()===2,'Existing lanes require a dropdown');check(!await page.getByLabel('Lock lane',{exact:true}).isVisible(),'Assignment controls are not transient');check(await page.getByRole('button',{name:'Lane 1, step 1 automation',exact:true}).getAttribute('aria-description')==='lock 12'&&await page.getByRole('button',{name:'Lane 2, step 1 automation',exact:true}).getAttribute('aria-description')==='lock 101','Independent first-page lane values missing')}
    const indices=new Set();do{for(const i of await page.locator(name==='Clip'?'[data-step]':'[data-automation-step]').evaluateAll(es=>es.map(e=>Number(e.dataset.step??e.dataset.automationStep))))indices.add(i);await noOverflow();if(await page.getByRole('button',{name:'Next steps page',exact:true}).isDisabled())break;await page.getByRole('button',{name:'Next steps page',exact:true}).click()}while(true);
    check(indices.size===256&&indices.has(255),`${name} did not expose all 256 steps`);
    if(name==='Automation'){check(await page.getByRole('button',{name:'Lane 1, step 256 automation',exact:true}).getAttribute('aria-description')==='lock 33'&&await page.getByRole('button',{name:'Lane 2, step 256 automation',exact:true}).getAttribute('aria-description')==='lock 77','Independent last-page lane values missing');await page.evaluate(()=>window.seq.update({playing:true,tracks:[{active:0,playing:0,posTick:255*24}]}));check(await page.locator('[data-automation-playhead]:not([hidden])').count()===2,'Paged lane playheads missing')}
   }
   await page.screenshot({path:`${out}/${size.width}-${name.toLowerCase()}.png`,fullPage:true});
  }
 }
 check(await page.evaluate(()=>JSON.stringify(window.doc))===before,'Paging mutated song');
 await tab('Clip');check(await page.locator('[data-note="0"]').count()===1,'First sounding note not framed');
 const follow=page.getByRole('button',{name:'Follow playhead',exact:true});if(await follow.getAttribute('aria-pressed')!=='true')await follow.click();
 await page.evaluate(()=>{window.transport.playing=true;window.transport.tracks[0].posTick=255*24;window.seq.update(window.transport)});
 check(await page.locator('[data-step="255"]').count()===1&&!await page.locator('[data-roll-playhead]').isHidden(),'Follow did not reach last native step');
 await page.evaluate(()=>{window.transport.tracks[0].posTick=0;window.seq.update(window.transport)});check(await page.locator('[data-step="0"]').count()===1&&!await page.locator('[data-roll-playhead]').isHidden(),'Loop wrap did not return first page');
 await page.getByRole('button',{name:'Next steps page',exact:true}).click();const manual=await page.locator('.sq-page-nav').textContent();
 await page.evaluate(()=>{window.transport.tracks[0].posTick=0;window.seq.update(window.transport)});check(await follow.getAttribute('aria-pressed')==='false'&&await page.locator('.sq-page-nav').textContent()===manual,'Manual paging did not stay put');
 await follow.click();await page.getByLabel('Loop length · steps',{exact:true}).focus();const held=await page.locator('.sq-page-nav').textContent();
 await page.evaluate(()=>{window.transport.tracks[0].posTick=255*24;window.seq.update(window.transport)});check(await page.locator('.sq-page-nav').textContent()===held,'Follow replaced an editing field');
 await page.getByLabel('Loop length · steps',{exact:true}).blur();await page.evaluate(()=>window.seq.update(window.transport));check(await page.locator('[data-step="255"]').count()===1,'Follow did not resume after edit');
 // Held pointers and unsaved fields keep their nodes while Follow/resize waits.
 await page.evaluate(()=>{document.querySelector('.sq').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));window.transport.tracks[0].posTick=0;window.seq.update(window.transport)});check(await page.locator('[data-step="255"]').count()===1,'Follow replaced held pointer target');
 await page.evaluate(()=>{window.dispatchEvent(new PointerEvent('pointerup'));window.seq.update(window.transport)});check(await page.locator('[data-step="0"]').count()===1,'Follow did not resume after pointer release');
 await page.getByLabel('Loop length · steps',{exact:true}).focus();await page.evaluate(()=>window.heldField=document.activeElement);await page.setViewportSize({width:1024,height:768});await page.waitForTimeout(80);check(await page.evaluate(()=>window.heldField.isConnected&&document.activeElement===window.heldField),'Resize replaced unsaved field');
 await page.getByLabel('Loop length · steps',{exact:true}).blur();await page.waitForFunction(()=>!window.heldField.isConnected,{},{timeout:2000});await noOverflow();
 await page.evaluate(async()=>{document.querySelector('#transport').replaceChildren();window.seq.update({playing:false});await window.seq.refresh(true);document.querySelector('main').append(window.seq.render())});check(await page.locator('#transport [data-play-position]').count()===1,'Transport remount did not recover');
 check(errors.length===0,errors.join('\n'));await page.evaluate(()=>{window.seq.destroy();document.querySelector('#transport').innerHTML='<span data-play-position>Replacement</span><span data-sq-meter="out.post_master" aria-valuenow="-60"></span>';window.seq.update(window.transport);window.seq.onTelemetry(new Float32Array([.5,.25]));window.seq.syncLevels()});check(await page.locator('#transport [data-play-position]').textContent()==='Replacement'&&await page.locator('#transport [data-sq-meter]').getAttribute('aria-valuenow')==='-60','Disposed instance mutated replacement transport');
 await writeFile(`${out}/results.json`,JSON.stringify({passed:true,checks:['viewport fit 1440 1024 844 667','compact icon pagers beside headings with every visible range and total','all 64 scene slots and arrangement entries','all 256 note and lock steps','external transport telemetry and lifecycle','icon metronome','first-note framing','native follow last-step loop-wrap manual-off edit-defer pointer-defer','responsive resize preserves unsaved input','multiple independent lane values and page playheads','track header whitespace and keyboard select without launch/name edit'],errors},null,2));console.log('PASS viewport grids and native Follow playhead');
}catch(e){await page.screenshot({path:`${out}/failure.png`,fullPage:true});throw e}finally{await browser.close();server.close()}
