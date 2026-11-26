"""Reusable viewer feedback. Distribute curated examples; keep observations across local skill updates."""
import argparse
from contextlib import closing
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile

from learning_bundle import DB_REL, ROOT, REPORTS, clean_note
from feedback_review import SCOPES, STATES, compare_audio, decide, decisions, replay

KINDS = ('issues', 'polyphones', 'letters')
SEEDS = Path(__file__).resolve().parents[1] / 'assets/feedback'


def database():
    override = os.environ.get('PHYSICS_NOTEBOOK_FEEDBACK_DB')
    if override:
        return Path(override).expanduser().resolve()
    return ROOT / DB_REL


@lru_cache(maxsize=2)
def _snapshot(path, stamp):
    rules = {kind: {row['key']: row for row in json.loads((SEEDS / f'{kind}.json').read_text(encoding='utf-8'))}
             for kind in KINDS}
    if stamp is not None:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='reports'").fetchone():
                return rules
            for kind, key, payload in db.execute('SELECT kind, key, payload FROM reports ORDER BY received,id'):
                values = json.loads(payload)
                previous = rules[kind].get(key, {})
                takeaway = values.get('takeaway')
                if takeaway:
                    reminders = list(dict.fromkeys([*previous.get('takeaways', []), takeaway]))
                    previous = {**previous, 'key':key, 'takeaways':reminders}
                    previous.setdefault('observed',takeaway)
                    if kind=='letters':
                        previous.setdefault('expected',values['expected'])
                    rules[kind][key] = previous
                if values.get('only_this_lesson'):
                    continue
                if kind == 'polyphones' and 'expected' in values and values['expected'] != previous.get('expected'):
                    previous = {k:v for k,v in previous.items() if k != 'hint'}
                if kind == 'polyphones' and values.get('focus'):
                    known_focus = previous.get('focus_chars', previous.get('focus', ''))
                    values['focus_chars'] = ''.join(dict.fromkeys(known_focus + values['focus']))
                rules[kind][key] = {**previous, **values, 'key': key}
    return rules


def catalog():
    path = database().resolve()
    try:
        stat = path.stat()
    except FileNotFoundError:
        return _snapshot(path, None)
    return _snapshot(path, (stat.st_ino, stat.st_size, stat.st_mtime_ns))


def record(kind, key, observed, expected=None, lesson='', at='', scope=None, match=None, hint=None, source_type=None, minimum_minutes=None, only_this_lesson=False, focus=None, example=None, card_flow=None, card_reading=None, takeaway=None, failed_stage=None):
    from pronunciation import FREE_SYMBOL, HAN_TERM, SYLLABLE, symbol_reading
    key, observed = key.strip(), observed.strip()
    if kind not in KINDS or not key or not observed:
        raise ValueError('请记录类别、词或问题编号，以及用户实际发现的现象。')
    if only_this_lesson and (not lesson.strip() or scope or minimum_minutes or hint or (expected and kind == 'polyphones')):
        raise ValueError('单课观察需要课名；读法覆盖和课时下限请分别写入本课的配音或时长设置。')
    if kind != 'issues' and (match or scope):
        raise ValueError('读音记录按实际出现的词或字母匹配。')
    if scope and scope not in ('concept','problem','all'):
        raise ValueError('课型可填 all、concept 或 problem。')
    if source_type is not None and (kind != 'issues' or source_type != 'article'):
        raise ValueError('文章课偏好须记录在问题库，source_type 填 article。')
    if minimum_minutes is not None and (kind != 'issues' or isinstance(minimum_minutes,bool)
            or not isinstance(minimum_minutes,(int,float)) or not math.isfinite(minimum_minutes) or minimum_minutes <= 0):
        raise ValueError('最低时长须为问题库中的正数分钟。')
    if kind == 'letters':
        if not FREE_SYMBOL.fullmatch(key):
            raise ValueError('字母记录需要单个字母。')
        if key.isascii():
            key = key.upper()
        standard = symbol_reading(key)
        if expected and expected != standard and expected.strip('/') != standard.split(' /')[-1].strip('/'):
            raise ValueError(f'该符号的标准字母名为 {standard}。其他听感写入 observed。')
        expected = standard
    if kind == 'polyphones':
        if not HAN_TERM.fullmatch(key):
            raise ValueError('请使用实际出现的中文词。')
        if len(key) == 1 and (expected or hint):
            raise ValueError('多音字的读法要绑定完整词语，例如用“相位”登记 xiang4 wei4；单字可先登记为待听。')
        if expected:
            syllables = expected.lower().replace('v','ü').split()
            if len(key) != len(syllables) or not all(SYLLABLE.fullmatch(s) for s in syllables):
                raise ValueError('每个汉字对应一个带 1–5 声调号的拼音音节。')
            expected = ' '.join(syllables)
    if focus and (kind != 'polyphones' or len(focus) != 1 or focus not in key or not HAN_TERM.fullmatch(focus)):
        raise ValueError('focus 填这个词中实际读错的一个汉字。')
    if hint and (kind != 'polyphones' or not expected or not HAN_TERM.fullmatch(hint) or len(key) != len(hint)):
        raise ValueError('本地同音提示需要已确认拼音和等长汉字。')
    if kind == 'issues' and key.startswith('term-flow-') and match and (
            len(match) < 2 or not HAN_TERM.fullmatch(match)):
        raise ValueError('读音卡需要完整的中文词语。')
    if card_reading or card_flow:
        if kind != 'issues' or not key.startswith('term-flow-') or not match or not HAN_TERM.fullmatch(match):
            raise ValueError('词卡连读反馈使用 term-flow-词语 和完整的 match。')
        if card_reading:
            parts = card_reading.lower().replace('v', 'ü').split()
            if len(parts) != len(match) or not all(SYLLABLE.fullmatch(v) for v in parts):
                raise ValueError('反馈词卡需要逐字带调拼音。')
            card_reading = ' '.join(parts)
    if example and (match or key) not in example and kind != 'letters':
        raise ValueError('例句需要包含所反馈的原词。')
    values = {'observed':clean_note(observed)}
    if failed_stage:
        from lesson_transfer import STAGES
        if failed_stage not in STAGES:
            raise ValueError('请选择实际查明的环节，尚未定位时选 unknown。')
        values['failed_stage'] = failed_stage
    if takeaway and takeaway.strip():
        values['takeaway'] = clean_note(takeaway.strip())
    if only_this_lesson:
        values['only_this_lesson'] = True
    for name, value in [('card_reading', card_reading), ('card_flow', card_flow), ('example', example), ('expected',expected), ('scope',scope), ('match',match), ('hint',hint), ('focus',focus), ('source_type',source_type), ('minimum_minutes',minimum_minutes)]:
        if value:
            values[name] = value
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True)
    path = database()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=15)) as db, db:
        db.execute(REPORTS)
        cursor = db.execute('INSERT OR IGNORE INTO reports(kind,key,payload,lesson,location) VALUES(?,?,?,?,?)',
                            (kind,key,payload,lesson,at))
        added = bool(cursor.rowcount)
    _snapshot.cache_clear()
    return {'bank':kind,'key':key,'recorded':added,'database':str(path)}


def history(lesson=None):
    path = database().resolve()
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='reports'").fetchone():
            return []
        sql = 'SELECT kind,key,lesson,location,received,payload FROM reports'
        rows = db.execute(sql + ' WHERE lesson=? ORDER BY received,id', (lesson,)) if lesson is not None else db.execute(sql + ' ORDER BY received,id')
        return [dict(bank=k,key=t,lesson=l,at=a,received=d,**json.loads(p)) for k,t,l,a,d,p in rows]


def save_report(path, result):
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        try:
            json.dump(result, f, ensure_ascii=False, indent=2)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def lesson_catalog(lesson):
    rules = {kind: dict(entries) for kind, entries in catalog().items()}
    title = lesson.get('title')
    if title:
        for item in history(lesson=title):
            if item.get('only_this_lesson'):
                kind, key = item['bank'], item['key']
                rules[kind][key] = {**rules[kind].get(key, {}), **item}
    return rules


def applicable_issues(lesson, rules=None):
    kind = lesson.get('kind','all')
    if rules is None:
        rules = lesson_catalog(lesson)
    return [r for r in rules['issues'].values()
            if r.get('scope','all') in ('all',kind)
            and (not r.get('source_type') or r['source_type'] == lesson.get('source_type'))]


def preparation(project,lesson):
    """A teacher can open this before a manuscript or any audio exists."""
    project=Path(project)
    rules=lesson_catalog(lesson)
    issues=applicable_issues(lesson,rules)
    lines=['# 备课前先看','', '本课按这些已发生过的问题安排讲稿、板书和动画。','']
    for issue in issues:
        for note in dict.fromkeys([issue.get('expected') or issue['observed'], *issue.get('takeaways',[])]):
            lines.append('- '+note)
    lines.extend(['','## 配音前','',
                  '写完讲稿后运行 feedback-check。按每个词和字母在本课的位置安排读法；正式音轨合成后听对应整句。',''])
    (project/'备课提醒.md').write_text('\n'.join(lines),encoding='utf-8')
    return {'issues':len(issues),'file':'备课提醒.md'}


def check(project, lesson=None, enforce=False):
    from pronunciation import local_tts_text, matched_pronunciations, spoken_symbols, term_pattern, PHYSICS_TERMS, PHYSICS_PINYIN, tone_targets, pronunciation_trial
    from speech_plan import apply
    project = Path(project).resolve()
    if lesson is None:
        lesson, _ = apply(project, json.loads((project/'lesson.json').read_text(encoding='utf-8')))
    from term_inventory import apply as apply_inventory
    lesson = apply_inventory(project,lesson)
    rules = lesson_catalog(lesson)
    from term_flow import candidate_terms, identify, script_inventory, term_counts
    from card_speech import lesson_inputs
    occurrences = identify(lesson, rules=rules)
    plans = lesson_inputs(lesson,occurrences)
    prep=preparation(project,lesson)
    mode = lesson.get('kind', 'all')
    applicable = applicable_issues(lesson, rules)
    manual = [r for r in applicable if not r.get('match')]
    hits, findings, tones = [], [], []
    conflict_file=Path(__file__).resolve().parents[1]/'assets/learning/reference-conflicts.json'
    if conflict_file.is_file():
        pending=[r for r in json.loads(conflict_file.read_text()) if r.get('status')=='pending']
        if pending:
            findings.append(dict(key='learning-conflict',severity='error',page=None,cue=None,
                message='随行学习资料有两份独立修改待合并，请查看 assets/learning/reference-conflicts.json，核实并合并词义、读法与教学记录后再配音。'))
    speech = lesson.get('speech', {})
    pattern = term_pattern(rules['polyphones'])
    for i, page in enumerate(lesson.get('pages', []), 1):
        pid = page.get('id', f'p{i:02d}')
        def flag(key, message, cue=None, severity='review'):
            findings.append(dict(key=key, page=pid, cue=cue, severity=severity, message=message))
        if page.get('camera',lesson.get('camera')) == 'focus':
            flag('camera','本页启用了镜头移动，查看讲解中是否发生意外缩放。')
        if page.get('show_title',lesson.get('show_titles')) is True:
            flag('page-title','本页开启了页标题，区分片头与正课页。')
        for cue in page.get('cues', []):
            cid = cue['id']
            text = cue.get('tts', cue.get('text',''))
            plan = plans[str(page.get('id',i)),str(cid)]
            for term in plan['conflicts'] + (plan['provider_exclusions'] if speech.get('backend')=='minimax' else []):
                flag(term, f'同一句中的“{term}”需要在 speech.term_uses 指定可区分的配音词形 spoken_as。',cid,'error')
            cue_tones = tone_targets(text, speech.get('minimax_pronunciation'), cue.get('minimax_pronunciation'),plan['targets'])
            tones.extend(dict(page=pid, cue=cid, context=text, **item) for item in cue_tones)
            for item in cue_tones:
                for c in item['conflicts']:
                    flag(c['word'], f"“{c['word']}”中的“{c['char']}”应读 {c['expected']}，"
                         f"本句的“{item['term']}”配置为 {c['configured']}。", cid, 'error')
            if speech.get('minimax_pronunciation') or cue.get('minimax_pronunciation'):
                configured = matched_pronunciations(text, speech.get('minimax_pronunciation'), cue.get('minimax_pronunciation'))
                already = {c['word'] for row in cue_tones for c in row['conflicts']}
                for term, actual in configured.items():
                    expected = PHYSICS_TERMS.get(term)
                    if term not in already and term not in rules['polyphones'] and expected and actual.replace('v','ü') != expected.replace('v','ü'):
                        flag(term, f'“{term}”在本句配置为 {actual}，学科词表读 {expected}。', cid, 'error')
            for rule in applicable:
                phrases = [rule['match']] if rule.get('match') else rule.get('review_phrases', ())
                if any(term_pattern([phrase]).search(text) for phrase in phrases):
                    flag(rule['key'], rule.get('expected') or rule['observed'], cid)
            matches = list(pattern.finditer(text))
            if matches:
                resolved = matched_pronunciations(text, speech.get('minimax_pronunciation'), cue.get('minimax_pronunciation'))
                segments = list(term_pattern(resolved).finditer(text)) if resolved else []
                default_input = local_tts_text(text, resolved)
                selected_input = local_tts_text(text, resolved, speech.get('plain_pronunciation'), cue.get('plain_pronunciation'))
            located = {c['offset'] for row in cue_tones for c in row['conflicts']}
            reported = set()
            for m in matches:
                key = m.group()
                expected = rules['polyphones'][key].get('expected') or PHYSICS_PINYIN.get(key)
                word = next((w for w in segments if w.start() <= m.start() and w.end() >= m.end()), None)
                ambiguous = rules['polyphones'][key].get('context_required') and (
                    word is None or word.group() == key or word.group() not in PHYSICS_PINYIN)
                choice = next((r for r in plan['targets'] if r['term']==key and r['offset']==m.start()
                               and r.get('reading_source')),None)
                if choice:
                    expected, ambiguous = choice['expected'], False
                hits.append(dict(bank='polyphones',key=key,expected=None if ambiguous else expected,
                                 page=pid,cue=cid,context=text,
                                 **({'context_note':'结合原句确认物理义项，矢量分量读 '+expected} if ambiguous and expected else {})))
                if expected and word and not ambiguous and not choice:
                    pos = m.start() - word.start()
                    actual = ' '.join(resolved[word.group()].split()[pos:pos+len(key)])
                    marker = (key, word.group(), actual)
                    if (not any(index in located for index in range(m.start(), m.end()))
                            and actual.replace('v','ü') != expected.replace('v','ü') and marker not in reported):
                        flag(key,f'“{word.group()}”配置的 {actual} 与反馈库 {expected} 有冲突。',cid,'error')
                        reported.add(marker)
                selection = slice(m.start(),m.end())
                hint = rules['polyphones'][key].get('hint')
                default, selected = default_input[selection], selected_input[selection]
                if hint and default != selected and (key,selected) not in reported:
                    flag(key,f'本地配音输入把“{key}”读作提示“{selected}”，默认提示为“{default}”，请用最终音色试听。',cid)
                    reported.add((key,selected))
            for key in dict.fromkeys(m.group().upper() if m.group().isascii() else m.group() for m in spoken_symbols(text)):
                if key in rules['letters']:
                    hits.append(dict(bank='letters',key=key,expected=rules['letters'][key]['expected'],viewer_note=rules['letters'][key].get('observed',''),page=pid,cue=cid,context=text))
            if cue.get('audio'):
                meta = (project / cue['audio']).with_suffix('.json')
                if meta.is_file():
                    take = json.loads(meta.read_text(encoding='utf-8'))
                    if isinstance(take,dict) and take.get('raw_file'):
                        try:
                            tempo = float(take.get('tempo',1))
                        except (ValueError, TypeError):
                            flag('pacing','原录音有变速记录，需与实际选用的音轨比较。',cid)
                        else:
                            if 0 < tempo < .999:
                                flag('pacing','已选用经过降速的录音，请换回对应的原速录音。',cid,'error')
    from classroom_terms import learning_cards
    for row in occurrences:
        if row['split_in_script']:
            findings.append(dict(key='term-flow-split', severity='error', page=row['page'], cue=row['cue'],
                                 message=f"“{row['term']}”被切开。请将完整术语放在同一条口播中：{row['text']}"))
    missing_readings = {}
    for row in occurrences:
        if not row['expected']:
            missing_readings.setdefault(row['term'], []).append(row['id'])
    for term, locations in missing_readings.items():
        findings.append(dict(key='term-reading-needed', severity='error',
                             message=f'“{term}”出现 {len(locations)} 次，需要按本课语境在 speech.physics_terms 补全拼音。'))
    script_rows = script_inventory(lesson,occurrences)
    if lesson.get('term_inventory_version',1)>=2:
        for row in script_rows:
            if not row['reviewed']:
                findings.append(dict(key='semantic-inventory-pending',severity='error',page=row['page'],cue=row['cue'],
                    message='制作端须对照这句完整口播和板书盘点物理术语，记录词义与读法；空的补词列表不作为完成记录。'))
    candidates = candidate_terms(lesson,occurrences,script_rows)
    for term,locations in candidates.items():
        findings.append(dict(key='term-candidate',severity='review',page=locations[0]['page'],cue=locations[0]['cue'],
            message=f'“{term}”可能是新术语，按原句补入 speech.physics_terms；本课中的普通短语可记入 speech.non_terms。'))
    from speech_context import inventory
    priority = {r['term'] for r in occurrences if r['priority']}
    classroom_sentences = [r for r in inventory(lesson, priority=priority) if r['targets']]
    for hit in hits:
        reminders=rules[hit['bank']][hit['key']].get('takeaways',[])
        if reminders:
            hit['listen_for']=reminders
    from lesson_transfer import classroom_checks, attach_retests
    result = {'preparation':prep,'speech_context':classroom_sentences, 'kind':mode, 'catalog_counts':{k:len(v) for k,v in rules.items()},
              'learning_checks':classroom_checks(lesson,occurrences,plans,applicable,history()),
              'physics_terms':term_counts(occurrences), 'term_occurrences':occurrences,
              'terms_needing_readings':missing_readings, 'term_candidates':candidates,
              'synthesis_targets':[dict(page=p,cue=c,**plan) for (p,c),plan in plans.items()],
              'term_script_inventory':script_rows,'classroom_cards':learning_cards(occurrences),
              'manual_checks':manual, 'listen':hits, 'tone_targets':tones, 'pronunciation_trial':pronunciation_trial(tones), 'findings':findings,
              'replay':replay(lesson, applicable, hits, findings),
              'status':'blocked' if any(x['severity']=='error' for x in findings) else 'review'}
    from trial_materials import build_plan, lesson_stamp
    attach_retests(result['learning_checks'],database().resolve())
    trials = build_plan(lesson=lesson, max_extra=12)
    trials.update(project=str(project.resolve()), lesson_files=lesson_stamp(project))
    save_report(project/'voice-trial-plan.json', trials)
    result['voice_trials'] = {'plan':'voice-trial-plan.json','sentences':len(trials['items']),
        'deferred':len(trials['coverage']['deferred']),
        'needs_material':len(trials['coverage']['needs_material']),
        'final_occurrence_review_required':True}
    save_report(project/'feedback-check.json', result)
    if enforce and (result['status']=='blocked' or candidates):
        raise ValueError('历史反馈检查发现可定位的错误，请查看 feedback-check.json。')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    cmds = p.add_subparsers(dest='cmd', required=True)
    r = cmds.add_parser('record')
    r.add_argument('kind',choices=KINDS)
    for arg in ['key','observed','expected','lesson','at','scope','match','hint','focus']:
        r.add_argument('--'+arg, required=arg in ('key','observed'))
    r.add_argument('--takeaway',help='下次遇到同类内容时，具体检查什么')
    from lesson_transfer import STAGES
    r.add_argument('--failed-stage',choices=STAGES,help='复查定位到问题第一次出现的环节')
    r.add_argument('--example')
    r.add_argument('--card-flow')
    r.add_argument('--card-reading')
    learn = cmds.add_parser('record-term', help='记录整词反馈，供新课的读音卡直接使用')
    learn.add_argument('term')
    learn.add_argument('--observed', required=True)
    for option in ('example','reading','flow','lesson','at','takeaway'):
        learn.add_argument('--'+option)
    learn.add_argument('--failed-stage',choices=STAGES)
    r.add_argument('--source-type', choices=['article'])
    r.add_argument('--minimum-minutes', type=float)
    r.add_argument('--only-this-lesson', action='store_true')
    pair = cmds.add_parser('compare-audio', help='按 A、B 顺序以原速拼接两个短句样本供试听')
    pair.add_argument('before')
    pair.add_argument('after')
    pair.add_argument('--output', required=True)
    review = cmds.add_parser('decide', help='保存候选办法、采用依据或撤回理由')
    review.add_argument('kind', choices=KINDS)
    review.add_argument('--state', required=True, choices=STATES)
    review.add_argument('--scope', required=True, choices=SCOPES)
    for name in ('key', 'action', 'evidence', 'before', 'example', 'lesson', 'model', 'reference-sha256', 'sample'):
        review.add_argument('--'+name, required=name in ('key', 'action', 'evidence'))
    cmds.add_parser('reviews', help='按时间显示本地修订历史和样本')
    cmds.add_parser('trial-audit',help='列出各项最新状态，以及该版本改法的跨课复试')
    retest=cmds.add_parser('retest',help='用另一课的真实材料记录复试结果')
    retest.add_argument('--decision-id',type=int,required=True)
    for name in ('lesson','text','method','outcome','evidence','sample','model','voice-sha256','actual-input'):
        retest.add_argument('--'+name,required=name in ('lesson','text','method','outcome','evidence'))
    cmds.add_parser('list')
    bridge=cmds.add_parser('import-learning',help='合并已有的制课学习记录及试听片段')
    bridge.add_argument('source',type=Path)
    cmds.add_parser('history')
    args = vars(p.parse_args())
    cmd = args.pop('cmd')
    if cmd == 'record-term':
        term = args.pop('term')
        result = record('issues','term-flow-'+term, args['observed'], match=term, example=args['example'],
                        card_reading=args['reading'],card_flow=args['flow'],takeaway=args.get('takeaway'),lesson=args['lesson'] or '',at=args['at'] or '',failed_stage=args.get('failed_stage'))
    elif cmd == 'record':
        result = record(**{k:v for k,v in args.items() if v is not None})
    elif cmd == 'import-learning':
        from learning_bundle import merge
        if not args['source'].is_file():
            raise FileNotFoundError(args['source'])
        result=merge(args['source'],database())
    elif cmd == 'compare-audio':
        result = compare_audio(**args)
    elif cmd == 'decide':
        result = decide(**{k:v for k,v in args.items() if v is not None})
    elif cmd == 'trial-audit':
        from lesson_transfer import trial_audit
        result=trial_audit(database().resolve())
    elif cmd == 'retest':
        from lesson_transfer import record_retest
        result=record_retest(database().resolve(),**{k:v for k,v in args.items() if v is not None})
    elif cmd == 'reviews':
        result = decisions(database().resolve())
    else:
        result = history() if cmd == 'history' else catalog()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
