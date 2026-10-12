import assert from 'node:assert/strict';
import { clipPlayback, automationSteps } from '../www/editor/sequence-playback.js';
import { emptyClip } from '../www/editor/sequence-model.js';
const fast = { ...emptyClip(16), loopStart: 8, scaleNum: 2, scaleDen: 1 };
const slow = { ...emptyClip(64), loopStart: 32, scaleNum: 1, scaleDen: 8 };
assert.deepEqual(clipPlayback(fast, { playing: 1, posTick: 8 * 24 + 192 }, true, 1), { fraction: .5, step: 16 });
assert.equal(clipPlayback(slow, { playing: 0, posTick: 32 * 24 + 192 }, true, 0).fraction, .125);
assert.equal(clipPlayback(fast, { playing: 1, posTick: 8 * 24 }, true, 1).fraction, 0);
assert.equal(clipPlayback(fast, { playing: 1, posTick: 8 * 24 + 6 }, true, 1).fraction, 6 / 384);
for (const [track, playing, scene] of [[{playing:1,posTick:192},false,1],[{playing:1,posTick:192},true,0],[{playing:1,posTick:0},true,1],[{playing:1,posTick:576},true,1],[{playing:1},true,1]]) assert.equal(clipPlayback(fast, track, playing, scene), null);
const c = { ...emptyClip(8), loopStart: 4,
  notes: [{step:6},{step:8}], locks: [{lane:0,step:4,value:90},{lane:0,step:8,value:20},{lane:0,step:11,value:100},{lane:1,step:7,value:30},{lane:0,step:1,value:1}] };
assert.deepEqual(automationSteps(c, 0, 64, 4, 12).map(p => p.value), [90,90,64,64,20,20,20,100]);
assert.equal(automationSteps(c, 0, 64, 6, 7)[0].reset, true);
assert.equal(automationSteps(c, 0, 64, 8, 9)[0].reset, false); // lock wins over note
assert.deepEqual(automationSteps(c, 1, 55, 4, 12).map(p => p.value), [55,55,55,30,55,55,55,55]);
const cyclic = {...emptyClip(4), locks:[{lane:0,step:3,value:100}]};
assert.deepEqual(automationSteps(cyclic,0,64,0,4).map(p=>p.value),[100,100,100,100]);
assert.equal(automationSteps(c,0,64,0,1)[0].inLoop,false);
assert.equal(automationSteps(c,0,64,0,1)[0].value,64);
assert.deepEqual(automationSteps(emptyClip(),0,31,0,2).map(p=>p.value),[31,31]);
assert.deepEqual(automationSteps(c,0,64,12,8),[]);
console.log('PASS native tick projections, independent ratios/offsets/wrap, lock precedence, cyclic carry and note resets');
