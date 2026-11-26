"""Local evidence and revision history for reusable viewer corrections."""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from uuid import uuid4
from learning_bundle import prepare_decisions, keep_sample, resolve_sample
from contextlib import closing
from pathlib import Path

STATES = ('trial', 'adopted', 'withdrawn')
SCOPES = ('lesson', 'concept', 'problem', 'all')


def digest(path):
    with path.open('rb') as source:
        result = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
        return result.hexdigest()


def decisions(path):
    if not path.is_file():
        return []
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=15)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='decisions'").fetchone():
            return []
        rows = db.execute('SELECT id, received, payload FROM decisions ORDER BY received,id')
        return [dict(id=i, received=t, **json.loads(payload)) for i, t, payload in rows]


def decide(kind, key, state, scope, action, evidence, lesson='', before='', example='',
           model='', reference_sha256='', sample=None):
    from feedback_bank import catalog, database, lesson_catalog
    key = key.strip()
    if kind == 'letters' and key.isascii():
        key = key.upper()
    available = lesson_catalog({'title': lesson.strip()}) if scope == 'lesson' else catalog()
    if key not in available.get(kind, {}):
        raise ValueError('请先用 record 登记原始反馈，再用相同的问题编号记录判断。')
    if state not in STATES or scope not in SCOPES:
        raise ValueError('请选择有效的状态和适用课型。')
    if not action.strip() or not evidence.strip() or (scope == 'lesson' and not lesson.strip()):
        raise ValueError('请写明做法、判断依据，并为单课修订填写课名。')
    model, reference_sha256 = model.strip(), reference_sha256.strip().lower()
    if bool(model) != bool(reference_sha256) or (model and not re.fullmatch('[0-9a-f]{64}', reference_sha256)):
        raise ValueError('音色比较需要实际模型名称和参考音频的 SHA256。')
    if sample and not model:
        raise ValueError('请把声音样本绑定到模型和音色。')
    if kind in ('letters', 'polyphones') and model and state == 'adopted' and not sample:
        raise ValueError('采用某一音色的具体读法需要保留选中的样本。')
    data = dict(bank=kind, key=key, state=state, scope=scope, action=action.strip(),
                evidence=evidence.strip(), lesson=lesson.strip(), before=before.strip(),
                example=example.strip(), model=model, reference_sha256=reference_sha256)
    if sample:
        path = Path(sample).expanduser().resolve(strict=True)
        checksum=digest(path)
        data.update(sample=keep_sample(database().resolve(),path,checksum), sample_sha256=checksum)
    # A new decision replaces only the same rule, audience and voice.
    identity = (kind, key, scope, data['lesson'] if scope == 'lesson' else '', model, reference_sha256)
    selector = json.dumps(identity, ensure_ascii=False)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    path = database()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=15)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        prepare_decisions(db)
        previous = db.execute('SELECT id,payload FROM decisions WHERE selector=? ORDER BY received DESC,id DESC LIMIT 1',
                              (selector,)).fetchone()
        if previous and previous[1] == payload:
            return {'id':previous[0], 'recorded':False}
        cursor = db.execute('INSERT INTO decisions(selector,payload,event_uid) VALUES(?,?,?)', (selector,payload,uuid4().hex))
        return {'id':cursor.lastrowid, 'recorded':True}


def compare_audio(before, after, output):
    both = [Path(name).expanduser().resolve(strict=True) for name in (before, after)]
    target = Path(output).expanduser().resolve()
    if target.suffix.lower() != '.wav' or target in both:
        raise ValueError('请选择新的 WAV 文件作为试听输出。')
    if target.exists():
        raise FileExistsError(target)
    graph = ('[0:a]aresample=24000,aformat=channel_layouts=mono[a];'
             'anullsrc=r=24000:cl=mono,atrim=duration=0.65[p];'
             '[1:a]aresample=24000,aformat=channel_layouts=mono[b];'
             '[a][p][b]concat=n=3:v=0:a=1[out]')
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        rendered = Path(tmp) / 'pair.wav'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(both[0]), '-i', str(both[1]),
                        '-filter_complex', graph, '-map', '[out]', '-c:a', 'pcm_s16le', str(rendered)], check=True)
        # Publish the complete pair only if the requested name is still unused.
        os.link(rendered, target)
    return dict(A=str(both[0]), B=str(both[1]), output=str(target))


def voice_context(lesson):
    profile = lesson.get('speech', {}).get('feedback_voice', {})
    if profile and (not isinstance(profile, dict) or not isinstance(profile.get('model'), str)
                    or not profile['model'].strip() or not isinstance(profile.get('reference_sha256'), str)
                    or not re.fullmatch('[0-9a-fA-F]{64}', profile['reference_sha256'])):
        raise ValueError('speech.feedback_voice 需要 model 和参考音频的 SHA256。')
    return (profile.get('model', '').strip(), profile.get('reference_sha256', '').lower()) if profile else ('', '')


def replay(lesson, applicable, hits, findings):
    from feedback_bank import database
    active = {}
    for item in decisions(database().resolve()):
        scope = item['scope']
        if scope == 'lesson' and item['lesson'] != lesson.get('title'):
            continue
        if scope not in ('all', 'lesson', lesson.get('kind')):
            continue
        key = (item['bank'], item['key'], scope, item['model'], item['reference_sha256'])
        if item['state'] == 'withdrawn':
            active.pop(key, None)
        elif item['state'] == 'adopted':
            active[key] = {'adopted': item}
        else:
            active.setdefault(key, {})['trial'] = item
    locations = {}
    for hit in hits:
        locations.setdefault((hit['bank'], hit['key']), []).append((hit['page'], hit['cue']))
    for finding in findings:
        if finding.get('cue'):
            locations.setdefault(('issues', finding['key']), []).append((finding['page'], finding['cue']))
    issues = {r['key']:r for r in applicable}
    voice = voice_context(lesson)
    out = []
    # A lesson-specific adopted correction takes precedence over a broader one.
    priority = {'all': 0, 'concept': 1, 'problem': 1, 'lesson': 2}
    strongest = {}
    for (bank, key, scope, model, ref), versions in active.items():
        if 'adopted' in versions:
            family = (bank, key, model, ref)
            strongest[family] = max(strongest.get(family, -1), priority[scope])
    auditions = set()
    for (bank, key, scope, model, ref), versions in active.items():
        cues = list(dict.fromkeys(locations.get((bank, key), ())))
        if bank == 'issues':
            if key not in issues or (issues[key].get('match') and not cues):
                continue
        elif not cues:
            continue
        positions = [dict(page=p, cue=c) for p, c in cues]
        if model and voice != (model, ref):
            if (bank, key, scope, *voice) in active or (bank, key, scope) in auditions:
                continue
            auditions.add((bank, key, scope))
            out.append(dict(bank=bank, key=key, scope=scope, status='audition_voice', cues=positions))
            continue
        for item in versions.values():
            if item['state'] == 'adopted' and priority[scope] < strongest[bank, key, model, ref]:
                continue
            status = 'compare' if item['state'] == 'trial' else 'apply_and_check'
            if item.get('sample'):
                try:
                    clip = resolve_sample(database().resolve(),item['sample'])
                    intact = digest(clip) == item['sample_sha256']
                except OSError:
                    intact = False
                if not intact:
                    status = 'restore_or_audition'
            entry = dict(review_id=item['id'], bank=bank, key=key, scope=scope,
                         status=status, cues=positions, example=item['example'],
                         before=item['before'], action=item['action'], evidence=item['evidence'])
            if status == 'apply_and_check' and item.get('sample'):
                entry['reference_sample'] = str(clip)
            out.append(entry)
    return out


def review_line(item):
    prompts = {'compare': '用同一句或同一帧对照候选改法',
               'apply_and_check': '将已采用的做法用在本课，回看或回听',
               'audition_voice': '为本次音色重新比较短句',
               'restore_or_audition': '原样本已移动或改变，找回后核实或重新试听'}
    where = '、'.join(f"{cue['page']}/{cue['cue']}" for cue in item['cues'][:3]) or '整课'
    detail = item.get('action', '')
    return f"{item['key']}（{where}） {prompts[item['status']]}。{detail}"
