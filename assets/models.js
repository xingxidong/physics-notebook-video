function drawDemonstration(m,t){
 if(m.kind==='pursuit')return drawPursuit(m,t);
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

function pursuitProgress(m,t){
 const segments=m.segments||[];
 if(segments.length&&segments[0].start!==undefined){let value=segments[0].from;
  for(const s of segments){if(t<s.start)break;if(t<=s.stop){const f=Math.max(0,Math.min(1,(t-s.start)/Math.max(.001,s.stop-s.start)));return s.from+(s.to-s.from)*f}value=s.to}return value;
 }
 return Math.max(0,Math.min(1,(t-m.start)/Math.max(.001,m.stop-m.start)));
}
function pursuitState(m,fraction){
 const track=m.track,t=Math.max(0,Math.min(1,fraction))*m.catch_time;let lo=0,hi=track.length;
 while(lo<hi){const mid=Math.floor((lo+hi)/2);if(track[mid][0]<t)lo=mid+1;else hi=mid}
 const ix=Math.min(track.length-1,lo);if(ix===0)return track[0];const a=track[ix-1],b=track[ix],u=(t-a[0])/Math.max(1e-15,b[0]-a[0]);return a.map((x,i)=>x+u*(b[i]-x));
}
function drawPursuit(m,t){
 const fraction=pursuitProgress(m,t),[physical,fx,dx,dy]=pursuitState(m,fraction),[ox,oy]=m.origin,scale=m.scale;
 const fox=[ox+fx*scale,oy],dog=[ox+dx*scale,oy-dy*scale],r=Math.hypot(fx-dx,dy),caught=r<m.L*.015;
 function path(points,color='#29333c',width=2.5){ctx.beginPath();ctx.moveTo(...points[0]);for(const p of points.slice(1))ctx.lineTo(...p);ctx.lineJoin=ctx.lineCap='round';ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke()}
 function line(a,b,color='#29333c',width=2.5){path([a,b],color,width)}
 function arrow(a,b,color,width=2.5){const x=b[0]-a[0],y=b[1]-a[1],length=Math.hypot(x,y);if(length<.01)return;line(a,b,color,width);const u=x/length,v=y/length;path([[b[0]-10*u+4*v,b[1]-10*v-4*u],b,[b[0]-10*u-4*v,b[1]-10*v+4*u]],color,width)}
 function label(name,x,y,color='#29333c'){for(const s of m.labels[name])path(s.points.map(([a,b])=>[x+a,y+b]),color,s.width)}
 function dashed(a,b){for(let k=0;k<12;k+=2)line([0,1].map(i=>a[i]+(b[i]-a[i])*k/12),[0,1].map(i=>a[i]+(b[i]-a[i])*(k+1)/12),'#9caeaa',1.5)}
 line([ox-35,oy],[ox+m.vF*m.catch_time*scale+60,oy],'#29333c',2.2);dashed([ox-22,oy],[ox-22,oy+m.L*scale]);label('L',ox-80,oy+m.L*scale/2-12);
 const trail=Array.from({length:65},(_,i)=>{const s=pursuitState(m,fraction*i/64);return[ox+s[2]*scale,oy-s[3]*scale]});path(trail,'#37684f',2.1);
 line([fox[0]-.1,fox[1]],[fox[0]+.1,fox[1]],'#205b96',7);
 if(caught)label('P',fox[0]-20,fox[1]-65,'#b54d40');else{line([dog[0]-.1,dog[1]],[dog[0]+.1,dog[1]],'#37684f',7);label('F',fox[0]-5,fox[1]-35,'#205b96');label('D',dog[0]-32,dog[1]+8,'#37684f')}
 if(!caught&&r>m.L*.10){line(dog,fox,'#b54d40',1.8);
  const end=[dog[0]+(fox[0]-dog[0])/(r*scale)*45,dog[1]+(fox[1]-dog[1])/(r*scale)*45];arrow(dog,end,'#37684f',2.7);label('vD',end[0]-55,end[1]-18,'#37684f');
  if(t>=(m.vector_start||0)){
  const projected=[fox[0],dog[1]];dashed(dog,projected);dashed(fox,projected);label('r',(dog[0]+fox[0])/2+6,(dog[1]+fox[1])/2-25,'#b54d40');if(fox[0]-dog[0]>30)label('x',(dog[0]+fox[0])/2-5,dog[1]+12,'#205b96');
  const angle=Math.atan2(fox[1]-dog[1],fox[0]-dog[0]),radius=25;path(Array.from({length:21},(_,i)=>[dog[0]+radius*Math.cos(angle*i/20),dog[1]+radius*Math.sin(angle*i/20)]),'#205b96',1.8);label('theta',dog[0]+29,dog[1]-21,'#205b96');
 }}
 if(m.vF>0){arrow(fox,[fox[0]+42,fox[1]],'#205b96',2.7);label('vF',fox[0]+22,fox[1]-35,'#205b96')}
}
