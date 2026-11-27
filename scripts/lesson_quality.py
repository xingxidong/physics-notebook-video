"""Local checks with concrete repair tasks, preserving unknowns that need viewing/listening."""
import argparse
import json
import re
import subprocess
import wave
from pathlib import Path


def handout_language(project, lesson):
    """Locate classroom prose edits in editable student handouts."""
    from classroom_language import ANNOUNCEMENTS, prose_findings
    from handout_bundle import source_files
    from lesson_review import local_file

    findings = []
    sources = {
        source for source in lesson.get('review_assets', [])
        if isinstance(source, str) and Path(source).suffix == '.tex'
    }
    default_source = project / '讲义.tex'
    if default_source.is_file():
        sources.add(default_source.name)
    sources.update(str(p.relative_to(project)) for p in source_files(project,lesson) if p.suffix=='.tex')
    handout = Path(lesson.get('handout', '讲义.md'))
    if handout.suffix.lower() in ('.md', '.markdown'):
        sources.add(str(handout))
    checked = False
    for source in sorted(sources):
        path = local_file(project, source, required=False)
        if not path.is_file():
            continue
        checked = True
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            text = re.split(r'(?<!\\)%', line, maxsplit=1)[0] if path.suffix == '.tex' else line
            hits = list(prose_findings(text))
            hits.extend(('stock-phrase', m.group(), '直接写图中关系、方程或结论。')
                        for m in ANNOUNCEMENTS.finditer(text))
            for kind, phrase, message in hits:
                findings.append({'code': 'handout-language', 'kind': kind, 'file': source, 'line': number,
                                 'message': f'{source} 第 {number} 行的“{phrase}”。{message}'})
    return findings, checked


def run(project,stage='plan',prepared=None,video_file=None):
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
        from feedback_bank import check as check_feedback
        from feedback_review import review_line
        feedback = check_feedback(project,lesson)
        coverage['viewer_feedback'] = {'catalogs':feedback['catalog_counts'], 'listen':len(feedback['listen']),
                                       'report':'feedback-check.json', 'replay':[review_line(i) for i in feedback['replay']]}
        add('viewer-feedback',[dict(row,code=row['key']) for row in feedback['findings']])
        manual.extend(coverage['viewer_feedback']['replay'])
        learned = feedback['learning_checks']['occurrences']
        coverage['viewer_feedback']['located_checks'] = {
            kind:sum(row['kind']==kind for row in learned) for kind in ('term','letter','formula')}
        if stage == 'final':
            # Declared steps already receive their own final-review task. Older lessons
            # can still have written equations with no declared derivation step.
            from step_review import steps, enabled
            declared = {(str(page),str(step.get('cue_id')),step.get('action_id'))
                        for page,step in steps(lesson) if enabled(lesson,step) and step.get('action_id')}
            for row in learned:
                if row['kind']=='formula' and (row['page'],row['cue'],row['action_id']) not in declared:
                    manual.append(f"对听 {row['page']}/{row['cue']} 第 {row['action_index']+1} 个动作"
                                  f"写出的 {row['formula']}，看运算和落笔能否逐步对应。")
        manual.extend(row.get('expected') or row['observed'] for row in feedback['manual_checks'])
        if lesson.get('source_type')=='article':
            from article_coverage import audit as audit_article
            gaps = audit_article(project,lesson)
            add('article',gaps,'error')
            coverage['article']='mapped' if not gaps else 'incomplete'
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
        coverage['derivation_evidence']=board.get('derivation_evidence',[])
        duration=duration_report(project,lesson,timeline)
        add('duration',[{'code':'duration-budget','message':m} for m in duration['issues']])
        floor = duration.get('minimum_seconds')
        coverage['minimum_seconds'] = floor
        if floor and timeline['duration'] < floor:
            add('duration',[{'code':'duration-below-minimum','message':
                f'当前时间轴 {timeline["duration"]:.1f} 秒，最低 {floor:g} 秒。补入前置知识、图上推导或实际变式后重新计时。'}],'error')
        coverage['duration']=duration['timeline_status']
        # Export current, consolidated diagnostics without changing the lesson/approval.
        write_json(project/'delivery-report.json',delivery)
        write_json(project/'board-review-report.json',board)
        write_json(project/'duration-estimate.json',duration)
        try:
            handout(project,lesson)
            coverage['handout']='file-present'
            from handout_bundle import main_source,verified
            if stage=='final' and main_source(project,lesson):
                if verified(project,lesson):
                    coverage['handout']='clean-xelatex-verified'
                else:
                    add('handout',[{'code':'handout-source-package','message':'运行 handout-pack，交付当前源码包和空目录编译的 PDF。'}],'error')
            wording, scanned = handout_language(project, lesson)
            if scanned:
                add('handout', wording)
                coverage['handout_language']='phrase-check'
            manual.append('交付前复读学生版讲义的标题、图注和末段，以具体物理结论收尾。')
        except ValueError as exc:
            add('handout',[{'code':'handout-missing','message':str(exc)}],'error')
        if stage=='plan' and native_preview(project,lesson)=='':
            add('animation',[{'code':'preview-missing','message':'当前原生动画尚无对应预览，生成后查看接触、轨迹、方向和标注。'}])
        if stage=='final':
            if lesson.get('speech_review_version')==1:
                from trial_review import require_target_voice
                try:
                    _, approved = require_target_voice(project,timeline['speech'])
                    measured = timeline.get('target_voice',{})
                    if any(measured.get(k)!=v for k,v in approved.items()) or not measured.get('matched_takes'):
                        raise ValueError('当前时间轴缺少各语段与已审听目标音色一致的记录，请用正式配音入口重新导出。')
                    coverage['target_voice'] = measured
                except (ValueError, OSError, KeyError) as exc:
                    add('voice',[dict(code='target-voice-unverified',message=str(exc))],'error')
            from voice_quality import audit as voice_audit,strict_findings,export_term_reel
            sound=voice_audit(project,timeline)
            add('voice',strict_findings(sound))
            coverage['voice']='signal-and-text-check'
            coverage['listening_cues']=len(sound['listening_checks'])
            reel = export_term_reel(project, sound['terminology']['items'])
            coverage['term_reel'] = {'status': reel['status'], 'clips': len(reel['clips']), 'audio': reel['audio']}
            if abs(sound['duration']-timeline['duration'])>.15:
                add('voice',[{'code':'audio-duration','message':'配音文件长度与时间轴不一致，重建音画同步。'}],'error')
            from video_quality import probe, review_points, extract_samples
            video=project / (video_file or 'video.mp4')
            if not video.is_file():
                add('video',[{'code':'video-missing','message':f'找不到待检查的成片 {video.name}。'}],'error')
            else:
                from speech_continuity import inspect as check_continuity
                try:
                    continuity = check_continuity(video, timeline)
                    write_json(project/'final-speech-continuity.json', continuity)
                    coverage['speech_continuity'] = dict(cues=continuity['spoken_cues'],
                        aligned_cues=continuity['aligned_cues'], candidates=len(continuity['candidates']))
                    manual.append('从本版 MP4 正常速度连听开头、相邻公式句和改过的整句前后，逐项确认词内、句间及板书衔接。')
                    for row in continuity['candidates']:
                        manual.append(f"成片 {row['start']:.2f} 秒，连听前后两句，记录停顿或接缝。原句为「{row['text']}」。")
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    write_json(project/'final-speech-continuity.json', dict(status='unavailable',error=str(exc)))
                    manual.append('从本版 MP4 逐句听语流和音画衔接，记录具体时间、原句与判断。')
                from term_flow import inspect as check_term_flow, refresh_manifest
                flow = None
                try:
                    flow = check_term_flow(project, timeline, video, lesson=lesson)
                    write_json(project/'final-term-flow.json', flow)
                    refresh_manifest(project,flow)
                    coverage['physics_terms'] = dict(terms=flow['terms'], total=len(flow['items']),
                                                     remaining=flow['remaining'])
                    if flow['inventory_pending']:
                        add('voice',[dict(code='term-inventory-pending',message=f"还有 {len(flow['inventory_pending'])} 句待制作端对照完整讲稿盘点术语，见 feedback-check.json。")],'error')
                    if flow['remaining']:
                        add('voice', [dict(code='final-terms-unchecked', message=
                            f"还有 {flow['remaining']} 处物理术语须在成片中分别确认读音和连读，见 final-term-flow.json。")], 'error')
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    write_json(project/'final-term-flow.json', {'status':'blocked','error':str(exc)})
                    add('voice',[dict(code='final-terms-incomplete',message=str(exc))],'error')
                from tone_review import inspect as check_tones
                tones = check_tones(project, timeline, video)
                write_json(project/'final-tone-review.json', tones)
                cue_count = len(tones['producer_queue'])
                coverage['final_tones'] = {'remaining': tones['remaining'], 'total': len(tones['items']),
                                           'producer_cues': cue_count}
                if tones['remaining']:
                    add('voice', [{'code': 'final-tones-unchecked', 'message':
                        f"制作端需复核 {cue_count} 段口播中的 {tones['remaining']} 处读音，按 final-tone-review.json 的 producer_queue 处理。"}], 'error')
                from speech_context import review_course, probe_python
                try:
                    context = review_course(project, timeline, video, lesson)
                    coverage['speech_context'] = dict(total=len(context['items']), remaining=context['remaining'])
                    coverage['formula_listening'] = sum(target['kind']=='formula'
                         for row in context['items'] for target in row['targets'])
                    if context['remaining']:
                        add('voice',[dict(code='speech-context-pending',message=
                            f"还有 {context['remaining']} 句需对听字母、接缝或核对板书，见 final-speech-context.json。")],'error')
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    write_json(project/'final-speech-context.json', dict(status='blocked',error=str(exc)))
                    add('voice',[dict(code='speech-context-incomplete',message=str(exc))],'error')
                else:
                    try:
                        audio_python = probe_python()
                        if audio_python and (coverage.get('physics_terms',{}).get('total') or context['remaining']):
                            subprocess.run([audio_python,str(Path(__file__).with_name('speech_probe.py')),
                                            str(project),'--pending'],check=True)
                            terms=json.loads((project/'final-physics-term-probes.json').read_text())
                            coverage['physics_term_probes']={'positions':terms['total'],'statuses':terms['statuses'],
                                'producer_review_sentences':len(terms.get('producer_review',[]))}
                            probes=json.loads((project/'final-speech-probes.json').read_text())
                            coverage['speech_probes']={'status':'measured','items':len(probes['items'])}
                    except (ValueError, OSError, subprocess.SubprocessError) as exc:
                        write_json(project/'final-speech-probes.json',dict(status='unavailable',error=str(exc)))
                        coverage['speech_probes']={'status':'unavailable'}
                        coverage['physics_term_probes']={'status':'unavailable'}
                        if flow and flow.get('file'):
                            previous=project/'final-physics-term-probes.json'
                            prior=json.loads(previous.read_text()) if previous.is_file() else {}
                            if prior.get('sha256')!=flow.get('sha256') or prior.get('total')!=len(flow['items']):
                                write_json(previous,dict(status='unavailable',error=str(exc)))
                        add('voice',[dict(code='speech-probe-unavailable',message=
                            '本机识音未完成，按整句清单实听。'+str(exc))])
                media = probe(video)
                coverage['media'] = media
                if floor and media['duration_seconds'] < floor:
                    add('video',[{'code':'media-below-minimum','message':
                        f'所选 MP4 实测 {media["duration_seconds"]:.2f} 秒，最低 {floor:g} 秒。'}],'error')
                if not media['audio_codec'] or not media['video_codec']:
                    add('video',[{'code':'video-stream','message':'成片须同时有音轨和视频轨。'}],'error')
                if abs(media['duration_seconds']-timeline['duration'])>1:
                    add('video',[{'code':'video-duration','message':'成片长度与当前配音时间轴不一致。'}],'error')
                elif media['video_codec']:
                    media['samples'] = extract_samples(video, media, review_points(timeline['pages'], pages), project/'review-video')
                    media['visual_review'] = 'pending'
                coverage['video']='stream-and-duration-check'
                manual.append('在原始分辨率查看抽帧中的上下标、负号和细线，在交付视频中以正常速度播放落笔与动画片段。')
            if reel['clips']:
                manual.append('打开[读音试听合辑](review-audio/term-reel.wav)，按 term-reel.json 对照每个词的读法和原片时间。')
            manual.append('按 voice-report.json 的 listening_checks 连听上下文，确认字母、单位、多音字、重音和段落衔接。')
            manual.append('按正常速度看一段常规讲解和一段难点推导，检查是否靠降语速、拖慢书写或空白补时长。')
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
    if stage=='final' and coverage.get('media'):
        from handout_bundle import digest as file_hash
        result['media_sha256']=file_hash(project/coverage['media']['file'])
        from final_review import attach
        result=attach(project,lesson,result)
    write_json(project/'quality-report.json',result)
    lines=['# 本课制作检查','',f'阶段：{stage}；状态：{result["status"]}。','']
    if result['findings']:
        for item in result['findings']:
            where=' / '.join(str(item[k]) for k in ('page','cue') if item.get(k))
            lines.append(f'- {item["area"]}'+(f' · {where}' if where else '')+'：'+item['message'])
    else:
        lines.append('已运行的自动检查未发现问题。')
    if 'media' in coverage:
        media = coverage['media']
        def rate(value):
            return f'{value / 1000:.0f} kb/s' if value is not None else '未提供'
        lines.extend(['', '## 交付视频', '',
                      f'{Path(media["file"]).name} · {media["size_bytes"] / 1e6:.1f} MB · {media["duration_seconds"]:.1f} 秒',
                      f'{media["width"]} × {media["height"]} · {media["fps"]} fps · {media["video_codec"]} 平均 {rate(media["video_average_bps"])} · {media["audio_codec"]} 平均 {rate(media["audio_average_bps"])}。'])
        for sample in media.get('samples', []):
            image = Path(sample['image']).relative_to(project).as_posix()
            lines.append(f'- {sample["seconds"]:.2f} 秒，{sample["look_for"]}。[查看原尺寸画面]({image})')
    lines.extend(['','## 制作端观看与试听' if stage == 'final' else '## 观看与试听',''])
    lines.extend('- '+task for task in result['manual_review']['tasks'])
    lines.extend(['','自动检查的范围记录在 quality-report.json。观看和试听结果由实际审阅填写到制作记录。',''])
    (project/'制作检查.md').write_text('\n'.join(lines))
    return result
