"""Bind physical-state transitions to spoken words, then hold the reached state."""
import math

def _number(v):
    if not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v):raise ValueError('Scene state must be a finite number')
    return float(v)

def validate(page):
    events=page.get('scene_events',[]);initial=page.get('scene_initial',{})
    if not isinstance(events,list) or not isinstance(initial,dict):raise ValueError('scene_events must be a list and scene_initial an object')
    for value in initial.values():_number(value)
    cues={c['id']:c for c in page['cues']};seen=set()
    for e in events:
        if not e.get('id') or e['id'] in seen:raise ValueError('Scene events need unique ids')
        seen.add(e['id'])
        if e.get('track') not in initial:raise ValueError(f'{e["id"]}: declare track in scene_initial')
        _number(e.get('to'))
        if ('duration' in e)==('until' in e):raise ValueError('Scene event needs exactly one of duration or until')
        if 'duration' in e and _number(e['duration'])<=0:raise ValueError('Scene duration must be positive')
        if e.get('easing','linear') not in ('linear','smooth'):raise ValueError('Scene easing must be linear or smooth')
        for point in [e]+([e['until']] if 'until' in e else []):
            cue=cues.get(point.get('cue_id',e.get('cue_id')))
            if cue is None:raise ValueError(f'{e["id"]}: unknown spoken cue')
            at=point.get('at','start')
            valid=at in ('start','end') if isinstance(at,str) else isinstance(at,dict)
            if not valid:raise ValueError('Scene anchors use start, end or a word object')
            if isinstance(at,dict):
                from course import anchor
                anchor(at,cue,{'duration':1,'words':[]})
    return events

def bind(page,cues,duration):
    from course import anchor
    validate(page);lookup={c['id']:c for c in cues};out=[]
    def at_point(point,default_cue):
        c=lookup[point.get('cue_id',default_cue)];at=point.get('at','start')
        if at=='start':return c['start'],'cue-start'
        if at=='end':return c['end'],'cue-end'
        local,quality=anchor(at,c,{'duration':c['end']-c['start'],'words':c.get('words',[])})
        time=c['start']+local
        if not c['start']<=time<=c['end']:raise ValueError('Scene word anchor leaves its spoken cue')
        return time,quality
    for e in page.get('scene_events',[]):
        start,q=at_point(e,e['cue_id'])
        end,q2=at_point(e['until'],e['cue_id']) if 'until' in e else (start+e['duration'],'duration')
        if not 0<=start<end<=duration+1e-6:raise ValueError(f'{e["id"]}: scene event leaves page time')
        out.append({**e,'start':start,'end':end,'anchor_quality':q,'end_anchor_quality':q2})
    out.sort(key=lambda x:x['start']);previous={}
    for e in out:
        prev=previous.get(e['track'])
        if prev and e['start']<prev['end']-1e-6:raise ValueError(f'{e["id"]}: overlapping scene events on {e["track"]}')
        e['from']=prev['to'] if prev else page['scene_initial'][e['track']]
        previous[e['track']]=e
    return {'initial':page.get('scene_initial',{}),'events':out}

def value(page,track,t):
    data=page.get('scene_tracks',page);result=data['initial'][track]
    for e in data['events']:
        if e['track']!=track:continue
        if t<e['start']:break
        f=max(0,min(1,(t-e['start'])/(e['end']-e['start'])))
        if e.get('easing')=='smooth':f=f*f*(3-2*f)
        result=e['from']+(e['to']-e['from'])*f
    return result
