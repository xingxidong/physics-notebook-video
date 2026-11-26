"""Review repeated readings and mixed-language formulae in their final classroom sentences."""
import argparse
from bisect import bisect_left, bisect_right
from collections import defaultdict
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile

from feedback_bank import save_report
from pronunciation import PHYSICS_TERMS, term_pattern, tone_targets
from terminology_review import _clean, _word_windows

RATE = 16000
_FLOW = {'电压差', '桥接'}


def probe_python():
    override = os.environ.get('PHYSICS_NOTEBOOK_AUDIO_PYTHON')
    if override is not None:
        return override
    path = Path.home()/'.local/share/physics-notebook-video/speech-probe.json'
    if path.is_file():
        config = json.loads(path.read_text())
        python = config.get('python')
        if not isinstance(python,str) or not Path(python).is_absolute():
            raise ValueError('本机 speech-probe.json 的 python 应为识音环境绝对路径。')
        return python
    return None


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def inventory(timeline, lesson=None, *, priority=()):
    """Return one row per cue, preserving the displayed symbols and repeated offsets."""
    from card_speech import contextual_targets, symbols_in_order
    choices = contextual_targets(timeline,lesson)
    boards = {}
    for page in (lesson or timeline)['pages']:
        for cue in page.get('cues', page.get('beats', [])):
            boards[page.get('id'), cue.get('id')] = [dict(id=a.get('id'), latex=a['latex'])
                for a in cue.get('actions', []) if a.get('type') == 'math' and a.get('latex')]
    rows = []
    flow_terms = sorted(_FLOW.union(priority))
    for pi, page in enumerate(timeline['pages'], 1):
        strokes = defaultdict(dict)
        for s in page.get('strokes', []):
            key = str(s.get('board_id') or s.get('action', ''))
            span = strokes[s.get('cue')].setdefault(key, [s['start'], s['end']])
            span[0], span[1] = min(span[0], s['start']), max(span[1], s['end'])
        for ci, cue in enumerate(page.get('cues', page.get('beats', [])), 1):
            text = cue.get('tts') or cue.get('say') or cue.get('text', '')
            if not text.strip():
                continue
            cid = cue.get('id', str(ci))
            start = page.get('start', 0) + cue.get('start', 0)
            windows = _word_windows(cue, text) if 'end' in cue else []
            items = []
            def add(kind, pos, stop, expected, core_end=None):
                core_end = stop if core_end is None else core_end
                lo, hi = len(_clean(text[:pos])), len(_clean(text[:core_end]))
                spans = windows[lo:hi]
                row = dict(kind=kind, offset=pos, text=text[pos:stop], expected=expected)
                if (spans and not (lo and windows[lo-1] == spans[0])
                        and not (hi < len(windows) and windows[hi] == spans[-1])):
                    row['window'] = [start + spans[0][0], start + spans[-1][1]]
                items.append(row)
            # Mask subscript syntax only for lexical detection. Offset and print case stay intact.
            for symbol in symbols_in_order(text):
                add('symbol', symbol['offset'], symbol['end'], symbol['expected'],symbol['core_end'])
                items[-1].update({k:symbol[k] for k in ('example','listen_for','subscript') if k in symbol})
                if symbol.get('subscript') in ('0','零'):
                    items[-1]['listen_for'] = '字母名后接零，留意重复的元音或多读的字母。'
            for term in flow_terms:
                for m in term_pattern([term]).finditer(text):
                    add('flow', *m.span(), 'joined')
                    items[-1]['reading'] = PHYSICS_TERMS.get(term)
            by_char = defaultdict(list)
            for hit in tone_targets(text,choices=choices[str(page.get('id',pi)),str(cid)]):
                for c in hit['characters']:
                    if c['expected']:
                        sounds = (hit['expected'] or '').split()
                        j = c['index']
                        soft = c['expected'][:-1]+'2' if c['expected'].endswith('3') and j+1 < len(sounds) and sounds[j+1].endswith('3') else None
                        by_char[c['char']].append((c['offset'], c['expected'], hit['term'], hit['reason']=='feedback', soft))
            for hits in by_char.values():
                contrast = len({hit[1] for hit in hits}) > 1
                for pos, sound, term, historical, soft in hits:
                    if historical or contrast:
                        add('tone', pos, pos+1, sound)
                        items[-1]['word'] = term
                        if soft:
                            items[-1]['accepted_surface'] = soft
            for item in items:
                item['id'] = f"{item['kind']}@{item['offset']}"
            rows.append(dict(id=f'{pi}.{ci}', page=page.get('id',str(pi)), cue=cid, text=text,
                             start=start, end=page.get('start',0)+cue.get('end',0),
                             targets=sorted(items,key=lambda t:t['offset']),
                             board=boards.get((page.get('id'), cid), []),
                             ink=strokes.get(cid, {})))
    return rows


def video_packets(media):
    """Bind visual receipts to local encoded frames, including their preceding keyframe."""
    raw = subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_packets',
        '-show_entries','packet=pts_time,dts_time,flags,data_hash','-show_data_hash','sha256',
        '-of','json',str(media)])
    packets = json.loads(raw).get('packets', [])
    records = sorted((float(p['pts_time']), p['data_hash'], 'K' in p['flags'])
                     for p in packets if p.get('pts_time') not in (None, 'N/A'))
    return [r[0] for r in records], [r[0] for r in records if r[2]], records


def inspect(project, timeline, media, *, lesson=None, priority=(), clip_id=None, findings=None):
    if timeline.get('draft'):
        raise ValueError('整句审查需要正式时间轴。')
    rows = inventory(timeline, lesson, priority=priority)
    folder = project/'review-audio'
    folder.mkdir(exist_ok=True)
    entries = {} if findings is None else findings
    ids = {r['id'] for r in rows}
    if not isinstance(entries, dict) or entries.keys()-ids or (clip_id and clip_id not in ids):
        raise ValueError('请使用本次整句清单中的位置编号。')
    stamps, keys, packets = video_packets(media) if rows else ([], [], [])
    queue = []
    author = []
    with tempfile.TemporaryFile() as pcm, closing(sqlite3.connect(folder/'speech-context.sqlite3',timeout=30)) as db, db:
        if rows:
            subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(media),'-map','0:a:0',
                '-ac','1','-ar',str(RATE),'-f','s16le','pipe:1'], stdout=pcm, check=True)
        duration = pcm.tell()/(2*RATE)
        db.execute('CREATE TABLE IF NOT EXISTS baseline (location TEXT PRIMARY KEY, signature TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS clips (token TEXT PRIMARY KEY, sha TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS hearings (token TEXT PRIMARY KEY, result TEXT)')
        initial = not db.execute('SELECT 1 FROM baseline LIMIT 1').fetchone()
        for i, row in enumerate(rows):
            a,b = row['start'], row['end']
            if not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= duration+.08):
                raise ValueError(f"{row['id']} 的句区间超出音轨。")
            # Keep the previous sentence ending and the following sentence opening even across a pause.
            left,right = max(0,a-.65), min(duration,b+.65)
            if i:
                left = min(left, max(rows[i-1]['start'],rows[i-1]['end']-1.4))
            if i+1 < len(rows):
                right = max(right,min(rows[i+1]['end'],rows[i+1]['start']+1.4))
            right = min(duration,right)
            pcm.seek(round(left*RATE)*2)
            raw = pcm.read((round(right*RATE)-round(left*RATE))*2)
            visual = bool(row['board'] or row['ink'] or any(t['kind']=='symbol' for t in row['targets']))
            frame_hash = None
            if visual and packets:
                key = keys[max(0,bisect_right(keys,left)-1)] if keys else 0
                # A B-frame may depend on a future displayed reference frame in this GOP.
                upper = keys[bisect_right(keys,right)] if bisect_right(keys,right)<len(keys) else math.inf
                frame_hash = digest(packets[bisect_left(stamps,key):bisect_right(stamps,upper)])
            token = digest([row, left, right, hashlib.sha256(raw).hexdigest(), frame_hash])
            location = json.dumps([row['page'],row['cue']])
            db.execute('INSERT OR IGNORE INTO baseline VALUES (?,?)',(location,token if initial else 'new'))
            changed = db.execute('SELECT signature FROM baseline WHERE location=?',(location,)).fetchone()[0] != token
            row.update(token=token, changed=changed, clip_range=[left,right], visual=visual)
            if not row['targets'] and not changed and row['id'] not in entries and row['id'] != clip_id:
                continue
            path = folder/('context-'+token+('.mp4' if packets else '.wav'))
            if row['id'] == clip_id:
                with tempfile.NamedTemporaryFile(dir=folder, suffix=path.suffix, delete=False) as tmp:
                    stage = Path(tmp.name)
                try:
                    opts = ['-map','0:v:0','-c:v','libx264','-preset','ultrafast','-c:a','aac'] if packets else ['-c:a','pcm_s16le']
                    subprocess.run(['ffmpeg','-nostdin','-y','-v','error','-ss',str(left),'-i',str(media),
                        '-t',str(right-left),'-map','0:a:0',*opts,str(stage)],check=True)
                    stage.replace(path)
                finally:
                    stage.unlink(missing_ok=True)
                from tone_review import _digest
                db.execute('INSERT OR REPLACE INTO clips VALUES (?,?)',(token,_digest(path)))
            if path.is_file():
                row['clip'] = str(path)
            if row['id'] in entries:
                from tone_review import _digest
                result = entries[row['id']]
                expected_fields = {t['id'] for t in row['targets']} | {'join'} | ({'board'} if visual else set())
                saved = db.execute('SELECT sha FROM clips WHERE token=?',(token,)).fetchone()
                if (not isinstance(result,dict) or result.get('token') != token or not saved or
                        not path.is_file() or saved[0] != _digest(path)):
                    raise ValueError('先导出并听看本版整句，再提交与该片段对应的记录。')
                checks = result.get('checks')
                if (not isinstance(checks,dict) or set(checks) != expected_fields
                        or any(v not in ('ok','wrong','unsure') for v in checks.values())):
                    raise ValueError('每次出现的目标、接缝和适用的板书均须填写 ok、wrong 或 unsure。')
                if visual and not packets and checks['board']=='ok':
                    raise ValueError('只含声音的文件无法确认板书。')
                db.execute('INSERT OR REPLACE INTO hearings VALUES (?,?)',(token,json.dumps(checks)))
            rec = db.execute('SELECT result FROM hearings WHERE token=?',(token,)).fetchone()
            checks = json.loads(rec[0]) if rec else {}
            row['checks'] = checks
            row['status'] = ('pending' if not rec else 'retake' if 'wrong' in checks.values()
                             else 'unsure' if 'unsure' in checks.values() else 'reviewed')
            if row['status']=='unsure' and changed:
                author.append(row['id'])
            queue.append(row)
    remaining = sum(r['status']!='reviewed' for r in queue)
    from tone_review import _digest
    return dict(file=str(media.resolve()), sha256=_digest(media), remaining=remaining, status='pending' if remaining else 'reviewed',
                items=queue, author_review=author)


def review_course(project,timeline,media,lesson,**options):
    from term_flow import manifest_entry, vocabulary
    _, priority = vocabulary(lesson)
    report = inspect(project,timeline,media,lesson=lesson,priority=priority,**options)
    save_report(project/'final-speech-context.json',report)
    manifest=project/'delivery-files.json'
    if manifest.is_file():
        record=json.loads(manifest.read_text())
        if record.get('video') and (project/record['video']).resolve()==media.resolve():
            record['speech_context']=manifest_entry(report)
            save_report(manifest,record)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path)
    parser.add_argument('--timeline',type=Path,default=Path('timeline.json'))
    parser.add_argument('--video-file',type=Path,default=Path('video.mp4'))
    parser.add_argument('--clip',metavar='ID')
    parser.add_argument('--hearings', type=Path)
    parser.add_argument('--strict',action='store_true')
    args=parser.parse_args()
    p=args.project
    timeline=json.loads((p/args.timeline).read_text())
    lesson=timeline
    if (p/'lesson.json').is_file():
        from speech_plan import apply
        lesson,_=apply(p,json.loads((p/'lesson.json').read_text()))
    report=review_course(p,timeline,p/args.video_file,lesson,clip_id=args.clip,
                   findings=json.loads(args.hearings.read_text()) if args.hearings else None)
    if args.clip:
        print(next(r['clip'] for r in report['items'] if r['id']==args.clip))
    print(f"待制作端复核 {report['remaining']} 句。")
    if args.strict and report['remaining']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
