"""Build voice trials from fixed sentences, portable cards, feedback and a lesson."""
import copy
import hashlib
import json
from pathlib import Path

from card_speech import lesson_inputs
from classroom_terms import ARCHIVE, learning_cards, letter_card, practice, reference_examples, saved_cards
from feedback_bank import catalog, history, save_report
from term_inventory import script_text

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'assets/starter-kit/voice-trial/sentences.json'
SPEECH_FIELDS = ('physics_terms', 'term_uses', 'non_terms', 'plain_pronunciation',
                 'minimax_pronunciation')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def case_context(lesson, page, cue):
    """Keep semantic choices, not credentials or machine-specific speech settings."""
    result = {'kind': lesson.get('kind', 'problem'), 'title': lesson.get('title', ''),
            'speech': {k: copy.deepcopy(lesson['speech'][k]) for k in SPEECH_FIELDS
                       if k in lesson.get('speech', {})},
            '_term_inventory': copy.deepcopy(lesson.get('_term_inventory', {})),
            'pages': [{'id': str(page['id']), 'cues': [{k: copy.deepcopy(v) for k, v in cue.items()
                      if k in ('id', 'tts', 'text', 'plain_pronunciation', 'minimax_pronunciation')}]}]}
    if 'term_uses' in result['speech']:
        result['speech']['term_uses'] = [r for r in result['speech']['term_uses']
            if (r['page'], r['cue']) == (str(page['id']), str(cue['id']))]
    return result


def make_case(ident, text, origin, *, context=None, flow='', fallback=(), sources=()):
    context = copy.deepcopy(context or {'pages': [{'id': 'trial', 'cues': [{'id': ident, 'tts': text}]}]})
    page = context['pages'][0]
    cue = page['cues'][0]
    cue['tts'] = text
    from term_flow import identify
    occurrences = identify(context)
    plan = lesson_inputs(context, occurrences)[str(page['id']), str(cue['id'])]
    hits = list(plan['targets'])
    hits.extend(r for r in occurrences if not r['expected'] and not r['split_in_script'])
    known = {(r['term'], r['offset']) for r in hits}
    for row in fallback:
        if (row['term'], row['offset']) not in known:
            hits.append(dict(row, expected=row.get('pinyin', '')))
    cards = learning_cards(hits)
    rules = catalog()
    targets = []
    for row in hits:
        term, offset = row['term'], row['offset']
        if not text.startswith(term, offset):
            raise ValueError(f'{ident}: 术语位置与原句不符：{term}')
        card = {key: value for key, value in cards.get(term, {}).items()
                if key != 'course_examples'}
        expected = row.get('expected', '')
        if (term, offset) not in known:
            readings = [r for r in card.get('readings', []) if r]
            expected = card.get('feedback_reading') or (readings[0] if len(readings) == 1 else expected)
        keys = []
        if term in rules['polyphones']:
            keys.append(['polyphones', term])
        keys.extend(['issues', k] for k, v in rules['issues'].items()
                    if k.startswith('term-flow-') and v.get('match') == term)
        targets.append({'id': f'term@{offset}:{term}', 'kind': 'term', 'term': term,
                        'offset': offset, 'pinyin': expected, 'flow': card.get('flow', '整词连读。'),
                        'card_fingerprint': fingerprint(card), 'feedback_keys': keys,
                        'observed': card.get('feedback', '')})
    for symbol in plan['symbols']:
        card = letter_card(symbol['symbol']) or {}
        card.pop('reference_examples', None)
        key = symbol['symbol'].upper()
        targets.append({'id': f"letter@{symbol['offset']}:{symbol['expression']}", 'kind': 'letter',
                        'term': symbol['symbol'], 'expression': symbol['expression'],
                        'offset': symbol['offset'], 'pinyin': symbol['expected'],
                        'flow': symbol.get('listen_for', '字母与两侧中文自然衔接。'),
                        'card_fingerprint': fingerprint(card),
                        'feedback_keys': [['letters', key]] if key in rules['letters'] else [],
                        'observed': rules['letters'].get(key, {}).get('observed', '')})
    targets.sort(key=lambda x: (x['offset'], x['id']))
    checks = [{'id': axis + ':' + row['id'], 'target': row['id'], 'axis': axis}
              for row in targets for axis in ('pronunciation', 'flow')]
    checks.extend({'id': axis, 'axis': axis} for axis in ('voice', 'continuity', 'delivery'))
    result = dict(id=ident, text=text, origin=origin, sources=list(sources), flow=flow,
                  targets=targets, checks=checks, context=context, fallback=list(fallback),
                  planned_input=plan, review_status='pending')
    result['material_fingerprint'] = fingerprint({k: result[k] for k in
        ('text', 'flow', 'targets', 'checks', 'planned_input')})
    return result


def refresh(row):
    return make_case(row['id'], row['text'], row['origin'], context=row.get('context'),
                     flow=row.get('flow', ''), fallback=row.get('fallback', ()), sources=row.get('sources', ()))


def load_lesson(project):
    from speech_plan import apply
    from term_inventory import apply as apply_inventory
    project = Path(project).resolve()
    lesson, _ = apply(project, json.loads((project / 'lesson.json').read_text()))
    return apply_inventory(project, lesson)


def lesson_stamp(project):
    return {name: hashlib.sha256((Path(project) / name).read_bytes()).hexdigest()
            for name in ('classroom-start.json', 'lesson.json', 'speech-plan.json', 'term-inventory.json')
            if (Path(project) / name).is_file()}


def build_plan(project=None, *, lesson=None, max_extra=16, rotation=0):
    if max_extra < 0 or rotation < 0:
        raise ValueError('试音句数和轮换编号须为非负数。')
    fixed = json.loads(FIXTURE.read_text())['items']
    cases = [make_case(r['id'], r['text'], 'fixed', flow=r['flow'], fallback=r['targets']) for r in fixed]
    pool, missing = [], []
    rules, reports = catalog(), history()
    recent = {(r['bank'], r['key']): i for i, r in enumerate(reports)}
    words = set(rules['polyphones']) | {r['match'] for k, r in rules['issues'].items()
                                      if k.startswith('term-flow-') and r.get('match')}
    cards = learning_cards([{'term': term} for term in words])
    for bank, entries in rules.items():
        for key, rule in entries.items():
            if bank == 'issues' and not key.startswith(('term-flow-', 'speech-trial-')):
                continue
            term = rule.get('match', key)
            card = letter_card(key) if bank == 'letters' else cards.get(term, {})
            card = card or {}
            examples = [rule.get('example'), card.get('feedback_example'), card.get('example')]
            examples += [s for s, targets in practice()['pairs'] if any(t == term for t, _ in targets)]
            text = next((s for s in examples if s and (term in s or
                        (bank == 'letters' and key.lower() in s.lower()))), None)
            if not text:
                missing.append({'bank': bank, 'key': key, 'term': term, 'reason': '需要含该词的完整课堂例句'})
                continue
            ident = 'history-' + fingerprint([bank, key, text])[:14]
            row = make_case(ident, text, 'history', sources=[{'bank': bank, 'key': key}],
                            flow=card.get('flow', card.get('listen_for', '听整句中的声调与连读。')))
            pool.append((3, recent.get((bank, key), -1), row))
    lesson = load_lesson(project) if project else lesson
    occurrences = []
    spoken_lines = []
    if lesson:
        lesson = copy.deepcopy(lesson)
        for pi, page in enumerate(lesson.get('pages', []), 1):
            page.setdefault('id', str(pi))
            for ci, cue in enumerate(page.get('cues', []), 1):
                cue.setdefault('id', str(ci))
        from term_flow import identify, script_inventory
        occurrences = identify(lesson)
        for page in lesson.get('pages', []):
            for cue in page.get('cues', []):
                text = script_text(cue)
                spoken_lines.append(text)
                ident = 'lesson-' + fingerprint([page['id'], cue['id'], text])[:14]
                row = make_case(ident, text, 'lesson', context=case_context(lesson, page, cue),
                                sources=[{'page': page['id'], 'cue': cue['id']}])
                if row['targets'] or lesson.get('classroom_workflow_version')==1:
                    pool.append((4 if any(x['feedback_keys'] for x in row['targets']) else 2, 0, row))
        semantic_pending = [dict(page=r['page'], cue=r['cue']) for r in script_inventory(lesson, occurrences)
                            if not r['reviewed']] if lesson.get('term_inventory_version', 1) >= 2 else []
    else:
        semantic_pending = []
    archive = saved_cards(ARCHIVE)
    library = [(term, c['example']) for term, c in sorted(archive.items()) if c.get('example') and term in c['example']]
    if library:
        start = (rotation * max(1, max_extra)) % len(library)
        library = library[start:] + library[:start]
    # Resolve only the candidates needed this round. All other cards remain explicitly untested.
    library_candidates = library[:max_extra]
    for index, (term, text) in enumerate(library_candidates):
        row = make_case('card-' + fingerprint([term, text])[:14], text, 'card', sources=[{'card': term}])
        pool.append((1, -index, row))
    lecture_text = '\n'.join(spoken_lines)
    reference_rows = list(reference_examples())
    if reference_rows:
        start = (rotation * max(1, max_extra)) % len(reference_rows)
        reference_rows = reference_rows[start:] + reference_rows[:start]
    if lesson:
        ranked = [(sum(len(word) for word in row['keywords'] if word in lecture_text), row)
                  for row in reference_rows]
        reference_rows = [row for score, row in sorted(ranked, key=lambda item: -item[0]) if score]
    for index, example in enumerate(reference_rows[:max_extra]):
        reference = {key: example[key] for key in ('source', 'kind', 'evidence', 'formula')}
        ident = 'reference-' + fingerprint([reference, example['text']])[:14]
        row = make_case(ident, example['text'], 'card', flow=example['flow'], sources=[reference])
        if row['targets']:
            pool.append((2, -index, row))
    seen = {fingerprint([x['text'], x['planned_input']]): x for x in cases}
    candidates, deferred = [], []
    for priority, rank, row in sorted(pool, key=lambda item: (-item[0], -item[1], item[2]['id'])):
        key = fingerprint([row['text'], row['planned_input']])
        if key in seen:
            seen[key]['sources'].extend(x for x in row['sources'] if x not in seen[key]['sources'])
            continue
        seen[key] = row
        candidates.append(row)
    # Give each source a place before filling by risk. New course/card examples
    # must not be permanently starved by a large historical-error collection.
    extra = []
    for origin in ('history', 'lesson', 'card'):
        if len(extra) < max_extra:
            match = next((r for r in candidates if r['origin'] == origin), None)
            if match:
                extra.append(match)
    for row in candidates:
        if row in extra:
            continue
        if len(extra) < max_extra:
            extra.append(row)
        else:
            deferred.append({'id': row['id'], 'text': row['text'], 'origin': row['origin'],
                             'sources': row['sources'], 'reason': '本轮试音预算未选入，尚未检查'})
    cases += extra
    result = {'schema': 2, 'items': cases, 'max_extra': max_extra, 'rotation': rotation,
              'project': str(Path(project).resolve()) if project else None,
              'lesson_files': lesson_stamp(project) if project else {},
              'coverage': {'fixed_sentences': len(fixed), 'selected_extra': len(extra),
                           'card_count': len(archive), 'deferred': deferred, 'needs_material': missing,
                           'selected_by_source': {o: sum(r['origin'] == o for r in extra)
                                                  for o in ('history', 'lesson', 'card')},
                           'cards_without_example': sum(not c.get('example') for c in archive.values()),
                           'library_candidates_this_round': len(library_candidates),
                           'library_examples_outside_this_round': max(0, len(library) - len(library_candidates)),
                           'lesson_term_occurrences': len(occurrences), 'semantic_pending': semantic_pending},
              'final_review': {'required': True, 'scope': '本课每个术语和字母的每次出现；试音结果不代替成片检查。'},
              'status': 'planned_not_listened'}
    result['fingerprint'] = fingerprint([r['material_fingerprint'] for r in cases])
    return result


def check_plan(plan):
    if plan.get('project') and lesson_stamp(plan['project']) != plan['lesson_files']:
        raise ValueError('讲稿、配音设置或术语盘点已改变，请重新生成试音计划。')
    changed = [r['id'] for r in plan['items'] if refresh(r)['material_fingerprint'] != r['material_fingerprint']]
    if changed:
        raise ValueError('读音卡或历史反馈已更新，请重新生成相关试音材料：' + ', '.join(changed))


def write_plan(path, **kwargs):
    plan = build_plan(**kwargs)
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    save_report(path, plan)
    return plan
