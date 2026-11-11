"""Link the formal statements students need to copy to actual board strokes."""
import math


def _clean(text):
    return ''.join(str(text).split())


def inspect_sources(lesson, pages):
    points = lesson.get('knowledge_points', [])
    errors = []
    records = []
    if lesson.get('kind') == 'concept' and not points:
        errors.append({'code': 'knowledge-points-required',
                       'message': 'List the concepts, definitions or laws and link their complete written statements to board actions.'})
    if not isinstance(points, list):
        return [], [{'code': 'knowledge-points-format', 'message': 'knowledge_points must be a list.'}]
    by_page = {page['id']: page for page in pages}
    seen = set()
    for point in points:
        if not isinstance(point, dict):
            errors.append({'code': 'knowledge-point-format', 'message': 'Each knowledge point must be an object.'})
            continue
        kid = point.get('id')
        page = by_page.get(point.get('page_id'))
        if not kid or kid in seen or page is None:
            errors.append({'code': 'knowledge-point-link', 'message': f'{kid}: use a unique id and an existing page_id.'})
            continue
        seen.add(kid)
        actions = {a.get('id'): (cue['id'], a, index)
                   for cue in page['cues']
                   for index, a in enumerate(cue.get('resolved_actions', cue.get('actions', []))) if a.get('id')}
        ids = point.get('statement_action_ids')
        if not isinstance(ids, list) or not ids or any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids):
            errors.append({'code': 'knowledge-statement-link', 'message': f'{kid}: link all written statement lines by action id.'})
            continue
        refs = []
        lines = []
        for action_id in ids:
            linked = actions.get(action_id)
            if linked is None or linked[1].get('type') != 'text':
                errors.append({'code': 'knowledge-statement-visible', 'message': f'{kid}: {action_id} must be a handwritten text action.'})
                continue
            cue_id, action, index = linked
            lines.append(action['text'])
            refs.append({'cue': cue_id, 'action': index, 'id': action_id})
        statement = point.get('statement', '')
        if not statement or _clean(''.join(lines)) != _clean(statement):
            errors.append({'code': 'knowledge-statement-content', 'message': f'{kid}: the complete statement must match the linked board text.'})
        name_id = point.get('name_action_id')
        if name_id:
            linked = actions.get(name_id)
            if linked is None or linked[1].get('type') != 'text' or _clean(linked[1].get('text')) != _clean(point.get('name', '')):
                errors.append({'code': 'knowledge-name-visible', 'message': f'{kid}: write the stated concept or law name on the board.'})
            else:
                refs.append({'cue': linked[0], 'action': linked[2], 'id': name_id})
        elif point.get('name') and _clean(point['name']) not in _clean(statement):
            errors.append({'code': 'knowledge-name-visible', 'message': f'{kid}: include the name in the statement or link its name_action_id.'})
        for action_id in point.get('formula_action_ids', []):
            linked = actions.get(action_id)
            if linked is None or linked[1].get('type') != 'math':
                errors.append({'code': 'knowledge-formula-visible', 'message': f'{kid}: link {action_id} to an actual formula action.'})
            else:
                refs.append({'cue': linked[0], 'action': linked[2], 'id': action_id})
        read_seconds = point.get('read_seconds', 4)
        if not isinstance(read_seconds, (int, float)) or not math.isfinite(read_seconds) or read_seconds < 0:
            errors.append({'code': 'knowledge-reading-time', 'message': f'{kid}: read_seconds must be a finite nonnegative number.'})
            continue
        records.append({'id': kid, 'name': point.get('name', ''), 'page_id': page['id'],
                        'statement': statement, 'actions': refs, 'read_seconds': read_seconds})
    return records, errors


def inspect_timeline(records, data):
    errors = []
    findings = []
    pages = {page['id']: page for page in data['pages']}
    for record in records:
        page = pages[record['page_id']]
        strokes = []
        for ref in record['actions']:
            events = [event for event in page['strokes'] if event['cue'] == ref['cue'] and event['action'] == ref['action']]
            if not events or any(event.get('render_kind') == 'tex' for event in events):
                errors.append({'code': 'knowledge-strokes-missing', 'message': f'{record["id"]}: {ref["id"]} has no handwriting on the measured timeline.'})
            strokes.extend(events)
        if not strokes:
            continue
        complete = max(event['end'] for event in strokes)
        remaining = page['duration'] - complete
        if remaining + 1e-6 < record['read_seconds']:
            errors.append({'code': 'knowledge-reading-time', 'message': f'{record["id"]}: leave {record["read_seconds"]:g}s after the complete statement and formulas are written.'})
        findings.append({'id': record['id'], 'name': record['name'], 'page_id': page['id'],
                         'complete_at': round(page['start'] + complete, 3),
                         'visible_until': round(page['start'] + page['duration'], 3),
                         'seconds_after_writing': round(remaining, 3)})
    return {'status': 'attention' if errors else 'pass' if records else 'not_applicable',
            'items': findings, 'errors': errors}
