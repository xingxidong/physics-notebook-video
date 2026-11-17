"""Check the teaching order and visible board references of a new-concept lesson."""

LEGACY_STAGES = {
    'orient': 'introduce', 'reason': 'explain', 'anchor': 'emphasize', 'apply': 'apply',
}


def stage_anchors(unit):
    """Read the actual teaching sequence from either supported source format."""
    if 'stages' not in unit:
        return [(purpose, unit.get(name + '_cue')) for purpose, name in LEGACY_STAGES.items()]
    stages = unit['stages']
    if not isinstance(stages, list):
        return []
    return [(row.get('purpose'), row.get('cue')) for row in stages if isinstance(row, dict)]


def check(lesson, pages):
    if lesson.get('kind') != 'concept':
        return {'status': 'not_applicable', 'units': []}, []
    units = lesson.get('concept_units')

    errors = []

    def issue(code, detail):
        errors.append({'code': code, 'message': detail})

    records = []
    if not isinstance(units, list) or not units:
        issue('concept-units-required', '声明 concept_units，再按引入、讲解、强调、应用检查编排新授课。')
        return {'status': 'attention', 'units': records}, errors

    def text(value):
        return value.strip() if isinstance(value, str) else ''

    def list_of_objects(value, field):
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            issue('concept-unit-format', f'{field} 须为对象列表。')
            return []
        return value

    def list_of_ids(value, field):
        if not isinstance(value, list) or not value or any(not text(item) for item in value):
            issue('concept-unit-format', f'{field} 须为非空的 ID 列表。')
            return []
        return value

    ordered = [(page['id'], cue) for page in pages for cue in page['cues']]
    order = {cue['id']: i for i, (_, cue) in enumerate(ordered)}
    actions = {}
    moving_pages = {page['id'] for page in pages if page.get('native_scenes') or page.get('demonstration')}
    for page_id, cue in ordered:
        for action in cue.get('resolved_actions', cue.get('actions', [])):
            if action.get('id'):
                actions[page_id, action['id']] = (cue['id'], action)
    knowledge = lesson.get('knowledge_points', [])
    points = {point['id']: point for point in (knowledge if isinstance(knowledge, list) else [])
              if isinstance(point, dict) and text(point.get('id'))}
    units = list_of_objects(units, 'concept_units')
    if not units:
        return {'status': 'attention', 'units': records}, errors

    def stages_for(unit, unit_id):
        """Accept the legacy four-stage form and an adaptive teaching route."""
        raw=unit.get('stages')
        if raw is None:
            return [{'purpose': purpose, 'cue': text(cue)} for purpose, cue in stage_anchors(unit)]
        if not isinstance(raw,list) or not raw or any(not isinstance(row,dict) for row in raw):
            issue('concept-stage-format',f'{unit_id} 的 stages 须为教学拍对象列表。')
            return []
        allowed={'orient','observe','contrast','model','reason','derive','anchor','apply','recap'}
        result=[]
        for purpose, cue in stage_anchors(unit):
            purpose=text(purpose);cue=text(cue)
            if purpose not in allowed or cue not in order:
                issue('concept-stage-format',f'{unit_id} 的 stages 每项须有有效 purpose 和 cue。')
                continue
            result.append({'purpose':purpose,'cue':cue})
        return result

    sequences = [stages_for(unit, text(unit.get('id')) or '某教学段') for unit in units]
    starts = [next((order[row['cue']] for row in stages if row['cue'] in order), -1)
              for stages in sequences]
    marked_points = set()
    unit_ids = set()
    for i, unit in enumerate(units):
        unit_id = text(unit.get('id'))
        focus = text(unit.get('focus'))
        if not unit_id or unit_id in unit_ids or not focus:
            issue('concept-unit-focus', f'{unit_id or i+1} 须有唯一 ID，并写出本段要讲清的一项知识。')
        unit_ids.add(unit_id)
        stages=sequences[i]
        begin = starts[i]
        stage_positions=[order[row['cue']] for row in stages if row.get('cue') in order]
        explain = next((order[row['cue']] for row in stages if row.get('cue') in order and row['purpose'] in ('reason','derive','model','contrast')), -1)
        emphasize = next((order[row['cue']] for row in stages if row.get('cue') in order and row['purpose']=='anchor'), -1)
        end = starts[i + 1] if i + 1 < len(starts) else len(ordered)
        apply = next((order[row['cue']] for row in stages if row.get('cue') in order and row['purpose']=='apply'), -1)
        if (not stage_positions or stage_positions != sorted(stage_positions) or len(set(stage_positions)) != len(stage_positions)
                or not (0 <= begin < emphasize < apply < end) or stage_positions[-1] >= end
                or ('stages' not in unit and (len(stage_positions) != 4 or explain <= begin))
                or (i == 0 and begin != 0)):
            issue('concept-unit-order', f'{unit_id} 的教学拍须按实际口播顺序推进，在正式结论落笔后安排应用检查。')
            continue
        if explain >= 0 and not begin <= explain < emphasize:
            issue('concept-unit-order', f'{unit_id} 的建模、对照或推理应发生在正式结论落笔之前。')
            continue
        if explain < 0:
            # Some definitions are introduced through a sharp contrast rather than
            # a derivation.  The anchor still needs a stated reason in the script.
            explain=begin
        if not any(row['purpose'] in ('orient','observe','contrast','model') for row in stages):
            issue('concept-unit-entry',f'{unit_id} 先安排一个具体情景、现象、对照或模型，让学生知道要解释什么。')
            continue

        question_count = {}
        application_questions = 0
        for q in list_of_objects(unit.get('questions', []), f'{unit_id}.questions'):
            ask_id, answer_id = text(q.get('cue')), text(q.get('answer_cue'))
            ask, answer = order.get(ask_id, -1), order.get(answer_id, -1)
            if not begin <= ask < answer < end:
                issue('concept-question-order', f'{unit_id}/{ask_id} 须先写出问题，再在后面的讲解中回答。')
                continue
            page_id = ordered[ask][0]
            plain = []
            for aid in list_of_ids(q.get('action_ids'), f'{ask_id}.action_ids'):
                attached_cue, action = actions.get((page_id, aid), (None, {}))
                if attached_cue != ask_id or action.get('type') != 'text':
                    issue('concept-question-visible', f'{ask_id}/{aid} 须对应提问时的手写文字。')
                plain.append(action.get('text', ''))
            question = text(q.get('text'))
            if not question.endswith(('？', '?')) or ''.join(''.join(plain).split()) != ''.join(question.split()):
                issue('concept-question-text', f'{ask_id} 的板书文字须完整写出所提的问题。')
            question_count[ask_id] = question_count.get(ask_id, 0) + 1
            if apply <= ask:
                application_questions += 1
        if not application_questions:
            issue('concept-application-required', f'{unit_id} 的应用检查须写下一个判断、预测或计算题，并在本段说明答案和依据。')
        for _, cue in ordered[begin:end]:
            punctuation = sum(cue.get('tts', '').count(mark) for mark in ('？', '?'))
            if punctuation > question_count.get(cue['id'], 0):
                issue('concept-spoken-question', f'{cue["id"]} 的口播提问还缺板书问题和对应的回答段。')

        for point_id in list_of_ids(unit.get('knowledge_point_ids'), f'{unit_id}.knowledge_point_ids'):
            point = points.get(point_id)
            if point is None or point_id in marked_points:
                issue('concept-unit-point', f'{unit_id} 须关联有效且未重复安排的知识点 {point_id}。')
                continue
            marked_points.add(point_id)
            ids = point.get('statement_action_ids') or []
            formulas = point.get('formula_action_ids') or []
            for aid in ids:
                attached_cue, _ = actions.get((point.get('page_id'), aid), (None, {}))
                if not emphasize <= order.get(attached_cue, -1) < apply:
                    issue('concept-emphasis-board', f'{unit_id}/{aid} 须在强调阶段写出完整结论。')
            for aid in formulas:
                attached_cue, _ = actions.get((point.get('page_id'), aid), (None, {}))
                if not begin <= order.get(attached_cue, -1) < apply:
                    issue('concept-emphasis-board', f'{unit_id}/{aid} 须在应用开始前写在正式结论所在的板书页。')

        annotated = set()
        scene_labels = list_of_objects(unit.get('scene_labels', []), f'{unit_id}.scene_labels')
        for label in scene_labels:
            page_id, aid = text(label.get('page_id')), text(label.get('action_id'))
            used = order.get(text(label.get('first_use_cue')), -1)
            attached_cue, action = actions.get((page_id, aid), (None, {}))
            written = order.get(attached_cue, -1)
            content = text(action.get('text') or action.get('latex') or action.get('label'))
            if not (begin <= written <= used < end and ordered[used][0] == page_id and content):
                issue('concept-scene-label', f'{unit_id}/{aid} 须是图上真实可见的标注，并在本页讲到该量时已可见。')
            else:
                annotated.add(page_id)
        if not scene_labels and not text(unit.get('scene_not_applicable')):
            issue('concept-scene-labels-required', f'{unit_id} 须登记图中的物理量，或说明本段为什么无需物理图。')
        native_during_unit = {page_id for page_id, _ in ordered[begin:end]} & moving_pages
        for page_id in sorted(native_during_unit - annotated):
            issue('concept-motion-labels-required', f'{page_id} 的运动图须关联实际画出的量和方向。')

        records.append({'id': unit_id, 'focus': focus, 'introduce_cue': ordered[begin][1]['id'],
                        'explain_cue': ordered[explain][1]['id'], 'emphasize_cue': ordered[emphasize][1]['id'],
                        'apply_cue': ordered[apply][1]['id'], 'questions': sum(question_count.values()),
                        'application_questions': application_questions, 'scene_labels': len(scene_labels),
                        'stages':stages})

    for point_id in sorted(points.keys() - marked_points):
        issue('concept-point-unassigned', f'{point_id} 尚未安排完整的教学顺序。')

    return {'status': 'attention' if errors else 'pass', 'units': records}, errors
