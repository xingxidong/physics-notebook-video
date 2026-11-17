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
        seen.update(page_ids)
        slow, fast = PACE[mode]
        low = max(visual, chars / fast) + extra
        high = max(visual, chars / slow) + extra
        nominal = max(visual, chars / ((fast + slow) / 2)) + extra
        rows.append({'title': title, 'reason': reason, 'mode': mode, 'pages': page_ids,
                     'visual_seconds':visual, 'observe_seconds':extra,
                     'estimate_seconds': round(nominal, 1), 'range_seconds': [round(low, 1), round(high, 1)]})
    target = source.get('requested_minutes')
    if target is not None:
        target = number(target, '用户指定时长（分钟）', .01) * 60
    opening = number(source.get('opening_seconds', 3), '片头时间')
    return {'status': 'planned', 'audience': audience, 'sections': rows, 'opening_seconds': opening,
            'recommended_seconds': round(opening + sum(r['estimate_seconds'] for r in rows)),
            'range_seconds': [round(opening + sum(r['range_seconds'][i] for r in rows)) for i in (0, 1)],
            'requested_seconds': target}


def load(project, source):
    if isinstance(source, dict):
        return source
    from lesson_review import local_file
    return json.loads(local_file(project, source).read_text())


def page_paces(project, lesson):
    source = lesson.get('duration_plan')
    if source is None:
        return {}
    plan = estimate(load(project, source))
    return {page: sum(PACE[row['mode']]) / 2 for row in plan['sections'] for page in row['pages']}


def report(project, lesson, timeline):
    total = round(timeline['duration'], 1)
    pages = [p for p in timeline['pages'] if p['id'] != 'opening-card']
    source = lesson.get('duration_plan')
    if source is None:
        plan = {'status': 'from-script', 'sections': [], 'recommended_seconds': None,
                'requested_seconds': None, 'range_seconds': None}
    else:
        plan = estimate(load(project, source))
        authored = [pid for r in plan['sections'] for pid in r['pages']]
        if authored != [p['id'] for p in pages]:
            raise ValueError('时长编排须按实际授课顺序把每个板书页分配到一个教学段。')
    durations = {p['id']: p['duration'] for p in pages}
    for row in plan['sections']:
        row['timeline_seconds'] = round(sum(durations[pid] for pid in row['pages']), 1)
        row['issues'] = []
        actual=row['timeline_seconds']
        low,high=row['range_seconds']
        if actual < low-max(5,low*.1):
            row['issues'].append('本段短于预计讲解范围，查看推导中间步骤和完整结论能否讲完。')
        elif actual > high+max(8,high*.15):
            row['issues'].append('本段长于预计讲解范围，复读是否重复铺垫、报式或归纳。')
        if actual+2 < row['visual_seconds']+row['observe_seconds']:
            row['issues'].append('当前时间不足以容纳已规划的落笔或观察，复看实际动画节奏。')
    if not plan['sections']:
        plan['sections'] = [{'title': p['title'], 'pages': [p['id']], 'timeline_seconds': round(p['duration'], 1)}
                            for p in pages]
    if not plan['requested_seconds'] and source is None and lesson.get('kind') == 'concept':
        from course_outline import load_outline
        if lesson.get('course_outline'):
            plan['outline_seconds'] = 60 * load_outline(project, lesson['course_outline'])['target_minutes']
    issues = []
    for row in plan['sections']:
        issues.extend(row['title']+'：'+message for message in row.get('issues',[]))
    target = plan['requested_seconds'] or plan.get('outline_seconds')
    if target and abs(total-target) > max(12, .12 * target):
        issues.append('时间轴与目标相差较大。复查绕行、重复或需要展开的步骤，再决定怎样调整内容。')
    span = plan['range_seconds']
    if span and (total < span[0] - 12 or total > span[1] + 12):
        issues.append('时间轴超出备课估算范围。对照分段时长检查口播、落笔和观察安排。')
    if span and target and (target < span[0] or target > span[1]):
        issues.append('指定时长在当前讲法的常见范围之外。调整例题数量或拆课，保留主线推导。')
    return {**plan, 'timeline_status': 'estimated' if timeline.get('draft') else 'measured',
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
    for issue in info.get('issues', []):
        lines.append(f'\n- {issue}')
    return '\n'.join(lines) + '\n'
