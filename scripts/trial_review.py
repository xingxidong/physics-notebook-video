"""Record actual listening results in the skill's portable learning database."""
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from feedback_bank import database, record, save_report
from learning_bundle import keep_sample, TRIAL_REVIEWS
from trial_materials import fingerprint, refresh


def speech_identity(speech):
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()
                    if not re.search(r'api.?key|secret|password|^(?:access_|auth_|bearer_)?token$|authorization|headers|\.env', k, re.I)}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    config = clean(speech)
    ref = speech.get('qwen', {}).get('reference_audio')
    if ref and Path(ref).is_file():
        config['reference_audio_sha256'] = hashlib.sha256(Path(ref).read_bytes()).hexdigest()
    return fingerprint(config)


def evidence_token(row, identity):
    return fingerprint([row['material_fingerprint'], identity, row['audio_sha256'],
                        row.get('synthesis_signature'), row.get('synthesis'), row.get('planned_input')])


def judgment_template(run):
    return {'reviewer': '', 'basis': 'producer_listening', 'evidence': '',
            'items': [{'id': r['id'], 'token': r['review_token'],
                       'checks': {c['id']: {'status': 'pending', 'note': ''} for c in r['checks']}}
                      for r in run['items']]}


def review_status(row):
    checks = row.get('listening', {}).get('checks', {})
    statuses = [checks.get(c['id'], {}).get('status', 'pending') for c in row['checks']]
    if 'wrong' in statuses:
        return 'needs_revision'
    return 'passed' if statuses and all(x == 'ok' for x in statuses) else 'pending'


def voice_profile(signature):
    backend = signature.get('backend')
    fields = ('model', 'reference_sha256') if backend == 'qwen' else ('voice', 'model')
    return {'backend': backend, **{key: signature.get(key) or '' for key in fields}}


def require_target_voice(project, speech):
    """Use the actual accepted trial as the speaking voice for a new course."""
    folder = Path(project) / 'voice-trial'
    path = folder / 'trial-results.json'
    if not path.is_file():
        raise ValueError('正式配音前请在 voice-trial 生成目标音色试音，并登记实际审听。')
    run = json.loads(path.read_text())
    rows = run.get('items', [])
    if run.get('schema') != 2 or not rows:
        raise ValueError('目标音色需要当前项目的实际试音文件。')
    source_project = run.get('source_plan',{}).get('project')
    if not source_project or Path(source_project).resolve()!=Path(project).resolve():
        raise ValueError('请用当前项目的试音计划录制并登记目标音色。')
    if not any(row.get('origin')=='lesson' for row in rows):
        raise ValueError('试音需包含本课的一段真实口播。')
    if any(review_status(row) != 'passed' or
           row.get('listening', {}).get('checks', {}).get('voice', {}).get('status') != 'ok'
           for row in rows):
        raise ValueError('目标音色试音仍有未审听或待修项目，请使用 voice_trials.py review。')
    validate_run(folder, run)
    target = voice_profile(rows[0].get('synthesis_signature', {}))
    if any(voice_profile(row.get('synthesis_signature', {})) != target for row in rows):
        raise ValueError('当前试音包含多个音色，请保留选定的音色试音。')
    backend = speech.get('backend', 'glm')
    if backend == 'qwen':
        from qwen_voice import config, sha
        source = config(project, speech)
        expected = dict(backend=backend, model=source['model'], reference_sha256=sha(source['reference_audio']))
    else:
        from voice import DEFAULTS, environment
        env = environment(project)
        expected = dict(backend=backend,
                        voice=speech.get('voice') or env.get(backend.upper()+'_VOICE') or DEFAULTS[backend],
                        model=speech.get('model') or (env.get('MINIMAX_MODEL','speech-2.8-hd') if backend=='minimax' else ''))
    if target != expected:
        raise ValueError('本次配音配置与已听过的目标音色不符，请恢复同一模型及音色参考或重新试音。')
    evidence = {'profile_sha256': fingerprint(target),
                'trial_sha256': fingerprint([row['review_token'] for row in rows]),
                'reviewed_samples': len(rows)}
    return target, evidence


def validate_run(folder, run, ids=None):
    from trial_materials import lesson_stamp
    source = run.get('source_plan', {})
    if source.get('project') and lesson_stamp(source['project']) != source['lesson_files']:
        raise ValueError('课程源已改变，当前试音记录须重新生成。')
    for row in run['items']:
        if ids is not None and row['id'] not in ids:
            continue
        if refresh(row)['material_fingerprint'] != row['material_fingerprint']:
            raise ValueError('本句读音卡或反馈已改变，需要重新试音：' + row['id'])
        audio = folder / row['audio']
        if not audio.is_file() or hashlib.sha256(audio.read_bytes()).hexdigest() != row['audio_sha256']:
            raise ValueError('实际录音已改变或丢失：' + row['id'])
        if evidence_token(row, run['speech_fingerprint']) != row['review_token']:
            raise ValueError('模型、输入或录音记录已改变：' + row['id'])


def run_status(folder, run=None):
    folder = Path(folder).resolve()
    run = run or json.loads((folder / 'trial-results.json').read_text())
    rows = []
    for row in run['items']:
        try:
            validate_run(folder, run, {row['id']})
            rows.append({'id': row['id'], 'status': review_status(row)})
        except ValueError as exc:
            rows.append({'id': row['id'], 'status': 'stale', 'reason': str(exc)})
    return {'status': 'passed_for_recorded_sentences' if rows and all(r['status'] == 'passed' for r in rows) else 'needs_review',
            'items': rows, 'not_recorded': run.get('not_requested', []),
            'coverage': run.get('source_plan', {}).get('coverage', {}),
            'final_video_review_required': True}


def import_review(folder, judgments):
    folder = Path(folder).resolve()
    run = json.loads((folder / 'trial-results.json').read_text())
    if run.get('schema') != 2:
        raise ValueError('旧试音输出没有逐处检查指纹，请用新程序重新生成。')
    reviewer, evidence = judgments.get('reviewer', '').strip(), judgments.get('evidence', '').strip()
    basis = judgments.get('basis')
    if not reviewer or not evidence or basis not in ('producer_listening', 'author_listening'):
        raise ValueError('请填写实际审听者、听过的内容及依据；自动识别不能记成实听。')
    lookup = {r['id']: r for r in run['items']}
    entries = judgments.get('items', [])
    if not entries or len({x['id'] for x in entries}) != len(entries):
        raise ValueError('请提供不重复的实际审听句子。')
    validate_run(folder, run, {x['id'] for x in entries})
    # Validate all answers before changing the learning database.
    for entry in entries:
        row = lookup.get(entry['id'])
        if row is None or entry.get('token') != row['review_token']:
            raise ValueError('审听答卷与当前录音不符：' + entry['id'])
        known = {c['id'] for c in row['checks']}
        if not entry.get('checks') or set(entry['checks']) - known:
            raise ValueError('答卷包含未知检查位置或没有检查项。')
        for result in entry['checks'].values():
            if not isinstance(result, dict) or result.get('status') not in ('ok', 'wrong', 'unsure', 'pending'):
                raise ValueError('逐处检查使用 ok、wrong、unsure 或 pending。')
            if result['status'] == 'wrong' and not result.get('note', '').strip():
                raise ValueError('错音须记下实际听到的现象。')
    path = database().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    events = []
    for entry in entries:
        row = lookup[entry['id']]
        checks = copy.deepcopy(row.get('listening', {}).get('checks', {}))
        checks.update({k: v for k, v in entry['checks'].items() if v['status'] != 'pending'})
        row['listening'] = dict(reviewer=reviewer, basis=basis, evidence=evidence, checks=checks)
        row['review_status'] = review_status(row)
        sample = keep_sample(path, folder / row['audio'], row['audio_sha256'])
        data = {'case_id': row['id'], 'text': row['text'], 'origin': row['origin'],
                'targets': row['targets'], 'material_fingerprint': row['material_fingerprint'],
                'speech_fingerprint': run['speech_fingerprint'], 'review_token': row['review_token'],
                'sample': sample, 'sample_sha256': row['audio_sha256'],
                'listening': row['listening'], 'status': row['review_status']}
        events.append((fingerprint(data), row['id'], json.dumps(data, ensure_ascii=False, sort_keys=True)))
    with closing(sqlite3.connect(path, timeout=30)) as db, db:
        db.execute(TRIAL_REVIEWS)
        db.executemany('INSERT OR IGNORE INTO voice_trial_reviews(event_uid,case_id,payload) VALUES(?,?,?)', events)
    for entry in entries:
        row = lookup[entry['id']]
        targets = {t['id']: t for t in row['targets']}
        checks = {c['id']: c for c in row['checks']}
        for ident, result in entry['checks'].items():
            if result['status'] != 'wrong':
                continue
            check = checks[ident]
            target = targets.get(check.get('target'))
            note = result['note'].strip()
            if target and target['kind'] == 'letter':
                record('letters', target['term'], note, lesson='固定及扩展试音', at=row['id'], example=row['text'])
            elif target and check['axis'] == 'pronunciation' and len(target['term']) > 1:
                record('polyphones', target['term'], note, lesson='固定及扩展试音', at=row['id'], example=row['text'])
            elif target and len(target['term']) > 1:
                record('issues', 'term-flow-' + target['term'], note, match=target['term'],
                       example=row['text'], lesson='固定及扩展试音', at=row['id'])
            else:
                next_check = {'continuity':'接句与连贯性。','delivery':'语速和讲课口吻。',
                              'voice':'所选教师声音和上下句音色一致性。'}.get(check['axis'],'当前词的读音和连读。')
                record('issues', 'speech-trial-' + check['axis'] + '-' + fingerprint(row['text'])[:12],
                       note, match=row['text'], example=row['text'],
                       lesson='固定及扩展试音', at=row['id'],
                       takeaway='在新课整句中检查' + next_check)
    current = run_status(folder, run)
    run['status'] = current['status']
    save_report(folder / 'trial-results.json', run)
    return {'status': run['status'], 'reviewed_sentences': len(entries),
            'passed_sentences': sum(r['status'] == 'passed' for r in current['items']),
            'database': str(path), 'final_video_review_required': True}
