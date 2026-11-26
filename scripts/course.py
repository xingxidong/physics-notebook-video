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
    from board_flow import carry, draw as flow_draw, references, reserve, underline
    from speech_plan import apply as apply_speech_plan
    project=Path(project).resolve()
    lesson=json.loads((project/'lesson.json').read_text()) if lesson is None else copy.deepcopy(lesson)
    lesson,speech_meta=apply_speech_plan(project,lesson);lesson['_speech_plan_meta']=speech_meta
    from term_inventory import apply as apply_inventory
    lesson=apply_inventory(project,lesson)
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
        prewritten=set((layout_spec or {}).get('prewritten', []))
        found_prewritten=set()
        camera=page.get('camera',lesson.get('camera','static'))
        if camera not in ('static','focus'):raise ValueError('camera must be static or focus')
        cooked={'id':pid,'title':page.get('title',lesson['title']),'show_title':page.get('show_title',lesson.get('show_titles',True)),'camera':camera,'cues':[],'components':[],'anchors':{},'index':pi};component_ids=set()
        cooked['paper']=page.get('paper',lesson.get('paper','grid'))
        if cooked['paper'] not in ('grid','plain'):raise ValueError('paper must be grid or plain')
        occupied = {}
        if layout_spec:
            cooked['layout']=layout_spec
            if layout_spec.get('carry'):
                cooked['carry_blocks']=carry(pages[-1] if pages else None, layout_spec['carry'], pid)
                for block in cooked['carry_blocks']:
                    reserve(occupied,block,layout_spec)
        if page.get('problem_id'):cooked['problem_id']=str(page['problem_id'])
        if page.get('native_scenes'):cooked['native_scenes']=copy.deepcopy(page['native_scenes'])
        if page.get('scene_events'):
            from scene_events import validate
            validate(page)
            cooked['scene_events']=copy.deepcopy(page['scene_events']);cooked['scene_initial']=copy.deepcopy(page.get('scene_initial',{}))
        if page.get('problem'):
            from cards import problem_card
            cooked['problem_card']=problem_card(page['problem'],font_path(lesson,project),project/'cache/problem-tex')
        if page.get('image'):
            from cards import source_image
            cooked['image']=source_image(project,page['image'])
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
                if a.get('_flow'):
                    try:
                        flow_draw(gi,a,layout_spec,occupied,size,color)
                    except ValueError as exc:
                        raise ValueError(f'{pid} / {cue["id"]}: {exc}') from None
                elif kind=='text':ink.text(gi,a['text'],n(a['x']),n(a['y']),size,color)
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
                if a.get('emphasis') and kind in ('text','math'):
                    underline(gi,color)
                for e in ink.groups[gi]:
                    if not e['points'] or any(not(120<=x<=1200 and 95<=y<=655) for x,y in e['points']):raise ValueError(f'{cue["id"]}, action {ai}: ink leaves the writing area x=120..1200, y=95..655')
                cue['blocks'].append({'id':a.get('id'),'board_group':a.get('board_group'),'emphasis':a.get('emphasis',False),'size':size,'strokes':ink.groups[gi],'at':a.get('at'),'write_seconds':write_seconds,'action':ai,'kind':kind,'zone':a.get('zone'),'allow_overlap':bool(a.get('allow_overlap',False)),'transform_group':a.get('transform_group'),'transform_step':a.get('transform_step'),'component_id':a.get('component_id'),'component_name':a.get('component_name'),'component_part':a.get('component_part')})
                block=cue['blocks'][-1]
                matched=references(block) & prewritten
                if matched:
                    if at is not None or write_seconds is not None:
                        raise ValueError(f'{pid} / {cue["id"]}: prewritten actions cannot set at or write_seconds')
                    block['prewritten']=True
                    found_prewritten.update(matched)
                if layout_spec and layout_spec.get('flow')=='measured':
                    reserve(occupied,block,layout_spec)
            cue['resolved_actions']=expanded
            cooked['cues'].append(cue)
        if missing := prewritten - found_prewritten:
            raise ValueError(f'{pid}: layout.prewritten 找不到本页笔迹 {", ".join(sorted(missing))}')
        if page.get('demonstration'):
            import models
            cooked['demonstration']=models.setup(page['demonstration'])
            cue_ids={c['id'] for c in cooked['cues']}
            models.validate_cues(cooked['demonstration'],cue_ids)
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

def schedule(cue,audio,*,classroom=False):
    blocks=[block for block in cue['blocks'] if not block.get('prewritten')];n=len(blocks)
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
            sw=[max(8,sum(math.dist(a,b) for a,b in zip(e['points'],e['points'][1:])))**.7+9 for e in strokes];cursor=t
            writing_span=span
            if block.get('write_seconds') is not None:
                writing_span=min(writing_span,block['write_seconds'])
            if classroom:
                # Speech can continue over a finished line. Size the pen action
                # by the amount of ink at the notebook's reference resolution.
                writing_span=min(writing_span,max(.18,sum(sw)/240))
            for e,w in zip(strokes,sw):
                dt=writing_span*w/sum(sw);event=copy.deepcopy(e);event.update(start=cursor,end=cursor+dt*.88,cue=cue['id'],action=j,board_id=block.get('id'),board_group=block.get('board_group'),anchor_quality=qualities.get(j,'sequence'),component_id=block.get('component_id'),component_name=block.get('component_name'),component_part=block.get('component_part'));events.append(event);cursor+=dt
            t += writing_span if classroom else span
    return events

def prepare(project,lesson,pages,args):
    from voice import synth,DEFAULTS,split_group
    from pronunciation import display_words
    cfg=copy.deepcopy(lesson.get('speech',{'backend':'glm'}))
    classroom=lesson.get('_speech_plan_meta',{}).get('delivery_profile')=='classroom'
    if args.backend:
        if args.backend!=cfg.get('backend'):cfg['voice']=DEFAULTS[args.backend]
        cfg['backend']=args.backend
    if args.voice:cfg['voice']=args.voice
    cfg.setdefault('audio_mastering',True)
    fps=args.fps;global_t=0;all_pcm=bytearray();timeline=[];voice_hits=voice_new=0
    from board_flow import initial_strokes
    from lesson_review import opening, opening_image
    from lesson_duration import page_paces
    pacing=page_paces(project,lesson) if args.draft else {}
    profile=opening(lesson)
    if profile:
        frames=round(3*fps)
        global_t=frames/fps
        silence=bytes(round(global_t*SR)*2)
        all_pcm.extend(silence)
        timeline.append({'id':'opening-card','title':profile['title'],'index':-1,'show_title':False,
                         'start':0.,'end':global_t,'duration':global_t,'frames':frames,'cues':[],
                         'strokes':[],'camera':'static','audio_sha256':digest(silence),
                         'image':opening_image(profile,font_path(lesson,project))})
    if not args.draft and cfg.get('backend') in ('minimax','qwen'):
        from card_speech import lesson_inputs, merged_provider, restore_script_words
        card_inputs=lesson_inputs({**lesson,'pages':pages})
    for p in pages:
        local=.35;pcm=bytearray(b'\0'*round(local*SR)*2);events=initial_strokes(p,fps);cues=[];focuses=[]
        records=[]
        if args.draft:
            for cue in p['cues']:
                pace=pacing.get(p['id'])
                spoken = cue.get('spoken_tts', cue['tts'])
                seconds=(sum(ch.isalnum() for ch in spoken)/(pace*cue.get('speed',1))
                         if pace else len(spoken)/4.2)
                records.append((cue,{'duration':max(1.2,seconds),'words':[],'file':None},None,
                                cue['pause_before'],cue['pause'],None))
        else:
            index=0
            while index<len(p['cues']):
                cue=p['cues'][index];group=cue.get('speech_group')
                members=[cue];index+=1
                if group:
                    while index<len(p['cues']) and p['cues'][index].get('speech_group')==group:
                        following = p['cues'][index]
                        if cfg.get('backend') == 'minimax' and following.get('minimax_pronunciation') != cue.get('minimax_pronunciation'):
                            break
                        if cfg.get('backend') == 'minimax':
                            try:
                                merged_provider([card_inputs[p['id'],member['id']] for member in [*members,following]])
                            except ValueError:
                                break
                        members.append(following);index+=1
                    if cfg.get('backend')=='user':
                        raise ValueError(f'{cue["id"]}: speech_group is unavailable with user-supplied audio files')
                    spoken_texts = [member.get('spoken_tts', member['tts']) for member in members]
                    grouped={**cue,'id':'speech-group-'+group,'tts':' '.join(spoken_texts)}
                    if cfg.get('backend') == 'minimax':
                        grouped['_card_provider']=merged_provider([card_inputs[p['id'],m['id']] for m in members])
                    elif cfg.get('backend') == 'qwen':
                        grouped['_qwen_input']=' '.join(card_inputs[p['id'],m['id']]['local_text'] for m in members)
                    audio=synth(project,cfg,grouped);voice_hits+=bool(audio['cache_hit']);voice_new+=not audio['cache_hit']
                    with wave.open(audio['file']) as w:clip=w.readframes(w.getnframes())
                    edge_report=None
                    if cfg.get('trim_edges',False):
                        from audio_edges import trim
                        clip,audio,edge_report=trim(clip,audio,SR,cfg['trim_edges'])
                    if '_card_provider' in grouped:
                        audio=restore_script_words(audio,grouped['_card_provider']['provider_text'],grouped['tts'])
                    pieces=split_group(audio,spoken_texts)
                    for member,piece_index,piece in zip(members,range(len(members)),pieces):
                        start=round(piece['start']*SR)*2;stop=round(piece['end']*SR)*2
                        segment={'duration':piece['duration'],'words':piece['words'],'file':audio['file'],
                                 'group':group,'timing':piece['timing'],'signature':audio.get('signature',{})}
                        records.append((member,segment,clip[start:stop],
                                        member['pause_before'] if piece_index==0 else 0,
                                        member['pause'] if piece_index==len(members)-1 else 0,
                                        edge_report if piece_index==0 else None))
                    continue
                request={**cue,'tts':cue.get('spoken_tts',cue['tts'])}
                if cfg.get('backend') == 'minimax':
                    request['_card_provider']=merged_provider([card_inputs[p['id'],cue['id']]])
                elif cfg.get('backend') == 'qwen':
                    request['_qwen_input']=card_inputs[p['id'],cue['id']]['local_text']
                audio=synth(project,cfg,request);voice_hits+=bool(audio['cache_hit']);voice_new+=not audio['cache_hit']
                with wave.open(audio['file']) as w:clip=w.readframes(w.getnframes())
                edge_report=None
                if cfg.get('trim_edges',False):
                    from audio_edges import trim
                    clip,audio,edge_report=trim(clip,audio,SR,cfg['trim_edges'])
                if '_card_provider' in request:
                    audio=restore_script_words(audio,request['_card_provider']['provider_text'],request['tts'])
                records.append((cue,audio,clip,cue['pause_before'],cue['pause'],edge_report))
        for cue,audio,clip,pause_before,pause_after,edge_report in records:
            pcm.extend(b'\0'*round(pause_before*SR)*2)
            # Quantise start to exact audio samples for every playback/export path.
            local=len(pcm)/(2*SR)
            if cue.get('symbol_readings'):
                audio = {**audio, 'words': display_words(cue['tts'], cue['symbol_readings'], audio.get('words', []))}
            for e in schedule(cue,audio,classroom=classroom):e.update(start=e['start']+local,end=e['end']+local);events.append(e)
            delivery={k:cue[k] for k in ('role','speed','pitch','volume','emotion','emphasis','pause_reason','speech_group','spoken_tts','symbol_readings','minimax_pronunciation') if k in cue}
            cues.append({'id':cue['id'],'text':cue['text'],'tts':cue['tts'],'start':local,'end':local+audio['duration'],'pause_before':pause_before,'pause':pause_after,'timing':'estimated' if args.draft else 'measured','words':audio.get('words',[]),**delivery})
            tone_entries=audio.get('signature',{}).get('pronunciation_dict',{}).get('tone',[])
            if tone_entries:cues[-1]['minimax_tone_entries']=tone_entries
            if edge_report:cues[-1]['audio_edges']=edge_report
            if cue.get('focus'):
                focused=copy.deepcopy(cue['focus']);focused.update(start=local,end=local+audio['duration']);focuses.append(focused)
            if args.draft:pcm.extend(b'\0'*round(audio['duration']*SR)*2)
            else:pcm.extend(clip)
            pcm.extend(b'\0'*round(pause_after*SR)*2)
        frames=math.ceil(len(pcm)/(2*SR)*fps);target=round(frames/fps*SR)*2;pcm.extend(b'\0'*max(0,target-len(pcm)))
        seconds=len(pcm)/(2*SR);prepared={'id':p['id'],'title':p['title'],'show_title':p.get('show_title',True),'index':p['index'],'start':global_t,'end':global_t+seconds,'duration':seconds,'frames':frames,'cues':cues,'strokes':events,'audio_sha256':digest(bytes(pcm))}
        prepared['paper']=p.get('paper','grid')
        if p.get('layout'):prepared['layout']=p['layout']
        if p.get('layout_report'):prepared['layout_report']=p['layout_report']
        if p.get('problem_id'):prepared['problem_id']=p['problem_id']
        if p.get('components'):prepared['components']=p['components']
        if p.get('anchors'):prepared['anchors']=p['anchors']
        prepared['camera']=p['camera']
        if focuses:prepared['focus']=focuses
        if 'image' in p:prepared['image']=p['image']
        if 'problem_card' in p:prepared['problem_card']=p['problem_card']
        if 'native_scenes' in p:prepared['native_scenes']=p['native_scenes']
        if p.get('scene_events'):
            from scene_events import bind
            prepared['scene_tracks']=bind(p,cues,seconds)
        if 'demonstration' in p:
            import models
            prepared['demonstration']=models.bind_cues(p['demonstration'],cues)
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
    if page.get('paper')=='plain':d.rounded_rectangle(box((35,8,1231,700)),round(9*scale),fill='#ffffff')
    if page.get('show_title',True):d.text((75*scale,29*scale),page['title'],font=ImageFont.truetype(str(font),round(24*scale)),fill='#344940')
    if page['index']>=0:
        d.text((1150*scale,659*scale),f'{page["index"]+1:02d}',font=ImageFont.truetype(str(font),round(16*scale)),fill='#83958a')
    if page.get('draft_preview'):d.text((420*scale,659*scale),'草稿 · 无配音 · 估算时间',font=ImageFont.truetype(str(font),round(16*scale)),fill='#a15936')
    if page.get('image'):
        a=page['image'];source=Image.open(io.BytesIO(base64.b64decode(a['data'].split(',',1)[1]))).convert('RGB');source=source.resize((round(a['w']*scale),round(a['h']*scale)),Image.Resampling.LANCZOS);im.paste(source,(round(a['x']*scale),round(a['y']*scale)))
    if page.get('problem_card'):
        a=page['problem_card'];source=Image.open(io.BytesIO(base64.b64decode(a['data'].split(',',1)[1]))).convert('RGB');source=source.resize((round(a['w']*scale),round(a['h']*scale)),Image.Resampling.LANCZOS);im.paste(source,(round(a['x']*scale),round(a['y']*scale)))
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
def demonstration_strokes(page,t,board=False):
    import models
    model=page['demonstration']
    if board and 'board_progress' in model:
        t=float(model['board_progress']);model={**model,'segments':[],'start':0,'stop':1,'vector_start':0}
    return models.strokes(model,t)

def frame(page,t,font,scale=1,board=False):
    from PIL import ImageDraw
    im=paper(page,font,scale)
    if page.get('demonstration'):
        for e in demonstration_strokes(page,t,board):paint(im,e,1,scale)
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
        im=frame(page,page['duration'],font,board=True);im.save(folder/(page['id']+'.png'));images.append(im)
        # Preview beginning, middle and end, so labels are checked during the process too.
        for f in (.15,.5,.95):sheets.append(frame(page,page['duration']*f,font).resize((640,360)))
        lines=['\\begin{tikzpicture}[x=.022cm,y=-.022cm,line cap=round,line join=round]','\\path[use as bounding box] (120,95) rectangle (1200,655);']
        if page.get('image'):
            a=page['image'];name=page['id']+'-source.png';(tikz/name).write_bytes(base64.b64decode(a['data'].split(',',1)[1]));lines.append(f'\\node[anchor=north west,inner sep=0pt] at ({a["x"]},{a["y"]}) {{\\includegraphics[width={a["w"]*.022}cm,height={a["h"]*.022}cm]{{{name}}}}};')
        if page.get('problem_card'):
            a=page['problem_card'];name=page['id']+'-problem.png';(tikz/name).write_bytes(base64.b64decode(a['data'].split(',',1)[1]));lines.append(f'\\node[anchor=north west,inner sep=0pt] at ({a["x"]},{a["y"]}) {{\\includegraphics[width={a["w"]*.022}cm,height={a["h"]*.022}cm]{{{name}}}}};')
            (tikz/(page['id']+'-problem.tex')).write_text(a['latex_source'])
        diagram_strokes=[]
        if page.get('demonstration'):
            diagram_strokes=demonstration_strokes(page,page['duration'],board=True)
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
    engine=digest(Path(__file__).read_bytes()+(ROOT/'scripts/ink.py').read_bytes()+(ROOT/'scripts/models.py').read_bytes()+(ROOT/'scripts/incline_motion.py').read_bytes()+(ROOT/'scripts/pursuit.py').read_bytes()+(ROOT/'scripts/cards.py').read_bytes()+(ROOT/'scripts/layout.py').read_bytes()+(ROOT/'scripts/components.py').read_bytes()+font.read_bytes())
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
                e=events[done];p=paint(im,e,(t-e['start'])/(e['end']-e['start']),scale)
                d=ImageDraw.Draw(im);r=5*scale;d.ellipse((p[0]-r,p[1]-r,p[0]+r,p[1]+r),fill='#355c49',outline='#fffef9',width=max(1,round(2*scale)))
            enc.stdin.write(apply_focus(im,page,t,scale).tobytes())
        enc.stdin.close()
        if enc.wait():raise RuntimeError(f'Could not render page {page["id"]}')
        part.replace(target);new+=1;print(f'rendered {page["id"]}',flush=True)
    listing=cache/'segments.txt';listing.write_text('\n'.join(f"file '{key}.mp4'" for key in keys))
    subprocess.run(['ffmpeg','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(project/'narration.wav'),'-c:v','copy','-c:a','aac','-b:a','128k','-shortest','-movflags','+faststart',str(project/'video.mp4')],check=True)
    return {'video_new':new,'video_reused':reused}

def run_build(project,args):
    from feedback_bank import check as check_feedback
    check_feedback(project, enforce=not args.draft)
    project=Path(project).resolve();lesson,pages=compile_lesson(project);font=font_path(lesson,project)
    if not args.draft:
        from final_review import invalidate
        invalidate(project)
    from teaching import audit as audit_teaching
    from lesson_review import require as require_review
    renderer=args.renderer or lesson.get('renderer','motion-canvas' if lesson.get('kind')=='problem' else 'notebook')
    if not args.draft:
        require_review(project,lesson,renderer)
    teaching_report=audit_teaching(project,lesson,pages);write_json(project/'teaching-report.json',teaching_report)
    if teaching_report['errors']:raise ValueError('Teaching source check failed: '+'; '.join(x['message'] for x in teaching_report['errors']))
    from delivery import inspect_script
    write_json(project/'delivery-report.json',inspect_script(lesson,backend=args.backend))
    from layout import audit_lesson
    layout_report=audit_lesson(pages);write_json(project/'layout-report.json',layout_report)
    from components import audit_components
    component_report=audit_components(pages);write_json(project/'component-report.json',component_report)
    if renderer not in ('notebook','motion-canvas','manim'):raise ValueError('Unknown animation renderer')
    if args.video and lesson.get('kind')=='problem' and renderer=='notebook':raise ValueError('Problem videos require Motion Canvas or Manim; notebook remains available for draft layout')
    if args.video and renderer!='notebook':
        from engine_render import versions,native_scene
        versions(renderer,args.runtime)
        for page in pages:native_scene(page,project,renderer)
    data,pcm,stats=prepare(project,lesson,pages,args)
    from board_review import check as check_board
    board_report=check_board(lesson,pages,data)
    write_json(project/'board-review-report.json',board_report)
    from course_outline import timing_report
    from lesson_duration import report as duration_report
    write_json(project/'course-timing-report.json',{**timing_report(project,lesson,data),
                                                  'lesson_duration':duration_report(project,lesson,data)})
    if not args.draft and lesson.get('review_required') and (layout_report['warnings'] or board_report['warnings']):
        raise ValueError('实际时间轴的板书检查未通过，见 board-review-report.json 和 layout-report.json。')
    from knowledge_board import inspect_timeline
    knowledge_report=inspect_timeline(teaching_report['knowledge_notes'],data)
    write_json(project/'knowledge-board-report.json',knowledge_report)
    if knowledge_report['errors']:raise ValueError('Knowledge board check failed: '+'; '.join(x['message'] for x in knowledge_report['errors']))
    scene_entries=[{'page':p['id'],**e} for p in data['pages'] for e in p.get('scene_tracks',{}).get('events',[])]
    estimated=sum(e['anchor_quality']=='estimated-word' or e['end_anchor_quality']=='estimated-word' for e in scene_entries)
    write_json(project/'scene-report.json',{'status':'attention' if estimated else 'pass' if scene_entries else 'not_applicable','events':len(scene_entries),'estimated_events':estimated,'bindings':scene_entries})
    math_entries=[{'page':p['id'],'cue':c['id'],'action':b['action'],'renderer':'handwriting'} for p in pages for c in p['cues'] for b in c['blocks'] if b['kind']=='math']
    write_json(project/'math-report.json',{'status':'pass' if math_entries else 'not_applicable','formulas':len(math_entries),'handwritten_formulas':len(math_entries),'items':math_entries})
    data['lesson_sha256']=digest(lesson)
    if not args.draft and lesson.get('review_required'):
        from lesson_review import current_review
        data['review_sha256']=current_review(project,lesson)['fingerprint']
    with wave.open(str(project/'narration.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes(pcm)
    prosody={'version':1,'source':data['speech_plan_source'],'speech':data['speech'],'cues':[{k:c[k] for k in ('id','role','tts','spoken_tts','speed','pitch','volume','emotion','emphasis','pause_before','pause') if k in c} for p in data['pages'] for c in p['cues']]}
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
        if lesson.get('review_required'):
            from lesson_review import export_delivery
            export_delivery(project,lesson)
        if not data.get('draft') and data.get('lesson_sha256'):
            from production_workflow import checkpoint
            checkpoint(project,lesson,data,project/'video.mp4')
    stats['renderer']=renderer;stats.update(layout_quality=layout_report['status'],layout_warnings=len(layout_report['warnings']),component_quality=component_report['status'],component_warnings=len(component_report['warnings']),components=sum(component_report['counts'].values()),teaching_quality=teaching_report['status'],motion_scenes=teaching_report['motion_scenes'],derivation_steps=teaching_report['derivation_steps'])
    stats.update(duration=data['duration'],draft=args.draft,pages=len(data['pages']),backend=data['speech']['backend']);write_json(project/'build-report.json',stats);print(json.dumps(stats,ensure_ascii=False))

def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='command',required=True)
    init=subs.add_parser('init',help='Start a lesson from a worked example')
    init.add_argument('project');init.add_argument('--title');init.add_argument('--backend',choices=['glm','doubao','minimax','edge','qwen','user'])
    template=init.add_mutually_exclusive_group()
    template.add_argument('--kind',choices=['problem','concept'],help='Start with the exercise or new-concept lesson example')
    template.add_argument('--example',choices=['starter','gauss','components','incline','pursuit','electric-field-intro','dimension-board'])
    build=subs.add_parser('build');build.add_argument('project');build.add_argument('--draft',action='store_true');build.add_argument('--video',action='store_true');build.add_argument('--backend',choices=['glm','doubao','minimax','edge','qwen','user']);build.add_argument('--voice');build.add_argument('--fps',type=int,choices=[12,24,30],default=24);build.add_argument('--width',type=int,choices=[1280,1920],default=1280)
    check=subs.add_parser('check');check.add_argument('project')
    board_check=subs.add_parser('board-check',help='Check visible relationships and motion on a silent timeline')
    board_check.add_argument('project');board_check.add_argument('--strict',action='store_true')
    review=subs.add_parser('review-plan',help='Generate the plan, complete script and silent review previews')
    review.add_argument('project')
    duration=subs.add_parser('estimate-duration',help='Estimate a teaching plan before narration or compare it with the drafted lesson')
    duration.add_argument('project');duration.add_argument('--plan-only',action='store_true')
    quality=subs.add_parser('quality-check',help='Check current lesson sources, pacing, layout and delivery with explicit review coverage')
    quality.add_argument('project');quality.add_argument('--stage',choices=('plan','final'),default='plan')
    quality.add_argument('--strict',action='store_true')
    quality.add_argument('--video-file',help='Final MP4 to inspect (relative to project, or absolute)')
    approval=subs.add_parser('approve-plan',help='Record the reviewer’s approval of the current plan')
    approval.add_argument('project');approval.add_argument('--feedback',required=True)
    layout_check=subs.add_parser('layout-check',help='Audit semantic zones, overlaps and one-page problem policy');layout_check.add_argument('project');layout_check.add_argument('--strict',action='store_true')
    component_check=subs.add_parser('component-check',help='Audit reusable physics components and their semantic zones');component_check.add_argument('project');component_check.add_argument('--strict',action='store_true')
    teaching_check=subs.add_parser('teaching-check',help='Check the selected lesson workflow, including visible derivations and concept notes');teaching_check.add_argument('project')
    voice_check=subs.add_parser('voice-check',help='Audit an existing narration.wav and timeline.json');voice_check.add_argument('project');voice_check.add_argument('--strict',action='store_true')
    voice_check.add_argument('--listen',metavar='CUE_ID',help='Extract a listening clip from the existing narration')
    voice_check.add_argument('--term-reel',action='store_true',help='Export a WAV and index of letters and polyphonic terms from measured audio')
    voice_check.add_argument('--context',action='store_true',help='Include neighboring cues when using --listen')
    batch=subs.add_parser('batch');batch.add_argument('manifest');batch.add_argument('--jobs',type=int,choices=[1,2,3,4],default=2);batch.add_argument('--draft',action='store_true');batch.add_argument('--video',action='store_true');batch.add_argument('--backend',choices=['glm','doubao','minimax','edge','qwen','user']);batch.add_argument('--voice');batch.add_argument('--fps',type=int,choices=[12,24,30],default=24);batch.add_argument('--width',type=int,choices=[1280,1920],default=1280)
    subs.add_parser('doctor')
    for target in (build,batch):
        target.add_argument('--renderer',choices=['notebook','motion-canvas','manim'])
        target.add_argument('--runtime',help='Workspace directory containing Motion Canvas node_modules')
    render_cmd=subs.add_parser('render',help='Render an existing measured timeline without synthesizing speech')
    render_cmd.add_argument('project');render_cmd.add_argument('--renderer',choices=['notebook','motion-canvas','manim'],required=True);render_cmd.add_argument('--runtime');render_cmd.add_argument('--width',type=int,choices=[1280,1920],default=1920)
    setup_cmd=subs.add_parser('setup-renderers');setup_cmd.add_argument('--runtime',required=True)
    preview=subs.add_parser('preview',help='Render silent native preview without changing final audio, timeline or video')
    preview.add_argument('project');preview.add_argument('--renderer',choices=['manim','motion-canvas'],default='manim');preview.add_argument('--runtime');preview.add_argument('--width',type=int,choices=[1280,1920],default=1280);preview.add_argument('--fps',type=int,choices=[12,24,30],default=24)
    pronunciation=subs.add_parser('pronunciation-check',help='逐词列出课堂口播中要审听的字和读法')
    source=pronunciation.add_mutually_exclusive_group(required=True)
    source.add_argument('--text', help='直接检查一段讲稿')
    source.add_argument('--project', help='按课程的实际配音配置检查所有句子')
    feedback=subs.add_parser('feedback-check',help='Check this lesson against past viewer feedback before production')
    feedback.add_argument('project')
    inventory=subs.add_parser('term-inventory',help='Prepare all sentences and board context for semantic vocabulary review')
    inventory.add_argument('project')
    from production_workflow import register, dispatch
    register(subs)
    from final_review import register as register_final, dispatch as dispatch_final
    register_final(subs)
    args=parser.parse_args()
    if args.command in ('review-final','finalize'):
        print(json.dumps(dispatch_final(args),ensure_ascii=False,indent=2));return
    if args.command=='term-inventory':
        from term_inventory import draft as draft_inventory
        from production_workflow import effective
        project=Path(args.project).resolve()
        print(json.dumps(draft_inventory(project,effective(project)),ensure_ascii=False,indent=2));return
    if args.command in ('status','revise','repair-reel','handout-pack'):
        print(json.dumps(dispatch(args),ensure_ascii=False,indent=2))
        return
    if args.command=='pronunciation-check':
        from pronunciation import tone_targets
        if args.text is not None:
            rows = tone_targets(args.text)
            issues = []
        else:
            from feedback_bank import check as check_feedback
            report = check_feedback(args.project)
            rows = report['tone_targets']
            issues = [item for item in report['findings'] if item['severity']=='error']
        if not rows:
            print('当前词表未命中这段口播。')
        for row in rows:
            location = f"{row['page']} / {row['cue']}　" if 'cue' in row else ''
            sounds = '，'.join(f"{c['char']} {c['reading'] or '按句意定音'}" for c in row['characters'])
            print(f"{location}第{row['offset']+1}字起　{row['term']}　{sounds or row['expected'] or '按句意定音'}")
        for item in issues:
            print(item['message'], file=sys.stderr)
        if issues:
            sys.exit(1)
        return
    if args.command in ('feedback-check','review-plan','preview','render'):
        from feedback_bank import check as check_feedback
        report=check_feedback(args.project,enforce=args.command=='render')
        if args.command=='feedback-check':
            print(json.dumps(report,ensure_ascii=False))
            if report['status']=='blocked':sys.exit(1)
            return
    if args.command=='quality-check':
        from lesson_quality import run
        if args.video_file and args.stage != 'final':
            parser.error('--video-file requires --stage final')
        result=run(args.project,args.stage,video_file=args.video_file)
        print(json.dumps(result,ensure_ascii=False))
        if result['status']=='blocked' or (args.strict and result['findings']):sys.exit(1)
        return
    if args.command=='estimate-duration':
        from lesson_duration import estimate,load,report
        project=Path(args.project).resolve()
        if args.plan_only or not (project/'lesson.json').is_file():
            lesson_file=project/'lesson.json'
            source=json.loads(lesson_file.read_text()).get('duration_plan','duration-plan.json') if lesson_file.is_file() else 'duration-plan.json'
            info=estimate(load(project,source))
        else:
            lesson,pages=compile_lesson(project)
            draft=argparse.Namespace(draft=True,fps=24,backend=None,voice=None)
            timeline,_,_=prepare(project,lesson,pages,draft)
            info=report(project,lesson,timeline)
        write_json(project/'duration-estimate.json',info)
        print(json.dumps(info,ensure_ascii=False));return
    if args.command=='preview':
        from engine_render import render
        from teaching import audit as audit_teaching
        from lesson_review import fingerprint,require_unchanged
        project=Path(args.project).resolve();lesson,pages=compile_lesson(project)
        source_revision=fingerprint(project,lesson)
        if lesson.get('review_required'):
            missing=[p['id'] for p in pages if p.get('native_scenes') and args.renderer not in p['native_scenes']]
            if missing:
                raise ValueError(f'选择与原生场景相符的预览引擎，待核对页面：{", ".join(missing)}。')
        report=audit_teaching(project,lesson,pages);write_json(project/'draft-preview-teaching-report.json',report)
        args.draft=True;args.backend=None;args.voice=None
        data,pcm,_=prepare(project,lesson,pages,args)
        for page in data['pages']:page['draft_preview']=True
        write_json(project/'draft-preview-timeline.json',data)
        audio=project/'cache/preview-audio.wav'
        with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes(pcm)
        result=render(project,data,font_path(lesson,project),args.width,args.renderer,args.runtime,preview=True,audio_file=audio)
        require_unchanged(project,source_revision)
        result.update(draft=True,teaching_status=report['status'],teaching_errors=report['errors'])
        if lesson.get('review_required') and result.get('video_file'):
            result.update(review_sha256=source_revision,
                          video_sha256=hashlib.sha256(Path(result['video_file']).read_bytes()).hexdigest())
        write_json(project/'draft-preview-report.json',result);print(json.dumps(result,ensure_ascii=False));return
    if args.command=='doctor':
        from engine_render import doctor
        print(json.dumps({'python':sys.executable,'Pillow':bool(importlib.util.find_spec('PIL')),'PyMuPDF':bool(importlib.util.find_spec('fitz')),'xelatex':shutil.which('xelatex') or ('/Library/TeX/texbin/xelatex' if Path('/Library/TeX/texbin/xelatex').exists() else None),'edge_tts':bool(importlib.util.find_spec('edge_tts')),'ffmpeg':shutil.which('ffmpeg'),'ffprobe':shutil.which('ffprobe'),'animation':doctor()},ensure_ascii=False));return
    if args.command=='voice-check':
        from voice_quality import audit, export_listening_clip, export_term_reel, strict_findings
        report=audit(args.project)
        if args.term_reel:report['term_reel']=export_term_reel(Path(args.project),report['terminology']['items'])
        if args.listen:report['listening_clip']=export_listening_clip(args.project,args.listen,args.context)
        print(json.dumps(report,ensure_ascii=False))
        if args.strict and strict_findings(report):sys.exit(1)
        return
    if args.command in ('board-check','review-plan','approve-plan'):
        from board_review import check as check_board
        from layout import audit_lesson
        from lesson_review import approve,prepare_review
        from teaching import audit as audit_teaching
        project=Path(args.project).resolve()
        lesson,pages=compile_lesson(project)
        from lesson_review import fingerprint,require_unchanged
        if args.command=='review-plan':
            from handout_bundle import main_source,build as build_handout
            if main_source(project,lesson):
                build_handout(project,lesson)
        source_revision=fingerprint(project,lesson)
        if args.command=='approve-plan':
            approve(project,lesson,args.feedback)
            print(project/'review-approval.json')
            return
        draft=argparse.Namespace(draft=True,fps=24,backend=None,voice=None,video=False,
                                 renderer=None,width=1280,runtime=None)
        data,_,_=prepare(project,lesson,pages,draft)
        report=check_board(lesson,pages,data)
        write_json(project/'board-review-report.json',report)
        if args.command=='review-plan':
            from course_outline import timing_report
            from lesson_duration import report as duration_report
            from delivery import inspect_script
            folder=project/'review-preview'
            folder.mkdir(exist_ok=True)
            export_boards(folder,data,font_path(lesson,project))
            template=(ROOT/'assets/player.html').read_text()
            template=template.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
            template=template.replace('__AUDIO__','').replace('__MODELS__',(ROOT/'assets/models.js').read_text())
            (folder/'preview.html').write_text(template)
            teaching=audit_teaching(project,lesson,pages)
            write_json(project/'teaching-report.json',teaching)
            duration=duration_report(project,lesson,data)
            language=inspect_script({**lesson,'pages':pages})
            write_json(project/'delivery-report.json',language)
            if not teaching['errors']:
                write_json(folder/'course-timing-report.json',{**timing_report(project,lesson,data),'lesson_duration':duration})
            require_unchanged(project,source_revision)
            from lesson_quality import run as check_quality
            quality=check_quality(project,'plan',prepared=(lesson,pages,data))
            prepare_review(project,lesson,pages,report,audit_lesson(pages),teaching,
                           duration=duration,language=language,quality=quality)
            print(project/'教案.md')
        else:
            print(json.dumps(report,ensure_ascii=False))
            if args.strict and report['warnings']:
                sys.exit(1)
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
    if args.command=='teaching-check':
        from teaching import audit as audit_teaching
        lesson,pages=compile_lesson(args.project);report=audit_teaching(args.project,lesson,pages);write_json(Path(args.project)/'teaching-report.json',report);print(json.dumps(report,ensure_ascii=False))
        if report['errors']:sys.exit(1)
        return
    if args.command=='setup-renderers':
        from engine_render import setup
        setup(args.runtime);return
    if args.command=='render':
        from engine_render import render
        project=Path(args.project).resolve();data=json.loads((project/'timeline.json').read_text());lesson=json.loads((project/'lesson.json').read_text());font=font_path(lesson,project)
        if any(event.get('render_kind')=='tex' for page in data['pages'] for event in page['strokes']):
            raise ValueError('Rebuild this v0.10.0 timeline with course.py build PROJECT --video to generate handwritten formulas. Cached narration will be reused.')
        if lesson.get('review_required'):
            from lesson_review import require as require_review,current_review
            reviewed,_=compile_lesson(project)
            require_review(project,reviewed,args.renderer)
            if data.get('draft') or data.get('review_sha256')!=current_review(project,reviewed)['fingerprint']:
                raise ValueError('请按当前已确认教案重新构建正式时间轴。')
        if lesson.get('kind') in ('problem','concept'):
            from teaching import audit as audit_teaching
            current,pages=compile_lesson(project);report=audit_teaching(project,current,pages);write_json(project/'teaching-report.json',report)
            if report['errors']:raise ValueError('Resolve teaching-report.json errors before rendering')
            if data.get('lesson_sha256')!=digest(current):raise ValueError('Problem source changed; rebuild its measured timeline before rendering')
            from board_review import check as check_board
            board = check_board(current,pages,data)
            write_json(project/'board-review-report.json',board)
            if board['warnings'] and lesson.get('review_required'):
                raise ValueError('实际落笔和板书检查未通过，见 board-review-report.json。')
            from knowledge_board import inspect_timeline
            knowledge_report=inspect_timeline(report['knowledge_notes'],data)
            write_json(project/'knowledge-board-report.json',knowledge_report)
            if knowledge_report['errors']:raise ValueError('Resolve knowledge-board-report.json errors before rendering')
        from final_review import invalidate
        invalidate(project)
        if args.renderer=='notebook':stats=video(project,data,font,args.width)
        else:stats=render(project,data,font,args.width,args.renderer,args.runtime)
        if lesson.get('review_required'):
            from lesson_review import export_delivery
            export_delivery(project,lesson)
        if not data.get('draft') and data.get('lesson_sha256'):
            from production_workflow import checkpoint
            checkpoint(project,lesson,data,project/'video.mp4')
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
        from qwen_setup import managed_config
        p=Path(args.project).resolve();p.mkdir(parents=True,exist_ok=True)
        if (p/'lesson.json').exists():raise ValueError('lesson.json already exists; edit it or choose another project')
        example=args.example or {'problem':'pursuit','concept':'dimension-board'}.get(args.kind,'starter')
        data=json.loads((ROOT/'assets'/(example+'.json')).read_text())
        if args.title:data['title']=args.title
        data.setdefault('show_titles',False);data.setdefault('camera','static')
        data['review_required']=True
        data['term_inventory_version']=2
        backend=args.backend or ('qwen' if managed_config() else 'glm')
        local_speech=(local_config().get('speech_defaults') or {}).get(backend,{})
        data['speech']={'backend':backend,'voice':local_speech.get('voice',DEFAULTS[backend]),'speed':1.0,'audio_mastering':True,'delivery_profile':'classroom','trim_edges':True}
        if local_speech.get('model'):data['speech']['model']=local_speech['model']
        for field in ('plain_pronunciation', 'minimax_pronunciation'):
            if field in local_speech:
                data['speech'][field] = local_speech[field]
        if example=='dimension-board':
            shutil.copy2(ROOT/'assets/examples/dimension-board/讲义.md',p/'讲义.md')
        if example=='pursuit':
            page=data['pages'][0]
            page['layout']={'preset':'lesson-board','zones':{'derivation':[650,234,520,410]}}
            for cue in page['cues']:
                for action in cue['actions']:
                    if action['type']=='math':
                        action.pop('x')
                        action.pop('y')
                        action['zone']='derivation'
                        if action['id']=='combined-derivative':
                            action['emphasis']=True
            from intake import register
            register(p,[ROOT/'assets/examples/pursuit/problem.md'],[ROOT/'assets/examples/pursuit/solution.md'])
            manifest=json.loads((p/'input-manifest.json').read_text());manifest.update(statement_file=manifest['problem_sources'][0]['file'],solution_file=manifest['solution_sources'][0]['file'],recognition_reviewed=True,formula_format='latex',formulas_reviewed=True,solution_reviewed=True,diagram={'mode':'redrawn','sources':[]},reference_notes='Bundled worked example; reviewed with the distributed derivation and numerical model')
            write_json(p/'input-manifest.json',manifest)
            worked=p/'讲义.md'
            stem=ROOT/'assets/examples/pursuit'
            worked.write_text((stem/'problem.md').read_text()+
                              '\n\n![图 1 追及情景与所用物理量](review-preview/pages/p01.png)\n\n'+
                              (stem/'solution.md').read_text()+
                              '\n[图 1 的可编辑 TikZ](review-preview/tikz/p01.tikz)\n')
        if example in ('pursuit','dimension-board'):
            template_dir=ROOT/'assets/examples'/example
            links=json.loads((template_dir/'step-links.json').read_text())
            for page in data['pages']:
                for step in page.get('derivation_steps',[]):
                    step.update(links[step['id']])
            for name in ('学生讲义.tex','model.tikz'):
                shutil.copy2(template_dir/name,p/name)
            data.update(workflow_version=1, handout_source='学生讲义.tex', handout='学生讲义.tex')
        data,plan=externalize(data)
        write_json(p/'lesson.json',data)
        write_json(p/'speech-plan.json',plan)
        from feedback_bank import preparation
        preparation(p,data)
        print(p/'lesson.json');return
    if args.command=='check':
        from layout import audit_lesson
        from components import audit_components
        l,p=compile_lesson(args.project);report=audit_lesson(p);component_report=audit_components(p);print(json.dumps({'title':l['title'],'pages':len(p),'cues':sum(len(x['cues']) for x in p),'geometry':'finite and within writing area','layout':report['status'],'layout_warnings':len(report['warnings']),'components':sum(component_report['counts'].values()),'component_quality':component_report['status'],'component_warnings':len(component_report['warnings'])}));return
    if args.draft and args.video:raise ValueError('Use --draft for layout, or --video for measured speech and final export')
    run_build(args.project,args)
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,ImportError,RuntimeError,OSError) as e:print(f'ERROR: {e}',file=sys.stderr);sys.exit(1)
