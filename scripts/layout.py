"""Semantic one-page layouts, formula-step expansion and visual QA."""
import copy

PRESETS={
    'one-page-problem':{
        'zones':{
            'diagram':[145,110,465,365],
            'derivation':[650,110,520,390],
            'explanation':[145,505,465,125],
            'result':[650,530,520,100],
        },
        'line_gap':58,'padding':12,
    },
    'full-derivation':{
        'zones':{
            'context':[145,110,1025,115],
            'derivation':[145,250,1025,310],
            'result':[145,585,1025,55],
        },
        'line_gap':58,'padding':12,
    },
}

def page_spec(value):
    if not value:return None
    if isinstance(value,str):value={'preset':value}
    if not isinstance(value,dict):raise ValueError('page.layout must be a preset name or object')
    preset=value.get('preset','one-page-problem')
    if preset not in PRESETS:raise ValueError(f'Unknown layout preset {preset!r}')
    spec=copy.deepcopy(PRESETS[preset]);spec.update({k:v for k,v in value.items() if k!='zones'});spec['preset']=preset
    spec['zones'].update(value.get('zones',{}))
    for name,rect in spec['zones'].items():
        if not isinstance(rect,list) or len(rect)!=4:raise ValueError(f'Layout zone {name} must be [x,y,w,h]')
        x,y,w,h=map(float,rect)
        if w<=0 or h<=0 or x<120 or y<95 or x+w>1200 or y+h>655:raise ValueError(f'Layout zone {name} leaves the writing area')
        spec['zones'][name]=[x,y,w,h]
    return spec

def _xy(zone,line,gap,padding,dx=0,dy=0):return zone[0]+padding+dx,zone[1]+padding+line*gap+dy

def expand_actions(actions,spec):
    """Expand formula_steps into aligned formula lines; connectors are opt-in."""
    out=[]
    for raw in actions:
        if raw.get('type')!='formula_steps':out.append(copy.deepcopy(raw));continue
        if spec is None:raise ValueError('formula_steps requires a page layout')
        steps=raw.get('steps')
        if not isinstance(steps,list) or not steps:raise ValueError('formula_steps needs a non-empty steps list')
        zone_name=raw.get('zone','derivation');zone=spec['zones'].get(zone_name)
        if zone is None:raise ValueError(f'Unknown formula_steps zone {zone_name!r}')
        start=int(raw.get('start_line',0));gap=float(raw.get('line_gap',spec['line_gap']));padding=float(spec.get('padding',12));previous_y=None
        for index,value in enumerate(steps):
            step={'latex':value} if isinstance(value,str) else copy.deepcopy(value)
            if not isinstance(step,dict) or not isinstance(step.get('latex'),str):raise ValueError('Each formula step needs LaTeX')
            line=int(step.pop('line',start+index));x,y=_xy(zone,line,gap,padding,float(raw.get('dx',0)),float(raw.get('dy',0)))
            if previous_y is not None and raw.get('connect',False):
                out.append({'type':'arrow','from':[x-18,previous_y+18],'to':[x-18,y-8],'width':1.8,'color':raw.get('connector_color','muted'),'zone':zone_name,'allow_overlap':True,'transform_group':raw.get('id')})
            action={k:v for k,v in raw.items() if k not in ('type','steps','start_line','line_gap','connect','connector_color','at','id')}
            action.update(step);action.update(type='math',x=x,y=y,zone=zone_name,transform_group=raw.get('id'),transform_step=index)
            if index==0 and 'at' in raw and 'at' not in action:action['at']=raw['at']
            out.append(action);previous_y=y
    return out

def place_action(raw,spec,state,anchors=None):
    action=copy.deepcopy(raw);place=action.pop('place',None);zone_name=action.get('zone')
    if place:
        if not isinstance(place,dict):raise ValueError('action.place must be an object')
        zone_name=place.get('zone',zone_name);action['zone']=zone_name
    if zone_name and spec is None:raise ValueError(f'Action uses zone {zone_name!r} without page.layout')
    zone=spec['zones'].get(zone_name) if spec and zone_name else None
    if zone_name and zone is None:raise ValueError(f'Unknown layout zone {zone_name!r}')
    if action['type'] in ('text','math') and not action.get('attach_to') and zone and ('x' not in action or 'y' not in action):
        line=int((place or {}).get('line',state.get(zone_name,0)));state[zone_name]=max(state.get(zone_name,0),line+1)
        x,y=_xy(zone,line,float((place or {}).get('line_gap',spec['line_gap'])),float(spec.get('padding',12)),float((place or {}).get('dx',0)),float((place or {}).get('dy',0)))
        action.setdefault('x',x);action.setdefault('y',y)
    relative=action.pop('relative_to',None);attachment=action.pop('attach_to',None)
    if relative and attachment:raise ValueError('Use either attach_to or relative_to on an action')
    if attachment:
        if not anchors or attachment not in anchors:raise ValueError(f'Unknown component anchor {attachment!r}; declare the component before its attached actions')
        ox,oy=anchors[attachment]
        if action['type'] in ('text','math'):action.setdefault('x',0);action.setdefault('y',0)
        if 'x' in action:action['x']=ox+action['x']
        if 'y' in action:action['y']=oy+action['y']
        for key in ('center','from','to','origin'):
            if key in action:action[key]=[ox+action[key][0],oy+action[key][1]]
        if 'points' in action:action['points']=[[ox+p[0],oy+p[1]] for p in action['points']]
    if relative:
        if spec is None or relative not in spec['zones']:raise ValueError(f'Unknown relative layout zone {relative!r}')
        ox,oy=spec['zones'][relative][:2]
        if 'x' in action:action['x']=ox+action['x']
        if 'y' in action:action['y']=oy+action['y']
        for key in ('center','from','to','origin'):
            if key in action:action[key]=[ox+action[key][0],oy+action[key][1]]
        if 'points' in action:action['points']=[[ox+p[0],oy+p[1]] for p in action['points']]
    return action

def focus_spec(value,spec):
    if not value:return None
    value={'zone':value} if isinstance(value,str) else copy.deepcopy(value)
    if not isinstance(value,dict):raise ValueError('cue.focus must be a zone name or object')
    if 'zone' in value:
        if spec is None or value['zone'] not in spec['zones']:raise ValueError(f'Unknown focus zone {value["zone"]!r}')
        value['rect']=spec['zones'][value['zone']]
    rect=value.get('rect')
    if not isinstance(rect,list) or len(rect)!=4:raise ValueError('cue.focus needs a layout zone or rect')
    zoom=float(value.get('zoom',1.06));transition=float(value.get('transition',.35))
    if not 1<=zoom<=1.15 or not .1<=transition<=1.5:raise ValueError('focus zoom must be 1..1.15 and transition 0.1..1.5 seconds')
    return {'rect':list(map(float,rect)),'zoom':zoom,'transition':transition,'zone':value.get('zone')}

def _bbox(block):
    points=[p for stroke in block.get('strokes',[]) for p in stroke['points']]
    if not points:return None
    xs=[p[0] for p in points];ys=[p[1] for p in points];return [min(xs),min(ys),max(xs),max(ys)]

def _intersection(a,b):
    w=max(0,min(a[2],b[2])-max(a[0],b[0]));h=max(0,min(a[3],b[3])-max(a[1],b[1]));return w*h

def audit_page(page):
    spec=page.get('layout');items=[];warnings=[]
    for cue in page['cues']:
        for block in cue['blocks']:
            box=_bbox(block)
            if box:items.append({'cue':cue['id'],'action':block['action'],'type':block.get('kind'),'zone':block.get('zone'),'bbox':[round(x,1) for x in box],'allow_overlap':block.get('allow_overlap',False)})
    readable=[x for x in items if x['type'] in ('text','math','charge') and not x['allow_overlap']]
    for i,a in enumerate(readable):
        for b in readable[i+1:]:
            area=_intersection(a['bbox'],b['bbox']);small=min((a['bbox'][2]-a['bbox'][0])*(a['bbox'][3]-a['bbox'][1]),(b['bbox'][2]-b['bbox'][0])*(b['bbox'][3]-b['bbox'][1]))
            if small>0 and area/small>.08:warnings.append({'code':'overlap','message':f'{a["cue"]}:{a["action"]} overlaps {b["cue"]}:{b["action"]}','items':[a,b]})
    if spec:
        for name,rect in spec['zones'].items():
            area=rect[2]*rect[3];used=sum(max(0,x['bbox'][2]-x['bbox'][0])*max(0,x['bbox'][3]-x['bbox'][1]) for x in readable if x['zone']==name)
            if area and used/area>.72:warnings.append({'code':'zone-density','message':f'Zone {name} density is {used/area:.0%}'})
    return {'page':page['id'],'preset':spec.get('preset') if spec else None,'items':items,'warnings':warnings}

def audit_lesson(pages):
    reports=[audit_page(page) for page in pages];problems={};warnings=[]
    for page,report in zip(pages,reports):
        warnings.extend({'page':page['id'],**w} for w in report['warnings'])
        if page.get('problem_id'):problems.setdefault(page['problem_id'],[]).append(page['id'])
    for problem,ids in problems.items():
        if len(ids)>1:warnings.append({'code':'problem-spans-pages','problem_id':problem,'pages':ids,'message':f'Problem {problem} spans {len(ids)} pages'})
    return {'status':'pass' if not warnings else 'attention','pages':reports,'warnings':warnings}

def focus_state(page,t):
    if page.get('camera')=='static':return {'amount':0,'zoom':1,'center':[640,360]}
    for event in page.get('focus',[]):
        transition=event['transition'];start,end=event['start'],event['end']
        if start-transition<=t<=end+transition:
            rise=max(0,min(1,(t-start+transition)/transition));fall=max(0,min(1,(end+transition-t)/transition));amount=min(rise,fall);amount=amount*amount*(3-2*amount)
            x,y,w,h=event['rect'];return {'amount':amount,'zoom':1+(event['zoom']-1)*amount,'center':[x+w/2,y+h/2]}
    return {'amount':0,'zoom':1,'center':[640,360]}
