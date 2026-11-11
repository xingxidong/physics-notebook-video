"""Load and validate the v0.4 teacher-delivery sidecar."""
import copy,json,re
from pathlib import Path
from oralize import render_parts

ROLE_PRESETS={
    'legacy':{},
    'read_problem':{'speed':1.00,'pause_before':0.05,'pause_after':0.55},
    'observe':{'speed':0.96,'pause_before':0.12,'pause_after':0.65},
    'model':{'speed':0.93,'pause_before':0.18,'pause_after':0.75},
    'derive':{'speed':0.97,'pause_before':0.08,'pause_after':0.65},
    'key_turn':{'speed':0.92,'pause_before':0.28,'pause_after':0.85},
    'conclusion':{'speed':0.91,'pause_before':0.22,'pause_after':1.00},
    'physical_meaning':{'speed':0.95,'pause_before':0.15,'pause_after':0.85},
    'transition':{'speed':1.00,'pause_before':0.08,'pause_after':0.50},
    'explain':{'speed':0.97,'pause_before':0.08,'pause_after':0.70},
}
CLASSROOM_ROLES={
    'read_problem':{'speed':1.02,'pause_before':.04,'pause_after':.25},
    'observe':{'speed':.99,'pause_before':.06,'pause_after':.35},
    'model':{'speed':.97,'pause_before':.08,'pause_after':.35},
    'derive':{'speed':1.00,'pause_before':.04,'pause_after':.22},
    'key_turn':{'speed':.96,'pause_before':.12,'pause_after':.55},
    'conclusion':{'speed':.98,'pause_before':.08,'pause_after':.70},
    'physical_meaning':{'speed':1.00,'pause_before':.06,'pause_after':.35},
    'transition':{'speed':1.04,'pause_before':.04,'pause_after':.15},
    'explain':{'speed':1.00,'pause_before':.04,'pause_after':.25},
}
DELIVERY_FIELDS=('tts','tts_parts','role','speed','pitch','volume','emotion','pause_before','pause_after','pause','pause_reason','emphasis','minimax_pronunciation')

def _safe_sidecar(project,value):
    path=(project/value).resolve()
    try:path.relative_to(project)
    except ValueError:raise ValueError('speech_plan must stay inside the lesson project') from None
    return path

def _clean(value):return ''.join(c for c in str(value) if c.isalnum())

def apply(project,lesson):
    """Merge speech-plan.json into a copied lesson and return metadata."""
    project=Path(project).resolve();lesson=copy.deepcopy(lesson);setting=lesson.get('speech_plan')
    path=None
    if setting is not False:
        candidate=_safe_sidecar(project,setting if isinstance(setting,str) else 'speech-plan.json')
        if candidate.exists():path=candidate
        elif isinstance(setting,str):raise ValueError(f'Missing speech plan: {candidate.name}')
    plan={'version':1,'cues':{}}
    if path:
        plan=json.loads(path.read_text())
        if plan.get('version')!=1 or not isinstance(plan.get('cues'),dict):raise ValueError('speech-plan.json needs version 1 and a cues object')
    if isinstance(plan.get('speech'),dict):lesson['speech']={**lesson.get('speech',{}),**plan['speech']}
    custom=plan.get('roles',{})
    if not isinstance(custom,dict):raise ValueError('speech-plan roles must be an object')
    profile=plan.get('delivery_profile',lesson.get('speech',{}).get('delivery_profile','classic'))
    if profile not in ('classic','classroom'):raise ValueError('delivery_profile must be classic or classroom')
    roles=copy.deepcopy(ROLE_PRESETS)
    if profile=='classroom':
        for name,settings in CLASSROOM_ROLES.items():roles[name].update(settings)
        lesson.setdefault('speech',{}).setdefault('trim_edges',True)
    for name,value in custom.items():
        if not isinstance(value,dict):raise ValueError(f'Custom speech role {name} must be an object')
        roles[name]={**roles.get(name,{}),**value}
    defaults=plan.get('defaults',{})
    if not isinstance(defaults,dict):raise ValueError('speech-plan defaults must be an object')
    entries=plan.get('cues',{});used=set();resolved=[];lexicon={**lesson.get('pronunciation',{}),**plan.get('pronunciation',{})}
    for pi,page in enumerate(lesson.get('pages',[])):
        for ci,original in enumerate(page.get('cues',[])):
            cid=original.setdefault('id',f'{page.get("id",f"p{pi+1:02d}")}-c{ci+1:02d}')
            entry=entries.get(cid,{})
            if not isinstance(entry,dict):raise ValueError(f'Speech plan cue {cid} must be an object')
            used.add(cid);role=entry.get('role',original.get('role',defaults.get('role','explain' if path else 'legacy')))
            if role not in roles:raise ValueError(f'Unknown speech role {role!r} in cue {cid}')
            delivery={**roles[role],**defaults}
            delivery.update({k:original[k] for k in DELIVERY_FIELDS if k in original})
            delivery.update(entry);delivery['role']=role
            if 'tts_parts' in delivery:delivery['tts']=render_parts(delivery['tts_parts'],lexicon)
            delivery.pop('tts_parts',None)
            delivery.setdefault('tts',original.get('text',''))
            if 'pause' in delivery and 'pause_after' not in entry and 'pause_after' not in original:delivery['pause_after']=delivery['pause']
            delivery.pop('pause',None)
            for key in DELIVERY_FIELDS:
                if key in delivery and key!='tts':original[key]=delivery[key]
            original['tts']=delivery['tts'];original['pause']=delivery.get('pause_after',.7);original['pause_before']=delivery.get('pause_before',0)
            emphasis=delivery.get('emphasis',[])
            if not isinstance(emphasis,list) or any(not isinstance(x,str) for x in emphasis):raise ValueError(f'{cid}: emphasis must be a list of words')
            missing=[x for x in emphasis if _clean(x) not in _clean(original['tts'])]
            if missing:raise ValueError(f'{cid}: emphasis words are absent from narration: {missing}')
            resolved.append({'id':cid,**{k:original[k] for k in ('role','tts','speed','pitch','volume','emotion','pause_before','pause') if k in original},'emphasis':emphasis})
    unknown=sorted(set(entries)-used)
    if unknown:raise ValueError(f'Speech plan refers to unknown cue ids: {unknown}')
    return lesson,{'source':path.name if path else 'lesson.json','resolved':resolved,'roles':roles,'delivery_profile':profile}

def externalize(lesson):
    """Move legacy cue narration and delivery fields into a sidecar document."""
    lesson=copy.deepcopy(lesson);cues={}
    for pi,page in enumerate(lesson.get('pages',[])):
        for ci,cue in enumerate(page.get('cues',[])):
            cid=cue.setdefault('id',f'{page.get("id",f"p{pi+1:02d}")}-c{ci+1:02d}')
            entry={}
            for key in DELIVERY_FIELDS:
                if key in cue:entry[key]=cue.pop(key)
            if 'tts' in entry:cue.setdefault('text',entry['tts'])
            if 'pause' in entry:entry['pause_after']=entry.pop('pause')
            entry.setdefault('role','explain');cues[cid]=entry
    lesson['speech_plan']='speech-plan.json'
    return lesson,{'version':1,'defaults':{'role':'explain'},'cues':cues}
