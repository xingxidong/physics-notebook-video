"""Check the teaching beats that make a lecture followable from beginning to end."""

PURPOSES=frozenset({'orient','model','reason','derive','anchor','apply','recap'})


def check(lesson,pages):
    """Return a compact, source-level lesson-arc report.

    The arc is intentionally about a student's changing question, rather than
    a list of slide titles.  It is required for review-gated lessons; older
    sources remain usable until they enter that workflow.
    """
    errors=[]
    required=bool(lesson.get('review_required') or lesson.get('lesson_arc_required'))
    arc=lesson.get('lesson_arc')
    if not required and not isinstance(arc,dict):
        return {'status':'not_applicable','beats':[],'errors':[]}
    if not isinstance(arc,dict):
        return {'status':'attention','beats':[], 'errors':[{
            'code':'lesson-arc-required',
            'message':'补充 lesson_arc：把整课拆成学生问题、画面依据和本段结论清楚的教学拍。'}]}

    entry=arc.get('entry_question')
    if not isinstance(entry,str) or not entry.strip():
        errors.append({'code':'arc-entry-question','message':'lesson_arc.entry_question 写出本课开头让学生追的问题。'})
    beats=arc.get('beats')
    if not isinstance(beats,list) or not beats:
        return {'status':'attention','beats':[], 'errors':errors+[{ 
            'code':'arc-beats-required','message':'lesson_arc.beats 至少列出引入、建立关系、落笔结论、应用或回顾等实际教学拍。'}]}

    ordered=[cue['id'] for page in pages for cue in page['cues']]
    positions={cue_id:index for index,cue_id in enumerate(ordered)}
    actions=set()
    for page in pages:
        if page.get('demonstration') or page.get('native_scenes'):
            actions.add('scene:'+page['id'])
        for cue in page['cues']:
            for action in cue.get('resolved_actions',cue.get('actions',[])):
                for value in (action.get('id'),action.get('board_group'),action.get('component_id')):
                    if isinstance(value,str) and value:
                        actions.add(value)
        for carried in page.get('carry_blocks',[]):
            for value in (carried.get('id'),carried.get('board_group'),carried.get('component_id')):
                if isinstance(value,str) and value:
                    actions.add(value)

    seen_cues=set();last=-1;seen_ids=set();reported=[]
    for index,beat in enumerate(beats,1):
        if not isinstance(beat,dict):
            errors.append({'code':'arc-beat-format','message':f'第 {index} 个教学拍需为对象。'});continue
        bid=beat.get('id');purpose=beat.get('purpose');cue_ids=beat.get('cue_ids')
        if not isinstance(bid,str) or not bid or bid in seen_ids:
            errors.append({'code':'arc-beat-id','message':f'第 {index} 个教学拍需要唯一 id。'})
        else:seen_ids.add(bid)
        if purpose not in PURPOSES:
            errors.append({'code':'arc-purpose','message':f'{bid or index}: purpose 取 orient、model、reason、derive、anchor、apply 或 recap。'})
        if not isinstance(cue_ids,list) or not cue_ids or any(item not in positions for item in cue_ids):
            errors.append({'code':'arc-cues','message':f'{bid or index}: cue_ids 须列出实际存在的连续口播段。'})
            continue
        cue_positions=[positions[item] for item in cue_ids]
        if cue_positions != list(range(min(cue_positions),max(cue_positions)+1)) or min(cue_positions)<=last:
            errors.append({'code':'arc-order','message':f'{bid or index}: 教学拍按实际口播顺序排列，cue_ids 连续且不交叠。'})
        last=max(last,max(cue_positions));seen_cues.update(cue_ids)
        for key,label in (('student_question','学生此刻要解决的问题'),('scene_change','这句话里图或板书发生的变化'),('takeaway','这一拍留下的结论或判断')):
            if not isinstance(beat.get(key),str) or not beat[key].strip():
                errors.append({'code':'arc-teaching-intent','message':f'{bid or index}: 写出{label}。'})
        visual=beat.get('visual_ids')
        if not isinstance(visual,list) or not visual or any(item not in actions for item in visual):
            errors.append({'code':'arc-visual','message':f'{bid or index}: visual_ids 要关联实际题图、标注、公式或组件。'})
        reported.append({'id':bid,'purpose':purpose,'cue_ids':cue_ids,
                         'student_question':beat.get('student_question',''),
                         'scene_change':beat.get('scene_change',''),
                         'takeaway':beat.get('takeaway',''),'visual_ids':visual or []})

    missing=[cue_id for cue_id in ordered if cue_id not in seen_cues]
    if missing:
        errors.append({'code':'arc-coverage','message':'以下口播尚未归入教学拍：'+ '、'.join(missing)+'。'})
    purposes={beat.get('purpose') for beat in beats if isinstance(beat,dict)}
    required_purposes={'orient','anchor','apply','recap'} if lesson.get('kind')=='concept' else {'model','derive','anchor','recap'}
    absent=required_purposes-purposes
    if absent:
        errors.append({'code':'arc-milestones','message':'课程编排缺少：'+ '、'.join(sorted(absent))+'。把这些教学作用安排成实际口播和板书。'})
    closure=lesson.get('closure',{})
    recap=closure.get('recap_cues',[]) if isinstance(closure,dict) else []
    if recap and not any(beat.get('purpose')=='recap' and beat.get('cue_ids')==recap for beat in beats if isinstance(beat,dict)):
        errors.append({'code':'arc-recap-link','message':'lesson_arc 的 recap 教学拍与 closure.recap_cues 使用同一组口播段。'})
    return {'status':'attention' if errors else 'pass','entry_question':entry,'beats':reported,'errors':errors}
