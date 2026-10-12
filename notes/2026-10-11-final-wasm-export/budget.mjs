import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {instantiateFm1} from './www/fm1-wasm.mjs';
const bytes=await readFile('./www/fm1.wasm');
console.log('wasmSHA256',createHash('sha256').update(bytes).digest('hex'));
for(const file of ['afterglow-relay-showcase.lunar','event-horizon-showcase.lunar','packet-bloom-showcase.lunar','satellite-hearts.lunar']) {
  const source=await readFile('./candidates/'+file,'utf8');
  const fm=await instantiateFm1(bytes),ex=fm.exports;
  ex.fm1w_init(44118); ex.fm1w_default_chain();
  const text=new TextEncoder().encode(source);
  assert(text.length<=ex.fm1w_text_cap());
  new Uint8Array(ex.memory.buffer,ex.fm1w_text_buf(),text.length).set(text);
  const loaded=ex.fm1w_state_load(1,0,0,4,text.length);
  const report=fm.string(ex.fm1w_state_report());
  assert.equal(loaded,1,file+': '+report);
  const ram=ex.fm1w_ram(),budget=ex.fm1w_ram_budget();
  assert(ram<=budget,file+': RAM '+ram+' exceeds '+budget);
  assert.equal(fm.calls.length,0);
  console.log(JSON.stringify({file,assetSHA256:createHash('sha256').update(source).digest('hex'),ram,budget,headroom:budget-ram,loaded,report}));
}
console.log('Four showcase exact-Wasm project loads and native RAM bounds: PASS; owner listening remains pending.');
