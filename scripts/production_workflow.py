"""Resume from current evidence, scope revisions and audition changed sentences in the shipped media."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import tempfile

from course import digest
from handout_bundle import digest as file_hash
from lesson_review import fingerprint
from step_review import steps


def read(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def save(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent,mode='w',encoding='utf-8',delete=False) as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False)
    os.replace(stream.name,path)


def effective(project):
    from speech_plan import apply
    from term_inventory import apply as terms
    lesson,meta=apply(project,read(project/'lesson.json'))
    lesson['_speech_plan_meta']=meta
    return terms(project,lesson)


def cue_rows(lesson):
    return [(p.get('id',f'p{i:02d}'),{'id':p.get('id',f'p{i:02d}')+f'-c{j:02d}',**c})
            for i,p in enumerate(lesson['pages'],1) for j,c in enumerate(p['cues'],1)]


def signature(lesson,project=None):
    from lesson_review import dependency_hashes
    return {'cues':{p+'/'+c['id']:digest(c) for p,c in cue_rows(lesson)},
            'conventions':deepcopy(lesson.get('conventions',{})), 'voice':digest(lesson.get('speech',{})),
            'steps':{pid+'/'+s['id']:digest(s) for pid,s in steps(lesson)},
            'globals':digest({k:v for k,v in lesson.items() if k not in
                             ('pages','speech','conventions','_speech_plan_meta','_term_inventory')}),
            'page_settings':{p.get('id',f'p{i:02d}'):digest({k:v for k,v in p.items() if k not in ('cues','derivation_steps')})
                             for i,p in enumerate(lesson['pages'],1)},
            'dependencies':dependency_hashes(project,lesson) if project is not None else {}}


def windows(timeline):
    return {p['id']+'/'+c['id']:(p['start']+c['start'],p['start']+c['end'])
            for p in timeline.get('pages',[]) for c in p['cues']}


def checkpoint(project, lesson, timeline, media):
    current=effective(project)
    if timeline.get('draft') or timeline.get('lesson_sha256')!=digest(current):
        raise ValueError('成片与课程源的时间轴不一致。')
    evidence={**signature(current,project),'source':fingerprint(project,current),
              'timeline':file_hash(project/'timeline.json'), 'windows':windows(timeline),
              'media':file_hash(media), 'file':media.name}
    save(project/'production-baseline.json',evidence)


def status(project):
    from lesson_review import current_review,require
    lesson=effective(project)
    source=fingerprint(project,lesson)
    out={'kind':lesson.get('kind'),'source':source,'next':'review-plan','stage':'prepare'}
    if lesson.get('review_required'):
        try:
            current_review(project,lesson)
        except ValueError as exc:
            return {**out,'reason':str(exc)}
        try:
            require(project,lesson)
        except ValueError as exc:
            return {**out,'stage':'awaiting-review','next':'approve-plan','reason':str(exc)}
    base=read(project/'production-baseline.json')
    timeline=project/'timeline.json'
    timed=read(timeline)
    measured=(not timed.get('draft') and timed.get('lesson_sha256')==digest(lesson)
              and (not lesson.get('review_required') or timed.get('review_sha256')==source))
    if not measured:
        return {**out,'stage':'approved' if lesson.get('review_required') else 'legacy-source','next':'build --video'}
    video=project/base.get('file','video.mp4')
    if not (video.is_file() and base.get('source')==source and base.get('timeline')==file_hash(timeline)
            and base.get('media')==file_hash(video)):
        return {**out,'stage':'timed','next':'render','reason':'成片与当前时间轴尚缺相符的导出记录。'}
    qa=read(project/'quality-report.json')
    checked=Path(qa.get('coverage',{}).get('media',{}).get('file','video.mp4'))
    if not checked.is_absolute():checked=project/checked
    if (qa.get('stage')!='final' or qa.get('source_sha256')!=source
            or not checked.is_file() or qa.get('media_sha256')!=file_hash(checked)):
        return {**out,'stage':'rendered','next':'quality-check --stage final'}
    from handout_bundle import main_source,verified
    if main_source(project,lesson) and not verified(project,lesson):
        return {**out,'stage':'handout-stale','next':'handout-pack'}
    from final_review import require as require_final
    delivery=read(project/'delivery-files.json')
    if delivery.get('status')=='reviewed':
        try:
            require_final(project,lesson,checked)
            return {**out,'stage':'delivered','next':None,'baseline':base['media']}
        except ValueError:
            pass
    finalize='finalize' if checked==project/'video.mp4' else 'finalize --video-file '+str(checked)
    return {**out,'stage':qa['status'],'next':finalize if qa['status']=='reviewed' else 'revise' if any(f['severity']=='error' for f in qa['findings']) else 'review-final',
            'manual_review':qa.get('manual_review',{}),'baseline':base['media']}


def scope(lesson, baseline, cues=(), conventions=(),project=None):
    current=signature(lesson,project)
    all_cues=current['cues']
    order=list(all_cues)
    selected=set()
    signs=set(conventions)
    reasons=[]
    full=False
    for name in cues:
        matches=[key for key in order if key==name or key.split('/',1)[1]==name]
        if len(matches)!=1:
            raise ValueError('句子编号缺失或不唯一：'+name)
        selected.update(matches)
    if baseline:
        selected.update(key for key,value in all_cues.items() if baseline['cues'].get(key)!=value)
        if baseline.get('voice')!=digest(lesson.get('speech',{})):
            selected.update(order)
        before=baseline.get('conventions',{})
        signs.update(k for k in before.keys()|lesson.get('conventions',{}).keys()
                     if before.get(k)!=lesson.get('conventions',{}).get(k))
        if baseline.get('globals')!=current['globals']:
            full=True;reasons.append('课程参数或整体设置改变；旧基线缺少此项时重新检查。')
        if project is not None and baseline.get('dependencies')!=current['dependencies']:
            full=True;reasons.append('图源、讲义、外部录音或其他依赖文件改变。')
        changed_pages={p for p in current['page_settings'] if current['page_settings'][p]!=baseline.get('page_settings',{}).get(p)}
        selected.update(k for k in order if k.split('/',1)[0] in changed_pages)
        # Deleting a sentence creates a new join even when the remaining text is unchanged.
        previous_order=list(baseline['cues'])
        for i,key in enumerate(previous_order):
            if key not in all_cues:
                for candidates in (reversed(previous_order[:i]), iter(previous_order[i+1:])):
                    neighbor=next((k for k in candidates if k in all_cues),None)
                    if neighbor: selected.add(neighbor)
    elif not (selected or signs):
        raise ValueError('旧课没有导出基线，请指定 --cue 或 --convention。')
    if set(conventions)-lesson.get('conventions',{}).keys():
        raise ValueError('指定的物理约定不存在。')
    links={pid+'/'+s['id']:(pid,s) for pid,s in steps(lesson)}
    if full:selected.update(order)
    affected={key for key,(p,s) in links.items() if signs.intersection(s.get('uses_conventions',[]))
              or p+'/'+s['cue_id'] in selected}
    if 'steps' in baseline:
        affected.update(key for key,(_,s) in links.items() if baseline['steps'].get(key)!=digest(s))
    while True:
        children={key for key,(p,s) in links.items() if any((d if '/' in d else p+'/'+d) in affected
                  for d in s.get('depends_on',[])+s.get('upstream_steps',[]))}
        if children<=affected:
            break
        affected|=children
    annotated={k for _,s in links.values() for k in s.get('uses_conventions',[])}
    full=full or bool(signs-annotated)
    if full:
        selected.update(order)
        affected.update(links)
    selected.update(p+'/'+s['cue_id'] for k,(p,s) in links.items() if k in affected)
    changed=[key for key in order if key in selected]
    return {'changed':changed,'conventions':sorted(signs),'physics_steps':sorted(affected),
            'reasons':reasons,
            'review_entire_course':full,'removed_cues':sorted(set(baseline.get('cues',{}))-set(order)),
            'adjacent_seams':[[a,b] for a,b in zip(order,order[1:]) if a in selected or b in selected],
            'board_and_handout':[{'step':k,'diagrams':s.get('requires_visible',[]),
            'action':s['action_id'],'label':s.get('handout_label')} for k,(p,s) in links.items()
            if k in affected or p+'/'+s['cue_id'] in selected]}


def audition(project):
    revision=read(project/'revision-plan.json')
    base=read(project/'production-baseline.json')
    if not revision.get('changed') or not base:
        raise ValueError('先登记改动的句子，并导出含这些修订的正式成片。')
    current=fingerprint(project,effective(project))
    if revision.get('target')!=current or base.get('source')!=current:
        raise ValueError('改动清单或成片与当前课程版本不同。')
    media=project/'video.mp4'
    if revision.get('previous_media')==base.get('media'):
        raise ValueError('本次修订尚无新的成片，当前文件仍是登记改动时的版本。')
    if base.get('media')!=file_hash(media) or base['timeline']!=file_hash(project/'timeline.json'):
        raise ValueError('时间轴或成片已经更换，请从同一次正式导出取样。')
    times=base['windows']
    order=list(times)
    intervals=[]
    for key in sorted(revision['changed'], key=order.index):
        i=order.index(key)
        start,end=times[key]
        if i:
            start=max(times[order[i-1]][0],times[order[i-1]][1]-.5)
        if i+1<len(order):
            end=min(times[order[i+1]][1],times[order[i+1]][0]+.5)
        if intervals and start<=intervals[-1][1]:
            intervals[-1][1]=max(end,intervals[-1][1]);intervals[-1][2].append(key)
        else:
            intervals.append([start,end,[key]])
    out=project/'revision-review'
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as temp:
        temp=Path(temp)
        for i,(start,end,_) in enumerate(intervals):
            subprocess.run(['ffmpeg','-v','error','-ss',str(start),'-i',str(media),'-t',str(end-start),
                            '-vn','-ac','1','-ar','24000',str(temp/f'{i}.wav')],check=True)
        (temp/'list').write_text(''.join(f"file '{i}.wav'\n" for i in range(len(intervals))))
        subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','1','-i','list','-c','copy','changes.wav'],cwd=temp,check=True)
        os.replace(temp/'changes.wav',out/'改动处试听.wav')
    old=revision.get('previous_windows',{})
    result={'media_sha256':base['media'],'source':current,'windows_in_final':intervals,
            'shifted_cues':[k for k in order if k in old and abs(times[k][0]-old[k][0])>.001],
            'file':'revision-review/改动处试听.wav'}
    save(out/'index.json',result)
    return result


def register(subs):
    for name in ('status','revise','repair-reel','handout-pack'):
        parser=subs.add_parser(name)
        parser.add_argument('project')
        if name=='revise':
            parser.add_argument('--cue',action='append',default=[])
            parser.add_argument('--convention',action='append',default=[])


def dispatch(args):
    project=Path(args.project).resolve()
    if args.command=='status':
        return status(project)
    if args.command=='repair-reel':
        return audition(project)
    lesson=effective(project)
    if args.command=='handout-pack':
        from handout_bundle import build
        return build(project,lesson)
    baseline=read(project/'production-baseline.json')
    result=scope(lesson,baseline,args.cue,args.convention,project)
    result.update(target=fingerprint(project,lesson),previous_media=baseline.get('media'),previous_windows=baseline.get('windows',{}))
    save(project/'revision-plan.json',result)
    return result
