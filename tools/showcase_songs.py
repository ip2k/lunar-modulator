#!/usr/bin/env python3
"""Original replacement showcases; independent from preserved legacy demos.

Generate Satellite Hearts' six-section electropop project. Musical acceptance
requires listening; this generator only asserts metadata and event invariants.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests import state_canon

META = {e['id']: e for e in json.loads((ROOT/'sim/web/www/meta.json').read_text())['engines']}
FORM = [('Signal', 4), ('Verse', 12), ('Lift', 8), ('Hearts', 16), ('Window', 8), ('Return', 12)]
# Deliberately major-key, including the borrowed iv rather than another minor
# four-chord loop. Every section has its own harmonic order and rhythm.
CHORDS = {'C': (48, 52, 55), 'Em': (47, 52, 55), 'F': (48, 53, 57),
          'Fm': (48, 53, 56), 'G': (47, 50, 55), 'Am': (48, 52, 57)}
ROOTS = {'C': 36, 'Em': 40, 'F': 41, 'Fm': 41, 'G': 43, 'Am': 45}
PROGS = [('C','C','F','G'), ('C','Em','F','Fm'), ('Am','F','G','G'),
         ('C','F','Am','G'), ('Fm','Fm','C','C','Em','F','G','G'),
         ('C','F','Am','G','C','F','Fm','G','C','F','G','C')]
# Hook pitches remain independent of the chord root: short statement, space,
# rising answer, then an emphatic descent. Each tuple is step, pitch, gate.
HOOK = [[(0,76,30),(3,79,36),(6,76,24),(10,74,60)],
        [(2,72,36),(5,74,24),(8,76,48),(14,79,30)],
        [(0,81,36),(4,79,30),(7,76,36),(12,74,48)],
        [(1,76,24),(4,74,24),(7,72,72)]]


def defaults(engine):
    return {p['name']: p['entries'][int(p['def'])] if p['type']=='enum' else p['def']
            for p in META[engine]['params'] if 'per_focus' not in p['flags']}


def sound(engine, level, arp, **overrides):
    params = defaults(engine)
    params.update(overrides)
    return {'engine':engine, 'params':params, 'level':level,
            'inserts':[None,None], 'midi_fx':[copy.deepcopy(arp)]}


def build_satellite():
    doc = copy.deepcopy(state_canon.loads((ROOT/'engines/state/examples/first-orbit.lunar').read_text()))
    doc.update(name='Satellite Hearts',title='Satellite Hearts',
               about='Original electropop: clipped saw hook, tonewheel bass and stabs, straight Comet drums. Six asymmetric sections with a borrowed-minor bridge and written final cadence. Personal MIT composition; listening review pending.')
    doc['session']['current']=3
    doc['session']['key']={'root':'C','scale':'major'}
    arp=copy.deepcopy(doc['sounds'][2]['midi_fx'][0]); arp['on']=False
    doc['sounds']=[sound('comet',65,arp,Kit='Classic',Volume=.63),
                   sound('drawbar',72,arp,Drawbars='Bass',Rotor='Off',Attack=3,Decay=110,Sustain=68,Release=45,Volume=.62),
                   sound('shapes',68,arp,Shape='Saw/Sqr',Timbre=.29,Color=.38,Attack=.008,Release=.14,Volume=.55),
                   sound('drawbar',58,arp,Drawbars='Mellow',Rotor='Off',Attack=8,Decay=170,Sustain=28,Release=90,Volume=.5)]
    drum=doc['sounds'][0]
    focus={p['name']: p['entries'][int(p['def'])] if p['type']=='enum' else p['def'] for p in META['comet']['params'] if 'per_focus' in p['flags']}
    drum['pads']=[copy.deepcopy(focus) for _ in range(16)]
    for pad, edits in {0:{'Decay':.35,'Level':.78,'Tone':.48},3:{'Decay':.23,'Level':.59},6:{'Decay':.13,'Level':.22,'Tone':.34},10:{'Decay':.24,'Level':.26}}.items():
        drum['pads'][pad].update(edits)
    doc['master'][0]['params'].update(Mix=.07,Decay=.3,Size=.43)
    doc['dx7']=[]; doc['mod']['cables']=[]
    lines=['movy1','bpm 12400','swing 50','link 0','key 0 0','sg 0 1 2 3 4 5','se 2']
    for s,(name,_) in enumerate(FORM): lines.append(f'sn {s} {name}')
    routes=[0,1,3,2,0,3,0,2]
    all_events={}
    for t,slot in enumerate(routes):
        lines += [f'tk {t} 0 0', f'rt {t} 1 {slot}']
        for scene,(_,bars) in enumerate(FORM):
            events=[]
            def add(bar,step,pitch,gate=24,velocity=90):
                tick=(bar*16+step)*24
                assert tick+gate<=bars*384
                events.append((tick,gate,pitch,velocity,bar*16+step))
            for bar in range(bars):
                chord=PROGS[scene][bar%len(PROGS[scene])]
                final=scene==5 and bar>=8
                end=scene==5 and bar==bars-1
                # The last bar lands on C and then leaves the final beat empty.
                if t==0:
                    steps=[0,4,8,12] if scene!=4 else ([0,9] if bar>=4 else [])
                    if scene==0 and bar<2: steps=[0,8]
                    if scene==3 and bar in (7,11): steps=[0,4,8] if bar==7 else [0,8]
                    if scene==1 and bar%4==3: steps=[0,4,8]
                    if end: steps=[0,4,8]
                    for step in steps: add(bar,step,36,18,101 if step==0 else 91)
                elif t==1:
                    steps=[(0,60),(6,36),(10,48),(14,30)] if scene in (3,5) else [(0,90),(8,60)]
                    if scene==4: steps=[(0,180)] if bar%2==0 else []
                    if end: steps=[(0,180)]
                    for step,gate in steps: add(bar,step,ROOTS[chord],gate,94)
                elif t==2:
                    steps=[2,10] if scene in (1,3,5) else [0,8] if scene==2 else [0] if scene==4 else []
                    if scene==4 and bar%2: steps=[]
                    if scene==3 and bar==11: steps=[]
                    if scene==3 and bar==7: steps=[2]
                    if end: steps=[0]
                    for step in steps:
                        for pitch in CHORDS[chord]: add(bar,step,pitch+12,42 if scene!=4 else 150,73)
                elif t==3:
                    phrase=HOOK[bar%4] if scene in (3,5) else HOOK[bar%4][:2] if scene==1 and bar%4>=2 else []
                    if scene==0 and bar==3: phrase=[(8,76,24),(11,79,30)]
                    if scene==2: phrase=[(4,74,42),(10,76,48)] if bar%2 else [(0,72,72)]
                    if scene==3 and bar==7: phrase=HOOK[3][:2]
                    if scene==3 and bar==11: phrase=[]
                    if scene==3 and bar in (9,13): phrase=[(2,76,36),(5,79,24),(8,81,48),(14,79,30)]
                    if scene==3 and bar==15: phrase=[(1,76,24),(4,74,24),(8,72,96)]
                    if scene==4:
                        middle=[[(1,68,60),(5,67,48),(10,65,72)],
                                [(3,63,72),(8,65,60),(13,67,36)],
                                [(0,64,96),(7,67,60),(12,72,60)],
                                [(2,71,72),(9,67,96)]]
                        phrase=middle[bar%4]
                        if bar==4: phrase=[(1,64,60),(5,67,48),(10,71,72)]
                        if bar==5: phrase=[(3,69,72),(8,67,60),(13,65,36)]
                        if bar==7: phrase=[(2,67,72),(9,71,96)]
                    if final: phrase=[(step,pitch-12,gate) for step,pitch,gate in phrase]
                    if end: phrase=[(0,72,132)]
                    for step,pitch,gate in phrase: add(bar,step,pitch,gate,97)
                elif t==4:
                    steps=[2,6,10,14] if scene in (1,3,5) else [6,14] if scene==2 else []
                    if scene==0 and bar>=2: steps=[6,14]
                    if scene==3 and bar in (7,11): steps=[2,6]
                    if scene==1 and bar%4==3: steps=[2,6,10]
                    if end: steps=[2,6]
                    for step in steps: add(bar,step,42,12,53 if step==14 else 43)
                elif t==5:
                    # A single midrange answer, never a duplicate chord note.
                    if scene in (3,5) and bar%4==3 and not end and bar not in (7,11): add(bar,14,67,36,67)
                elif t==6:
                    if scene not in (0,4):
                        steps=[4,12] if not end else [4]
                        if scene==3 and bar in (7,11): steps=[4]
                        for step in steps: add(bar,step,39,18,86)
                    if scene==1 and bar%4==3: add(bar,15,37,18,64)
                    if scene==3 and bar==15: add(bar,15,38,18,68)
                    if scene==2 and bar==bars-1: add(bar,15,38,18,67)
                elif t==7:
                    # No polyphonic doubling of the main hook: octave answer
                    # only in its resting last beat, and absent at the cadence.
                    if scene==3 and bar%4==3 and bar not in (7,11,15): add(bar,13,84,36,73)
                    if scene==5 and bar%4==1 and not final: add(bar,12,84,24,69)
            events.sort()
            assert len(events)<=512
            all_events[t,scene]=events
            encoded=';'.join(':'.join(map(str,e)) for e in events)
            lines += [f'cl {t} {scene} {bars*16} 0 {encoded}',f'cp {t} {scene} 1 1 0 0']
    # Exact same-pitch overlaps across tracks routed to one sound are invalid
    # for these envelope-driven parts, even if separate clip authoring hid them.
    for scene in range(len(FORM)):
        for slot in range(1,4):
            sounding={}
            for e in sorted(e for (t,s),ev in all_events.items() if s==scene and routes[t]==slot for e in ev):
                tick,gate,pitch,*_=e
                assert tick>=sounding.get(pitch,0),(scene,slot,pitch,tick)
                sounding[pitch]=tick+gate
    doc['set']=lines
    for s in doc['sounds']:
        for p in META[s['engine']]['params']:
            records=s.get('pads',[]) if 'per_focus' in p['flags'] else [s['params']]
            for record in records:
                v=record[p['name']]
                assert v in p['entries'] if p['type']=='enum' else p['min']<=v<=p['max'],(s['engine'],p['name'],v)
    assert len(doc['about'])<=240
    return doc



def build_packet():
    """Fractured E-Dorian piece: call/space/answer, not a chord-loop reskin."""
    doc=copy.deepcopy(state_canon.loads((ROOT/'engines/state/examples/first-orbit.lunar').read_text()))
    doc.update(name='Packet Bloom',title='Packet Bloom',
               about='Original fractured electronic piece: E-Dorian modal calls, rounded phase bass, sparse Crater drums and tuned Sophie accents. Five asymmetric scenes with an empty hinge and dissolving tail; owner listening pending.')
    doc['session']['current']=3; doc['session']['key']={'root':'E','scale':'dorian'}
    arp=copy.deepcopy(doc['sounds'][2]['midi_fx'][0]);arp['on']=False
    doc['sounds']=[sound('crater',57,arp,Volume=.57,Accent=75),
                   sound('phase-bend',66,arp,**{'Wave':'Double Sine','DCW':19,'Env':27,'Attack':15,'Decay':460,'Sustain':48,'Release':260,'Volume':.55}),
                   sound('macro-heavy',60,arp,**{'Model':'Modal','Harmonics':.24,'Timbre':.34,'Morph':.47,'Decay':.48,'Colour':.27,'Volume':.5,'LPG':'Ping'}),
                   sound('sw-sophie',43,arp)]
    for slot,engine in [(0,'crater'),(3,'sw-sophie')]:
        pad={p['name']:p['entries'][int(p['def'])] if p['type']=='enum' else p['def'] for p in META[engine]['params'] if 'per_focus' in p['flags']}
        doc['sounds'][slot]['pads']=[copy.deepcopy(pad) for _ in range(16)]
    for pad,edits in {0:{'Decay':.3,'Level':.78},2:{'Decay':.24,'Level':.46},6:{'Decay':.09,'Level':.15},8:{'Decay':.17,'Level':.2}}.items(): doc['sounds'][0]['pads'][pad].update(edits)
    # Sophie note numbers select pads, not chromatic pitches: tune each chosen
    # pad explicitly. Short metallic accents cannot become a shrill chord bed.
    for pad,tune in [(1,-12),(4,-5),(7,2),(11,7)]:
        doc['sounds'][3]['pads'][pad].update(Tune=tune,Decay=.19,Model='Fuse',Color=16,Metal=12,Feedback=3,Sweep=0)
    doc['master'][0]['params'].update(Mix=.12,Decay=.48,Size=.57)
    doc['dx7']=[];doc['mod']['cables']=[]
    form=[('Mist',8),('Packets',10),('Hinge',6),('Bloom',12),('Dissolve',4)]
    lines=['movy1','bpm 8200','swing 50','link 0','key 4 3','sg 0 1 2 3 4','se 2']
    for scene,(name,_) in enumerate(form):lines.append(f'sn {scene} {name}')
    routes=[0,1,2,3,0,2,0,3];all_events={}
    # Original four-bar modal call: leaps and offbeat entries with a full
    # silent bar. B-D-E-F#-A is never a chord-root transposition template.
    calls=[[(1,71,96),(9,74,60)],[(5,76,84),(13,78,48)],[],[(3,81,48),(8,78,60),(12,76,72)]]
    for t,slot in enumerate(routes):
        lines += [f'tk {t} 0 0',f'rt {t} 1 {slot}']
        for scene,(_,bars) in enumerate(form):
            events=[]
            def add(bar,step,pitch,gate=24,vel=80,nudge=0):
                tick=(bar*16+step)*24+nudge
                assert 0<=tick and tick+gate<=bars*384
                events.append((tick,gate,pitch,vel,bar*16+step))
            for bar in range(bars):
                tail=scene==4;hinge=scene==2
                if t==0:
                    steps=([0,11] if bar%2==0 else [3]) if scene in (1,3) else [0] if scene==0 and bar in (4,6) else []
                    if scene==3 and bar in (4,7):steps=[11] if bar==4 else []
                    if tail and bar==0:steps=[0]
                    for step in steps:add(bar,step,36,18,90,nudge=0 if step==0 else 3)
                elif t==1:
                    if not hinge and (not tail or bar==0):
                        pitch=[40,40,45,47][bar%4] if scene==3 else 40
                        step=6 if scene==3 and bar==5 else 0 if bar%2==0 else 3
                        add(bar,step,pitch,190 if bar%2==0 else 150,83)
                elif t==2:
                    phrase=calls[bar%4]
                    if hinge:phrase=[(6,66,150)] if bar in (0,3) else []
                    if scene==0 and bar<4:phrase=phrase[:1]
                    if scene==3 and bar in (5,9):phrase=[(5,73,60),(9,74,48),(13,78,48)]  # C-sharp Dorian color
                    if scene==3 and bar==7:phrase=[(3,81,48),(10,78,72)]
                    if scene==3 and bar>=8:phrase=[(step,pitch-12,gate) for step,pitch,gate in phrase]
                    if tail:phrase=[(2,76,150)] if bar==0 else [(7,71,150)] if bar==2 else []
                    for step,pitch,gate in phrase:add(bar,step,pitch,gate,84,nudge=3)
                elif t==3:
                    if scene==3 and bar==7:add(bar,13,47,18,45,nudge=-3)
                    if scene in (1,3) and bar%4 in (1,2) and not (scene==3 and bar==6):add(bar,10 if bar%4==1 else 5,37 if bar%4==1 else 43,18,55,nudge=-3)
                elif t==4:
                    if scene in (1,3):
                        steps=[2,10,15] if bar%2==0 else [6,13]
                        if scene==3 and 4<=bar<8:steps=[1,7,12] if bar in (4,6) else [5,14]
                        for step in steps:add(bar,step,42,12,42,nudge=4)
                elif t==5:
                    # Low modal answering voice on separate pitches, sparse.
                    if scene==3 and bar%4==2:add(bar,7,61 if bar==6 else 62,126,65,nudge=6)
                    if scene==1 and bar in (3,7):add(bar,1,57,170,62)
                elif t==6:
                    if scene in (1,3) and not (scene==3 and bar in (4,7)):add(bar,8,38,18,74,nudge=6)
                    if scene==1 and bar==9:add(bar,14,44,18,48,nudge=-4)
                elif t==7:
                    if scene==0 and bar in (2,6):add(bar,12,40,18,46)
                    if hinge and bar==4:add(bar,2,47,18,43)
            events.sort();assert len(events)<=512;all_events[t,scene]=events
            lines += [f'cl {t} {scene} {bars*16} 0 '+ ';'.join(':'.join(map(str,e))for e in events),f'cp {t} {scene} 1 1 0 0']
    for scene in range(len(form)):
        for slot in (1,2):
            ends={}
            for tick,gate,pitch,*_ in sorted(e for (t,s),ev in all_events.items() if s==scene and routes[t]==slot for e in ev):
                assert tick>=ends.get(pitch,0),(scene,slot,pitch,tick)
                ends[pitch]=tick+gate
    doc['set']=lines
    for snd in doc['sounds']:
        for param in META[snd['engine']]['params']:
            records=snd.get('pads',[]) if 'per_focus' in param['flags'] else [snd['params']]
            for record in records:
                v=record[param['name']]
                assert v in param['entries'] if param['type']=='enum' else param['min']<=v<=param['max']
    assert len(doc['about'])<=240
    return doc



def build_relay_or_event(style):
    from tools import demo_songs
    config=next(x for x in demo_songs.SONGS if x['style']==style)
    # Retain the required engine/patch work, replace every legacy clip/chain.
    doc=demo_songs.build(config)
    arp=copy.deepcopy(state_canon.loads((ROOT/'engines/state/examples/first-orbit.lunar').read_text())['sounds'][2]['midi_fx'][0]);arp['on']=False
    for snd in doc['sounds']:snd['midi_fx']=[copy.deepcopy(arp)]
    doc['mod']['cables']=[]
    future=style=='future'
    if future:
        form=[('Air',8),('Call',12),('Rise',4),('Impact',16),('Suspense',8),('OpenSky',16),('Land',4)]
        routes=[0,3,1,2,0,1,0,2]
        prog=[(41,48,53,56),(37,44,49,53),(44,51,56,60),(39,46,51,55)]
        melody=[[(1,77,48),(5,80,60),(11,84,72)],[(0,82,96),(8,80,48),(13,77,48)],[(2,75,60),(7,77,96)],[(0,80,72),(6,77,72),(12,75,60)]]
        doc['about']='Original future bass: seven asymmetric sections, per-note Trio Saw x3 filter-envelope hook, EP replies and long held Acid Square bass. Deep drums use half-time and displaced accents. Acid post-note release capability remains unchanged.'
    else:
        form=[('Porch',8),('Relay',16),('Drift',12),('Home',8)]
        routes=[0,1,2,3,0,2,0,3]
        prog=[(45,52,57,60),(41,48,53,57),(38,45,50,53),(40,47,56,59)]
        melody=[[(1,76,96),(7,79,72),(12,76,60)],[(3,74,96),(10,72,96)],[(0,69,120),(8,72,48),(12,74,72)],[(2,76,144),(11,72,96)]]
        doc['about']='Original chillwave: a foreground FM6 LUNAR LEAD melody with warm short chords, soft Punch drums and uneven delayed hats. Four long contrasting sections, major-color drift and a written minor-home ending. Owner listening pending.'
        doc['sounds'][0]['level']=60
        doc['master'][0]['params']['Mix']=.08
    lines=['movy1',f"bpm {15000 if future else 10400}",'swing 50','link 0',f"key {5 if future else 9} 1",'sg '+' '.join(map(str,range(len(form)))),'se 2']
    for scene,(name,_) in enumerate(form):lines.append(f'sn {scene} {name}')
    all_events={}
    for t,slot in enumerate(routes):
        lines += [f'tk {t} 0 0',f'rt {t} 1 {slot}']
        for scene,(_,bars) in enumerate(form):
            events=[]
            def add(bar,step,pitch,gate=24,vel=84,nudge=0):
                tick=(bar*16+step)*24+nudge
                assert 0<=tick and tick+gate<=bars*384
                events.append((tick,gate,pitch,vel,bar*16+step))
            for bar in range(bars):
                p=prog[bar%4]
                last=scene==len(form)-1 and bar==bars-1
                if future:
                    drop=scene in (3,5);empty=scene==4
                    if t==0:
                        steps=[0,6,14] if drop and bar%2==0 else [0,10] if drop else [0] if scene==1 else []
                        if drop and bar%8==7:steps=[0]
                        if scene==5 and bar>=8 and bar%4==2:steps=[2,12]
                        if last:steps=[0]
                        for st in steps:add(bar,st,36,18,99)
                    elif t==1:
                        if scene not in (0,2,4):
                            if last:add(bar,0,41,264,94)
                            else:
                                add(bar,0,p[0],252,94)
                                if bar%4!=3:add(bar,12,p[0],72,86)
                    elif t==2:
                        if scene in (0,1,4,6):
                            for pitch in p[1:]:add(bar,2,pitch+12,132 if not empty else 240,68)
                    elif t==3:
                        phrase=melody[bar%4] if drop else melody[bar%4][:1] if scene==1 and bar%4>1 else []
                        if scene==2:phrase=[(4,77,48),(10,80,72)] if bar<3 else [(0,84,72)]
                        if scene==5 and bar>=8:
                            phrase=[(st,note+12 if bar%4==0 else note,gate)for st,note,gate in phrase]
                            if bar%4==1:phrase=[(3,82,72),(11,77,60)]
                            if bar%4==2:phrase=[]  # EP/Trio answer owns this bar
                        if drop and bar%8==7:phrase=[(2,80,72),(10,77,72)]
                        if last:phrase=[(0,77,240)]
                        for st,note,gate in phrase:add(bar,st,note,gate,104)
                    elif t==4:
                        if drop or scene==1:
                            for st in ([3,7,11,15] if bar%2==0 else [5,13]):add(bar,st,42,12,38)
                    elif t==5:
                        if drop and bar%4==2:
                            for pitch in p[1:]:add(bar,1,pitch,96,64)
                        if empty and bar in (1,5):add(bar,9,72,96,61)
                    elif t==6:
                        if drop or scene==1:
                            if not(scene==5 and bar>=8 and bar%4==2):add(bar,8,38,18,84)
                            else:add(bar,10,38,18,78)
                        if scene==2 and bar>=2:
                            for st in (4,10,13):add(bar,st,38,18,56+bar*4)
                        if last:add(bar,8,39,18,70)
                    elif t==7:
                        # Answer belongs after main releases and on a different
                        # pitch, not duplicated retriggers on a second track.
                        if scene==5 and bar%4==2:
                            if bar>=8:
                                for st,note,gate in [(1,72,72),(6,75,72),(12,77,72)]:add(bar,st,note,gate,82)
                            else:add(bar,13,72,48,78)
                else:
                    main=scene in (1,3);drift=scene==2
                    if drift:p=[(48,55,60,64),(43,50,55,59),(41,48,53,57),(38,45,50,53)][bar%4]
                    if scene==3 and bar>=6:p=prog[0]
                    if t==0:
                        steps=[0,7,10] if main and bar%2==0 else [0,9] if main else [0] if scene==0 and bar>=4 else []
                        if drift and bar>=8:steps=[0,10]
                        if last:steps=[0]
                        for st in steps:add(bar,st,36,18,86,nudge=0 if st==0 else 4)
                    elif t==1:
                        if scene!=0 or bar>=2:add(bar,0,p[0],240,80,nudge=2)
                    elif t==2:
                        if scene!=0 or bar>=2:
                            for st in ([2,10] if main else [1]):
                                for pitch in p[1:]:add(bar,st,pitch,72 if main else 156,65,nudge=3)
                    elif t==3:
                        phrase=melody[bar%4] if main else [(3,79,120),(11,76,96)] if drift and bar%4==1 else []
                        if scene==0 and bar==7:phrase=[(10,72,96)]
                        if scene==1 and bar in (7,11):phrase=[]
                        if scene==3 and bar>=4:phrase=[(st,note-12,gate)for st,note,gate in phrase]
                        if last:phrase=[(1,69,240)]
                        for st,note,gate in phrase:add(bar,st,note,gate,96,nudge=-2)
                    elif t==4:
                        if main:
                            for st,vel in ([(2,37),(6,44),(13,34)] if bar%2==0 else [(5,39),(11,33)]):add(bar,st,42,12,vel,nudge=6)
                    elif t==5:
                        if drift and bar%4==3:add(bar,9,64,120,57,nudge=5)
                    elif t==6:
                        if main:add(bar,4,38,18,73,nudge=4);add(bar,12,38,18,67,nudge=5)
                        if drift and bar in (3,7,11):add(bar,12,37,18,54,nudge=4)
                    elif t==7:
                        if drift and bar%4==2:add(bar,6,71,132,79,nudge=2)
            events.sort();assert len(events)<=512;all_events[t,scene]=events
            lines += [f'cl {t} {scene} {bars*16} 0 '+';'.join(':'.join(map(str,e))for e in events),f'cp {t} {scene} 1 1 0 0']
    for scene in range(len(form)):
        for slot in range(1,4):
            ends={}
            for tick,gate,pitch,*_ in sorted(e for (t,s),ev in all_events.items() if s==scene and routes[t]==slot for e in ev):
                assert tick>=ends.get(pitch,0),(style,scene,slot,pitch,tick)
                ends[pitch]=tick+gate
    doc['set']=lines
    assert len(doc['about'])<=240
    return doc


def main():
    doc=build_satellite()
    content=state_canon.dumps(doc)
    for relative in ['engines/state/examples/satellite-hearts.lunar','sim/web/www/examples/satellite-hearts.lunar']:
        (ROOT/relative).write_text(content)
    (ROOT/'sim/web/test/satellite-hearts.json').write_text(json.dumps([{'file':'../../../engines/state/examples/satellite-hearts.lunar','title':'Satellite Hearts','bpm':124,'bars':60,'scenes':6}],indent=2)+'\n')
    print('Satellite Hearts: 60 bars, six distinct chained scenes, 124 BPM; source invariants passed')
    packet=state_canon.dumps(build_packet())
    # New path keeps the owner-rejected original Packet Bloom example intact.
    for relative in ['engines/state/examples/packet-bloom-showcase.lunar','sim/web/www/examples/packet-bloom-showcase.lunar']:
        (ROOT/relative).write_text(packet)
    (ROOT/'sim/web/test/packet-bloom-showcase.json').write_text(json.dumps([{'file':'../../../engines/state/examples/packet-bloom-showcase.lunar','title':'Packet Bloom','bpm':82,'bars':40,'scenes':5}],indent=2)+'\n')
    print('Packet Bloom: 40 bars, five distinct chained scenes, 82 BPM; source invariants passed')
    for style,slug,bpm,bars,scenes,title in [('chill','afterglow-relay-showcase',104,44,4,'Afterglow Relay'),('future','event-horizon-showcase',150,68,7,'Event Horizon')]:
        content=state_canon.dumps(build_relay_or_event(style))
        for relative in [f'engines/state/examples/{slug}.lunar',f'sim/web/www/examples/{slug}.lunar']:(ROOT/relative).write_text(content)
        (ROOT/f'sim/web/test/{slug}.json').write_text(json.dumps([{'file':f'../../../engines/state/examples/{slug}.lunar','title':title,'bpm':bpm,'bars':bars,'scenes':scenes}],indent=2)+'\n')
        print(f'{title}: {bars} bars, {scenes} distinct scenes, {bpm} BPM; source invariants passed')

if __name__=='__main__': main()
