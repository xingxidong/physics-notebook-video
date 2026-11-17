"""Local checks with concrete repair tasks, preserving unknowns that need viewing/listening."""
import argparse
import json
import subprocess
import wave
from pathlib import Path


def run(project,stage='plan',prepared=None):
    from course import compile_lesson,digest,prepare,write_json
    from teaching import audit
    from layout import audit_lesson
    from board_review import check
    from delivery import inspect_script
    from lesson_duration import report as duration_report
    from lesson_review import fingerprint,require_unchanged,handout,native_preview
    project=Path(project).resolve()
    findings=[]
    coverage={}
    manual=[]

    def add(area,rows,severity='review'):
        for row in rows:
            findings.append({'area':area,'severity':severity,**row})

    try:
        if prepared is None:
            lesson,pages=compile_lesson(project)
        else:
            lesson,pages,_=prepared
        revision=fingerprint(project,lesson)
        teaching=audit(project,lesson,pages)
        add('teaching',teaching['errors'],'error')
        add('teaching',teaching.get('warnings',[]))
        coverage['teaching']='structural-check'
        layout=audit_lesson(pages)
        add('layout',layout['warnings'])
        delivery=inspect_script({**lesson,'pages':pages})
        add('script',delivery['warnings'])
        coverage['script']='heuristic-check'
        if not lesson.get('duration_plan'):
            add('duration',[{'code':'duration-unplanned','message':'补充 duration_plan，写出学生基础、各段预算和讲法依据。'}])
        if lesson.get('kind')=='problem':
            notes=lesson.get('review_notes',{})
            for field in ('focus','difficulty','outcome'):
                if not isinstance(notes,dict) or not isinstance(notes.get(field),str) or not notes[field].strip():
                    add('teaching',[{'code':'lesson-focus','message':f'在 review_notes.{field} 写出重点、难点讲法或可观察的学习结果。'}])
            focus=notes.get('focus_actions',[]) if isinstance(notes,dict) else []
            if not isinstance(focus,list) or not focus:
                add('teaching',[{'code':'focus-not-linked','message':'在 review_notes.focus_actions 关联本题关键步骤的 page、cue、action_id，并在板书上突出这一行。'}])
            else:
                lookup={(p['id'],c['id'],a.get('id')):a for p in pages for c in p['cues']
                        for a in c.get('resolved_actions',[])}
                for entry in focus:
                    if not isinstance(entry,dict) or any(not isinstance(entry.get(k),str) for k in ('page','cue','action_id')):
                        add('teaching',[{'code':'focus-format','message':'focus_actions 每项须写 page、cue、action_id。'}],'error')
                        continue
                    action=lookup.get((entry['page'],entry['cue'],entry['action_id']))
                    if not action or action.get('type') not in ('text','math'):
                        add('teaching',[{**entry,'code':'focus-action','message':'重点须指向实际落笔的文字或公式。'}],'error')
                    elif not action.get('emphasis') and action.get('color','ink') in ('ink','#29333c'):
                        add('teaching',[{**entry,'code':'focus-emphasis','message':'给这一条关键关系加下划线或强调色，并在对应句解释它的作用。'}])
        if stage=='plan':
            if prepared is None:
                timeline,_,_=prepare(project,lesson,pages,argparse.Namespace(draft=True,fps=24,backend=None,voice=None))
            else:
                timeline=prepared[2]
        else:
            timeline=json.loads((project/'timeline.json').read_text())
            if timeline.get('draft') or timeline.get('lesson_sha256')!=digest(lesson):
                raise ValueError('正式时间轴与当前课程源不一致，请先按当前教案构建配音与时间轴。')
            if lesson.get('review_required') and timeline.get('review_sha256')!=revision:
                raise ValueError('正式时间轴所依据的图文素材已变，请重新生成对应内容。')
        board=check(lesson,pages,timeline)
        add('board',board['warnings'])
        coverage['board']=board.get('coverage',[])
        duration=duration_report(project,lesson,timeline)
        add('duration',[{'code':'duration-budget','message':m} for m in duration['issues']])
        coverage['duration']=duration['timeline_status']
        # Export current, consolidated diagnostics without changing the lesson/approval.
        write_json(project/'delivery-report.json',delivery)
        write_json(project/'board-review-report.json',board)
        write_json(project/'duration-estimate.json',duration)
        try:
            handout(project,lesson)
            coverage['handout']='file-present'
        except ValueError as exc:
            add('handout',[{'code':'handout-missing','message':str(exc)}],'error')
        if stage=='plan' and native_preview(project,lesson)=='':
            add('animation',[{'code':'preview-missing','message':'当前原生动画尚无对应预览，生成后查看接触、轨迹、方向和标注。'}])
        if stage=='final':
            from voice_quality import audit as voice_audit,strict_findings
            sound=voice_audit(project,timeline)
            add('voice',strict_findings(sound))
            coverage['voice']='signal-and-text-check'
            coverage['listening_cues']=len(sound['listening_checks'])
            if abs(sound['duration']-timeline['duration'])>.15:
                add('voice',[{'code':'audio-duration','message':'配音文件长度与时间轴不一致，重建音画同步。'}],'error')
            video=project/'video.mp4'
            if not video.is_file():
                add('video',[{'code':'video-missing','message':'成片 video.mp4 尚未生成。'}],'error')
            else:
                data=json.loads(subprocess.check_output(
                    ['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type','-of','json',str(video)],text=True))
                if {'audio','video'}-set(s.get('codec_type') for s in data.get('streams',[])):
                    add('video',[{'code':'video-stream','message':'成片须同时有音轨和视频轨。'}],'error')
                if abs(float(data['format']['duration'])-timeline['duration'])>1:
                    add('video',[{'code':'video-duration','message':'成片长度与当前配音时间轴不一致。'}],'error')
                coverage['video']='stream-and-duration-check'
            manual.append('按 voice-report.json 的 listening_checks 连听上下文，确认多音字、吞字、拖字、重音和段落衔接。')
        manual.extend(['观看开场、重难点和结论，确认提问已经上屏、所指物理量可见、结论能用于记笔记。',
                       '按原题、题图与参考解独立推导；核对学生讲义图文相接、公式和视频一致。'])
        if any(p.get('native_scenes') or p.get('demonstration') for p in pages):
            manual.append('查看动画开始、接触前后、极值与结束；抽样检测之外的状态仍需观看。')
        require_unchanged(project,revision)
        status='blocked' if any(f['severity']=='error' for f in findings) else 'needs_revision' if findings else 'ready_for_review'
        result={'status':status,'stage':stage,'source_sha256':revision,
                'coverage':coverage,'findings':findings,'manual_review':{'status':'pending','tasks':manual}}
    except (ValueError,OSError,KeyError,subprocess.SubprocessError,wave.Error) as exc:
        result={'status':'blocked','stage':stage,'coverage':coverage,
                'findings':[*findings,{'area':'source','severity':'error','code':'check-incomplete','message':str(exc)}],
                'manual_review':{'status':'pending','tasks':manual}}
    write_json(project/'quality-report.json',result)
    lines=['# 本课制作检查','',f'阶段：{stage}；状态：{result["status"]}。','']
    if result['findings']:
        for item in result['findings']:
            where=' / '.join(str(item[k]) for k in ('page','cue') if item.get(k))
            lines.append(f'- {item["area"]}'+(f' · {where}' if where else '')+'：'+item['message'])
    else:
        lines.append('已运行的自动检查未发现问题。')
    lines.extend(['','## 观看与试听',''])
    lines.extend('- '+task for task in result['manual_review']['tasks'])
    lines.extend(['','自动检查的范围记录在 quality-report.json。观看和试听结果由实际审阅填写到制作记录。',''])
    (project/'制作检查.md').write_text('\n'.join(lines))
    return result
