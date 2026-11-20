"""Trace an article's substantive content to narration and board actions."""
import json

from lesson_review import local_file


def audit(project, lesson):
    if lesson.get('source_type') != 'article':
        return []
    manifest = lesson.get('article_coverage')
    if not manifest:
        return [{'code': 'article-source-map', 'message': '请登记原文各节、公式、图和读图活动的去向。'}]
    data = json.loads(local_file(project, manifest).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('items'), list) or not data.get('source'):
        return [{'code': 'article-source-map', 'message': '原文对照表须列出文章版本和具体条目。'}]
    actions = {
        cue['id']: {a['id'] for a in cue.get('actions', []) if a.get('id')}
        for page in lesson['pages'] for cue in page['cues']
        if str(cue.get('tts', cue.get('text', ''))).strip()
    }
    findings = []
    substantive = 0
    for row in data['items']:
        if not isinstance(row, dict):
            findings.append({'code': 'article-source-gap', 'message': '原文条目缺少出处与课堂内容。'})
            continue
        reference = row.get('source_ref')
        if row.get('kind') == 'background' and row.get('note') and reference:
            continue
        substantive += 1
        cues = row.get('cues')
        board = row.get('actions')
        valid = reference and row.get('student_task') and isinstance(cues, list) and cues and all(
            isinstance(c, str) and c in actions for c in cues
        )
        if valid:
            available = set().union(*(actions[c] for c in cues))
            valid = isinstance(board, list) and board and all(isinstance(a, str) and a in available for a in board)
        if not valid:
            findings.append({'code': 'article-source-gap',
                             'message': f'{reference or "未注明出处的条目"}需要对应到口播、板书和学生要做的推理。'})
    if not substantive:
        findings.append({'code': 'article-source-map', 'message': '请把原文的教学内容对应到课程。'})
    return findings
