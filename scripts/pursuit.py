"""Finite pure pursuit: exact polar solution sampled for deterministic playback."""
import bisect,copy,math
import ink

def setup(spec):
    m={'vF':1.0,'vD':1.5,'L':1.0,'origin':[210,305],'scale':210,'samples':2048,**copy.deepcopy(spec)}
    for key in ('vF','vD','L','scale'):
        if not isinstance(m[key],(int,float)) or not math.isfinite(m[key]):raise ValueError(f'pursuit.{key} must be finite')
    if m['vF']<0 or m['vD']<=m['vF'] or m['L']<=0 or m['scale']<=0:raise ValueError('Finite pursuit demo requires vD > vF >= 0 and L, scale > 0')
    if not isinstance(m['origin'],list) or len(m['origin'])!=2 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in m['origin']):raise ValueError('pursuit.origin must be [x,y]')
    count=int(m['samples'])
    if not 256<=count<=10000:raise ValueError('pursuit.samples must be 256..10000')
    if 'board_progress' in m and (not isinstance(m['board_progress'],(int,float)) or not 0<=m['board_progress']<=1):raise ValueError('board_progress must be 0..1')
    u,v,L=m['vF'],m['vD'],m['L'];tc=v*L/(v*v-u*u);track=[]
    for i in range(count+1):
        if u==0:
            t=tc*i/count;track.append([t,0,0,-L+v*t]);continue
        if i==count:track.append([tc,u*tc,u*tc,0]);continue
        theta=math.pi/2*(1-i/count);r=L*math.tan(theta/2)**(v/u)/math.sin(theta)
        t=(v*L-r*(v+u*math.cos(theta)))/(v*v-u*u)
        track.append([max(0,t),u*t,u*t-r*math.cos(theta),-r*math.sin(theta)])
    m['track']=track;m['track_times']=[row[0] for row in track];m['catch_time']=tc;m['start']=0;m['stop']=1;m['vector_start']=0
    saved=ink.groups;ink.groups=[[]];labels={}
    try:
        for name,obj,size in [('F','F',25),('D','D',25),('P','F=D',24),('vF',['sub','v','F'],24),('vD',['sub','v','D'],24),('r','r',25),('x','x',24),('L','L',25),('theta','θ',23)]:
            ink.groups[0]=[];ink.formula(0,obj,0,0,size,'#29333c');labels[name]=copy.deepcopy(ink.groups[0])
    finally:ink.groups=saved
    m['labels']=labels
    for k in range(21):
        for stroke in strokes(m,k/20):
            if any(not(120<=x<=1200 and 95<=y<=655) for x,y in stroke['points']):raise ValueError('Pursuit drawing leaves the writing area; adjust origin or scale')
    return m

def progress(m,t):
    segments=m.get('segments',[])
    if segments and 'start' in segments[0]:
        value=segments[0]['from']
        for segment in segments:
            if t<segment['start']:break
            if t<=segment['stop']:
                ratio=max(0,min(1,(t-segment['start'])/max(.001,segment['stop']-segment['start'])))
                return segment['from']+(segment['to']-segment['from'])*ratio
            value=segment['to']
        return value
    return max(0,min(1,(t-m['start'])/max(.001,m['stop']-m['start'])))

def state(m,fraction):
    track=m['track'];t=max(0,min(1,fraction))*m['catch_time']
    index=min(len(track)-1,bisect.bisect_left(m['track_times'],t))
    if index==0:return track[0]
    a,b=track[index-1],track[index];u=(t-a[0])/max(1e-15,b[0]-a[0])
    return [a[i]+u*(b[i]-a[i]) for i in range(4)]

def strokes(m,t):
    fraction=progress(m,t);physical,fox_x,dog_x,dog_y=state(m,fraction);out=[];ox,oy=m['origin'];scale=m['scale']
    fox=[ox+fox_x*scale,oy];dog=[ox+dog_x*scale,oy-dog_y*scale]
    r=math.hypot(fox_x-dog_x,dog_y);caught=r<m['L']*.015
    def path(points,color='#29333c',width=2.5):out.append({'points':points,'color':color,'width':width})
    def line(a,b,color='#29333c',width=2.5):path([a,b],color,width)
    def arrow(a,b,color,width=2.5):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<.01:return
        line(a,b,color,width);ux,uy=dx/length,dy/length
        path([[b[0]-10*ux+4*uy,b[1]-10*uy-4*ux],b,[b[0]-10*ux-4*uy,b[1]-10*uy+4*ux]],color,width)
    def label(name,x,y,color='#29333c'):
        for stroke in m['labels'][name]:path([[x+a,y+b] for a,b in stroke['points']],color,stroke['width'])
    def dashed(a,b):
        for k in range(0,12,2):line([a[i]+(b[i]-a[i])*k/12 for i in (0,1)],[a[i]+(b[i]-a[i])*(k+1)/12 for i in (0,1)],'#9caeaa',1.5)
    line([ox-35,oy],[ox+m['vF']*m['catch_time']*scale+60,oy],'#29333c',2.2)
    dashed([ox-22,oy],[ox-22,oy+m['L']*scale]);label('L',ox-80,oy+m['L']*scale/2-12)
    trail=[]
    for i in range(65):
        sample=state(m,fraction*i/64);trail.append([ox+sample[2]*scale,oy-sample[3]*scale])
    path(trail,'#37684f',2.1)
    line([fox[0]-.1,fox[1]],[fox[0]+.1,fox[1]],'#205b96',7)
    if caught:label('P',fox[0]-20,fox[1]-65,'#b54d40')
    else:
        line([dog[0]-.1,dog[1]],[dog[0]+.1,dog[1]],'#37684f',7)
        label('F',fox[0]-5,fox[1]-35,'#205b96');label('D',dog[0]-32,dog[1]+8,'#37684f')
    if not caught and r>m['L']*.10:
        line(dog,fox,'#b54d40',1.8)
        length=45;ux=(fox[0]-dog[0])/(r*scale);uy=(fox[1]-dog[1])/(r*scale)
        end=[dog[0]+ux*length,dog[1]+uy*length];arrow(dog,end,'#37684f',2.7);label('vD',end[0]-55,end[1]-18,'#37684f')
        if t>=m.get('vector_start',0):
            projected=[fox[0],dog[1]];dashed(dog,projected);dashed(fox,projected)
            label('r',(dog[0]+fox[0])/2+6,(dog[1]+fox[1])/2-25,'#b54d40')
            if fox[0]-dog[0]>30:label('x',(dog[0]+fox[0])/2-5,dog[1]+12,'#205b96')
            angle=math.atan2(fox[1]-dog[1],fox[0]-dog[0]);radius=25
            path([[dog[0]+radius*math.cos(angle*i/20),dog[1]+radius*math.sin(angle*i/20)] for i in range(21)],'#205b96',1.8)
            label('theta',dog[0]+29,dog[1]-21,'#205b96')
    if m['vF']>0:arrow(fox,[fox[0]+42,fox[1]],'#205b96',2.7);label('vF',fox[0]+22,fox[1]-35,'#205b96')
    return out
