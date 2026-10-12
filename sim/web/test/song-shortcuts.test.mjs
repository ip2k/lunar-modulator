// Keyboard policy and note semantics; no DOM/DSP substitution. MIT.
import test from 'node:test';
import assert from 'node:assert/strict';
import { songCommand, noteNudge, duplicateNote } from '../www/editor/song-shortcuts.js';
const key = (key, options = {}) => ({ key, ...options });

test('transport and view keys keep native Tab/button activation and modifiers', () => {
  assert.equal(songCommand(key(' '), {canvas:true}), 'transport');
  assert.equal(songCommand(key(' ', {shiftKey:true}), {canvas:true}), 'restart');
  assert.equal(songCommand(key(' ')), null);
  assert.equal(songCommand(key('Tab'), {canvas:true}), 'arrangeMix');
  for (const e of [key('Tab'), key('Tab',{shiftKey:true}), key(' ',{ctrlKey:true}), key('Enter')]) assert.equal(songCommand(e), null);
  assert.equal(songCommand(key('e')), 'clip');
  assert.equal(songCommand(key('a')), 'automation');
  assert.equal(songCommand(key('d')), 'device');
  assert.equal(songCommand(key('i')), 'sidebar');
});
test('duplicate requires selection focus while browser/system shortcuts survive', () => {
  for (const modifier of ['ctrlKey','metaKey']) {
    assert.equal(songCommand(key('d',{[modifier]:true})), null);
    assert.equal(songCommand(key('d',{[modifier]:true}),{note:true}), 'duplicate');
    for (const k of ['t','b','z','e','a','0']) assert.equal(songCommand(key(k,{[modifier]:true}),{canvas:true}), null);
  }
  assert.equal(songCommand(key('a',{altKey:true})), 'mute');
  assert.equal(songCommand(key('0')), 'mute');
});
test('repeat, IME, handled events and unrelated controls cannot delete/nudge', () => {
  for (const flag of ['repeat','isComposing','defaultPrevented']) assert.equal(songCommand(key('Delete',{[flag]:true}),{note:true}),null);
  for (const k of ['Delete','Backspace','ArrowUp','ArrowLeft','F2']) assert.equal(songCommand(key(k)),null);
  assert.equal(songCommand(key('Delete'),{section:true}), 'delete');
  assert.equal(songCommand(key('ArrowRight'),{note:true}), 'arrowright');
  assert.equal(songCommand(key('ArrowUp'),{section:true}), null);
  assert.equal(songCommand(key('F2'),{note:true}), 'rename');
});
const fixture = () => ({loopStart:4,length:4,notes:[{step:4,tick:93,gate:36,pitch:60,vel:80}],trigs:[{step:4,lane:60,prob:51,a:2,b:3,invert:1}]});
test('duplicate copies timing, gate, velocity and trigger to next step', () => {
  const c=fixture(), original=structuredClone(c.notes[0]);
  assert.equal(duplicateNote(c,original),1);
  assert.deepEqual(c.notes[1],{...original,step:5,tick:117});
  assert.deepEqual(c.trigs[1],{...c.trigs[0],step:5});
  assert.deepEqual(c.notes[0],original);
});
test('duplicate refuses stale source, end-of-clip, note and trigger collisions', () => {
  const c=fixture(); assert.throws(()=>duplicateNote(c,{...c.notes[0],vel:90}),/changed elsewhere/);
  c.length=1;assert.throws(()=>duplicateNote(c,c.notes[0]),/No next step/); c.length=4;
  c.notes.push({...c.notes[0],step:5,tick:120});assert.throws(()=>duplicateNote(c,c.notes[0]),/already has this pitch/);c.notes.pop();
  c.trigs.push({...c.trigs[0],step:5});assert.throws(()=>duplicateNote(c,c.notes[0]),/already has a trigger/);
  assert.equal(c.notes.length,1);
});
test('nudge preserves microtiming and clamps pitch and clip window', () => {
  const c=fixture(),n=c.notes[0];
  assert.deepEqual(noteNudge(c,n,1,1),{step:5,tick:117,pitch:61});
  assert.deepEqual(noteNudge(c,n,-20,-100),{step:4,tick:93,pitch:0});
  assert.deepEqual(noteNudge(c,n,20,100),{step:7,tick:165,pitch:127});
});
