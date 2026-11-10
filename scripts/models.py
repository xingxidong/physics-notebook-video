"""Deterministic 2-D demonstrations; geometry is evaluated from physical parameters."""
import copy,math
import ink

def setup(spec):
    if spec.get('kind')=='pursuit':
        from pursuit import setup as pursuit_setup
        return pursuit_setup(spec)
    if spec.get('kind')!='equal-circles':raise ValueError('Unknown demonstration model')
    m={'cx':350,'cy':405,'radius':155,'d0':.45,'d1':1.75,**copy.deepcopy(spec)}
    if not 0<m['d0']<2 or not 0<m['d1']<2:raise ValueError('Circle demo needs 0 < d/R < 2')
    saved=ink.groups;ink.groups=[[]];labels={}
    try:
        for name,obj,size in [('O1',['sub','O','1'],25),('O2',['sub','O','2'],25),('P','P',28),('d','d',27),('v0',['sub','v','0'],27),('vx',['sub','v','x'],26),('vy',['sub','v','y'],26),('v','v',28)]:
            ink.groups[0]=[];ink.formula(0,obj,0,0,size,'#29333c');labels[name]=copy.deepcopy(ink.groups[0])
    finally:ink.groups=saved
    m['labels']=labels;m['start']=0;m['stop']=1;m['vector_start']=0
    for t in [j/10 for j in range(11)]:
        for e in strokes(m,t):
            if any(not(120<=x<=1200 and 95<=y<=655) for x,y in e['points']):raise ValueError('Demonstration leaves the writing area')
    return m

def strokes(m,t):
    if m.get('kind')=='pursuit':
        from pursuit import strokes as pursuit_strokes
        return pursuit_strokes(m,t)
    u=max(0,min(1,(t-m['start'])/max(.001,m['stop']-m['start'])))
    R=m['radius'];d=R*(m['d0']+(m['d1']-m['d0'])*u);h=math.sqrt(R*R-d*d/4);cx,cy=m['cx'],m['cy'];P=[cx+d/2,cy-h];out=[]
    def path(points,color='#29333c',width=2.6):out.append({'points':points,'color':color,'width':width})
    def line(a,b,color='#29333c',width=2.6):path([a,b],color,width)
    def arrow(a,b,color='#205b96',width=2.8):
        line(a,b,color,width);dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy);ux,uy=dx/length,dy/length
        path([[b[0]-11*ux+4.5*uy,b[1]-11*uy-4.5*ux],b,[b[0]-11*ux-4.5*uy,b[1]-11*uy+4.5*ux]],color,width)
    def label(name,x,y,color='#29333c'):
        for e in m['labels'][name]:path([[x+a,y+b] for a,b in e['points']],color,e['width'])
    for x,color in [(cx,'#29333c'),(cx+d,'#205b96')]:
        path([[x+R*math.cos(j*math.tau/100),cy+R*math.sin(j*math.tau/100)] for j in range(101)],color,2.4)
        line([x-.5,cy],[x+.5,cy],color,5)
    line([cx,cy],[cx+d,cy],'#9caeaa',1.5);line([cx,cy],P,'#9caeaa',1.5)
    label('O1',cx-30,cy+9);label('O2',cx+d+5,cy+9,'#205b96');label('P',P[0]-8,P[1]-37,'#b54d40')
    line([P[0]-.4,P[1]],[P[0]+.4,P[1]],'#b54d40',6)
    yy=cy+R+12;arrow([cx,yy],[cx+d,yy],'#9caeaa',1.6);label('d',cx+d/2-7,yy+9)
    arrow([cx+d+18,yy+41],[cx+d+98,yy+41],'#205b96',2.5);label('v0',cx+d+42,yy+5,'#205b96')
    if m.get('show_vectors',True) and t>=m.get('vector_start',0):
        vx=65;vy=d/(2*h)*vx;A=[P[0]+vx,P[1]];B=[P[0],P[1]+vy];V=[P[0]+vx,P[1]+vy]
        arrow(P,A,'#205b96');arrow(P,B,'#205b96');arrow(P,V,'#b54d40',3.2)
        for a,b in [(A,V),(B,V)]:
            for k in range(0,8,2):line([a[j]+(b[j]-a[j])*k/8 for j in (0,1)],[a[j]+(b[j]-a[j])*(k+1)/8 for j in (0,1)],'#9caeaa',1.3)
        label('vx',P[0]+27,P[1]-80,'#205b96');label('vy',P[0]-49,B[1]+4,'#205b96');label('v',V[0]+10,V[1]-20,'#b54d40')
    return out

def validate_cues(m,ids):
    segments=m.get('segments')
    if segments:
        if m.get('kind')!='pursuit':raise ValueError('Segmented motion is currently supported by pursuit')
        previous=0
        for segment in segments:
            if segment.get('start_cue') not in ids or segment.get('end_cue') not in ids:raise ValueError('Motion segment cue ids must belong to this page')
            a,b=segment.get('from',0),segment.get('to',1)
            if not 0<=a<=b<=1 or a<previous:raise ValueError('Motion segments need ordered progress ranges in 0..1')
            previous=b
    elif any(m.get(k) not in ids for k in ('start_cue','end_cue')):raise ValueError('Demonstration cue ids must belong to this page')
    if m.get('vectors_cue') and m['vectors_cue'] not in ids:raise ValueError('vectors_cue must belong to this page')

def bind_cues(m,cues):
    m=copy.deepcopy(m);lookup={c['id']:c for c in cues}
    if m.get('segments'):
        previous=-1
        for segment in m['segments']:
            segment['start']=lookup[segment['start_cue']]['start'];segment['stop']=lookup[segment['end_cue']]['end']
            if segment['stop']<=segment['start'] or segment['start']<previous:raise ValueError('Motion segment times must be ordered and nonoverlapping')
            previous=segment['stop']
        m['start']=m['segments'][0]['start'];m['stop']=m['segments'][-1]['stop']
        first=m['segments'][0]['start_cue']
    else:
        m['start']=lookup[m['start_cue']]['start'];m['stop']=lookup[m['end_cue']]['end'];first=m['start_cue']
        if m['stop']<=m['start']:raise ValueError('Demonstration must end after it starts')
    m['vector_start']=lookup[m.get('vectors_cue',first)]['start'];return m

def motion_report(m):
    if m.get('kind')=='pursuit':
        from pursuit import state
        segments=m.get('segments');lo=segments[0]['from'] if segments else 0;hi=segments[-1]['to'] if segments else 1
        a,b=state(m,lo),state(m,hi);distance=math.hypot(b[2]-a[2],b[3]-a[3])*m['scale']
        return {'moving':distance>5,'kind':'pursuit','dog_displacement_pixels':distance,'catch_time':m['catch_time']}
    if m.get('kind')=='equal-circles':
        distance=abs(m['d1']-m['d0'])*m['radius'];return {'moving':distance>5,'kind':'equal-circles','center_displacement_pixels':distance}
    return {'moving':False,'kind':m.get('kind')}
