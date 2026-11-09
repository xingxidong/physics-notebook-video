#!/usr/bin/env python3
"""Reusable notebook course builder: content JSON -> strokes, speech, pages, MP4.
All rendering is local. Run --help; no language-model API is used.
"""
import argparse,ast,base64,copy,hashlib,importlib.util,io,json,math,operator,os,re,shutil,subprocess,sys,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PALETTE={'ink':'#29333c','blue':'#205b96','red':'#b54d40','green':'#37684f','muted':'#9caeaa'}
W,H,SR=1280,720,24000
def digest(x):return hashlib.sha256(x if isinstance(x,bytes) else json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write_json(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2))
def finite(x):
    x=float(x)
    if not math.isfinite(x):raise ValueError('Drawing contains a non-finite number')
    return x
def number(value,params):
    if isinstance(value,(int,float)):return finite(value)
    tree=ast.parse(str(value).removeprefix('='),mode='eval')
    funcs={k:getattr(math,k) for k in ('sin','cos','tan','sqrt','exp','log','asin','acos','atan')}
    binary={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}
    def walk(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)):return n.value
        if isinstance(n,ast.Name):return params[n.id] if n.id in params else {'pi':math.pi,'e':math.e}[n.id]
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and type(n.op) in binary:return binary[type(n.op)](walk(n.left),walk(n.right))
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in funcs and not n.keywords:return funcs[n.func.id](*(walk(a) for a in n.args))
        raise ValueError('Use numeric parameters and supported math functions in drawing expressions')
    return finite(walk(tree.body))

def font_path(lesson,project):
    candidates=[lesson.get('font'),os.environ.get('PHYSICS_NOTEBOOK_FONT'),'/System/Library/Fonts/Supplemental/Songti.ttc','/System/Library/Fonts/STHeiti Light.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    for value in candidates:
        if not value:continue
        p=Path(value);p=p if p.is_absolute() else project/p
        if p.exists():return p
    raise ValueError('Set lesson.font or PHYSICS_NOTEBOOK_FONT to a Chinese TTF/TTC font')

def compile_lesson(project,lesson=None):
    import ink
    from mathparse import parse
    from layout import page_spec,expand_actions,place_action,focus_spec,audit_page
    from components import expand_component
    from speech_plan import apply as apply_speech_plan
    project=Path(project).resolve()
    lesson=json.loads((project/'lesson.json').read_text()) if lesson is None else copy.deepcopy(lesson)
    lesson,speech_meta=apply_speech_plan(project,lesson);lesson['_speech_plan_meta']=speech_meta
    if not lesson.get('title') or not lesson.get('pages'):raise ValueError('A lesson needs a title and pages')
    cache=project/'cache/hanzi';cache.mkdir(parents=True,exist_ok=True)
    for seed in (ROOT/'assets/hanzi').glob('*.json'):
        if not (cache/seed.name).exists():shutil.copy2(seed,cache/seed.name)
    ink.CACHE=cache;ink.groups=[];params={k:finite(v) for k,v in lesson.get('parameters',{}).items()};seen=set();pages=[]
    for pi,page in enumerate(lesson['pages']):
        pid=page.get('id',f'p{pi+1:02d}')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*',pid):raise ValueError('Page ids use letters, digits, hyphens or underscores')
        if pid in seen:raise ValueError(f'Duplicate page id {pid}')
        seen.add(pid)
        if not page.get('cues'):raise ValueError(f'Page {pid} needs cues')
        layout_spec=page_spec(page.get('layout'));layout_state={}
        camera=page.get('camera',lesson.get('camera','static'))
        if camera not in ('static','focus'):raise ValueError('camera must be static or focus')
        cooked={'id':pid,'title':page.get('title',lesson['title']),'show_title':page.get('show_title',lesson.get('show_titles',True)),'camera':camera,'cues':[],'components':[],'anchors':{},'index':pi};component_ids=set()
        if layout_spec:cooked['layout']=layout_spec
        if page.get('problem_id'):cooked['problem_id']=str(page['problem_id'])
        if page.get('native_scenes'):cooked['native_scenes']=copy.deepcopy(page['native_scenes'])
        if page.get('image'):
            spec=copy.deepcopy(page['image']);source=(project/spec.pop('file')).resolve();spec['data']='data:image/png;base64,'+base64.b64encode(source.read_bytes()).decode();cooked['image']=spec
        for ci,cue in enumerate(page['cues']):
            cue=copy.deepcopy(cue);cue.setdefault('id',f'{pid}-c{ci+1:02d}');cue.setdefault('tts',cue.get('text',''));cue.setdefault('text',cue['tts']);cue.setdefault('role','explain');cue.setdefault('pause_before',0);cue.setdefault('pause',.8)
            cue['pause']=finite(cue['pause']);cue['pause_before']=finite(cue['pause_before'])
            if cue['pause']<0:raise ValueError(f'{cue["id"]}: pause must be nonnegative')
            if cue['pause_before']<0:raise ValueError(f'{cue["id"]}: pause_before must be nonnegative')
            if 'speed' in cue and not .5<=finite(cue['speed'])<=2:raise ValueError(f'{cue["id"]}: speed must be 0.5..2')
            if 'volume' in cue and not .1<=finite(cue['volume'])<=10:raise ValueError(f'{cue["id"]}: volume must be 0.1..10')
            if not cue['tts'].strip():raise ValueError(f'{cue["id"]}: missing speakable narration')
            if cue['id'] in seen:raise ValueError(f'Duplicate cue id {cue["id"]}')
            seen.add(cue['id']);cue['blocks']=[]
            if camera=='static':cue.pop('focus',None)
            elif cue.get('focus'):cue['focus']=focus_spec(cue['focus'],layout_spec)
            expanded=[]
            for ri,raw_action in enumerate(expand_actions(cue.get('actions',[]),layout_spec)):
                primitives,manifest=expand_component(raw_action,f'{cue["id"]}-component-{ri+1}')
                if manifest:
                    if manifest['id'] in component_ids:raise ValueError(f'Duplicate component id {manifest["id"]} on page {pid}')
                    component_ids.add(manifest['id']);cooked['components'].append(manifest)
                    relative=manifest.get('relative_to');offset=[0,0]
                    if relative:
                        if not layout_spec or relative not in layout_spec['zones']:raise ValueError(f'Unknown component zone {relative!r}')
                        offset=layout_spec['zones'][relative][:2]
                    for name,point_value in manifest.get('anchors',{}).items():
                        cooked['anchors'][manifest['id']+'.'+name]=[point_value[i]+offset[i] for i in (0,1)]
                expanded.extend(primitives)
            for ai,raw_action in enumerate(expanded):
                a=place_action(raw_action,layout_spec,layout_state,cooked['anchors'])
                write_seconds=finite(a['write_seconds']) if 'write_seconds' in a else None
                if write_seconds is not None and not .1<=write_seconds<=30:raise ValueError(f'{cue["id"]}: write_seconds must be 0.1..30')
                at=a.get('at')
                if isinstance(at,(int,float)) and not 0<=at<=1:raise ValueError(f'{cue["id"]}: numeric anchors must be 0..1')
                if isinstance(at,dict):
                    clean=lambda s:''.join(c for c in s if c.isalnum())
                    word=clean(at.get('word',''));occurrence=int(at.get('occurrence',1))
                    if not word or occurrence<1 or clean(cue['tts']).count(word)<occurrence:raise ValueError(f'{cue["id"]}: keyword anchor is absent from narration')
                gi=len(ink.groups);ink.groups.append([]);kind=a['type'];color=PALETTE.get(a.get('color','ink'),a.get('color','ink'))
                if not re.fullmatch(r'#[0-9a-fA-F]{6}',color):raise ValueError(f'{cue["id"]}: unknown color {color!r}')
                def n(v):return number(v,params)
                def point(v):return [n(x) for x in v]
                width=n(a.get('width',3));size=n(a.get('size',32))
                if width<=0 or size<=0:raise ValueError(f'{cue["id"]}: width and size must be positive')
                if kind=='text':ink.text(gi,a['text'],n(a['x']),n(a['y']),size,color)
                elif kind=='math':ink.formula(gi,parse(a['latex']) if 'latex' in a else a['value'],n(a['x']),n(a['y']),size,color)
                elif kind in ('line','arrow','dashed_line'):
                    fn={'line':ink.line,'arrow':ink.arrow,'dashed_line':ink.dashed}[kind]
                    args=[gi,point(a['from']),point(a['to']),color]
                    if kind!='dashed_line':args.append(width)
                    fn(*args)
                elif kind=='stroke':ink.stroke(gi,[point(p) for p in a['points']],color,width,a.get('curved',False))
                elif kind=='ellipse':ink.ellipse(gi,point(a['center']),n(a['rx']),n(a.get('ry',a['rx'])),color,width)
                elif kind=='dashed_circle':ink.circle_dashed(gi,point(a['center']),n(a['radius']),color)
                elif kind=='charge':ink.charge(gi,point(a['center']),a.get('label','q'),size,color,a.get('sign',1))
                elif kind=='rect':
                    x,y=n(a['x']),n(a['y']);w,h=n(a['w']),n(a['h']);ink.stroke(gi,[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]],color,width)
                elif kind=='plot':
                    origin=point(a['origin']);sx,sy=point(a['scale']);lo,hi=point(a['domain']);pts=[]
                    samples=int(a.get('samples',100))
                    if not 2<=samples<=2000:raise ValueError('plot.samples must be 2..2000')
                    for k in range(samples):
                        x=lo+(hi-lo)*k/(samples-1);y=number(a['expr'],{**params,'x':x});pts.append([origin[0]+sx*x,origin[1]-sy*y])
                    ink.stroke(gi,pts,color,width)
                else:raise ValueError(f'Unknown action type {kind}')
                for e in ink.groups[gi]:
                    if not e['points'] or any(not(120<=x<=1200 and 95<=y<=655) for x,y in e['points']):raise ValueError(f'{cue["id"]}, action {ai}: ink leaves the writing area x=120..1200, y=95..655')
                cue['blocks'].append({'strokes':ink.groups[gi],'at':a.get('at'),'write_seconds':write_seconds,'action':ai,'kind':kind,'zone':a.get('zone'),'allow_overlap':bool(a.get('allow_overlap',False)),'transform_group':a.get('transform_group'),'transform_step':a.get('transform_step'),'component_id':a.get('component_id'),'component_name':a.get('component_name'),'component_part':a.get('component_part')})
            cooked['cues'].append(cue)
        if page.get('demonstration'):
            import models
            cooked['demonstration']=models.setup(page['demonstration'])
            cue_ids={c['id'] for c in cooked['cues']}
            if any(cooked['demonstration'].get(k) not in cue_ids for k in ('start_cue','end_cue')):raise ValueError('Demonstration cue ids must belong to this page')
        cooked['layout_report']=audit_page(cooked);pages.append(cooked)
    return lesson,pages

def anchor(at,cue,audio):
    if isinstance(at,(int,float)):
        if not 0<=at<=1:raise ValueError('Numeric action.at is a fraction from 0 to 1')
        return at*audio['duration'],'fraction'
    if not isinstance(at,dict) or not at.get('word'):raise ValueError('action.at needs a fraction or {word, occurrence?, offset?}')
    clean=lambda s:''.join(c for c in s if c.isalnum())
    word=clean(at['word']);occurrence=int(at.get('occurrence',1));offset=float(at.get('offset',0));text=clean(cue['tts'])
    def locate(s):
        index=-1
        for _ in range(occurrence):index=s.find(word,index+1)
        return index
    if not word or occurrence<1 or locate(text)<0:raise ValueError(f'Anchor {at["word"]!r} is absent from cue {cue["id"]}')
    words=audio.get('words',[]);joined=''.join(clean(w['text']) for w in words);ix=locate(joined)
    if ix>=0:
        used=0
        for w in words:
            length=len(clean(w['text']))
            if used+length>ix:return w['start']+(w['end']-w['start'])*(ix-used)/max(1,length)+offset,'provider-word'
            used+=length
    return locate(text)/max(1,len(text))*audio['duration']+offset,'estimated-word'

def schedule(cue,audio):
    blocks=cue['blocks'];n=len(blocks)
    if not n:return []
    weights=[sum(max(8,sum(math.dist(a,b) for a,b in zip(e['points'],e['points'][1:])))**.7+9 for e in b['strokes']) or 1 for b in blocks]
    anchors={0:.12,n:max(.3,audio['duration']-.2)};qualities={}
    for j,b in enumerate(blocks):
        if b['at'] is not None:anchors[j],qualities[j]=anchor(b['at'],cue,audio)
    keys=sorted(anchors);events=[]
    for left,right in zip(keys,keys[1:]):
        begin,end=anchors[left],anchors[right]
        if begin<0 or end<=begin or end>audio['duration']+cue['pause']:raise ValueError(f'{cue["id"]}: action anchors are out of order or outside the speech interval')
        t=begin
        for j in range(left,right):
            span=(end-begin)*weights[j]/sum(weights[left:right]);block=blocks[j];strokes=block['strokes']
            writing_span=min(span,block['write_seconds']) if block.get('write_seconds') is not None else span
            sw=[max(8,sum(math.dist(a,b) for a,b in zip(e['points'],e['points'][1:])))**.7+9 for e in strokes];cursor=t
            for e,w in zip(strokes,sw):
                dt=writing_span*w/sum(sw);event=copy.deepcopy(e);event.update(start=cursor,end=cursor+dt*.88,cue=cue['id'],action=j,anchor_quality=qualities.get(j,'sequence'),component_id=block.get('component_id'),component_name=block.get('component_name'),component_part=block.get('component_part'));events.append(event);cursor+=dt
            t+=span
    return events

def prepare(project,lesson,pages,args):
    from voice import synth,DEFAULTS
    cfg=copy.deepcopy(lesson.get('speech',{'backend':'glm'}))
    if args.backend:
        if args.backend!=cfg.get('backend'):cfg['voice']=DEFAULTS[args.backend]
        cfg['backend']=args.backend
    if args.voice:cfg['voice']=args.voice
    cfg.setdefault('audio_mastering',True)
    fps=args.fps;global_t=0;all_pcm=bytearray();timeline=[];voice_hits=voice_new=0
    for p in pages:
        local=.35;pcm=bytearray(b'\0'*round(local*SR)*2);events=[];cues=[];focuses=[]
        for cue in p['cues']:
            pcm.extend(b'\0'*round(cue['pause_before']*SR)*2)
            if args.draft:
                audio={'duration':max(1.2,len(cue['tts'])/4.2),'words':[],'file':None}
            else:
                audio=synth(project,cfg,cue);voice_hits+=bool(audio['cache_hit']);voice_new+=not audio['cache_hit']
                with wave.open(audio['file']) as w:clip=w.readframes(w.getnframes())
            # Quantise start to exact audio samples for every playback/export path.
            local=len(pcm)/(2*SR)
            for e in schedule(cue,audio):e.update(start=e['start']+local,end=e['end']+local);events.append(e)
            delivery={k:cue[k] for k in ('role','speed','pitch','volume','emotion','emphasis') if k in cue}
            cues.append({'id':cue['id'],'text':cue['text'],'tts':cue['tts'],'start':local,'end':local+audio['duration'],'pause_before':cue['pause_before'],'pause':cue['pause'],'timing':'estimated' if args.draft else 'measured','words':audio.get('words',[]),**delivery})
            if cue.get('focus'):
                focused=copy.deepcopy(cue['focus']);focused.update(start=local,end=local+audio['duration']);focuses.append(focused)
            if args.draft:pcm.extend(b'\0'*round(audio['duration']*SR)*2)
            else:pcm.extend(clip)
            pcm.extend(b'\0'*round(cue['pause']*SR)*2)
        frames=math.ceil(len(pcm)/(2*SR)*fps);target=round(frames/fps*SR)*2;pcm.extend(b'\0'*max(0,target-len(pcm)))
        seconds=len(pcm)/(2*SR);prepared={'id':p['id'],'title':p['title'],'show_title':p.get('show_title',True),'index':p['index'],'start':global_t,'end':global_t+seconds,'duration':seconds,'frames':frames,'cues':cues,'strokes':events,'audio_sha256':digest(bytes(pcm))}
        if p.get('layout'):prepared['layout']=p['layout']
        if p.get('layout_report'):prepared['layout_report']=p['layout_report']
        if p.get('problem_id'):prepared['problem_id']=p['problem_id']
        if p.get('components'):prepared['components']=p['components']
        if p.get('anchors'):prepared['anchors']=p['anchors']
        prepared['camera']=p['camera']
        if focuses:prepared['focus']=focuses
        if 'image' in p:prepared['image']=p['image']
        if 'native_scenes' in p:prepared['native_scenes']=p['native_scenes']
        if 'demonstration' in p:
            m=copy.deepcopy(p['demonstration']);lookup={c['id']:c for c in cues};m['start']=lookup[m['start_cue']]['start'];m['stop']=lookup[m['end_cue']]['end'];m['vector_start']=lookup[m.get('vectors_cue',m['start_cue'])]['start'];prepared['demonstration']=m
        timeline.append(prepared);all_pcm.extend(pcm);global_t+=seconds
    return {'title':lesson['title'],'width':W,'height':H,'fps':fps,'duration':global_t,'draft':args.draft,'speech':cfg,'speech_plan_source':lesson.get('_speech_plan_meta',{}).get('source','lesson.json'),'pages':timeline},all_pcm,{'speech_new':voice_new,'speech_reused':voice_hits}

def portion(points,fraction):
    remaining=sum(math.dist(a,b) for a,b in zip(points,points[1:]))*min(1,max(0,fraction));out=[points[0]]
    for a,b in zip(points,points[1:]):
        length=math.dist(a,b)
        if remaining>=length:out.append(b);remaining-=length
        else:
            f=remaining/length if length else 0;out.append([a[j]+f*(b[j]-a[j]) for j in (0,1)]);break
    return out

def paper(page,font,scale=1):
    from PIL import Image,ImageDraw,ImageFont
    im=Image.new('RGB',(round(W*scale),round(H*scale)),'#e9ece7');d=ImageDraw.Draw(im)
    box=lambda a:tuple(v*scale for v in a)
    d.rounded_rectangle(box((35,8,1231,700)),round(9*scale),fill='#fffef9')
    for x in range(75,1210,26):d.line(box((x,86,x,678)),fill='#e8eeec',width=max(1,round(scale)))
    for y in range(86,679,26):d.line(box((64,y,1205,y)),fill='#e8eeec',width=max(1,round(scale)))
    d.line(box((113,86,113,678)),fill='#e5bdb6',width=max(1,round(scale)))
    if page.get('show_title',True):d.text((75*scale,29*scale),page['title'],font=ImageFont.truetype(str(font),round(24*scale)),fill='#344940')
    d.text((1150*scale,659*scale),f'{page["index"]+1:02d}',font=ImageFont.truetype(str(font),round(16*scale)),fill='#83958a')
    if page.get('image'):
        a=page['image'];source=Image.open(io.BytesIO(base64.b64decode(a['data'].split(',',1)[1]))).convert('RGB');source=source.resize((round(a['w']*scale),round(a['h']*scale)),Image.Resampling.LANCZOS);im.paste(source,(round(a['x']*scale),round(a['y']*scale)))
    return im
def paint(im,event,fraction=1,scale=1):
    from PIL import ImageDraw
    pts=portion(event['points'],fraction);d=ImageDraw.Draw(im);width=max(1,round(event['width']*scale));p=[(x*scale,y*scale) for x,y in pts]
    d.line(p,fill=event['color'],width=width,joint='curve')
    for x,y in (p[0],p[-1]):d.ellipse((x-width/2,y-width/2,x+width/2,y+width/2),fill=event['color'])
    return p[-1]
def apply_focus(im,page,t,scale=1):
    from PIL import Image
    from layout import focus_state
    state=focus_state(page,t);zoom=state['zoom']
    if zoom<=1.00001:return im
    cx,cy=[v*scale for v in state['center']];inv=1/zoom
    return im.transform(im.size,Image.Transform.AFFINE,(inv,0,cx*(1-inv),0,inv,cy*(1-inv)),resample=Image.Resampling.BICUBIC)
def frame(page,t,font,scale=1):
    from PIL import ImageDraw
    im=paper(page,font,scale)
    if page.get('demonstration'):
        import models
        for e in models.strokes(page['demonstration'],t):paint(im,e,1,scale)
    for event in page['strokes']:
        if event['start']>t:break
        f=(t-event['start'])/(event['end']-event['start']);p=paint(im,event,f,scale)
        if f<1:
            d=ImageDraw.Draw(im);r=5*scale;d.ellipse((p[0]-r,p[1]-r,p[0]+r,p[1]+r),fill='#355c49',outline='#fffef9',width=max(1,round(2*scale)))
    return apply_focus(im,page,t,scale)

def export_boards(project,data,font):
    from PIL import Image,JpegImagePlugin
    folder=project/'pages';folder.mkdir(exist_ok=True);tikz=project/'tikz';tikz.mkdir(exist_ok=True);images=[];sheets=[]
    for page in data['pages']:
        im=frame(page,page['duration'],font);im.save(folder/(page['id']+'.png'));images.append(im)
        # Preview beginning, middle and end, so labels are checked during the process too.
        for f in (.15,.5,.95):sheets.append(frame(page,page['duration']*f,font).resize((640,360)))
        lines=['\\begin{tikzpicture}[x=.022cm,y=-.022cm,line cap=round,line join=round]','\\path[use as bounding box] (120,95) rectangle (1200,655);']
        if page.get('image'):
            a=page['image'];name=page['id']+'-source.png';(tikz/name).write_bytes(base64.b64decode(a['data'].split(',',1)[1]));lines.append(f'\\node[anchor=north west,inner sep=0pt] at ({a["x"]},{a["y"]}) {{\\includegraphics[width={a["w"]*.022}cm,height={a["h"]*.022}cm]{{{name}}}}};')
        diagram_strokes=[]
        if page.get('demonstration'):
            import models
            diagram_strokes=models.strokes(page['demonstration'],page['duration'])
        last_component=None
        for e in diagram_strokes+page['strokes']:
            component=e.get('component_id')
            if component and component!=last_component:lines.append(f'% component: {component} ({e.get("component_name","")})')
            last_component=component or last_component
            r,g,b=[int(e['color'][i:i+2],16) for i in (1,3,5)];coords=' '.join(f'({x:.2f},{y:.2f})' for x,y in e['points'])
            lines.append(f'\\draw[draw={{rgb,255:red,{r};green,{g};blue,{b}}},line width={e["width"]*.55:.2f}pt] plot coordinates {{{coords}}};')
        (tikz/(page['id']+'.tikz')).write_text('\n'.join(lines+['\\end{tikzpicture}']))
    images[0].save(project/'boards.pdf',save_all=True,append_images=images[1:],resolution=110)
    sheet=Image.new('RGB',(1920,360*len(data['pages'])),'white')
    for j,im in enumerate(sheets):sheet.paste(im,((j%3)*640,(j//3)*360))
    sheet.save(project/'contact-sheet.png')
    wrapper='\\documentclass[a4paper,landscape]{article}\n\\usepackage[margin=1cm]{geometry}\n\\usepackage{tikz,graphicx}\n\\pagestyle{empty}\n\\begin{document}\n\\centering\n'
    wrapper+='\n\\newpage\n'.join('\\resizebox{\\linewidth}{!}{\\input{'+p['id']+'.tikz}}' for p in data['pages'])+'\n\\end{document}\n';(tikz/'boards.tex').write_text(wrapper)
    if frame(data['pages'][0],.51,font).tobytes()!=frame(data['pages'][0],.51,font).tobytes():raise RuntimeError('Non-deterministic frame rendering')

def video(project,data,font,width):
    if data['draft']:raise ValueError('Draft timing cannot be exported as a narrated final video')
    cache=project/'cache/video';cache.mkdir(parents=True,exist_ok=True);keys=[];new=reused=0;scale=width/W
    engine=digest(Path(__file__).read_bytes()+(ROOT/'scripts/ink.py').read_bytes()+(ROOT/'scripts/models.py').read_bytes()+(ROOT/'scripts/layout.py').read_bytes()+(ROOT/'scripts/components.py').read_bytes()+font.read_bytes())
    for page in data['pages']:
        local={k:v for k,v in page.items() if k not in ('start','end')};key=digest([local,width,data['fps'],engine]);target=cache/(key+'.mp4');keys.append(key)
        if target.exists():reused+=1;continue
        part=cache/(key+'.part.mp4');enc=subprocess.Popen(['ffmpeg','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{round(H*scale)}','-r',str(data['fps']),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','22','-pix_fmt','yuv420p',str(part)],stdin=subprocess.PIPE)
        baked=paper(page,font,scale);done=0;events=page['strokes']
        for fi in range(page['frames']):
            t=fi/data['fps']
            if page.get('demonstration'):
                enc.stdin.write(frame(page,t,font,scale).tobytes());continue
            while done<len(events) and events[done]['end']<=t:paint(baked,events[done],1,scale);done+=1
            im=baked.copy()
            if done<len(events) and events[done]['start']<=t:
                from PIL import ImageDraw
                e=events[done];p=paint(im,e,(t-e['start'])/(e['end']-e['start']),scale);d=ImageDraw.Draw(im);r=5*scale;d.ellipse((p[0]-r,p[1]-r,p[0]+r,p[1]+r),fill='#355c49',outline='#fffef9',width=max(1,round(2*scale)))
            enc.stdin.write(apply_focus(im,page,t,scale).tobytes())
        enc.stdin.close()
        if enc.wait():raise RuntimeError(f'Could not render page {page["id"]}')
        part.replace(target);new+=1;print(f'rendered {page["id"]}',flush=True)
    listing=cache/'segments.txt';listing.write_text('\n'.join(f"file '{key}.mp4'" for key in keys))
    subprocess.run(['ffmpeg','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(project/'narration.wav'),'-c:v','copy','-c:a','aac','-b:a','128k','-shortest','-movflags','+faststart',str(project/'video.mp4')],check=True)
    return {'video_new':new,'video_reused':reused}

def run_build(project,args):
    project=Path(project).resolve();lesson,pages=compile_lesson(project);font=font_path(lesson,project)
    from layout import audit_lesson
    layout_report=audit_lesson(pages);write_json(project/'layout-report.json',layout_report)
    from components import audit_components
    component_report=audit_components(pages);write_json(project/'component-report.json',component_report)
    renderer=args.renderer or lesson.get('renderer','notebook')
    if renderer not in ('notebook','motion-canvas','manim'):raise ValueError('Unknown animation renderer')
    if args.video and renderer!='notebook':
        from engine_render import versions,native_scene
        versions(renderer,args.runtime)
        for page in pages:native_scene(page,project,renderer)
    data,pcm,stats=prepare(project,lesson,pages,args)
    with wave.open(str(project/'narration.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes(pcm)
    prosody={'version':1,'source':data['speech_plan_source'],'speech':data['speech'],'cues':[{k:c[k] for k in ('id','role','tts','speed','pitch','volume','emotion','emphasis','pause_before','pause') if k in c} for p in data['pages'] for c in p['cues']]}
    write_json(project/'prosody.json',prosody)
    if not args.draft:
        from voice import master
        mastering=master(project,data['speech'],project/'narration.wav',data['duration']);stats['audio_mastering']=mastering
        from voice_quality import audit
        voice_report=audit(project,data);stats.update(voice_quality=voice_report['status'],voice_warnings=len(voice_report['warnings']))
        subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(project/'narration.wav'),'-c:a','libmp3lame','-q:a','3',str(project/'narration.mp3')],check=True)
    write_json(project/'timeline.json',data);export_boards(project,data,font)
    audio='' if args.draft else 'data:audio/mpeg;base64,'+base64.b64encode((project/'narration.mp3').read_bytes()).decode()
    template=(ROOT/'assets/player.html').read_text().replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/')).replace('__AUDIO__',audio).replace('__MODELS__',(ROOT/'assets/models.js').read_text())
    (project/'preview.html').write_text(template)
    (project/'narration.md').write_text('# '+lesson['title']+'\n\n'+'\n\n'.join('## '+p['title']+'\n\n'+'\n\n'.join(c['tts'] for c in p['cues']) for p in data['pages']))
    if args.video:
        if renderer=='notebook':stats.update(video(project,data,font,args.width))
        else:
            from engine_render import render
            stats.update(render(project,data,font,args.width,renderer,args.runtime))
    stats['renderer']=renderer;stats.update(layout_quality=layout_report['status'],layout_warnings=len(layout_report['warnings']),component_quality=component_report['status'],component_warnings=len(component_report['warnings']),components=sum(component_report['counts'].values()))
    stats.update(duration=data['duration'],draft=args.draft,pages=len(data['pages']),backend=data['speech']['backend']);write_json(project/'build-report.json',stats);print(json.dumps(stats,ensure_ascii=False))

def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='command',required=True)
    init=subs.add_parser('init');init.add_argument('project');init.add_argument('--title');init.add_argument('--backend',choices=['glm','doubao','minimax','edge','user'],default='glm');init.add_argument('--example',choices=['starter','gauss','components','incline'],default='starter')
    build=subs.add_parser('build');build.add_argument('project');build.add_argument('--draft',action='store_true');build.add_argument('--video',action='store_true');build.add_argument('--backend',choices=['glm','doubao','minimax','edge','user']);build.add_argument('--voice');build.add_argument('--fps',type=int,choices=[12,24,30],default=24);build.add_argument('--width',type=int,choices=[1280,1920],default=1280)
    check=subs.add_parser('check');check.add_argument('project')
    layout_check=subs.add_parser('layout-check',help='Audit semantic zones, overlaps and one-page problem policy');layout_check.add_argument('project');layout_check.add_argument('--strict',action='store_true')
    component_check=subs.add_parser('component-check',help='Audit reusable physics components and their semantic zones');component_check.add_argument('project');component_check.add_argument('--strict',action='store_true')
    voice_check=subs.add_parser('voice-check',help='Audit an existing narration.wav and timeline.json');voice_check.add_argument('project');voice_check.add_argument('--strict',action='store_true')
    batch=subs.add_parser('batch');batch.add_argument('manifest');batch.add_argument('--jobs',type=int,choices=[1,2,3,4],default=2);batch.add_argument('--draft',action='store_true');batch.add_argument('--video',action='store_true');batch.add_argument('--backend',choices=['glm','doubao','minimax','edge','user']);batch.add_argument('--voice');batch.add_argument('--fps',type=int,choices=[12,24,30],default=24);batch.add_argument('--width',type=int,choices=[1280,1920],default=1280)
    subs.add_parser('doctor')
    for target in (build,batch):
        target.add_argument('--renderer',choices=['notebook','motion-canvas','manim'])
        target.add_argument('--runtime',help='Workspace directory containing Motion Canvas node_modules')
    render_cmd=subs.add_parser('render',help='Render an existing measured timeline without synthesizing speech')
    render_cmd.add_argument('project');render_cmd.add_argument('--renderer',choices=['notebook','motion-canvas','manim'],required=True);render_cmd.add_argument('--runtime');render_cmd.add_argument('--width',type=int,choices=[1280,1920],default=1920)
    setup_cmd=subs.add_parser('setup-renderers');setup_cmd.add_argument('--runtime',required=True)
    args=parser.parse_args()
    if args.command=='doctor':
        from engine_render import doctor
        print(json.dumps({'python':sys.executable,'Pillow':bool(importlib.util.find_spec('PIL')),'edge_tts':bool(importlib.util.find_spec('edge_tts')),'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),'animation':doctor()},ensure_ascii=False));return
    if args.command=='voice-check':
        from voice_quality import audit
        report=audit(args.project);print(json.dumps(report,ensure_ascii=False))
        if args.strict and report['warnings']:sys.exit(1)
        return
    if args.command=='layout-check':
        from layout import audit_lesson
        lesson,pages=compile_lesson(args.project);report=audit_lesson(pages);write_json(Path(args.project)/'layout-report.json',report);print(json.dumps(report,ensure_ascii=False))
        if args.strict and report['warnings']:sys.exit(1)
        return
    if args.command=='component-check':
        from components import audit_components
        lesson,pages=compile_lesson(args.project);report=audit_components(pages);write_json(Path(args.project)/'component-report.json',report);print(json.dumps(report,ensure_ascii=False))
        if args.strict and report['warnings']:sys.exit(1)
        return
    if args.command=='setup-renderers':
        from engine_render import setup
        setup(args.runtime);return
    if args.command=='render':
        from engine_render import render
        project=Path(args.project).resolve();data=json.loads((project/'timeline.json').read_text());lesson=json.loads((project/'lesson.json').read_text());font=font_path(lesson,project)
        if args.renderer=='notebook':stats=video(project,data,font,args.width)
        else:stats=render(project,data,font,args.width,args.renderer,args.runtime)
        stats.update(duration=data['duration'],renderer=args.renderer)
        write_json(project/('render-report-'+args.renderer+'.json'),stats);print(json.dumps(stats,ensure_ascii=False));return
    if args.command=='batch':
        from concurrent.futures import ThreadPoolExecutor
        manifest=Path(args.manifest).resolve();jobs=json.loads(manifest.read_text())['projects']
        if args.draft and args.video:raise ValueError('Draft mode and final video mode are separate')
        def one(value):
            project=(manifest.parent/value).resolve();cmd=[sys.executable,str(Path(__file__).resolve()),'build',str(project),'--fps',str(args.fps),'--width',str(args.width)]
            for flag in ('draft','video'):
                if getattr(args,flag):cmd.append('--'+flag)
            for flag in ('backend','voice','renderer','runtime'):
                if getattr(args,flag):cmd.extend(['--'+flag,getattr(args,flag)])
            r=subprocess.run(cmd,capture_output=True,text=True);result={'project':str(project),'ok':r.returncode==0,'message':(r.stderr if r.returncode else r.stdout)[-2000:]};print(json.dumps(result,ensure_ascii=False),flush=True);return result
        with ThreadPoolExecutor(args.jobs) as pool:results=list(pool.map(one,jobs))
        write_json(manifest.parent/'batch-report.json',results)
        if any(not x['ok'] for x in results):sys.exit(1)
        return
    if args.command=='init':
        from voice import DEFAULTS
        from speech_plan import externalize
        from engine_render import local_config
        p=Path(args.project).resolve();p.mkdir(parents=True,exist_ok=True)
        if (p/'lesson.json').exists():raise ValueError('lesson.json already exists; edit it or choose another project')
        data=json.loads((ROOT/'assets'/(args.example+'.json')).read_text())
        if args.title:data['title']=args.title
        data.setdefault('show_titles',False);data.setdefault('camera','static')
        local_speech=(local_config().get('speech_defaults') or {}).get(args.backend,{})
        data['speech']={'backend':args.backend,'voice':local_speech.get('voice',DEFAULTS[args.backend]),'speed':1.0,'audio_mastering':True}
        if local_speech.get('model'):data['speech']['model']=local_speech['model']
        data,plan=externalize(data);write_json(p/'lesson.json',data);write_json(p/'speech-plan.json',plan);print(p/'lesson.json');return
    if args.command=='check':
        from layout import audit_lesson
        from components import audit_components
        l,p=compile_lesson(args.project);report=audit_lesson(p);component_report=audit_components(p);print(json.dumps({'title':l['title'],'pages':len(p),'cues':sum(len(x['cues']) for x in p),'geometry':'finite and within writing area','layout':report['status'],'layout_warnings':len(report['warnings']),'components':sum(component_report['counts'].values()),'component_quality':component_report['status'],'component_warnings':len(component_report['warnings'])}));return
    if args.draft and args.video:raise ValueError('Use --draft for layout, or --video for measured speech and final export')
    run_build(args.project,args)
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,ImportError,RuntimeError,OSError) as e:print(f'ERROR: {e}',file=sys.stderr);sys.exit(1)
