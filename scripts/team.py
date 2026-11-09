#!/usr/bin/env python3
"""Create, validate, and merge section work packages for long physics courses."""
import argparse,json,re,shlex,subprocess,sys
from pathlib import Path

ID_RE=re.compile(r'^[a-z0-9][a-z0-9-]{0,31}$')
DEFAULT_SPEECH={'backend':'minimax','voice':'Chinese (Mandarin)_Gentleman','model':'speech-2.8-hd','speed':1.0}

def read_json(path):
    try:return json.loads(Path(path).read_text())
    except FileNotFoundError:raise ValueError(f'Missing file: {path}') from None
    except json.JSONDecodeError as e:raise ValueError(f'Invalid JSON in {path}: line {e.lineno}, column {e.colno}') from None

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def clean_text(value):return ''.join(str(value).split())

def validate_plan(plan):
    course=plan.get('course') or {};sections=plan.get('sections') or []
    if not clean_text(course.get('title','')):raise ValueError('plan.course.title is required')
    if float(course.get('target_minutes',0))<=0:raise ValueError('plan.course.target_minutes must be positive')
    minimum=float(course.get('minimum_minutes',course['target_minutes']))
    if minimum<=0 or minimum>float(course['target_minutes']):raise ValueError('minimum_minutes must be positive and no larger than target_minutes')
    if not sections:raise ValueError('plan.sections needs at least one section')
    if not isinstance(plan.get('symbols',{}),dict):raise ValueError('plan.symbols must be an object')
    if not isinstance(plan.get('page_policy',{}),dict):raise ValueError('plan.page_policy must be an object')
    ids=set();total=0
    for index,section in enumerate(sections,1):
        sid=section.get('id','')
        if not ID_RE.fullmatch(sid):raise ValueError(f'section {index}: id uses lowercase letters, digits, and hyphens')
        if sid in ids:raise ValueError(f'Duplicate section id: {sid}')
        ids.add(sid)
        if not clean_text(section.get('title','')):raise ValueError(f'{sid}: title is required')
        target=float(section.get('target_minutes',0))
        if target<=0:raise ValueError(f'{sid}: target_minutes must be positive')
        total+=target
        if not isinstance(section.get('source_files',[]),list):raise ValueError(f'{sid}: source_files must be a list')
    if abs(total-float(course['target_minutes']))>.11:
        raise ValueError(f'Section targets total {total:g} minutes, course target is {float(course["target_minutes"]):g}')
    return course,sections

def paths(project):
    project=Path(project).resolve();team=project/'team'
    return project,team,team/'course-contract.json',team/'manifest.json'

def init(project,plan_file):
    project,team,contract_path,manifest_path=paths(project)
    if team.exists():raise ValueError(f'{team} already exists; keep the current work packages or choose a new project')
    plan=read_json(plan_file);course,sections=validate_plan(plan)
    from engine_render import local_config
    local_speech=(local_config().get('speech_defaults') or {}).get('minimax',{})
    speech=course.get('speech') or {**DEFAULT_SPEECH,**local_speech}
    lesson={
        'title':course['title'],'show_titles':bool(course.get('show_titles',False)),
        'renderer':course.get('renderer','motion-canvas'),
        'camera':course.get('camera','static'),
        'speech':speech,
    }
    for key in ('font','parameters'):
        if key in course:lesson[key]=course[key]
    contract={
        'schema_version':1,'course':course,'lesson':lesson,
        'audience':plan.get('audience',''),'teaching_goal':plan.get('teaching_goal',''),
        'symbols':plan.get('symbols',{}),
        'page_policy':plan.get('page_policy',{'prefer_complete_unit_per_page':True,'show_titles':False,'layout_preset':'one-page-problem'}),
        'voice_policy':plan.get('voice_policy',{}),
        'deliverables':plan.get('deliverables',['video','subtitles','lesson-source','tikz','boards-pdf']),
    }
    manifest={'schema_version':1,'sections':[]}
    team.mkdir(parents=True)
    write_json(contract_path,contract)
    skill_root=Path(__file__).resolve().parents[1]
    for index,section in enumerate(sections,1):
        sid=section['id'];folder=team/'sections'/sid;prefix=f's{index:02d}-'
        source_inputs=section.get('source_files',[])
        source_files=[value if '://' in str(value) else str((project/value).resolve()) for value in source_inputs]
        assignment={
            'schema_version':1,'section_id':sid,'order':index,'page_prefix':prefix,
            'title':section['title'],'target_minutes':section['target_minutes'],
            'brief':section.get('brief',''),'project_root':str(project),'skill_root':str(skill_root),
            'source_files_input':source_inputs,'source_files':source_files,
            'bridge_in':section.get('bridge_in',''),'bridge_out':section.get('bridge_out',''),
            'symbols':contract['symbols'],'page_policy':contract['page_policy'],
            'audience':contract['audience'],'teaching_goal':contract['teaching_goal'],
        }
        manifest['sections'].append({'id':sid,'order':index,'title':section['title'],'target_minutes':section['target_minutes'],'page_prefix':prefix,'folder':f'team/sections/{sid}','bridge_in':section.get('bridge_in',''),'bridge_out':section.get('bridge_out','')})
        write_json(folder/'assignment.json',assignment)
        validate_cmd=' '.join(shlex.quote(x) for x in [sys.executable,str(Path(__file__).resolve()),'validate',str(project)])
        prompt=f"""你负责课程的章节 `{sid}`：{section['title']}。\n\n读取本目录的 assignment.json 和其中列出的绝对路径原始资料，只在本目录写 fragment.json、讲义片段与 TikZ。你与其他 Agent 同时工作，不要修改、移动或撤销其他目录中的文件。保持共同符号表；需要新符号时记录在 handoff.md，交给主 Agent 更新课程合同。每个板书页尽量完成一个完整问题或概念单元，设置 problem_id，并按 page_policy 采用一页一题语义布局；确需跨页时写明 continuation_reason。主图在本页保持原位，优先复用 references/components.md 中与题型匹配的参数化物理组件，推导使用 formula_steps。默认固定画面，公式逐行出现；力、位移等物理方向保留箭头。受力线和标签用 attach_to 跟随组件的 block_center，结果用 write_seconds 提前写完并留观看时间。每页同时完成物理推导、自然口播、板书动作与配图。不要调用正式 TTS，不要写项目根目录的 lesson.json。\n\n完成后可直接运行：\n\n```sh\n{validate_cmd}\n```\n\n主 Agent 负责最终合并。\n"""
        (folder/'AGENT_PROMPT.md').write_text(prompt)
    write_json(manifest_path,manifest)
    print(json.dumps({'project':str(project),'sections':len(sections),'target_minutes':course['target_minutes'],'team_dir':str(team)},ensure_ascii=False))

def load_team(project):
    project,team,contract_path,manifest_path=paths(project)
    return project,team,read_json(contract_path),read_json(manifest_path)

def inspect_team(project,deep=False):
    project,team,contract,manifest=load_team(project);errors=[];warnings=[];details=[];seen=set();all_pages=[];all_cues=[];seconds=0
    symbols=contract.get('symbols',{});policy=contract.get('page_policy',{})
    for item in sorted(manifest.get('sections',[]),key=lambda x:x['order']):
        sid=item['id'];fragment_path=team/'sections'/sid/'fragment.json'
        detail={'id':sid,'fragment':str(fragment_path),'status':'missing','pages':0,'cues':0,'estimated_minutes':0,'bridge_in':{'contract':item.get('bridge_in',''),'fragment':''},'bridge_out':{'contract':item.get('bridge_out',''),'fragment':''}}
        if not fragment_path.exists():
            errors.append(f'{sid}: missing fragment.json');details.append(detail);continue
        try:fragment=read_json(fragment_path)
        except ValueError as e:errors.append(str(e));detail['status']='invalid';details.append(detail);continue
        detail['status']='ready'
        if fragment.get('section_id')!=sid:errors.append(f'{sid}: fragment.section_id must match its assignment')
        for key in ('bridge_in','bridge_out'):
            detail[key]['fragment']=fragment.get(key,'')
            if clean_text(item.get(key,'')) and not clean_text(fragment.get(key,'')):errors.append(f'{sid}: {key} is required by the assignment')
        used=fragment.get('symbols_used',[])
        if not isinstance(used,list):errors.append(f'{sid}: symbols_used must be a list');used=[]
        for symbol in used:
            if symbol not in symbols:errors.append(f'{sid}: symbol {symbol!r} is absent from the course contract')
        pages=fragment.get('pages') or []
        if not pages:errors.append(f'{sid}: pages must not be empty')
        for page in pages:
            pid=page.get('id','')
            if not pid.startswith(item['page_prefix']):errors.append(f'{sid}: page id {pid!r} must start with {item["page_prefix"]!r}')
            if pid in seen:errors.append(f'Duplicate id: {pid}')
            seen.add(pid);all_pages.append(page)
            if not clean_text(page.get('board_unit','')):errors.append(f'{pid}: board_unit is required')
            if policy.get('prefer_complete_unit_per_page',True) and page.get('complete_on_page') is not True and not clean_text(page.get('continuation_reason','')):
                errors.append(f'{pid}: finish the unit on this page or explain continuation_reason')
            cues=page.get('cues') or []
            if not cues:errors.append(f'{pid}: cues must not be empty')
            if not any(c.get('actions') for c in cues):errors.append(f'{pid}: at least one cue must draw on the board')
            for cue in cues:
                cid=cue.get('id','')
                if not cid.startswith(pid+'-'):errors.append(f'{pid}: cue id {cid!r} must start with {pid+"-"!r}')
                if cid in seen:errors.append(f'Duplicate id: {cid}')
                seen.add(cid);all_cues.append(cue)
                tts=cue.get('tts',cue.get('text',''))
                if not clean_text(tts):errors.append(f'{cid}: speakable tts is required')
                pause=float(cue.get('pause',.8))
                if pause<0:errors.append(f'{cid}: pause must be nonnegative');pause=0
                seconds+=max(1.2,len(clean_text(tts))/4.2)+pause
        detail.update(pages=len(pages),cues=sum(len(p.get('cues',[])) for p in pages))
        section_seconds=sum(max(1.2,len(clean_text(c.get('tts',c.get('text',''))))/4.2)+max(0,float(c.get('pause',.8))) for p in pages for c in p.get('cues',[]))
        detail['estimated_minutes']=round(section_seconds/60,2)
        target=float(item['target_minutes'])
        if section_seconds/60<target*.72:warnings.append(f'{sid}: estimated {section_seconds/60:.1f} min is far below target {target:g} min')
        details.append(detail)
    course_check={'ok':None,'message':'not run'}
    if deep and all_pages and not errors:
        try:
            from course import compile_lesson
            from layout import audit_lesson
            from components import audit_components
            validation_lesson=dict(contract['lesson']);validation_lesson['pages']=all_pages
            _,compiled=compile_lesson(project,validation_lesson);layout_report=audit_lesson(compiled);component_report=audit_components(compiled)
            warnings.extend('layout: '+x['message'] for x in layout_report['warnings'])
            warnings.extend('component: '+x['message'] for x in component_report['warnings'])
            course_check={'ok':True,'message':'actions, glyphs, parameters, anchors, geometry, semantic layout, and physics components are valid','layout':layout_report['status'],'components':component_report['status']}
        except (ValueError,KeyError,TypeError,ImportError,OSError) as e:
            errors.append(f'Course action check: {e}');course_check={'ok':False,'message':str(e)}
    target=float(contract['course']['target_minutes']);minimum=float(contract['course'].get('minimum_minutes',target));estimated=seconds/60
    if estimated<minimum*.72:warnings.append(f'Course estimate {estimated:.1f} min is far below minimum {minimum:g} min')
    report={'ok':not errors,'errors':errors,'warnings':warnings,'duration_ready':estimated>=minimum*.85,'course_check':course_check,'sections':details,'pages':len(all_pages),'cues':len(all_cues),'estimated_minutes':round(estimated,2),'target_minutes':target,'minimum_minutes':minimum}
    return project,team,contract,manifest,all_pages,report

def validate(project,strict_duration=False):
    *_,report=inspect_team(project,deep=True)
    if strict_duration and not report['duration_ready']:
        report['ok']=False;report['errors'].append(f'Estimated duration must reach at least 85% of the {report["minimum_minutes"]:g}-minute minimum before formal synthesis')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['ok']:sys.exit(1)

def status(project,fail_on_error=False):
    try:*_,report=inspect_team(project)
    except ValueError as e:print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False));sys.exit(1)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if fail_on_error and not report['ok']:sys.exit(1)

def merge(project,output):
    project,team,contract,manifest,pages,report=inspect_team(project,deep=True)
    if not report['ok']:
        print(json.dumps(report,ensure_ascii=False,indent=2));raise ValueError('Fix team validation errors before merging')
    target=(project/output).resolve()
    if target.exists():
        old=read_json(target)
        if (old.get('team') or {}).get('generated_by')!='physics-notebook-video/team.py':
            raise ValueError(f'{target} exists and was not generated by team.py; choose --output or move it yourself')
    lesson=dict(contract['lesson']);lesson['symbols']=contract.get('symbols',{});lesson['page_policy']=contract.get('page_policy',{})
    lesson['team']={'generated_by':'physics-notebook-video/team.py','contract':'team/course-contract.json','manifest':'team/manifest.json','sections':[x['id'] for x in sorted(manifest['sections'],key=lambda x:x['order'])],'target_minutes':report['target_minutes'],'minimum_minutes':report['minimum_minutes']}
    lesson['pages']=pages;write_json(target,lesson);write_json(team/'merge-report.json',report)
    print(json.dumps({'lesson':str(target),'sections':len(manifest['sections']),'pages':len(pages),'estimated_minutes':report['estimated_minutes'],'warnings':report['warnings']},ensure_ascii=False))

def build_final(project,args):
    project,team,contract,manifest,pages,report=inspect_team(project,deep=True)
    if not report['ok']:raise ValueError('Fix team validation errors before formal synthesis')
    if not report['duration_ready']:
        raise ValueError(f'Estimated duration must reach at least 85% of the {report["minimum_minutes"]:g}-minute minimum before formal synthesis')
    merge(project,args.output)
    command=[sys.executable,str(Path(__file__).with_name('course.py')),'build',str(project),'--video','--fps',str(args.fps),'--width',str(args.width)]
    for flag in ('backend','voice','renderer','runtime'):
        value=getattr(args,flag)
        if value:command.extend(['--'+flag,value])
    subprocess.run(command,check=True)

def verify_video(project,video):
    project,team,contract,manifest=load_team(project);video=Path(video).resolve()
    if not video.exists():raise ValueError(f'Missing video: {video}')
    raw=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(video)],text=True).strip()
    seconds=float(raw);minimum=float(contract['course'].get('minimum_minutes',contract['course']['target_minutes']))*60
    report={'ok':seconds>=minimum,'video':str(video),'duration_seconds':round(seconds,3),'duration_minutes':round(seconds/60,2),'minimum_minutes':minimum/60}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['ok']:sys.exit(1)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('init');p.add_argument('project');p.add_argument('--plan',required=True)
    p=sub.add_parser('status');p.add_argument('project');p.add_argument('--fail-on-error',action='store_true')
    p=sub.add_parser('validate');p.add_argument('project');p.add_argument('--strict-duration',action='store_true')
    p=sub.add_parser('merge');p.add_argument('project');p.add_argument('--output',default='lesson.json')
    p=sub.add_parser('verify-video');p.add_argument('project');p.add_argument('--video',required=True)
    p=sub.add_parser('build-final');p.add_argument('project');p.add_argument('--output',default='lesson.json');p.add_argument('--backend',choices=['glm','doubao','minimax','edge','user']);p.add_argument('--voice');p.add_argument('--renderer',choices=['notebook','motion-canvas','manim']);p.add_argument('--runtime');p.add_argument('--fps',type=int,choices=[12,24,30],default=24);p.add_argument('--width',type=int,choices=[1280,1920],default=1920)
    args=parser.parse_args()
    if args.command=='init':init(args.project,args.plan)
    elif args.command=='status':status(args.project,args.fail_on_error)
    elif args.command=='validate':validate(args.project,args.strict_duration)
    elif args.command=='merge':merge(args.project,args.output)
    elif args.command=='verify-video':verify_video(args.project,args.video)
    else:build_final(args.project,args)

if __name__=='__main__':
    try:main()
    except (ValueError,TypeError,KeyError,OSError) as e:print(f'ERROR: {e}',file=sys.stderr);sys.exit(1)
