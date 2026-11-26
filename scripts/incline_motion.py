"""Contact-preserving motion on a fixed frictionless incline, in notebook coordinates."""
import math
import copy
import ink


def setup(spec):
    m={'origin':[160,345],'length':280,'angle':30,'distance':2,'g':10,
       'start_fraction':.15,'box_width':34,'box_height':25,**copy.deepcopy(spec)}
    if not 0<m['angle']<80 or m['distance']<=0 or m['g']<=0:
        raise ValueError('Incline requires 0 < angle < 80 degrees, positive distance and g')
    m['acceleration']=m['g']*math.sin(math.radians(m['angle']))
    m['physical_duration']=math.sqrt(2*m['distance']/m['acceleration'])
    m['start']=0;m['stop']=1
    saved=ink.groups;ink.groups=[[]]
    try:
        m['labels']={}
        for name,size in [('s',23),('v',23),('θ',22),('m',23)]:
            ink.groups[0]=[];ink.formula(0,name,0,0,size,'#29333c')
            m['labels'][name]=copy.deepcopy(ink.groups[0])
    finally:ink.groups=saved
    return m


def state(m,t):
    f=max(0,min(1,(t-m['start'])/max(.001,m['stop']-m['start'])))
    theta=math.radians(m['angle']);u=[math.cos(theta),math.sin(theta)];n=[math.sin(theta),-math.cos(theta)]
    travel=m['length']*.63*f*f
    base=[m['origin'][j]+u[j]*(m['length']*m['start_fraction']+travel) for j in (0,1)]
    center=[base[j]+n[j]*m['box_height']/2 for j in (0,1)]
    corners=[[base[j]+u[j]*a+n[j]*b for j in (0,1)]
             for a,b in [(-m['box_width']/2,0),(m['box_width']/2,0),(m['box_width']/2,m['box_height']),(-m['box_width']/2,m['box_height'])]]
    return {'u':u,'n':n,'base':base,'center':center,'corners':corners,
            'distance':m['distance']*f*f,'speed':m['acceleration']*m['physical_duration']*f}


def strokes(m,t):
    s=state(m,t);o=m['origin'];u=s['u'];out=[]
    def line(points,color='#29333c',width=2.5):out.append({'points':points,'color':color,'width':width})
    def label(name,x,y):
        for e in m['labels'][name]:line([[x+a,y+b] for a,b in e['points']],e['color'],e['width'])
    end=[o[j]+u[j]*m['length'] for j in (0,1)]
    line([o,end,[o[0],end[1]],o]);line([*s['corners'],s['corners'][0]],'#205b96',3)
    label('m',s['center'][0]-5,s['center'][1]-40)
    label('θ',end[0]-45,end[1]-24);label('s',(o[0]+end[0])/2-15,(o[1]+end[1])/2+25)
    if s['speed']>.05:
        a=s['center'];v=20+45*s['speed']/(m['acceleration']*m['physical_duration'])
        b=[a[j]+u[j]*v for j in (0,1)];line([a,b],'#37684f')
        line([[b[0]-9*u[0]+4*u[1],b[1]-9*u[1]-4*u[0]],b,
              [b[0]-9*u[0]-4*u[1],b[1]-9*u[1]+4*u[0]]],'#37684f')
        label('v',b[0]+7,b[1]-25)
    return out
