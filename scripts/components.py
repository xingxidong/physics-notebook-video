"""Parameterized physics diagrams expanded into ordinary editable ink actions."""
import copy,math,re

CATALOG={
    'force-diagram':'受力图',
    'inclined-plane':'斜面与滑块',
    'projectile-trajectory':'抛体轨迹',
    'electric-dipole':'电偶极与场线',
    'gaussian-surface':'高斯面',
    'circuit-loop':'直流回路',
    'thin-lens':'薄透镜成像',
    'wave-profile':'机械波形',
}

def _number(value,name,lo=None,hi=None):
    if not isinstance(value,(int,float)) or not math.isfinite(float(value)):
        raise ValueError(f'component.{name} must be a finite number')
    value=float(value)
    if lo is not None and value<lo:raise ValueError(f'component.{name} must be at least {lo}')
    if hi is not None and value>hi:raise ValueError(f'component.{name} must be at most {hi}')
    return value

def _point(value,name='origin'):
    if not isinstance(value,list) or len(value)!=2:raise ValueError(f'component.{name} must be [x,y]')
    return [_number(value[0],name),_number(value[1],name)]

def _pt(origin,x,y,scale=1):return [origin[0]+x*scale,origin[1]+y*scale]

def _poly(points,**style):return {'type':'stroke','points':points,**style}

def _arrow_label(origin,angle,length,label,color,scale):
    a=math.radians(angle);tip=_pt(origin,length*math.cos(a),-length*math.sin(a),scale)
    side=1 if math.sin(a)>=0 else -1
    label_at=[tip[0]+8*scale,tip[1]-12*side*scale]
    return [
        {'type':'arrow','from':origin,'to':tip,'color':color,'width':2.7*scale},
        {'type':'math','latex':label,'x':label_at[0],'y':label_at[1],'size':27*scale,'color':color},
    ]

def _force_diagram(raw):
    o=_point(raw.get('origin',[220,180]));s=_number(raw.get('scale',1),'scale',.35,2.5)
    body=raw.get('body',[62,42])
    if not isinstance(body,list) or len(body)!=2:raise ValueError('force-diagram body must be [width,height]')
    bw,bh=[_number(v,'body',12,180)*s for v in body]
    actions=[{'type':'rect','x':o[0]-bw/2,'y':o[1]-bh/2,'w':bw,'h':bh,'color':raw.get('body_color','ink'),'width':2.6*s}]
    forces=raw.get('forces') or [
        {'label':r'F_N','angle':90,'length':92,'color':'blue'},
        {'label':'mg','angle':-90,'length':92,'color':'red'},
        {'label':'f','angle':180,'length':72,'color':'green'},
    ]
    if not isinstance(forces,list) or not 1<=len(forces)<=10:raise ValueError('force-diagram forces needs 1..10 vectors')
    for force in forces:
        if not isinstance(force,dict) or not force.get('label'):raise ValueError('Each force needs a label')
        angle=_number(force.get('angle'),'force angle',-720,720);length=_number(force.get('length',86),'force length',18,260)
        actions.extend(_arrow_label(o,angle,length,str(force['label']),force.get('color','blue'),s))
    return actions

def _inclined_plane(raw):
    o=_point(raw.get('origin',[28,318]));s=_number(raw.get('scale',1),'scale',.35,2.2)
    length=_number(raw.get('length',350),'length',120,520)*s;angle=_number(raw.get('angle',28),'angle',8,70);a=math.radians(angle)
    top=[o[0]+length*math.cos(a),o[1]-length*math.sin(a)]
    actions=[
        {'type':'line','from':o,'to':top,'color':'ink','width':3*s},
        {'type':'line','from':o,'to':[top[0],o[1]],'color':'ink','width':2.2*s},
        {'type':'dashed_line','from':top,'to':[top[0],o[1]],'color':'muted'},
    ]
    r=42*s;arc=[_pt(o,r*math.cos(t),-r*math.sin(t)) for t in [a*k/18 for k in range(19)]]
    actions.extend([_poly(arc,color='blue',width=2*s),{'type':'math','latex':raw.get('angle_label',r'\theta'),'x':o[0]+48*s,'y':o[1]-12*s,'size':25*s,'color':'blue'}])
    f=_number(raw.get('block_position',.58),'block_position',.18,.86);c=[o[0]+f*(top[0]-o[0]),o[1]+f*(top[1]-o[1])]
    tangent=[math.cos(a),-math.sin(a)];normal=[-math.sin(a),-math.cos(a)];bw,bh=62*s,39*s
    corners=[]
    for u,v in [(-bw/2,-bh/2),(bw/2,-bh/2),(bw/2,bh/2),(-bw/2,bh/2),(-bw/2,-bh/2)]:
        corners.append([c[0]+u*tangent[0]+v*normal[0],c[1]+u*tangent[1]+v*normal[1]])
    actions.append(_poly(corners,color=raw.get('block_color','red'),width=2.8*s))
    actions.append({'type':'math','latex':raw.get('block_label','m'),'x':c[0]-9*s,'y':c[1]-5*s,'size':24*s,'color':raw.get('block_color','red')})
    return actions

def _projectile(raw):
    o=_point(raw.get('origin',[38,305]));s=_number(raw.get('scale',1),'scale',.25,2.5)
    speed=_number(raw.get('speed',22),'speed',1,200);angle=_number(raw.get('angle',42),'angle',2,88);gravity=_number(raw.get('gravity',9.8),'gravity',.1,50)
    flight=2*speed*math.sin(math.radians(angle))/gravity;duration=_number(raw.get('duration',flight),'duration',.05,100)
    space=_number(raw.get('space_scale',7.2),'space_scale',.3,40)*s
    pts=[]
    for k in range(61):
        t=duration*k/60;x=speed*math.cos(math.radians(angle))*t;y=speed*math.sin(math.radians(angle))*t-.5*gravity*t*t;pts.append([o[0]+space*x,o[1]-space*y])
    vmax=82*s;tip=[o[0]+vmax*math.cos(math.radians(angle)),o[1]-vmax*math.sin(math.radians(angle))]
    mid=pts[len(pts)//2]
    return [
        {'type':'arrow','from':o,'to':[o[0]+max(220*s,pts[-1][0]-o[0]+20*s),o[1]],'color':'ink','width':2.2*s},
        {'type':'arrow','from':o,'to':[o[0],o[1]-210*s],'color':'ink','width':2.2*s},
        _poly(pts,color=raw.get('trajectory_color','blue'),width=3*s),
        {'type':'arrow','from':o,'to':tip,'color':'red','width':2.8*s},
        {'type':'math','latex':raw.get('velocity_label',r'v_0'),'x':tip[0]+5*s,'y':tip[1]-8*s,'size':26*s,'color':'red'},
        {'type':'arrow','from':[mid[0]+20*s,mid[1]-25*s],'to':[mid[0]+20*s,mid[1]+45*s],'color':'green','width':2.6*s},
        {'type':'math','latex':'g','x':mid[0]+30*s,'y':mid[1]+17*s,'size':25*s,'color':'green'},
    ]

def _electric_dipole(raw):
    c=_point(raw.get('center',[225,185]),'center');s=_number(raw.get('scale',1),'scale',.35,2.2);sep=_number(raw.get('separation',180),'separation',70,330)*s
    left=[c[0]-sep/2,c[1]];right=[c[0]+sep/2,c[1]];actions=[]
    for height in (52,92,132):
        for sign in (-1,1):
            points=[]
            for k in range(41):
                t=k/40;x=left[0]+sep*t;y=c[1]+sign*4*height*t*(1-t);points.append([x,y])
            actions.append(_poly(points,color='blue',width=2.1*s))
            p=points[20];q=points[23];actions.append({'type':'arrow','from':p,'to':q,'color':'blue','width':1.8*s})
    actions.extend([
        {'type':'charge','center':left,'label':raw.get('positive_label','+q'),'size':25*s,'color':'red'},
        {'type':'charge','center':right,'label':raw.get('negative_label','-q'),'size':25*s,'color':'blue'},
        {'type':'arrow','from':[right[0],c[1]+160*s],'to':[left[0],c[1]+160*s],'color':'red','width':2.6*s},
        {'type':'math','latex':raw.get('moment_label',r'\vec p'),'x':c[0]-12*s,'y':c[1]+142*s,'size':27*s,'color':'red'},
    ])
    return actions

def _gaussian_surface(raw):
    c=_point(raw.get('center',[220,185]),'center');s=_number(raw.get('scale',1),'scale',.35,2.2);shape=raw.get('shape','sphere')
    if shape not in ('sphere','cylinder','plane'):raise ValueError('gaussian-surface shape must be sphere, cylinder or plane')
    actions=[]
    if shape=='sphere':
        radius=_number(raw.get('radius',105),'radius',35,190)*s
        actions.extend([{'type':'dashed_circle','center':c,'radius':radius,'color':'blue'},{'type':'charge','center':c,'label':raw.get('charge_label','Q'),'size':27*s,'color':'red'}])
        for angle in range(0,360,45):
            a=math.radians(angle);start=[c[0]+radius*.48*math.cos(a),c[1]+radius*.48*math.sin(a)];end=[c[0]+radius*1.26*math.cos(a),c[1]+radius*1.26*math.sin(a)]
            actions.append({'type':'arrow','from':start,'to':end,'color':'green','width':2.2*s})
        actions.append({'type':'math','latex':raw.get('surface_label',r'\Sigma'),'x':c[0]+radius*.72,'y':c[1]-radius*.72,'size':26*s,'color':'blue'})
    elif shape=='cylinder':
        length=_number(raw.get('length',260),'length',100,390)*s;radius=_number(raw.get('radius',65),'radius',25,120)*s;left=[c[0]-length/2,c[1]];right=[c[0]+length/2,c[1]]
        actions.extend([{'type':'ellipse','center':left,'rx':22*s,'ry':radius,'color':'blue','width':2.2*s},{'type':'ellipse','center':right,'rx':22*s,'ry':radius,'color':'blue','width':2.2*s},{'type':'line','from':[left[0],c[1]-radius],'to':[right[0],c[1]-radius],'color':'blue','width':2.2*s},{'type':'line','from':[left[0],c[1]+radius],'to':[right[0],c[1]+radius],'color':'blue','width':2.2*s}])
        for dy in (-radius*.55,0,radius*.55):actions.append({'type':'arrow','from':[left[0]+25*s,c[1]+dy],'to':[right[0]-25*s,c[1]+dy],'color':'green','width':2.2*s})
    else:
        w=_number(raw.get('width',280),'width',100,420)*s;h=_number(raw.get('height',145),'height',60,260)*s;x,y=c[0]-w/2,c[1]-h/2
        for a,b in [([x,y],[x+w,y]),([x+w,y],[x+w,y+h]),([x+w,y+h],[x,y+h]),([x,y+h],[x,y])]:actions.append({'type':'dashed_line','from':a,'to':b,'color':'blue'})
        for k in range(5):
            px=x+w*(k+1)/6;actions.append({'type':'arrow','from':[px,c[1]+55*s],'to':[px,c[1]-55*s],'color':'green','width':2.2*s})
    return actions

def _circuit(raw):
    o=_point(raw.get('origin',[35,55]));s=_number(raw.get('scale',1),'scale',.35,2.2);w=_number(raw.get('width',350),'width',160,500)*s;h=_number(raw.get('height',240),'height',100,380)*s
    x,y=o;mid=x+w/2;gap=72*s;actions=[]
    actions.extend([
        {'type':'line','from':[x,y],'to':[mid-gap/2,y],'color':'ink','width':2.7*s},
        {'type':'line','from':[mid+gap/2,y],'to':[x+w,y],'color':'ink','width':2.7*s},
        {'type':'line','from':[x+w,y],'to':[x+w,y+h],'color':'ink','width':2.7*s},
        {'type':'line','from':[x+w,y+h],'to':[x,y+h],'color':'ink','width':2.7*s},
        {'type':'line','from':[x,y+h],'to':[x,y+h*.60],'color':'ink','width':2.7*s},
        {'type':'line','from':[x,y+h*.40],'to':[x,y],'color':'ink','width':2.7*s},
    ])
    zig=[]
    for k in range(9):zig.append([mid-gap/2+gap*k/8,y+(0 if k in (0,8) else (-1 if k%2 else 1)*11*s)])
    actions.extend([_poly(zig,color='red',width=2.7*s),{'type':'math','latex':raw.get('resistance_label','R'),'x':mid-10*s,'y':y-34*s,'size':27*s,'color':'red'}])
    actions.extend([
        {'type':'line','from':[x-18*s,y+h*.44],'to':[x+18*s,y+h*.44],'color':'blue','width':2.6*s},
        {'type':'line','from':[x-29*s,y+h*.56],'to':[x+29*s,y+h*.56],'color':'blue','width':2.6*s},
        {'type':'math','latex':raw.get('emf_label',r'\varepsilon'),'x':x+20*s,'y':y+h*.47,'size':26*s,'color':'blue'},
        {'type':'arrow','from':[x+w*.68,y+h],'to':[x+w*.48,y+h],'color':'green','width':2.5*s},
        {'type':'math','latex':raw.get('current_label','I'),'x':x+w*.57,'y':y+h-34*s,'size':26*s,'color':'green'},
    ])
    return actions

def _thin_lens(raw):
    c=_point(raw.get('center',[225,185]),'center');s=_number(raw.get('scale',1),'scale',.35,2.2);f=_number(raw.get('focal_length',70),'focal_length',20,150)*s;u=_number(raw.get('object_distance',140),'object_distance',25,330)*s;h=_number(raw.get('object_height',78),'object_height',20,150)*s
    if u<=f:raise ValueError('thin-lens object_distance must be greater than focal_length for the real-image component')
    v=f*u/(u-f);magnification=-v/u;image_h=h*magnification;obj=[c[0]-u,c[1]-h];image=[c[0]+v,c[1]-image_h]
    actions=[
        {'type':'arrow','from':[c[0]-max(u+35*s,190*s),c[1]],'to':[c[0]+max(v+35*s,190*s),c[1]],'color':'ink','width':2*s},
        {'type':'line','from':[c[0],c[1]-155*s],'to':[c[0],c[1]+155*s],'color':'blue','width':3*s},
        {'type':'arrow','from':[c[0]-u,c[1]],'to':obj,'color':'red','width':3*s},
        {'type':'arrow','from':[c[0]+v,c[1]],'to':image,'color':'green','width':3*s},
        {'type':'ellipse','center':[c[0]-f,c[1]],'rx':3*s,'color':'ink','width':2*s},
        {'type':'ellipse','center':[c[0]+f,c[1]],'rx':3*s,'color':'ink','width':2*s},
        {'type':'math','latex':'F','x':c[0]-f-7*s,'y':c[1]+18*s,'size':21*s,'color':'ink'},
        {'type':'math','latex':"F'",'x':c[0]+f-7*s,'y':c[1]+18*s,'size':21*s,'color':'ink'},
        {'type':'line','from':obj,'to':[c[0],obj[1]],'color':'red','width':2.1*s},
        {'type':'line','from':[c[0],obj[1]],'to':image,'color':'red','width':2.1*s},
        {'type':'line','from':obj,'to':image,'color':'blue','width':2.1*s},
    ]
    return actions

def _wave(raw):
    o=_point(raw.get('origin',[30,185]));s=_number(raw.get('scale',1),'scale',.35,2.2);length=_number(raw.get('length',380),'length',120,520)*s;amp=_number(raw.get('amplitude',70),'amplitude',15,140)*s;wavelength=_number(raw.get('wavelength',150),'wavelength',35,360)*s;phase=_number(raw.get('phase',0),'phase',-12.57,12.57)
    points=[[o[0]+length*k/100,o[1]-amp*math.sin(2*math.pi*(length*k/100)/wavelength+phase)] for k in range(101)]
    x1=o[0]+wavelength*.18;x2=x1+wavelength;y=o[1]+amp+45*s
    return [
        {'type':'arrow','from':[o[0]-18*s,o[1]],'to':[o[0]+length+22*s,o[1]],'color':'ink','width':2*s},
        _poly(points,color='blue',width=3*s),
        {'type':'arrow','from':[x1,y],'to':[x2,y],'color':'red','width':2.2*s},
        {'type':'arrow','from':[x2,y],'to':[x1,y],'color':'red','width':2.2*s},
        {'type':'math','latex':raw.get('wavelength_label',r'\lambda'),'x':(x1+x2)/2-8*s,'y':y-30*s,'size':26*s,'color':'red'},
    ]

BUILDERS={
    'force-diagram':_force_diagram,
    'inclined-plane':_inclined_plane,
    'projectile-trajectory':_projectile,
    'electric-dipole':_electric_dipole,
    'gaussian-surface':_gaussian_surface,
    'circuit-loop':_circuit,
    'thin-lens':_thin_lens,
    'wave-profile':_wave,
}

def expand_component(raw,default_id):
    """Return primitive actions and a compact manifest entry for one action."""
    if raw.get('type')!='component':return [copy.deepcopy(raw)],None
    name=raw.get('name')
    if name not in BUILDERS:raise ValueError(f'Unknown physics component {name!r}; choose one of {", ".join(CATALOG)}')
    component_id=str(raw.get('id',default_id))
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',component_id):raise ValueError('component id uses letters, digits, hyphens or underscores')
    actions=BUILDERS[name](raw)
    if not actions:raise ValueError(f'Physics component {name} produced no drawing actions')
    zone=raw.get('zone');relative=raw.get('relative_to',zone)
    for index,action in enumerate(actions):
        if zone:action.setdefault('zone',zone)
        if relative:action.setdefault('relative_to',relative)
        action.update(component_id=component_id,component_name=name,component_part=index)
        if index==0 and 'at' in raw:action['at']=copy.deepcopy(raw['at'])
        if raw.get('allow_overlap'):action['allow_overlap']=True
    public={k:copy.deepcopy(v) for k,v in raw.items() if k not in ('type','at')}
    manifest={'id':component_id,'name':name,'label':CATALOG[name],'zone':zone,'primitive_count':len(actions),'parameters':public}
    return actions,manifest

def _bbox(blocks):
    points=[p for block in blocks for stroke in block.get('strokes',[]) for p in stroke.get('points',[])]
    if not points:return None
    xs=[p[0] for p in points];ys=[p[1] for p in points];return [min(xs),min(ys),max(xs),max(ys)]

def audit_components(pages):
    reports=[];warnings=[];counts={name:0 for name in CATALOG}
    for page in pages:
        blocks=[b for cue in page.get('cues',[]) for b in cue.get('blocks',[])]
        page_items=[]
        for item in page.get('components',[]):
            owned=[b for b in blocks if b.get('component_id')==item['id']];box=_bbox(owned);entry={**item,'bbox':[round(x,1) for x in box] if box else None}
            counts[item['name']]+=1
            if not box:
                warning={'code':'empty-component','page':page['id'],'component_id':item['id'],'message':f'Component {item["id"]} has no ink'};warnings.append(warning);entry.setdefault('warnings',[]).append(warning)
            zone=item.get('zone');spec=page.get('layout')
            if box and zone and spec and zone in spec.get('zones',{}):
                x,y,w,h=spec['zones'][zone];slack=5
                if box[0]<x-slack or box[1]<y-slack or box[2]>x+w+slack or box[3]>y+h+slack:
                    warning={'code':'component-leaves-zone','page':page['id'],'component_id':item['id'],'zone':zone,'message':f'Component {item["id"]} leaves zone {zone}'};warnings.append(warning);entry.setdefault('warnings',[]).append(warning)
            page_items.append(entry)
        reports.append({'page':page['id'],'components':page_items})
    return {'status':'pass' if not warnings else 'attention','catalog':CATALOG,'counts':{k:v for k,v in counts.items() if v},'pages':reports,'warnings':warnings}
