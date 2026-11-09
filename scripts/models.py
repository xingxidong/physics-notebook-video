"""Deterministic 2-D demonstrations; geometry is evaluated from physical parameters."""
import copy,math
import ink

def setup(spec):
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
