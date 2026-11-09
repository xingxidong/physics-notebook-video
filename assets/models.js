function drawDemonstration(m,t){
 const u=Math.max(0,Math.min(1,(t-m.start)/Math.max(.001,m.stop-m.start))),R=m.radius,d=R*(m.d0+(m.d1-m.d0)*u),h=Math.sqrt(R*R-d*d/4),cx=m.cx,cy=m.cy,P=[cx+d/2,cy-h];
 function path(points,color='#29333c',width=2.6){ctx.beginPath();ctx.moveTo(...points[0]);for(const q of points.slice(1))ctx.lineTo(...q);ctx.lineCap=ctx.lineJoin='round';ctx.lineWidth=width;ctx.strokeStyle=color;ctx.stroke()}
 function line(a,b,color='#29333c',width=2.6){path([a,b],color,width)}
 function arrow(a,b,color='#205b96',width=2.8){line(a,b,color,width);const dx=b[0]-a[0],dy=b[1]-a[1],l=Math.hypot(dx,dy),ux=dx/l,uy=dy/l;path([[b[0]-11*ux+4.5*uy,b[1]-11*uy-4.5*ux],b,[b[0]-11*ux-4.5*uy,b[1]-11*uy+4.5*ux]],color,width)}
 function label(name,x,y,color='#29333c'){for(const e of m.labels[name])path(e.points.map(([a,b])=>[x+a,y+b]),color,e.width)}
 for(const [x,color] of [[cx,'#29333c'],[cx+d,'#205b96']]){path(Array.from({length:101},(_,j)=>[x+R*Math.cos(j*Math.PI*2/100),cy+R*Math.sin(j*Math.PI*2/100)]),color,2.4);line([x-.5,cy],[x+.5,cy],color,5)}
 line([cx,cy],[cx+d,cy],'#9caeaa',1.5);line([cx,cy],P,'#9caeaa',1.5);label('O1',cx-30,cy+9);label('O2',cx+d+5,cy+9,'#205b96');label('P',P[0]-8,P[1]-37,'#b54d40');line([P[0]-.4,P[1]],[P[0]+.4,P[1]],'#b54d40',6);
 const yy=cy+R+12;arrow([cx,yy],[cx+d,yy],'#9caeaa',1.6);label('d',cx+d/2-7,yy+9);arrow([cx+d+18,yy+41],[cx+d+98,yy+41],'#205b96',2.5);label('v0',cx+d+42,yy+5,'#205b96');
 if(m.show_vectors!==false&&t>=m.vector_start){const vx=65,vy=d/(2*h)*vx,A=[P[0]+vx,P[1]],B=[P[0],P[1]+vy],V=[P[0]+vx,P[1]+vy];arrow(P,A,'#205b96');arrow(P,B,'#205b96');arrow(P,V,'#b54d40',3.2);for(const [a,b] of [[A,V],[B,V]])for(let k=0;k<8;k+=2)line([0,1].map(j=>a[j]+(b[j]-a[j])*k/8),[0,1].map(j=>a[j]+(b[j]-a[j])*(k+1)/8),'#9caeaa',1.3);label('vx',P[0]+27,P[1]-80,'#205b96');label('vy',P[0]-49,B[1]+4,'#205b96');label('v',V[0]+10,V[1]-20,'#b54d40')}
}
