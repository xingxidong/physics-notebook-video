"""Prepare a teacher review and bind approval to the exact authored lesson."""
import base64
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def opening(lesson):
    if 'opening' in lesson:
        value=lesson['opening']
    elif lesson.get('review_required'):
        profile=ROOT/'author-profile.local.json'
        value=json.loads(profile.read_text()) if profile.is_file() else {}
    else:
        return None
    if value is False and not lesson.get('review_required'):
        return None
    if not isinstance(value,dict):
        raise ValueError('opening 须为作者信息对象。')
    title=value.get('title',lesson['title'])
    if not isinstance(title,str) or not title.strip():
        raise ValueError('片头需要课名。')
    lines=[]
    for field in ('author','school','contact'):
        if field in value:
            line=value[field]
            if not isinstance(line,str) or '\n' in line:
                raise ValueError(f'opening.{field} 须为一行文字。')
            if line.strip():
                lines.append(line.strip())
    return {'title':title.strip(),'lines':lines}


def opening_image(profile,font):
    from PIL import Image,ImageDraw,ImageFont
    # Use the same image path in HTML, Notebook, Manim and Motion Canvas.
    width,height=1120,570
    image=Image.new('RGB',(width,height),'#fffef9')
    draw=ImageDraw.Draw(image)
    title_font=ImageFont.truetype(str(font),55)
    author_font=ImageFont.truetype(str(font),30)
    words=[]
    line=''
    for char in profile['title']:
        if line and draw.textlength(line+char,font=title_font)>width-164:
            words.append(line)
            line=char
        else:
            line+=char
    words.append(line)
    if len(words)>3:
        raise ValueError('片头课名超过三行，请在 opening.title 填写适合屏幕显示的课名。')
    y=176-(len(words)-1)*37
    for line in words:
        draw.text((width/2,y),line,anchor='mt',font=title_font,fill='#243d32')
        y+=74
    y+=28
    for line in profile['lines']:
        if draw.textlength(line,font=author_font)>width-120:
            raise ValueError('单行作者信息过长。')
        draw.text((width/2,y),line,anchor='mt',font=author_font,fill='#40594d')
        y+=43
    buffer=io.BytesIO()
    image.save(buffer,format='PNG')
    return {'x':80,'y':59,'w':width,'h':height,
            'data':'data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()}


def local_file(project,name,*,required=True):
    project=Path(project).resolve()
    if not isinstance(name,str) or not name.strip():
        raise ValueError('教案依赖须为项目内的文件路径。')
    path=(project/name).resolve()
    if not path.is_relative_to(project):
        raise ValueError(f'教案依赖应放在项目目录内：{name}')
    if required and not path.is_file():
        raise ValueError(f'缺少教案依赖：{name}')
    return path


def handout(project,lesson):
    path=local_file(project,lesson.get('handout','讲义.md'))
    if path.stat().st_size==0:
        raise ValueError('请准备包含正文的学生讲义。')
    return path


def dependency_hashes(project,lesson):
    assets=lesson.get('review_assets',[])
    if not isinstance(assets,list) or any(not isinstance(name,str) for name in assets):
        raise ValueError('review_assets 须列出项目内的素材路径。')
    from handout_bundle import digest, source_files
    names=set(assets) | {str(p.relative_to(project)) for p in source_files(project,lesson)}
    for key in ('course_outline','duration_plan','handout','input_manifest','article_coverage'):

        if isinstance(lesson.get(key),str):
            names.add(lesson[key])
    if lesson.get('input_manifest'):
        intake=json.loads(local_file(project,lesson['input_manifest']).read_text())
        for key in ('problem_sources','solution_sources'):
            names.update(row['file'] for row in intake.get(key,[]))
    default=project/'讲义.md'
    if default.is_file() and 'handout' not in lesson:
        names.add(default.name)
    for page in lesson['pages']:
        if isinstance(page.get('image'),dict) and page['image'].get('file'):
            names.add(page['image']['file'])
        for scene in page.get('native_scenes',{}).values():
            if scene.get('source'):
                names.add(scene['source'])
            names.update(scene.get('dependencies',[]))
        for cue in page.get('cues',[]):
            if cue.get('audio'):
                names.add(cue['audio'])
            if cue.get('alignment'):
                names.add(cue['alignment'])
    files={name:digest(local_file(project,name))
           for name in sorted(names)}
    return files


def fingerprint(project,lesson):
    files=dependency_hashes(project,lesson)
    value={'lesson':lesson,'opening':opening(lesson),'files':files}
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def require_unchanged(project,expected):
    """A render/review must describe the source it actually started from."""
    from course import compile_lesson
    latest,_=compile_lesson(project)
    if fingerprint(project,latest)!=expected:
        raise ValueError('制作期间课程源或素材发生变化，请用当前版本重新生成预览或教案。')


def native_preview(project,lesson):
    if not lesson.get('classroom_workflow_version') and not any(p.get('native_scenes') for p in lesson['pages']):
        return None
    manifest=project/'draft-preview-report.json'
    from handout_bundle import digest
    if manifest.is_file():
        record=json.loads(manifest.read_text())
        if lesson.get('classroom_workflow_version')==1:
            from production_workflow import read
            expected_pages=['opening-card'] if opening(lesson) else []
            expected_pages.extend(page.get('id',f'p{i:02d}') for i,page in enumerate(lesson['pages'],1))
            if (record.get('workflow_run')!=read(project/'classroom-start.json').get('run')
                    or record.get('preview_kind')!='full-silent-lesson'
                    or record.get('pages')!=expected_pages or not record.get('video_frames')
                    or record.get('audio_tracks')!=0):
                return ''
        if record.get('review_sha256')==fingerprint(project,lesson) and record.get('video_file'):
            name=Path(record['video_file']).name
            path=project/name
            if path.is_file() and record.get('video_sha256')==digest(path):
                return name
    return ''


def plan_text(project,lesson,pages,timing,layout,teaching,*,duration=None,language=None,quality=None):
    from course_outline import load_outline, markdown
    lines=[f'# {lesson["title"]} · 教案','']
    profile=opening(lesson)
    if profile:
        lines.extend(['## 片头','',profile['title'],'',*profile['lines'],'','[片头预览](review-preview/pages/opening-card.png)',''])
    if lesson.get('kind')=='concept':
        lines.append(markdown(load_outline(project,lesson['course_outline'])).split('\n',1)[1].strip())
    notes=lesson.get('review_notes')
    if isinstance(notes,dict) and notes:
        lines.extend(['','## 本课教什么',''])
        for key,label in (('focus','重点'),('difficulty','难点与讲法'),('outcome','学完能做')):
            if isinstance(notes.get(key),str) and notes[key].strip():
                lines.extend([f'**{label}**：{notes[key]}',''])
    arc=teaching.get('lesson_arc',{}) if isinstance(teaching,dict) else {}
    if arc.get('beats'):
        lines.extend(['## 课堂推进','',f'开场问题：{arc.get("entry_question","")}',''])
        for beat in arc['beats']:
            lines.append(f'- {beat.get("id","教学拍")} · {beat.get("purpose","")}：{beat.get("student_question","")}')
            lines.append(f'  - 画面：{ "、".join(beat.get("visual_ids",[])) }')
            lines.append(f'  - 变化：{beat.get("scene_change","")}')
            lines.append(f'  - 留下：{beat.get("takeaway","")}')
        lines.append('')
    if duration:
        from lesson_duration import markdown as duration_markdown
        lines.extend(['',duration_markdown(duration).rstrip()])
    lines.extend(['','## 逐页板书与完整口播',''])
    for page in pages:
        lines.extend([f'### {page["title"]}','','板书预览 [PNG](review-preview/pages/'+page['id']+'.png)',''])
        if page.get('layout',{}).get('carry'):
            lines.append('延续上一页笔迹　'+ '、'.join(page['layout']['carry']))
        if page.get('demonstration') or page.get('native_scenes') or page.get('scene_events'):
            lines.extend(['动画审核　逐帧对照初末状态、接触位置和运动方向，检查穿模与遮挡。',''])
        for cue in page['cues']:
            lines.append(cue['tts'])
            notes=[]
            for action in cue.get('resolved_actions',[]):
                if action['type']=='text':
                    value=action['text']
                elif action['type']=='math':
                    value='$'+action.get('latex','')+'$'
                else:
                    continue
                notes.append('**'+value+'**' if action.get('emphasis') else value)
            if notes:
                lines.append('- 落笔　'+' / '.join(notes))
            lines.append('')
    closure=lesson.get('closure')
    if isinstance(closure,dict):
        lines.extend(['## 收束总结',''])
        for point in closure.get('points',[]):
            if isinstance(point,dict) and str(point.get('text','')).strip():
                lines.append('- '+point['text'])
        recap=set(closure.get('recap_cues',[]))
        closing=[cue['tts'] for page in pages for cue in page['cues'] if cue['id'] in recap]
        if closing:
            lines.extend(['','总结口播：'+' '.join(closing),''])
        visible=closure.get('visible_action_ids',[])
        if visible:
            lines.extend(['总结时保留板书：'+'、'.join(visible),''])
    if language:
        warnings=language['warnings']
        lines.extend(['## 课堂口播复读','',
                      '在图旁逐段读：学生现在看哪一处、这一句增加了什么、下一句接哪条依据。重点段连起来读，听说理和落笔能否跟上。','',
                      f'文字检查提示 {len(warnings)} 处，见[逐句报告](delivery-report.json)。',''])
        for item in warnings[:8]:
            text=item.get('excerpt','')
            lines.append(f'- {item.get("cue","整课")}：'+(f'「{text}」 ' if text else '')+item['message'])
        lines.append('')
    if quality:
        lines.extend(['## 制作复查','', '[当前制作检查清单](制作检查.md) · [本课历史反馈与逐句试听位置](feedback-check.json)',''])
        for note in quality.get('coverage',{}).get('viewer_feedback',{}).get('replay',[]):
            lines.append('- '+note)
        for item in quality.get('findings',[]):
            lines.append('- '+item['message'])
        lines.append('')
    from step_review import steps,enabled
    linked_steps=[(pid,s) for pid,s in steps(lesson) if enabled(lesson,s)]
    if linked_steps:
        lines.extend(['## 逐步核对口播、板书与讲义',''])
        for pid,s in linked_steps:
            lines.extend([f"**{pid}/{s.get('id')}**　{s.get('question','')}",
                          f"口播「{s.get('spoken_anchor','')}」　板书 `{s.get('action_id')}`　讲义 `{s.get('handout_label')}`",
                          '先呈现：'+'、'.join(s.get('requires_visible',[])) if s.get('requires_visible') else '', ''])
    lines.extend(['## 审阅','',
                  '请先确认本课重难点、推导、口播、片头和学生讲义，再确认可进入正式制作。','',
                  '[横屏尺寸板书检查图](review-preview/contact-sheet.png) · [无配音板书预览](review-preview/preview.html)',''])
    preview=native_preview(project,lesson)
    if preview:
        lines.extend([f'[全课无配音视频 MP4]({preview})',''])
    elif preview=='':
        lines.extend(['运行 preview 生成全课无配音 MP4。看完动画、逐笔板书和图上标记后重新出教案。',''])
    for finding in [*teaching.get('errors',[]),*layout.get('warnings',[]),*timing.get('warnings',[])]:
        lines.append('- '+finding['message'])
    linked=lesson.get('handout','讲义.md')
    if (project/'handout-delivery/receipt.json').is_file():
        from handout_bundle import main_source,verified
        if main_source(project,lesson) and verified(project,lesson):
            linked='handout-delivery/学生讲义.pdf'
    if local_file(project,linked,required=False).is_file():
        lines.extend(['',f'[学生讲义]({linked})',''])
    return '\n'.join(lines)+'\n'


def prepare_review(project,lesson,pages,timing,layout,teaching,*,duration=None,language=None,quality=None,pilot_sha=None):
    from classroom_workflow import enabled, require_active, write_drafts
    started=require_active(project,lesson) if enabled(lesson) else None
    path=project/'教案.md'
    path.write_text(plan_text(project,lesson,pages,timing,layout,teaching,duration=duration,language=language,quality=quality))
    state={'fingerprint':fingerprint(project,lesson),
           'document_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
           'native_preview':native_preview(project,lesson),
           'warnings':len(layout['warnings'])+len(timing['warnings']),
           'teaching_errors':len(teaching['errors']),
           'quality_errors':sum(row['severity']=='error' for row in quality.get('findings',[])) if quality else 0}
    if started:
        write_drafts(project,pages)
        state.update(workflow_run=started['run'],estimated_seconds=(duration or {}).get('timeline_seconds'),
                     pilot_sha256=pilot_sha)
    write_json(project/'review-plan.json',state)
    return state


def current_review(project,lesson):
    manifest=project/'review-plan.json'
    document=project/'教案.md'
    if not manifest.is_file() or not document.is_file():
        raise ValueError('先用 review-plan 生成教案，再请人审阅。')
    planned=json.loads(manifest.read_text())
    if (planned['fingerprint']!=fingerprint(project,lesson)
            or planned['document_sha256']!=hashlib.sha256(document.read_bytes()).hexdigest()):
        raise ValueError('教案、讲稿或素材已更新，请重新生成教案并确认。')
    return planned


def approve(project,lesson,feedback):
    if not feedback.strip():
        raise ValueError('请记录审阅者对当前教案的实际确认。')
    plan=current_review(project,lesson)
    handout(project,lesson)
    if plan.get('native_preview')=='' or plan.get('native_preview')!=native_preview(project,lesson):
        raise ValueError('请先生成当前版本的全课无配音 MP4 并重新提交教案。')
    if plan['teaching_errors'] or plan['warnings'] or plan.get('quality_errors'):
        raise ValueError('先处理教案中的教学与排版检查项，再提交确认。')
    from classroom_workflow import enabled, require_active, require_packet
    if enabled(lesson):
        require_active(project,lesson)
        plan={**plan,'classroom_packet':require_packet(project,lesson,plan)['packet_sha256']}
    write_json(project/'review-approval.json',{**plan,'feedback':feedback.strip(),
                                               'approved_at':datetime.now(timezone.utc).isoformat()})


def require(project,lesson,renderer=None):
    from classroom_workflow import enabled, require_active, require_packet
    strict=enabled(lesson)
    if strict:
        require_active(project,lesson)
    if not lesson.get('review_required'):
        return
    plan=current_review(project,lesson)
    handout(project,lesson)
    evidence=project/'review-approval.json'
    if not evidence.is_file():
        raise ValueError('请等待人审教案，再用 approve-plan 记录对当前版本的确认。')
    result=json.loads(evidence.read_text())
    if any(result.get(k)!=plan[k] for k in ('fingerprint','document_sha256')):
        raise ValueError('当前教案需要重新确认。')
    if not result.get('feedback'):
        raise ValueError('确认记录需保留审阅者的确认内容。')
    packet=None
    if strict:
        packet=require_packet(project,lesson,plan)
        if result.get('classroom_packet')!=packet['packet_sha256']:
            raise ValueError('当前整套教案、板书、讲义、讲稿、全课无配音视频及试音须重新确认。')
    animation=packet['files']['全课无配音视频']['file'] if packet else native_preview(project,lesson)
    if plan.get('native_preview')!=animation:
        raise ValueError('全课无配音视频已变动，请重新审阅。')
    if renderer and plan.get('native_preview'):
        recorded=json.loads((project/'draft-preview-report.json').read_text())['renderer']
        if renderer!=recorded:
            raise ValueError('正式合成应使用全课无配音视频中已确认的渲染引擎。')
    return packet


def export_delivery(project,lesson,*,publish=False,video_file='video.mp4'):
    import zipfile
    from final_review import invalidate
    from classroom_workflow import before_finalize, enabled
    workflow=before_finalize(project,lesson,video_file) if publish and enabled(lesson) else None
    invalidate(project)

    document=handout(project,lesson)
    files={document}
    if document.suffix.lower() in ('.md','.markdown'):
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',document.read_text()):
            name=target.strip().strip('<>').split('#',1)[0]
            if not name or re.match(r'[A-Za-z][A-Za-z+.-]*:',name):
                continue
            dep=(document.parent/name).resolve()
            if not dep.is_relative_to(project) or not dep.is_file():
                raise ValueError(f'学生讲义的本地链接无法打包：{target}')
            files.add(dep)
    media=local_file(project,video_file)
    record={'video':str(media.relative_to(project)),'handout':str(document.relative_to(project)),
            'boards':'boards.pdf','tikz':'tikz/boards.tex'}
    from term_flow import inspect as check_term_flow, manifest_entry
    from feedback_bank import save_report
    timeline = json.loads((project/'timeline.json').read_text())
    report = check_term_flow(project, timeline, media, lesson=lesson)
    save_report(project/'final-term-flow.json', report)
    record['term_review'] = manifest_entry(report)
    from speech_context import review_course
    context = review_course(project,timeline,media,lesson)
    record['speech_context'] = manifest_entry(context)
    from handout_bundle import main_source, build as build_handout, verified
    if main_source(project,lesson):
        receipt=json.loads((project/'handout-delivery/receipt.json').read_text()) if verified(project,lesson) else build_handout(project,lesson)
        record.update(handout=receipt['pdf'], handout_bundle=receipt['archive'],
                      handout_receipt='handout-delivery/receipt.json')
    elif len(files)>1:
        bundle=project/'学生讲义.zip'
        part=bundle.with_suffix('.part.zip')
        with zipfile.ZipFile(part,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(files):
                archive.write(path,path.relative_to(project))
        part.replace(bundle)
        record['handout_bundle']=bundle.name
    subtitles=project/'subtitles.srt'
    if subtitles.is_file():
        record['subtitles']=subtitles.name
    record['status']='awaiting_review'
    write_json(project/'delivery-candidate.json',record)
    if publish:
        if report.get('inventory_pending') or report['remaining'] or context['remaining']:
            raise ValueError('术语、字母或整句仍有待审项，不能标记为可交付。')
        from final_review import require
        reviewed=require(project,lesson,media)
        for name in ('video','handout','boards','tikz'):
            local_file(project,record[name])
        record.update(status='reviewed',review_binding=reviewed['review_binding'])
        if workflow:
            record['classroom_workflow']=workflow
        write_json(project/'delivery-files.json',record)
    return record
