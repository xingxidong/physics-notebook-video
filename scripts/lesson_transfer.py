"""Turn past classroom observations into located checks on a different lesson."""
from collections import defaultdict

STAGES = ('inventory', 'script', 'synthesis', 'editing', 'board', 'export', 'unknown')
FORMULA_ISSUES = ('formula-narration-sync', 'formula-without-speaking', 'simultaneous-formula-writing')


def classroom_checks(lesson, occurrences, plans, applicable, reports):
    title = lesson.get('title','')
    active = {r['key']:r for r in applicable}
    previous = defaultdict(list)
    for row in reports:
        if row.get('only_this_lesson') and row.get('lesson') != title and not row.get('takeaway'):
            continue
        if row.get('scope','all') not in ('all', lesson.get('kind')):
            continue
        if row.get('source_type') and row['source_type'] != lesson.get('source_type'):
            continue
        previous[row['bank'],row['key']].append(row)
    by_word = defaultdict(list)
    for k,rule in active.items():
        if k.startswith(('connected-physics-term-', 'term-flow-')) and rule.get('match'):
            by_word[rule['match']].append(('issues',k))

    guidance = {}
    locations = []
    def link(keys):
        refs=[]
        for bank,key in keys:
            history=previous.get((bank,key),[])
            if not history:
                continue
            ref=bank+'/'+key
            if ref not in guidance:
                guidance[ref]={'bank':bank,'key':key,'observations':len(history),
                    'located_causes':sorted({r['failed_stage'] for r in history if r.get('failed_stage')}),
                    'takeaways':list(dict.fromkeys(r['takeaway'] for r in history if r.get('takeaway')))}
            refs.append(ref)
        return refs

    for row in occurrences:
        word=row['term']
        refs=link([('polyphones',word),*by_word.get(word,[])])
        if refs:
            locations.append(dict(kind='term',page=row['page'],cue=row['cue'],offset=row['offset'],
                                  text=word,expected=row.get('expected'),refs=refs,
                                  split_in_script=row['split_in_script']))
    for (page,cue),plan in plans.items():
        for item in plan['symbols']:
            letter=item['symbol']
            key=letter.upper() if letter.isascii() else letter
            refs=link([('letters',key)])
            if refs:
                locations.append(dict(kind='letter',page=page,cue=cue,offset=item['offset'],
                                      text=item['expression'],expected=item['expected'],refs=refs))
    formula_refs=link([('issues',k) for k in FORMULA_ISSUES if k in active])
    if formula_refs:
        for pi,page in enumerate(lesson.get('pages',[]),1):
            for ci,cue in enumerate(page.get('cues',[]),1):
                for index,action in enumerate(cue.get('actions',[])):
                    if action.get('type')=='math' and not action.get('prewritten'):
                        locations.append(dict(kind='formula',page=str(page.get('id',pi)),
                            cue=str(cue.get('id',ci)),action_index=index,action_id=action.get('id'),
                            formula=action.get('latex',action.get('value')),refs=formula_refs))
    return {'references':guidance,'occurrences':locations,
            'check_in_final':{'term':['读音','词内连读'],'letter':['字母名','两侧汉字与上下标'],
                              'formula':['读到的运算','对应笔迹出现的次序']}}


def decision_hash(item):
    # IDs and sample paths can change when two installations are merged.
    from hashlib import sha256
    import json
    body={k:v for k,v in item.items() if k not in ('id','received','sample','cross_lesson_tests','earlier_tests')}
    return sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def record_retest(path, decision_id, *, lesson, text, method, outcome, evidence, sample=None,
                  model='', voice_sha256='', actual_input=''):
    from contextlib import closing
    from pathlib import Path
    import hashlib, json, re, sqlite3
    from feedback_review import decisions
    from learning_bundle import RETESTS, keep_sample, sha
    item=next((r for r in decisions(path) if r['id']==decision_id),None)
    if not item or not all(x.strip() for x in (lesson,text,evidence)) or lesson.strip()==item['lesson'].strip():
        raise ValueError('选择已有改法，填写另一节课、完整课堂句及实际观察。')
    if method not in ('audio_probe','producer_listen','author_listen','board_timing','content_review') or outcome not in ('supported','problem','inconclusive'):
        raise ValueError('请分别标明检查方法和本次结果。')
    row=dict(lesson=lesson.strip(),text=text.strip(),method=method,outcome=outcome,evidence=evidence.strip())
    if method in ('audio_probe','producer_listen','author_listen'):
        if not sample or not model.strip() or not actual_input.strip():
            raise ValueError('声音复试须留下实际短样、模型和送入文字。')
    if voice_sha256 and not re.fullmatch('[a-fA-F0-9]{64}',voice_sha256):
        raise ValueError('参考音色指纹应为 SHA256。')
    if sample:
        clip=Path(sample).expanduser().resolve(strict=True)
        checksum=sha(clip)
        row.update(model=model.strip(),voice_sha256=voice_sha256.lower(),actual_input=actual_input.strip(),
                   sample=keep_sample(path,clip,checksum),sample_sha256=checksum)
    revision=decision_hash(item)
    payload=json.dumps(row,ensure_ascii=False,sort_keys=True)
    key=hashlib.sha256((revision+payload).encode()).hexdigest()
    with closing(sqlite3.connect(path,timeout=30)) as db,db:
        db.execute(RETESTS)
        added=db.execute('INSERT OR IGNORE INTO classroom_retests VALUES(?,?,?)',(key,revision,payload)).rowcount
    return {'recorded':bool(added),'decision_hash':revision,'event_uid':key}


def trial_audit(path):
    from contextlib import closing
    import sqlite3,json
    from feedback_review import decisions
    path=path.resolve()
    latest={}
    revisions=defaultdict(list)
    for r in decisions(path):
        selector=(r['bank'],r['key'],r['scope'],r['lesson'] if r['scope']=='lesson' else '',r['model'],r['reference_sha256'])
        latest[selector]=r
        key=decision_hash(r)
        if key not in revisions[selector]:
            revisions[selector].append(key)
    tests=defaultdict(list)
    if path.is_file():
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='classroom_retests'").fetchone():
                for key,payload in db.execute('SELECT decision_hash,payload FROM classroom_retests ORDER BY rowid'):
                    tests[key].append(json.loads(payload))
    return [{**r,'cross_lesson_tests':tests[decision_hash(r)],
             'earlier_tests':[dict(decision_hash=k,**test) for k in revisions[sel]
                              if k!=decision_hash(r) for test in tests[k]]}
            for sel,r in latest.items()]


def attach_retests(checks, path):
    for record in trial_audit(path):
        ref=checks['references'].get(record['bank']+'/'+record['key'])
        if not ref or record['state']=='withdrawn':
            continue
        for test in record['cross_lesson_tests']:
            ref.setdefault('other_lesson_results',[]).append({
                'lesson':test['lesson'],'method':test['method'],'outcome':test['outcome'],
                'evidence':test['evidence'],'decision_hash':decision_hash(record)})

