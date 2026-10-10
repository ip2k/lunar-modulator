import {readFileSync,writeFileSync} from 'node:fs';
import {instantiateFm1} from '../../sim/web/www/fm1-wasm.mjs';
const results=[];
for (const restore of [false,true]) {
 const m=await instantiateFm1(readFileSync('sim/web/www/fm1.wasm')),e=m.exports;
 e.fm1w_init(44118); e.fm1w_default_chain();
 const text=new Uint8Array(m.memory.buffer,e.fm1w_text_buf(),e.fm1w_text_cap());
 const json=new TextEncoder().encode(JSON.stringify({lunar:'1.0',kind:'project',sounds:[{engine:'test-sine',params:{Volume:.7}}],mix:{levels:[100,0,0,0]}}));
 text.set(json); if(!e.fm1w_state_load(0,0,0,4,json.length)) throw Error(m.string(e.fm1w_state_report()));
 const n=e.fm1w_state_save(2,0,2),bin=text.slice(0,n);
 e.fm1w_unit_note_on(0,69,100);
 const audio=[];
 for(let k=0;k<100;k++) { if(k===50 && restore) {text.set(bin);if(!e.fm1w_state_load(2,0,0,20,bin.length))throw Error('restore refused');} const p=e.fm1w_render(64);audio.push(...new Float32Array(m.memory.buffer,p,128)); }
 writeFileSync('scratch/ab-capture/'+(restore?'restore':'control')+'.f32',Buffer.from(new Float32Array(audio).buffer));
 const peak=(a)=>Math.max(...a.map(Math.abs));
 results.push({restore,boundaryFrame:3200,last:audio[6398],first:audio[6400],step:audio[6400]-audio[6398],afterPeak:peak(audio.slice(6400)),beforePeak:peak(audio.slice(6200,6400))});
}
writeFileSync('scratch/ab-capture/probe.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results));
