"""Reusable viewer feedback. Distribute curated examples; keep observations across local skill updates."""
import argparse
from contextlib import closing
from functools import lru_cache
import json
import os
from pathlib import Path
import sqlite3
import tempfile

KINDS = ('issues', 'polyphones', 'letters')
SEEDS = Path(__file__).resolve().parents[1] / 'assets/feedback'


def database():
    override = os.environ.get('PHYSICS_NOTEBOOK_FEEDBACK_DB')
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return base / 'physics-notebook-video/feedback.sqlite3'


@lru_cache(maxsize=2)
def _snapshot(path, stamp):
    rules = {kind: {row['key']: row for row in json.loads((SEEDS / f'{kind}.json').read_text(encoding='utf-8'))}
             for kind in KINDS}
    if stamp is not None:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='reports'").fetchone():
                return rules
            for kind, key, payload in db.execute('SELECT kind, key, payload FROM reports ORDER BY id'):
                values = json.loads(payload)
                previous = rules[kind].get(key, {})
                if kind == 'polyphones' and 'expected' in values and values['expected'] != previous.get('expected'):
                    previous = {k:v for k,v in previous.items() if k != 'hint'}
                rules[kind][key] = {**previous, **values, 'key': key}
    return rules


def catalog():
    path = database().resolve()
    try:
        stat = path.stat()
    except FileNotFoundError:
        return _snapshot(path, None)
    return _snapshot(path, (stat.st_ino, stat.st_size, stat.st_mtime_ns))


def record(kind, key, observed, expected=None, lesson='', at='', scope=None, match=None, hint=None):
    from pronunciation import FREE_SYMBOL, HAN_TERM, SYLLABLE, symbol_reading
    key, observed = key.strip(), observed.strip()
    if kind not in KINDS or not key or not observed:
        raise ValueError('请记录类别、词或问题编号，以及用户实际发现的现象。')
    if kind != 'issues' and (match or scope):
        raise ValueError('读音记录按实际出现的词或字母匹配。')
    if scope and scope not in ('concept','problem','all'):
        raise ValueError('课型可填 all、concept 或 problem。')
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
    if hint and (kind != 'polyphones' or not expected or not HAN_TERM.fullmatch(hint) or len(key) != len(hint)):
        raise ValueError('本地同音提示需要已确认拼音和等长汉字。')
    values = {'observed':observed}
    for name, value in [('expected',expected), ('scope',scope), ('match',match), ('hint',hint)]:
        if value:
            values[name] = value
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True)
    path = database()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=15)) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY, kind TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
            lesson TEXT NOT NULL, location TEXT NOT NULL, received TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(kind, key, payload, lesson, location))''')
        cursor = db.execute('INSERT OR IGNORE INTO reports(kind,key,payload,lesson,location) VALUES(?,?,?,?,?)',
                            (kind,key,payload,lesson,at))
        added = bool(cursor.rowcount)
    _snapshot.cache_clear()
    return {'bank':kind,'key':key,'recorded':added,'database':str(path)}


def history():
    path = database().resolve()
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
        return [dict(bank=k,key=t,lesson=l,at=a,received=d,**json.loads(p))
                for k,t,l,a,d,p in db.execute('SELECT kind,key,lesson,location,received,payload FROM reports ORDER BY id')]


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


def check(project, lesson=None, enforce=False):
    from pronunciation import local_tts_text, matched_pronunciations, spoken_symbols, term_pattern, PHYSICS_PINYIN
    from speech_plan import apply
    project = Path(project).resolve()
    if lesson is None:
        lesson, _ = apply(project, json.loads((project/'lesson.json').read_text(encoding='utf-8')))
    rules = catalog()
    mode = lesson.get('kind', 'all')
    applicable = [r for r in rules['issues'].values() if r.get('scope','all') in ('all',mode)]
    manual = [r for r in applicable if not r.get('match')]
    hits, findings = [], []
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
            for rule in applicable:
                if rule.get('match') and rule['match'] in text:
                    flag(rule['key'], rule.get('expected') or rule['observed'], cid)
            matches = list(pattern.finditer(text))
            if matches:
                resolved = matched_pronunciations(text, speech.get('minimax_pronunciation'), cue.get('minimax_pronunciation'))
                segments = list(term_pattern(resolved).finditer(text)) if resolved else []
                default_input = local_tts_text(text, resolved)
                selected_input = local_tts_text(text, resolved, speech.get('plain_pronunciation'), cue.get('plain_pronunciation'))
            reported = set()
            for m in matches:
                key = m.group()
                expected = rules['polyphones'][key].get('expected') or PHYSICS_PINYIN.get(key)
                hits.append(dict(bank='polyphones',key=key,expected=expected,page=pid,cue=cid,context=text))
                word = next((w for w in segments if w.start() <= m.start() and w.end() >= m.end()), None)
                if expected and word:
                    pos = m.start() - word.start()
                    actual = ' '.join(resolved[word.group()].split()[pos:pos+len(key)])
                    marker = (key, word.group(), actual)
                    if actual.replace('v','ü') != expected.replace('v','ü') and marker not in reported:
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
                    hits.append(dict(bank='letters',key=key,expected=rules['letters'][key]['expected'],page=pid,cue=cid,context=text))
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
    result = {'kind':mode, 'catalog_counts':{k:len(v) for k,v in rules.items()},
              'manual_checks':manual, 'listen':hits, 'findings':findings,
              'status':'blocked' if any(x['severity']=='error' for x in findings) else 'review'}
    save_report(project/'feedback-check.json', result)
    if enforce and result['status']=='blocked':
        raise ValueError('历史反馈检查发现可定位的错误，请查看 feedback-check.json。')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    cmds = p.add_subparsers(dest='cmd', required=True)
    r = cmds.add_parser('record')
    r.add_argument('kind',choices=KINDS)
    for arg in ['key','observed','expected','lesson','at','scope','match','hint']:
        r.add_argument('--'+arg, required=arg in ('key','observed'))
    cmds.add_parser('list')
    cmds.add_parser('history')
    args = vars(p.parse_args())
    cmd = args.pop('cmd')
    if cmd == 'record':
        result = record(**{k:v for k,v in args.items() if v is not None})
    else:
        result = history() if cmd == 'history' else catalog()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
