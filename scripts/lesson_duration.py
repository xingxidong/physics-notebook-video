"""Estimate teaching time before drafting and compare it with the review/final timeline."""
import json
import math
from pathlib import Path

# Spoken units per second: conversational Chinese, with room for pauses in a sentence.
PACE = {
    'orient': (3.5, 4.5),
    'explain': (3.2, 4.2),
    'derive': (2.7, 3.7),
    'apply': (3.0, 4.0),
}
LABELS = {'orient': '读图与引入', 'explain': '概念与判断', 'derive': '推导', 'apply': '应用与回收'}


def estimate(source):
    if not isinstance(source, dict) or not isinstance(source.get('sections'), list) or not source['sections']:
        raise ValueError('duration_plan 须包含按授课顺序排列的 sections。')

    def number(value, label, minimum=0):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < minimum:
            raise ValueError(f'{label} 须为不小于 {minimum} 的有限数值。')
        return value

    def required_text(row, field):
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'时长编排缺少 {field}。')
        return value.strip()

    audience = required_text(source, 'audience')
    rows = []
    seen = set()
    for section in source['sections']:
        if not isinstance(section, dict):
            raise ValueError('时长编排的每个 section 须为对象。')
        mode = section.get('mode')
        if not isinstance(mode, str) or mode not in PACE:
            raise ValueError('mode 须为 orient、explain、derive 或 apply。')
        title, reason = (required_text(section, k) for k in ('title', 'reason'))
        chars = number(section.get('spoken_chars'), title + ' 预计口播单位')
        visual = number(section.get('visual_seconds', 0), title + ' 并行板书或动画时间')
        extra = number(section.get('observe_seconds', 0), title + ' 单独观察或自然转场时间')
        if extra:
            required_text(section, 'observe_reason')
        if not (chars or visual):
            raise ValueError(f'{title} 须有预计口播、板书或动画。')
        page_ids = section.get('pages', [])
        if not isinstance(page_ids, list) or any(not isinstance(p, str) or not p.strip() for p in page_ids):
            raise ValueError(f'{title} 的 pages 须为页 ID 列表。')
        if len(set(page_ids)) != len(page_ids) or seen.intersection(page_ids):
            raise ValueError(f'{title} 重复分配了板书页。')
        extension = section.get('extension')
        if extension is not None:
            if not isinstance(extension, dict) or not page_ids:
                raise ValueError(f'{title} 的 extension 须写出教学收获、用到它的步骤和对应板书页。')
            extension = {key: required_text(extension, key) for key in ('outcome', 'used_in')}
        seen.update(page_ids)
        slow, fast = PACE[mode]
        low = max(visual, chars / fast) + extra
        high = max(visual, chars / slow) + extra
        nominal = max(visual, chars / ((fast + slow) / 2)) + extra
        rows.append({**({'extension': extension} if extension else {}), 'title': title, 'reason': reason, 'mode': mode, 'pages': page_ids,
                     'visual_seconds':visual, 'observe_seconds':extra,
                     'estimate_seconds': round(nominal, 1), 'range_seconds': [round(low, 1), round(high, 1)]})
    target = source.get('requested_minutes')
    if target is not None:
        target = number(target, '用户指定时长（分钟）', .01) * 60
    opening = number(source.get('opening_seconds', 3), '片头时间')
    base = opening + sum(row['estimate_seconds'] for row in rows if 'extension' not in row)
    added = sum(row['estimate_seconds'] for row in rows if 'extension' in row)
    return {'base_seconds': round(base, 1), 'extension_seconds': round(added, 1), 'status': 'planned', 'audience': audience, 'sections': rows, 'opening_seconds': opening,
            'recommended_seconds': round(opening + sum(r['estimate_seconds'] for r in rows)),
            'range_seconds': [round(opening + sum(r['range_seconds'][i] for r in rows)) for i in (0, 1)],
            'requested_seconds': target}


def load(project, source):
    if isinstance(source, dict):
        return source
    from lesson_review import local_file
    return json.loads(local_file(project, source).read_text())


def minimum_seconds(project, lesson):
    from feedback_bank import applicable_issues
    source = load(project,lesson['duration_plan']) if lesson.get('duration_plan') else {}
    explicit = source.get('minimum_minutes')
    if explicit is not None:
        if isinstance(explicit,bool) or not isinstance(explicit,(int,float)) or not math.isfinite(explicit) or explicit<=0:
            raise ValueError('minimum_minutes 须为有限正数。')
        return explicit*60
    if source.get('requested_minutes') is not None:
        return None
    limits = [r['minimum_minutes'] for r in applicable_issues(lesson) if r.get('minimum_minutes')]
    return 60*max(limits) if limits else None


def page_paces(project, lesson):
    source = lesson.get('duration_plan')
    if source is None:
        return {}
    plan = estimate(load(project, source))
    return {page: sum(PACE[row['mode']]) / 2 for row in plan['sections'] for page in row['pages']}


def spoken_budget(previous, current):
    """Estimate voice time from the reference speaker's recorded sentence timings."""
    if previous.get('draft') is not False:
        raise ValueError('语速依据应选用已有正式音轨的时间轴。')

    def sentences(timeline):
        return (cue for page in timeline['pages'] if page.get('id') != 'opening-card'
                for cue in page.get('cues', []) if (cue.get('tts') or '').strip())

    def units(cue):
        return sum(char.isalnum() for char in cue['tts'])

    recorded = [cue for cue in sentences(previous) if cue['end'] > cue['start'] and units(cue)]
    seconds = sum(cue['end'] - cue['start'] for cue in recorded)
    if not seconds:
        raise ValueError('参考时间轴缺少有文字、起止时间的发声句段。')
    old_units = sum(map(units, recorded))
    new_units = sum(map(units, sentences(current)))
    return {'reference_units': old_units, 'reference_seconds': seconds,
            'current_units': new_units, 'units_per_second': old_units / seconds,
            'estimated_spoken_seconds': new_units * seconds / old_units}


def compare_pace(previous, current):
    """Compare like-for-like recorded sentences and identical pen paths."""
    if previous.get('draft') is not False:
        raise ValueError('reference_timeline 应当是原版正式配音的时间轴。')

    def collect(data):
        cues, actions = {}, {}
        for page in data['pages']:
            for cue in page.get('cues', []):
                spoken = cue.get('spoken_tts', cue.get('tts', ''))
                if spoken.strip():
                    cues[(cue['id'], spoken.strip())] = cue['end'] - cue['start']
            for stroke in page.get('strokes', []):
                if stroke['start'] < 0 or stroke['end'] <= stroke['start'] or not stroke.get('points'):
                    continue
                key = (page['id'], stroke.get('cue'), stroke.get('board_id') or stroke.get('action'))
                actions.setdefault(key, []).append(stroke)
        return cues, actions

    old_cues, old_actions = collect(previous)
    new_cues, new_actions = collect(current)
    matched = old_cues.keys() & new_cues.keys()
    voice_old = sum(old_cues[k] for k in matched)
    voice_new = sum(new_cues[k] for k in matched)
    pen_old = pen_new = 0
    actions = 0
    for key in old_actions.keys() & new_actions.keys():
        before, after = old_actions[key], new_actions[key]
        if len(before) != len(after) or any(a['points'] != b['points'] for a, b in zip(before, after)):
            continue
        actions += 1
        pen_old += sum(s['end'] - s['start'] for s in before)
        pen_new += sum(s['end'] - s['start'] for s in after)
    issues = []
    for name, before, after in [('相同讲稿的口播', voice_old, voice_new), ('相同笔迹的落笔', pen_old, pen_new)]:
        if before >= 15 and after - before >= 3 and after > 1.1 * before:
            issues.append(f'{name}累计从 {before:.1f} 秒变为 {after:.1f} 秒。对照两版回看；需要加长课程时，把时间用在新的解释、推导或应用。')
    return {'matched_cues': len(matched), 'matched_actions': actions,
            'spoken_seconds': [round(voice_old, 2), round(voice_new, 2)],
            'ink_seconds': [round(pen_old, 2), round(pen_new, 2)], 'issues': issues}


def report(project, lesson, timeline):
    total = round(timeline['duration'], 1)
    pages = [p for p in timeline['pages'] if p['id'] != 'opening-card']
    source = lesson.get('duration_plan')
    if source is None:
        plan = {'status': 'from-script', 'sections': [], 'recommended_seconds': None,
                'requested_seconds': None, 'range_seconds': None}
    else:
        definition = load(project, source)
        plan = estimate(definition)
        if definition.get('reference_timeline') and (lesson.get('source_type') == 'article' or not timeline.get('draft')):
            from lesson_review import local_file
            reference = local_file(project, definition['reference_timeline'])
            if reference == (Path(project) / 'timeline.json').resolve():
                raise ValueError('请使用单独保存的旧版正式时间轴对照节奏。')
            previous = json.loads(reference.read_text())
            if lesson.get('source_type') == 'article':
                plan['spoken_budget'] = spoken_budget(previous, timeline)
            if not timeline.get('draft'):
                plan['pace_comparison'] = compare_pace(previous, timeline)
        authored = [pid for r in plan['sections'] for pid in r['pages']]
        if authored != [p['id'] for p in pages]:
            raise ValueError('时长编排须按实际授课顺序把每个板书页分配到一个教学段。')
    by_id = {page['id']: page for page in pages}
    for row in plan['sections']:
        section_pages = [by_id[pid] for pid in row['pages']]
        row['timeline_seconds'] = round(sum(page['duration'] for page in section_pages), 1)
        row['issues'] = []
        cues = [cue for page in section_pages for cue in page.get('cues', []) if cue.get('tts')]
        spoken_seconds = sum(cue['end'] - cue['start'] for cue in cues)
        if spoken_seconds > 0:
            units = sum(sum(char.isalnum() for char in cue.get('spoken_tts', cue['tts'])) for cue in cues)
            pace = units / spoken_seconds
            row['spoken_units_per_second'] = round(pace, 2)
            if spoken_seconds >= 30 and pace < .8 * PACE[row['mode']][0]:
                row['issues'].append('本段口播密度偏低。连听常规讲解与推导，检查是否整体降速。需要增加课时，在自然速度下补具体教学内容。')
        actual=row['timeline_seconds']
        low,high=row['range_seconds']
        if actual < low-max(5,low*.1):
            row['issues'].append('本段短于预计讲解范围，查看推导中间步骤和完整结论能否讲完。')
        elif actual > high+max(8,high*.15):
            row['issues'].append('本段长于预计讲解范围，检查重复讲述、语速、书写速度和空白时间。')
        if actual+2 < row['visual_seconds']+row['observe_seconds']:
            row['issues'].append('当前时间不足以容纳已规划的落笔或观察，复看实际动画节奏。')
    if not plan['sections']:
        plan['sections'] = [{'title': p['title'], 'pages': [p['id']], 'timeline_seconds': round(p['duration'], 1)}
                            for p in pages]
    if not plan['requested_seconds'] and source is None and lesson.get('kind') == 'concept':
        from course_outline import load_outline
        if lesson.get('course_outline'):
            plan['outline_seconds'] = 60 * load_outline(project, lesson['course_outline'])['target_minutes']
    issues = list(plan.get('pace_comparison', {}).get('issues', []))
    floor = minimum_seconds(project, lesson)
    budget = plan.get('spoken_budget')
    if floor and budget and budget['estimated_spoken_seconds'] < floor and timeline.get('draft'):
        issues.append('按参考音色的实录语速，当前讲稿发声时长低于成片下限。请查看哪些时间用于真实演示，并在教案中补足需要的推导、读图或应用。')
    for row in plan['sections']:
        issues.extend(row['title']+'：'+message for message in row.get('issues',[]))
    target = plan['requested_seconds'] or plan.get('outline_seconds')
    if target and abs(total-target) > max(12, .12 * target):
        issues.append('时间轴与目标相差较大。复查绕行、重复或需要展开的步骤，再决定怎样调整内容。')
    span = plan['range_seconds']
    if span and (total < span[0] - 12 or total > span[1] + 12):
        issues.append('时间轴超出备课估算范围。对照分段时长检查口播、落笔和观察安排。')
    if span and target and (target < span[0] or target > span[1]):
        issues.append('指定时长在当前讲法的常见范围之外。用自然节奏补充有作用的先修、推导或应用，或调整例题数量和课次。')
    return {**plan, 'minimum_seconds': floor, 'timeline_status': 'estimated' if timeline.get('draft') else 'measured',
            'timeline_seconds': total, 'issues': issues}


def clock(seconds):
    minutes, seconds = divmod(round(seconds), 60)
    return f'{minutes}:{seconds:02d}'


def markdown(info):
    lines = ['## 讲多久', '']
    if info.get('audience'):
        lines.append('学生基础：' + info['audience'])
    if info['recommended_seconds'] is not None:
        low, high = info['range_seconds']
        lines.append(f'建议约 **{clock(info["recommended_seconds"])}**，备课估算范围 {clock(low)}–{clock(high)}。')
    if info.get('minimum_seconds'):
        lines.append(f'成片最低时长 {clock(info["minimum_seconds"])}，按正常语速和实际导出文件检查。')
    if info.get('spoken_budget'):
        budget = info['spoken_budget']
        lines.append(f'同音色参考句段合计 {budget["reference_seconds"]:.1f} 秒，每秒 {budget["units_per_second"]:.2f} 个有效字和字母。按当前口播预计 {clock(budget["estimated_spoken_seconds"])}。')
    if info.get('requested_seconds'):
        lines.append(f'用户指定时长：{clock(info["requested_seconds"])}。')
    if 'timeline_seconds' in info:
        label = '按完整讲稿推算' if info['timeline_status'] == 'estimated' else '按成片时间轴实测'
        lines.append(f'{label}：**{clock(info["timeline_seconds"])}**（含片头如有）。')
    lines.extend(['', '| 教学段 | 备课预计 | 当前时间轴 | 为什么这样分配 |',
                  '| --- | ---: | ---: | --- |'])
    for row in info['sections']:
        planned = clock(row['estimate_seconds']) if 'estimate_seconds' in row else '—'
        current = clock(row['timeline_seconds']) if 'timeline_seconds' in row else '—'
        reason = row.get('reason', '—').replace('|', '／').replace('\n', ' ')
        lines.append(f'| {row["title"].replace("|", "／")} | {planned} | {current} | {reason} |')
    if 'pace_comparison' in info:
        comparison = info['pace_comparison']
        lines.append(f'\n两版有 {comparison["matched_cues"]} 句相同口播，{comparison["matched_actions"]} 处相同落笔可直接比较。')
    if any('extension' in row for row in info['sections']):
        lines.extend(['', f'原有内容约 {clock(info["base_seconds"])}，新增教学内容约 {clock(info["extension_seconds"])}。'])
        for row in info['sections']:
            if 'extension' in row:
                addition = row['extension']
                lines.append(f'- {row["title"]}（{clock(row["estimate_seconds"])}）：{addition["outcome"]}。用在{addition["used_in"]}。板书页 {", ".join(row["pages"])}。')
    for issue in info.get('issues', []):
        lines.append(f'\n- {issue}')
    return '\n'.join(lines) + '\n'
