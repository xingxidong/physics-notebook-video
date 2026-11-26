"""Track how each reported polyphone sounds in the actual delivery file."""
import argparse
from contextlib import closing
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

from feedback_bank import save_report
from pronunciation import classroom_syllables, SYLLABLE, tone_targets
from terminology_review import _clean, _word_windows


def targets(timeline):
    from card_speech import contextual_targets
    choices = contextual_targets(timeline)
    rows = []
    for pi, page in enumerate(timeline['pages'], 1):
        cues = page['cues'] if 'cues' in page else page['beats']
        for ci, cue in enumerate(cues, 1):
            script = cue['tts'] if 'tts' in cue else cue['say']
            hits = tone_targets(script, timeline.get('speech', {}).get('minimax_pronunciation'),
                                cue.get('minimax_pronunciation'),choices[str(page.get('id',pi)),str(cue.get('id',ci))])
            if not hits:
                continue
            start = page.get('start', 0) + cue['start']
            end = page.get('start', 0) + cue['end']
            windows = _word_windows(cue, script)
            for hit in hits:
                offset, word = hit['offset'], hit['term']
                lo = len(_clean(script[:offset]))
                spans = windows[lo:lo + len(word)]
                begin, finish = (start + spans[0][0], start + spans[-1][1]) if spans else (start, end)
                syllables = []
                for j, (a, b) in enumerate(spans):
                    ix = lo + j
                    if b - a < .08 or (ix and windows[ix-1] == (a, b)) or (
                            ix + 1 < len(windows) and windows[ix+1] == (a, b)):
                        continue
                    syllables.append({'char': word[j], 'index': j, 'start': round(start+a, 3),
                                      'end': round(start+b, 3)})
                rows.append(dict(hit, syllables=syllables, id=f'{pi}.{ci}.{offset}', page=page.get('id', str(pi)),
                                 cue=cue.get('id') or cue.get('original_cue') or str(ci),
                                 text=script, start=round(begin, 3), end=round(finish, 3),
                                 clip_start=round(max(start, begin - 1.25), 3),
                                 clip_end=round(min(end, finish + 1.25), 3),
                                 timing='word' if spans else 'cue'))
    return rows


def _digest(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def pitch_evidence(media, row):
    """Use measured voiced frames only as a triage aid, never as a listening receipt."""
    if not row['syllables']:
        return {'status': 'no_syllable_timing', 'items': []}
    try:
        import librosa
        import numpy as np
    except ImportError as exc:
        raise ValueError('音高辅助分析需要 librosa 和 NumPy；成片截取、复听登记可独立运行。') from exc
    readings = row['expected'].split() if row['expected'] else []
    items = []
    for part in row['syllables']:
        begin, end = part['start'], part['end']
        origin = max(0, begin - .45)
        raw = subprocess.check_output(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(origin),
                                      '-i', str(media), '-map', '0:a:0', '-t', str(end-origin+.45),
                                      '-ac', '1', '-ar', '16000', '-f', 's16le', 'pipe:1'])
        y = np.frombuffer(raw, dtype='<i2').astype(float) / 32768
        item = dict(part, expected=readings[part['index']] if readings else None, trend='unclear')
        if len(y) >= 1024:
            hz, voiced, _ = librosa.pyin(y, sr=16000, fmin=65, fmax=450, frame_length=1024, hop_length=160)
            points = []
            for j, f in enumerate(hz):
                stamp = origin+j*.01
                if not begin <= stamp <= end or not voiced[j] or not np.isfinite(f):
                    continue
                frame = y[max(0, j*160-320):j*160+320]
                lag = round(16000/f)
                centered = frame-frame.mean()
                if len(frame) <= lag or np.sqrt(np.mean(centered**2)) < .003:
                    continue
                left, right = centered[:-lag], centered[lag:]
                periodicity = (left @ right) / (np.linalg.norm(left)*np.linalg.norm(right)+1e-12)
                if periodicity >= .70:
                    points.append((stamp, float(f)))
            item['points'] = [[round(t, 3), round(f, 1)] for t, f in points]
            if len(points) >= 7 and points[-1][0]-points[0][0] >= .06:
                freq = np.array([f for _, f in points])
                step = max(2, len(freq)//4)
                first, last = np.median(freq[:step]), np.median(freq[-step:])
                delta = float(12*np.log2(last/first))
                item['change_semitones'] = round(delta, 2)
                item['trend'] = 'rising' if delta >= 2 else 'falling' if delta <= -2 else 'unclear'
        items.append(item)
    return {'status': 'acoustic_evidence_only', 'items': items}


def inspect(project, timeline, media, *, select=None, clip=False, pitch=False, heard=None, intended=None, cue_clip=False, hearings=None):
    if (clip or cue_clip or pitch or heard is not None or hearings is not None) and select is None:
        raise ValueError('请指定实际成片的读音位置。')
    rows = targets(timeline)
    if not rows and select is None:
        return {'status': 'no_matches', 'items': [], 'remaining': 0, 'producer_queue': []}
    media = Path(media).resolve()
    version = _digest(media)
    folder = Path(project) / 'review-audio'
    folder.mkdir(exist_ok=True)
    output = {'file': str(media), 'sha256': version, 'items': rows}
    chosen = next((row for row in rows if row['id'] == select), None)
    if select is not None and not chosen:
        raise ValueError(f'在当前时间轴中找不到读音位置 {select}')
    for row in rows:
        row['evidence_key'] = hashlib.sha256(json.dumps([version, {k:v for k,v in row.items() if k not in ('reason', 'characters', 'conflicts')}], sort_keys=True,
                                                         ensure_ascii=False).encode()).hexdigest()
    if pitch:
        output['pitch_evidence'] = pitch_evidence(media, chosen)
    cue_items = {}
    if cue_clip or hearings is not None:
        prefix = select.rsplit('.', 1)[0]
        cue_items = {r['id']:r for r in rows if r['id'].rsplit('.', 1)[0] == prefix}
        output['cue_items'] = [{k:r[k] for k in ('id','term','offset','expected','characters')} for r in cue_items.values()]
    if clip or cue_clip:
        start, end = chosen['clip_start'], chosen['clip_end']
        suffix = chosen['id']
        if cue_clip:
            pi, ci, _ = map(int, select.split('.'))
            page = timeline['pages'][pi-1]
            cue = (page['cues'] if 'cues' in page else page['beats'])[ci-1]
            start, end = (page.get('start', 0) + cue[k] for k in ('start', 'end'))
            suffix = f'{pi}.{ci}-sentence'
        target = folder / f"tone-{version[:12]}-{suffix}.wav"
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', str(start),
                        '-i', str(media), '-map', '0:a:0', '-t', str(end-start),
                        '-c:a', 'pcm_s16le', str(target)], check=True)
        output['clip'] = str(target)
    with closing(sqlite3.connect(folder / 'tone-listening.sqlite3', timeout=15)) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS hearings (evidence_key TEXT PRIMARY KEY, intended TEXT, heard TEXT)')
        observations = {}
        if hearings is not None:
            if not isinstance(hearings, dict) or any(key not in cue_items for key in hearings):
                raise ValueError('整句复听记录按本句的读音位置填写。')
            observations.update(hearings)
        if heard is not None:
            observations[select] = {'heard': heard, 'intended': intended}
        for position, entry in observations.items():
            row = cue_items[position] if position in cue_items else chosen
            if not isinstance(entry, dict) or not isinstance(entry.get('heard'), str):
                raise ValueError('每处填写实际听到的拼音 heard。')
            goal = row['expected'] or entry.get('intended')
            if not isinstance(goal, str) or not goal or (entry.get('intended') and entry['intended'] != goal):
                raise ValueError('按句意填写这个词的目标拼音。已有确定读法时沿用词表。')
            goal, heard_value = (' '.join(v.lower().replace('v', 'ü').split()) for v in (goal, entry['heard']))
            for value in (goal, heard_value):
                syllables = value.split()
                if len(syllables) != len(row['term']) or not all(SYLLABLE.fullmatch(s) for s in syllables):
                    raise ValueError('请记录逐字带调拼音，如 ce4 liang2。')
            db.execute('INSERT OR REPLACE INTO hearings VALUES (?, ?, ?)',
                       (row['evidence_key'], goal, heard_value))
        hearings = {k: (i, h) for k, i, h in db.execute('SELECT evidence_key, intended, heard FROM hearings')}
    for row in rows:
        decision = hearings.get(row['evidence_key'])
        row['status'] = 'pending'
        if decision:
            row['intended'], row['heard'] = decision
            wanted, actual = (v.split() for v in decision)
            match = classroom_syllables(row['term'], *decision)
            row['character_results'] = [
                dict(char=item['char'], offset=item['offset'], expected=wanted[item['index']],
                     heard=actual[item['index']], matches=match[item['index']])
                for item in row['characters']]
            row['status'] = 'heard_correct' if all(match) else 'needs_retake'
    remaining = sum(row['status'] != 'heard_correct' for row in rows)
    # The producer checks a cue once, recording separate findings for every occurrence.
    by_cue = {}
    for row in rows:
        if row['status'] == 'heard_correct':
            continue
        cue_key = row['id'].rsplit('.', 1)[0]
        group = by_cue.setdefault(cue_key, {'page': row['page'], 'cue': row['cue'],
                                             'listen_id': row['id'], 'items': [], 'needs_retake': False})
        group['items'].append(row['id'])
        if row['status'] == 'needs_retake':
            group['needs_retake'] = True
    queue = sorted(by_cue.values(), key=lambda group: not group['needs_retake'])
    output.update(status='pending' if remaining else 'heard_correct', remaining=remaining, producer_queue=queue)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--video-file', type=Path, default=Path('video.mp4'))
    parser.add_argument('--timeline', type=Path, default=Path('timeline.json'))
    parser.add_argument('--id', help='命中位置，见报告 items[].id')
    parser.add_argument('--clip', action='store_true', help='从所选成片截取本处原速试听')
    parser.add_argument('--cue-clip', action='store_true', help='从成片一次听这一整句及其中所有候查词')
    parser.add_argument('--hearings-file', type=Path, help='本句逐处实听结果 JSON，未填写的继续待听')
    parser.add_argument('--pitch', action='store_true', help='查看原片该词的音节基频走势')
    parser.add_argument('--heard', help='实听后登记逐字带调拼音')
    parser.add_argument('--intended', help='词义待定时，登记本句应读的拼音')
    args = parser.parse_args()
    if (args.clip or args.cue_clip or args.hearings_file or args.pitch or args.heard) and not args.id or args.intended and not args.heard:
        parser.error('取样和实听结果需指定 --id；--intended 配合 --heard 使用。')
    timeline = json.loads((args.project / args.timeline).read_text())
    report = inspect(args.project, timeline, args.project / args.video_file, select=args.id,
                     clip=args.clip, pitch=args.pitch, heard=args.heard, intended=args.intended,
                     cue_clip=args.cue_clip,
                     hearings=json.loads(args.hearings_file.read_text()) if args.hearings_file else None)
    save_report(args.project / 'final-tone-review.json', report)
    print(report.get('clip') or args.project / 'final-tone-review.json')
    print(f"制作端待处理 {len(report['producer_queue'])} 段口播，涉及 {report['remaining']} 处读音。")


if __name__ == '__main__':
    main()
