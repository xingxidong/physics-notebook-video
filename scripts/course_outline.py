"""Plan a concept lesson before writing narration and check the completed lesson against it."""
import argparse
import json
import math
from pathlib import Path
from concept_units import LEGACY_STAGES, stage_anchors


def clean(value):
    return value.strip() if isinstance(value, str) else ''


def normalized(value):
    return ''.join(clean(value).split())


def minutes(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if math.isfinite(number) and number > 0 else None


def load_outline(root, source):
    if isinstance(source, dict):
        return source
    if not clean(source):
        raise ValueError('新授课须先提交 course_outline，可以内嵌，也可引用项目内的 JSON 文件。')
    root = Path(root).resolve()
    path = (root / source).resolve()
    if not path.is_relative_to(root):
        raise ValueError('course_outline 须位于课程目录内。')
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f'无法读取课程编排 {source}：{exc}') from None


def validate(outline):
    errors = []

    def issue(code, message):
        errors.append({'code': code, 'message': message})

    def fields(item, required, name):
        for field in required:
            if not clean(item.get(field)):
                issue('outline-field', f'{name} 缺少 {field}。')

    def records(item, field, name, *, required=True):
        value = item.get(field, [] if not required else None)
        if not isinstance(value, list) or (required and not value) or any(not isinstance(row, dict) for row in value):
            issue('outline-format', f'{name} 的 {field} 须为对象列表。')
            return []
        return value

    def references(item, field, available, name, code, *, required=True):
        value = item.get(field)
        if not isinstance(value, list) or (required and not value) or any(not clean(ref) for ref in value):
            issue('outline-format', f'{name} 的 {field} 须列出 ID。')
            return set()
        if len(set(value)) != len(value):
            issue('outline-duplicate', f'{name} 的 {field} 重复引用。')
        missing = set(value) - available
        if missing:
            issue(code, f'{name} 的 {field} 引用了尚未建立或不存在的内容：{", ".join(sorted(missing))}。')
        return set(value) - missing

    def register(record, name, ids):
        key = clean(record.get('id'))
        if not key or key != record['id'] or key in ids:
            issue('outline-id', f'{name} 须有唯一的 ID。')
        else:
            ids.add(key)
        return key

    if not isinstance(outline, dict):
        return [{'code': 'outline-format', 'message': '课程编排须为 JSON 对象。'}]
    fields(outline, ('title', 'audience', 'main_question'), '整课')
    total = minutes(outline.get('target_minutes'))
    if total is None:
        issue('outline-duration', '全课预计时长须为正数。')

    prior_ids = set()
    for row in records(outline, 'prior_knowledge', '整课', required=False):
        register(row, '先修知识', prior_ids)
        fields(row, ('description',), '先修知识')

    objective_ids = set()
    for row in records(outline, 'objectives', '整课'):
        register(row, '课末目标', objective_ids)
        fields(row, ('outcome',), '课末目标')

    taught = set(prior_ids)
    focus_texts = set()
    touched = set()
    previous_board=None
    detailed=outline.get('planning_version',1)==2
    planned = 0.
    for row in records(outline, 'units', '整课'):
        key = clean(row.get('id'))
        name = key or '某教学段'
        dependencies = references(row, 'needs', taught, name, 'outline-prerequisite', required=False)
        if key in dependencies:
            issue('outline-prerequisite', f'{name} 把本段知识列为先修。')
        register(row, name, taught)
        fields(row, ('focus', 'opening', 'reasoning', 'board_statement', 'handoff'), name)
        focus = normalized(row.get('focus'))
        if focus and focus in focus_texts:
            issue('outline-duplicate-focus', f'{name} 和前面的教学段写了同一个重点。')
        focus_texts.add(focus)
        touched.update(references(row, 'objective_ids', objective_ids, name, 'outline-objective'))
        duration = minutes(row.get('minutes'))
        if duration is None:
            issue('outline-duration', f'{name} 的预计时长须为正数。')
        else:
            planned += duration

        if detailed:
            fields(row, ('key_point',), name)
            difficulty=row.get('difficulty')
            if not isinstance(difficulty,dict):
                issue('outline-difficulty', f'{name} 须列出容易卡住之处和准备怎样讲通。')
            else:
                fields(difficulty,('obstacle','treatment'),name+' 的难点')
            board=records(row,'board_pages',name)
            board_ids=set()
            for page in board:
                page_id=register(page,name+' 的板书页',board_ids)
                fields(page,('goal',),name+' 的板书页')
                if page.get('from_page') and (page['from_page']!=previous_board or page_id==previous_board):
                    issue('outline-board-continuity', f'{page_id} 须从相邻上一页承接。')
                previous_board=page_id
            budget=row.get('stage_minutes')
            phases=('introduce','explain','emphasize','apply')
            if not isinstance(budget,dict) or set(budget)!=set(phases) or any(minutes(budget.get(k)) is None for k in phases):
                issue('outline-stage-budget', f'{name} 须分别分配引入、讲解、强调、应用检查的时间。')
            elif duration is not None and not math.isclose(sum(budget.values()),duration,abs_tol=.05):
                issue('outline-stage-budget', f'{name} 的四阶段时间合计须与本段时间一致。')

        diagram = row.get('diagram')
        if isinstance(diagram, dict):
            fields(diagram, ('scene',), name + ' 的情景图')
            labels = diagram.get('labels')
            if not isinstance(labels, list) or not labels or any(not clean(label) for label in labels):
                issue('outline-scene-labels', f'{name} 须列出图中会用到的量、符号、数值或方向。')
        elif diagram is not None or not clean(row.get('no_diagram')):
            issue('outline-diagram', f'{name} 须规划情景图，或说明为什么用文字或式子即可。')
        if 'intro_question' in row and not clean(row['intro_question']).endswith(('？', '?')):
            issue('outline-question', f'{name} 的引入问题须写成完整问句。')
        application = row.get('application')
        if not isinstance(application, dict):
            issue('outline-application', f'{name} 须规划应用检查。')
        else:
            fields(application, ('question', 'expected_answer'), name + ' 的应用检查')
            if not clean(application.get('question')).endswith(('？', '?')):
                issue('outline-question', f'{name} 的应用问题须写成完整问句。')

    checked = set()
    exit_questions = set()
    for row in records(outline, 'exit_checks', '整课'):
        name = '课末检查'
        fields(row, ('question', 'expected_answer'), name)
        question = normalized(row.get('question'))
        if not question.endswith(('？', '?')):
            issue('outline-question', '课末检查须写出完整问题。')
        elif question in exit_questions:
            issue('outline-duplicate', f'课末问题重复：{question}')
        exit_questions.add(question)
        checked.update(references(row, 'objective_ids', objective_ids, name, 'outline-objective'))
    for key in sorted(objective_ids - touched):
        issue('outline-objective-unassigned', f'课末目标 {key} 还没有教学段支撑。')
    for key in sorted(objective_ids - checked):
        issue('outline-objective-unassessed', f'课末目标 {key} 还没有课末检查。')
    if total is not None and not math.isclose(total, planned, abs_tol=.05):
        issue('outline-duration', f'教学段合计 {planned:g} 分钟，整课目标为 {total:g} 分钟。')

    for row in records(outline, 'deferred', '整课', required=False):
        fields(row, ('topic', 'reason'), '后续内容')
    return errors


def check_lesson(project, lesson, pages):
    if lesson.get('kind') != 'concept':
        return {'status': 'not_applicable'}, []
    source = lesson.get('course_outline')
    try:
        outline = load_outline(project, source)
    except ValueError as exc:
        return {'status': 'attention'}, [{'code': 'outline-source', 'message': str(exc)}]
    errors = validate(outline)
    if errors:
        return {'status': 'attention'}, errors

    planned_units = outline['units']
    units = lesson.get('concept_units')
    if not isinstance(units, list) or not all(isinstance(unit, dict) for unit in units):
        units = []
    ids = [unit['id'] for unit in planned_units]
    if [unit.get('id') for unit in units] != ids:
        errors.append({'code': 'outline-unit-order', 'message': '课程源中的教学段须与编排表的教学段一一对应，并保持原顺序。'})
        return {'status': 'attention', 'unit_ids': ids}, errors

    cue_pages={cue['id']:page['id'] for page in pages for cue in page['cues']}
    page_lookup={page['id']:page for page in pages}
    cue_order = {
        cue['id']: index for index, cue in
        enumerate(cue for page in pages for cue in page['cues'])
    }
    notes = lesson.get('knowledge_points')
    points = {point['id']: normalized(point.get('statement')) for point in notes
              if isinstance(point, dict) and clean(point.get('id'))} if isinstance(notes, list) else {}
    for index, (plan, unit) in enumerate(zip(planned_units, units)):
        key = plan['id']
        if normalized(plan['focus']) != normalized(unit.get('focus')):
            errors.append({'code': 'outline-unit-focus', 'message': f'{key} 的口播重点须与课程编排表一致。'})
        point_ids = unit.get('knowledge_point_ids', [])
        linked = {points.get(point_id) for point_id in point_ids if clean(point_id)} if isinstance(point_ids, list) else set()
        if normalized(plan['board_statement']) not in linked:
            errors.append({'code': 'outline-board', 'message': f'{key} 须把编排表中的正式结论写进本段的 knowledge_points。'})

        questions = unit.get('questions')
        questions = [q for q in questions if isinstance(q, dict)] if isinstance(questions, list) else []
        stages = [(purpose, cue_order.get(clean(cue), -1)) for purpose, cue in stage_anchors(unit)]
        introduce = stages[0][1] if stages else -1
        opening_end = 'anchor' if 'stages' in unit else 'reason'
        explain = next((position for purpose, position in stages if purpose == opening_end), -1)
        apply = next((position for purpose, position in stages if purpose == 'apply'), -1)
        next_stages = stage_anchors(units[index + 1]) if index + 1 < len(units) else []
        end = cue_order.get(clean(next_stages[0][1]), len(cue_order)) if next_stages else len(cue_order)
        opening = {normalized(q.get('text')) for q in questions
                   if 0 <= introduce <= cue_order.get(clean(q.get('cue')), -1) < explain}
        application = {normalized(q.get('text')) for q in questions
                       if 0 <= apply <= cue_order.get(clean(q.get('cue')), -1) < end}
        intro_question = normalized(plan.get('intro_question'))
        if outline.get('planning_version')==2:
            begin=introduce
            actual=list(dict.fromkeys(cue_pages[c] for c,i in cue_order.items() if begin<=i<end))
            expected=[p['id'] for p in plan['board_pages']]
            if begin<0 or actual!=expected:
                errors.append({'code':'outline-board-pages','message':f'{key} 的实际板书页须按教案顺序：{", ".join(expected)}。'})
            for row in plan['board_pages']:
                if row.get('from_page') and not page_lookup.get(row['id'],{}).get('layout',{}).get('carry'):
                    errors.append({'code':'outline-board-continuity','message':f'{row["id"]} 须带入上一页所需的图或关系。'})
            selected=unit.get('knowledge_point_ids',[])
            source_points={point['id']:point for point in notes if isinstance(point,dict) and point.get('id')}
            marked=False
            for pk in selected:
                point=source_points.get(pk,{})
                page=page_lookup.get(point.get('page_id'),{})
                formal=set(point.get('statement_action_ids',[])+point.get('formula_action_ids',[]))
                marked |= any(action.get('emphasis') and action.get('id') in formal
                              for cue in page.get('cues',[]) for action in cue.get('resolved_actions',[]))
            if not marked:
                errors.append({'code':'outline-emphasis','message':f'{key} 须突出至少一条正式结论或核心公式。'})

        if intro_question and intro_question not in opening:
            errors.append({'code': 'outline-intro-question', 'message': f'{key} 的引入须按编排表写出问题。'})
        if normalized(plan['application']['question']) not in application:
            errors.append({'code': 'outline-application-question', 'message': f'{key} 须在应用阶段安排编排表中的问题。'})
        if key == ids[-1]:
            for row in outline['exit_checks']:
                if normalized(row['question']) not in application:
                    errors.append({'code': 'outline-exit-question', 'message': f'最后一段应用检查须写出课末问题「{row["question"]}」。'})

    return {
        'status': 'attention' if errors else 'pass',
        'main_question': outline['main_question'],
        'target_minutes': outline['target_minutes'],
        'unit_ids': ids,
        'exit_checks': len(outline['exit_checks']),
    }, errors


def markdown(outline):
    def cell(text):
        return ' '.join(text.split()).replace('|', r'\|')

    lines = [f'# {outline["title"]} · 课程编排', '',
             f'**整课问题**　{outline["main_question"]}', '',
             f'**对象**　{outline["audience"]}　　**预计时长**　{outline["target_minutes"]:g} 分钟', '']
    if outline.get('prior_knowledge'):
        lines.extend(['## 先修知识', ''])
        lines.extend(f'- {row["description"]}' for row in outline['prior_knowledge'])
        lines.append('')
    lines.extend(['## 课末目标', ''])
    goal_numbers = {row['id']: i for i, row in enumerate(outline['objectives'], 1)}
    lines.extend(f'{goal_numbers[row["id"]]}. {row["outcome"]}' for row in outline['objectives'])
    lines.extend(['', '## 教学段安排', '',
                  '| 时间 | 本段重点 | 开场问题或情景 | 讲解用图 | 正式板书 | 应用检查 | 承接 |',
                  '| --- | --- | --- | --- | --- | --- | --- |'])
    elapsed = 0.
    for row in outline['units']:
        end = elapsed + row['minutes']
        diagram = row.get('diagram')
        values = [f'{elapsed:g}–{end:g} 分钟', row['focus'], row.get('intro_question') or row['opening'],
                  diagram['scene'] if diagram else row['no_diagram'], row['board_statement'],
                  row['application']['question'], row['handoff']]
        lines.append('| ' + ' | '.join(cell(value) for value in values) + ' |')
        elapsed = end
    captions = {row['id']: row['description'] for row in outline.get('prior_knowledge', [])}
    captions.update({row['id']: row['focus'] for row in outline['units']})
    lines.extend(['', '## 各段讲解依据', ''])
    for row in outline['units']:
        lines.extend([f'### {row["focus"]}', '', row['opening'], ''])
        if row['needs']:
            lines.append('- 用到的先修或上一段结论　' + '、'.join(captions[key] for key in row['needs']))
        if row.get('key_point'):
            lines.append('- 重点　'+row['key_point'])
        if row.get('difficulty'):
            lines.extend(['- 难点　'+row['difficulty']['obstacle'],'- 讲法　'+row['difficulty']['treatment']])
        if row.get('stage_minutes'):
            labels={'introduce':'引入','explain':'讲解','emphasize':'强调','apply':'应用'}
            lines.append('- 时间　'+'、'.join(f'{labels[key]} {value:g} 分钟' for key,value in row['stage_minutes'].items()))
        for page in row.get('board_pages',[]):
            lines.append(f'- 板书 {page["id"]}　{page["goal"]}')
        if row.get('diagram'):
            lines.append('- 图上标注　' + '、'.join(row['diagram']['labels']))
        lines.extend(['- 关键一步　' + row['reasoning'],
                      '- 应用题答案依据　' + row['application']['expected_answer'], ''])
    lines.extend(['## 课末检查', ''])
    for row in outline['exit_checks']:
        goals = '、'.join(str(goal_numbers[key]) for key in row['objective_ids'])
        lines.append(f'- {row["question"]}（目标 {goals}）')
        lines.append(f'  答案依据　{row["expected_answer"]}')
    if outline.get('deferred'):
        lines.extend(['', '## 后续内容', ''])
        lines.extend(f'- {row["topic"]}　{row["reason"]}' for row in outline['deferred'])
    return '\n'.join(lines) + '\n'


def timing_report(project,lesson,timeline):
    if lesson.get('kind')!='concept':
        return {'status':'not_applicable'}
    outline=load_outline(project,lesson['course_outline'])
    budgets={unit['id']:unit for unit in outline['units']}
    times={cue['id']:page['start']+cue['start']
           for page in timeline['pages'] for cue in page['cues']}
    units=lesson.get('concept_units',[])
    report=[]
    for i,unit in enumerate(units):
        stages = stage_anchors(unit)
        anchors = [times[cue] for _, cue in stages]
        stop = times[stage_anchors(units[i+1])[0][1]] if i+1<len(units) else timeline['duration']
        anchors.append(stop)
        row=budgets[unit['id']]
        values=[]
        for (purpose, _), start, stop in zip(stages, anchors, anchors[1:]):
            phase = purpose if 'stages' in unit else LEGACY_STAGES[purpose]
            values.append({'phase':phase,'start':round(start,3),'end':round(stop,3),
                           'planned_minutes':row.get('stage_minutes',{}).get(phase),
                           'actual_minutes':round((stop-start)/60,3)})
        report.append({'unit':unit['id'],'planned_minutes':row['minutes'],'stages':values})
    return {'status':'estimated' if timeline.get('draft') else 'measured',
            'target_minutes':outline['target_minutes'],'actual_minutes':round(timeline['duration']/60,3),'units':report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'table'))
    parser.add_argument('outline', type=Path)
    parser.add_argument('--output', type=Path, help='Markdown output path for table')
    args = parser.parse_args()
    try:
        outline = load_outline(args.outline.parent, args.outline.name)
        errors = validate(outline)
    except ValueError as exc:
        errors = [{'code': 'outline-source', 'message': str(exc)}]
    if errors or args.command == 'check':
        print(json.dumps({'ok': not errors, 'errors': errors}, ensure_ascii=False, indent=2))
        return int(bool(errors))
    table = markdown(outline)
    if args.output:
        args.output.write_text(table)
        print(args.output)
    else:
        print(table, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
