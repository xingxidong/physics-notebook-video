#!/usr/bin/env python3
"""Editable collision, cyclotron and film-interference examples from shared parameters."""
import argparse
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets/starter-kit/animations'


def calculate(p):
    c=p['collision'];m1,m2,u1,u2=(float(c[k]) for k in ('m1','m2','u1','u2'))
    if m1<=0 or m2<=0 or u1<=u2:raise ValueError('Collision needs positive masses and left particle approaching the right particle: u1 > u2.')
    v1=((m1-m2)*u1+2*m2*u2)/(m1+m2);v2=(2*m1*u1+(m2-m1)*u2)/(m1+m2)
    b=p['magnetic'];mass,q,B,v=(float(b[k]) for k in ('m','q','B','v'))
    if mass<=0 or v<=0 or B<=0 or q==0:raise ValueError('Magnetic model needs m,v,B > 0 and nonzero q; B points into the screen.')
    radius=mass*v/abs(q*B);omega=q*B/mass
    f=p['film'];n0,n,n2,d,angle,lam=(float(f[k]) for k in ('n0','n','n2','d_nm','theta_deg','lambda_nm'))
    if min(n0,n,n2,d,lam)<=0 or not 0<=angle<80:raise ValueError('Film needs positive indices/thickness/wavelength and 0 <= incidence < 80 degrees.')
    sn=n0/n*math.sin(math.radians(angle))
    if abs(sn)>=1:raise ValueError('This film example uses transmitted rays; choose parameters below total internal reflection.')
    theta=math.asin(sn);delta=2*n*d*math.cos(theta)
    flips=(int(n2>n)-int(n>n0))*math.pi
    return {'collision':{'v1':v1,'v2':v2},'magnetic':{'radius':radius,'omega':omega},
            'film':{'theta_inside':theta,'optical_path_nm':delta,'reflection_phase':flips,
                    'phase':2*math.pi*delta/lam+flips}}


def tikz(p,derived):
    c=p['collision'];v=derived['collision']
    a=[r'\begin{tikzpicture}[>=Stealth]',r'\draw[gray] (-3,0)--(4,0);']
    for x,name,mass,vel in [(-1,'1',c['m1'],c['u1']),(1,'2',c['m2'],c['u2'])]:
        a.append(rf'\fill[blue] ({x},0) circle (2pt) node[above] {{$m_{name}={mass:g}$}};')
        if abs(vel)>1e-9:a.append(rf'\draw[->,blue,thick] ({x},-.3)--({x+vel*.3},-.3) node[midway,below] {{$u_{name}={vel:g}$}};')
        else:a.append(rf'\node[blue,below] at ({x},-.3) {{$u_{name}=0$}};')
    for x,name,mass,vel in [(-1,'1',c['m1'],v['v1']),(1,'2',c['m2'],v['v2'])]:
        a.append(rf'\fill[red] ({x},-1.7) circle (2pt) node[above] {{$m_{name}$}};')
        if abs(vel)>1e-9:a.append(rf'\draw[->,red,thick] ({x},-2)--({x+vel*.3},-2) node[midway,below] {{$v_{name}={vel:g}$}};')
        else:a.append(rf'\node[red,below] at ({x},-2) {{$v_{name}=0$}};')
    a.append(r'\end{tikzpicture}')
    b=p['magnetic'];r=derived['magnetic']['radius'];sign=1 if derived['magnetic']['omega']>0 else -1
    magnetic=rf'''\begin{{tikzpicture}}[>=Stealth]
\draw[gray,dashed] (0,0) circle (1.7);
\draw[blue,thick,->] (0,{-sign*1.7}) arc[start angle={-sign*90},delta angle={sign*120},radius=1.7];
\draw[dashed] (0,0)--(-1.7,0) node[midway,above] {{$r={r:.3g}$}};
\fill (0,{-sign*1.7}) circle (2pt);
\draw[->,green!50!black] (0,{-sign*1.7})--(1.1,{-sign*1.7}) node[right] {{$v$}};
\draw[->,red] (0,{-sign*1.7})--(0,{-sign*.7}) node[left] {{$q\,\mathbf v\times\mathbf B$}};
\node at (2.8,1) {{$B$ 指向纸内}};
\node at (2.8,.3) {{$q={b['q']:g}$}};
\node at (2.8,-.4) {{$r=mv/|qB|$}};
\end{{tikzpicture}}'''
    f=p['film'];th=derived['film']['theta_inside'];dx=1.3*math.tan(th);air=1.3*math.tan(math.radians(f['theta_deg']))
    film=rf'''\begin{{tikzpicture}}[>=Stealth]
\fill[blue!8] (-2,-1.3) rectangle (3,0);
\draw (-2,0)--(3,0);\draw (-2,-1.3)--(3,-1.3);
\draw[dashed] (0,-1.6)--(0,1.5);
\draw[gray] (0,.8) arc[start angle=90,delta angle={f['theta_deg']:g},radius=.8];
\node at (-.2,1.05) {{$\theta_0$}};
\draw[gray] (0,-.65) arc[start angle=-90,delta angle={math.degrees(th):.5f},radius=.65];
\node at (.26,-.9) {{$\theta_t$}};
\draw[->,red,thick] ({-air:.5f},1.3)--(0,0);
\draw[->,blue,thick] (0,0)--({air:.5f},1.3);
\draw[->,green!50!black,thick] (0,0)--({dx:.5f},-1.3)--({2*dx:.5f},0)--({2*dx+air:.5f},1.3);
\draw[<->] (2.7,0)--(2.7,-1.3) node[midway,right] {{$d={f['d_nm']:g}\,\mathrm{{nm}}$}};
\node at (-1.3,.6) {{$n_0={f['n0']:g}$}};\node at (-1.3,-.6) {{$n={f['n']:g}$}};\node at (-1.3,-1.7) {{$n_2={f['n2']:g}$}};
\node at (1,-2.4) {{$\delta=2nd\cos\theta_t={derived['film']['optical_path_nm']:.2f}\,\mathrm{{nm}}$}};
\end{{tikzpicture}}'''
    return {'collision':'\n'.join(a),'magnetic':magnetic,'film':film}


def build(params,output):
    p=json.loads(params.read_text());derived=calculate(p);output.mkdir(parents=True,exist_ok=True)
    (output/'parameters.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
    (output/'derived.json').write_text(json.dumps(derived,ensure_ascii=False,indent=2))
    for name,source in tikz(p,derived).items():(output/(name+'.tikz')).write_text(source+'\n')
    template=(ASSETS/'gallery-template.html').read_text()
    (output/'index.html').write_text(template.replace('__PARAMS__',json.dumps(p).replace('</','<\\/')))
    return {'output':str(output),'derived':derived}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--params',type=Path,default=ASSETS/'parameters.json');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(args.params,args.output),ensure_ascii=False))
