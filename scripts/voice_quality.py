#!/usr/bin/env python3
"""Local narration quality report: levels, silence, pacing and script hygiene."""
import argparse,array,json,math,re,wave
from bisect import bisect_right
from pathlib import Path
from classroom_language import review_narration
from terminology_review import inspect_terminology

TEMPLATE_PHRASES=('首先我们来','接下来我们将','综上所述','通过以上分析我们可以看出','这道题告诉我们')
DEFENSIVE_PHRASES=('不表示','不代表','不意味着','不能据此认为','并不是说')
TEACHING_PAUSES={'read_formula','observe_motion','think','transition'}

def _db(value):return 20*math.log10(max(value,1)/32768)

def _silences(samples,rate,threshold_db=-46,min_seconds=1.8):
    width=max(1,round(rate*.02));quiet=[]
    for start in range(0,len(samples),width):
        block=samples[start:start+width];rms=math.sqrt(sum(x*x for x in block)/max(1,len(block)))
        quiet.append(_db(rms)<threshold_db)
    spans=[];begin=None
    for i,value in enumerate(quiet+[False]):
        if value and begin is None:begin=i
        elif not value and begin is not None:
            start=begin*width/rate;end=min(len(samples),(i*width))/rate
            if end-start>=min_seconds and start>.25 and end<len(samples)/rate-.25:spans.append({'start':round(start,3),'end':round(end,3),'duration':round(end-start,3)})
            begin=None
    return spans

def _review_joins(pages, pauses):
    """Use measured silence to locate joins worth hearing as a pair."""
    starts = [pause['start'] for pause in pauses]
    findings = []
    cues = _absolute_cues(pages)
    for before, after in zip(cues, cues[1:]):
        gap = max(0, after['start']-before['end'])
        purpose = before.get('pause_reason') in TEACHING_PAUSES or after.get('pause_reason') in TEACHING_PAUSES
        join = (before['end'] + after['start']) / 2
        index = bisect_right(starts, join) - 1
        if index < 0:
            continue
        pause = pauses[index]
        if join >= pause['end'] or pause['duration'] < .85 or (purpose and pause['duration'] <= gap+.35):
            continue
        findings.append({
            'code': 'audible-cue-gap', 'cue': after['id'], 'related_cues': [before['id'], after['id']],
            'start': pause['start'], 'end': pause['end'], 'quiet_seconds': pause['duration'],
            'message': '连着听相邻两段，确认是否在一句话讲完前断开，还是自然换气或转场。',
        })
    return findings

def _absolute_cues(pages):
    return [{**cue, 'start': page.get('start',0) + cue['start'], 'end': page.get('start',0) + cue['end']}
            for page in pages for cue in page['cues']]

def _review_inside(cues, pauses):
    starts = [cue['start'] for cue in cues]
    findings = []
    for pause in pauses:
        index = bisect_right(starts, pause['start']) - 1
        if index < 0:
            continue
        cue = cues[index]
        if pause['start'] < cue['start'] + .15 or pause['end'] > cue['end'] - .15:
            continue
        findings.append({
            'code': 'in-cue-hesitation', 'cue': cue['id'], 'start': pause['start'], 'end': pause['end'],
            'quiet_seconds': pause['duration'],
            'message': '句群中出现实测静音。回听是否卡在术语、数值或因果关系中间；正常语义停顿保留。',
        })
    return findings

def _listening_checks(cues, findings):
    if not cues:
        return []
    selections = {}
    def add(cue, reason):
        selections.setdefault(cue['id'], []).append(reason)
    add(cues[0], '开场：是否直接指向本课要看的图、量或问题')
    candidates = [cue for cue in cues if cue.get('role') in ('derive', 'explain','key_turn','model')]
    add(max(candidates or cues, key=lambda c: c['end'] - c['start']),
        '最长的讲解或推导：回听术语、逻辑连接、语速和落笔')
    add(cues[-1], '收束：检查结论读法、前一句的衔接和句尾')
    for cue in cues:
        if cue.get('role')=='key_turn':
            add(cue,'关键转折：重点词、推导依据与眼前图式是否连贯')
    groups={}
    for cue in cues:
        if cue.get('speech_group'):
            groups.setdefault(cue['speech_group'],[]).append(cue)
    for group,items in groups.items():
        add(items[0],f'连续讲述组「{group}」：连听整段，确认句间没有重新起句或机械停顿')
    for row in findings:
        if row.get('cue'):
            selections.setdefault(row['cue'], []).append(row.get('code','physics-term')+('：'+row['term'] if row.get('term') else ''))
    return [{'cue': cue['id'], 'start': round(cues[max(0,i-1)]['start'],3),
             'end': round(cues[min(len(cues)-1,i+1)]['end'],3),
             'reasons': list(dict.fromkeys(selections[cue['id']]))}
            for i,cue in enumerate(cues) if cue['id'] in selections]

def audit(project,data=None):
    project=Path(project);wav_path=project/'narration.wav'
    if data is None:data=json.loads((project/'timeline.json').read_text())
    with wave.open(str(wav_path)) as w:
        if w.getsampwidth()!=2 or w.getnchannels()!=1:raise ValueError('Voice audit expects mono 16-bit narration.wav')
        rate=w.getframerate();samples=array.array('h',w.readframes(w.getnframes()))
    if not samples:raise ValueError('Narration is empty')
    peak=max(abs(x) for x in samples);rms=math.sqrt(sum(x*x for x in samples)/len(samples));clip=sum(abs(x)>=32760 for x in samples)/len(samples)
    cues=[c for p in data['pages'] for c in p['cues']];warnings=[]
    if _db(peak)>-0.8:warnings.append({'code':'peak-high','message':'峰值距离满刻度不足 0.8 dB。'})
    if clip>.0001:warnings.append({'code':'clipping','message':f'削波样本比例为 {clip:.4%}。'})
    if _db(rms)<-34:warnings.append({'code':'level-low','message':'全片平均电平偏低。'})
    pauses=_silences(samples,rate,min_seconds=.65)
    long_silence=[span for span in pauses if span['duration']>=1.8];planned=[]
    for span in long_silence:
        intentional=any(c.get('pause_reason') in TEACHING_PAUSES
                        and span['start']<=p.get('start',0)+c['end']<=span['end']
                        and span['duration']<=c.get('pause',0)+.35
                        for p in data['pages'] for c in p['cues'])
        if intentional:planned.append(span)
        else:warnings.append({'code':'long-silence','message':f'{span["start"]:.2f}—{span["end"]:.2f} 秒存在较长静音。'})
    formula_re=re.compile(r'[\\{}_^]|\b(?:frac|sqrt|vec|dot)\b')
    timed=0
    for cue in cues:
        duration=max(.01,cue['end']-cue['start']);chars=len(re.sub(r'\s','',cue['tts']));rate_c=chars/duration
        if rate_c>7.2:warnings.append({'code':'cue-fast','cue':cue['id'],'message':f'{cue["id"]} 的口语密度为 {rate_c:.1f} 字/秒。'})
        if duration>4 and rate_c<1.5:warnings.append({'code':'cue-slow','cue':cue['id'],'message':f'{cue["id"]} 的口语密度为 {rate_c:.1f} 字/秒。'})
        if formula_re.search(cue['tts']):warnings.append({'code':'raw-formula','cue':cue['id'],'message':f'{cue["id"]} 仍含未口语化的公式标记。'})
        for phrase in TEMPLATE_PHRASES+DEFENSIVE_PHRASES:
            if phrase in cue['tts']:warnings.append({'code':'script-style','cue':cue['id'],'message':f'{cue["id"]} 含模板化表达“{phrase}”。'})
        timed+=bool(cue.get('words'))
    terminology,spelling_warnings=inspect_terminology(data)
    warnings.extend(spelling_warnings)
    timed_script = _absolute_cues(data['pages'])
    classroom = review_narration(timed_script)+_review_joins(data['pages'],pauses)+_review_inside(timed_script,pauses)
    listening = _listening_checks(timed_script, [*classroom,*warnings,*terminology['items']])
    audio_attention=any(row['code'] in ('in-cue-hesitation','audible-cue-gap') for row in classroom)
    report={
        'status':'attention' if warnings or audio_attention else 'pass','duration':round(len(samples)/rate,3),'sample_rate':rate,
        'peak_dbfs':round(_db(peak),2),'rms_dbfs':round(_db(rms),2),'clipping_ratio':round(clip,7),
        'long_silences':long_silence,'planned_silences':planned,'cues':len(cues),'word_timing_coverage':round(timed/max(1,len(cues)),3),
        'warnings':warnings,'terminology':terminology,
        'classroom_delivery':classroom,'listening_checks':listening,
    }
    (project/'voice-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report

def export_listening_clip(project, cue_id, context=False):
    """Extract one whole cue from the already mastered narration for audition."""
    project = Path(project)
    data = json.loads((project / 'timeline.json').read_text())
    all_cues = _absolute_cues(data['pages']) if context else []
    for page_index, page in enumerate(data['pages'], 1):
        for cue_index, cue in enumerate(page['cues'], 1):
            if cue['id'] != cue_id:
                continue
            offset = page.get('start', 0)
            suffix = '-context' if context else ''
            output = project / 'review-audio' / f'cue-{page_index:03d}-{cue_index:03d}{suffix}.wav'
            output.parent.mkdir(exist_ok=True)
            with wave.open(str(project / 'narration.wav'), 'rb') as source:
                rate = source.getframerate()
                begin, finish = offset + cue['start'], offset + cue['end']
                if context:
                    i = next(i for i, item in enumerate(all_cues) if item['id'] == cue_id)
                    begin, finish = all_cues[max(0,i-1)]['start'],all_cues[min(len(all_cues)-1,i+1)]['end']
                start = max(0, round((begin - .2) * rate))
                end = min(source.getnframes(), round((finish + .2) * rate))
                source.setpos(start)
                with wave.open(str(output), 'wb') as clip:
                    clip.setparams(source.getparams())
                    clip.writeframes(source.readframes(end - start))
            return str(output.resolve())
    raise ValueError(f'Cue not found in timeline: {cue_id}')

def export_term_reel(project, items):
    """Collect first occurrences of each distinct risky reading for one listening pass."""
    folder = Path(project) / 'review-audio'
    folder.mkdir(exist_ok=True)
    seen = set()
    intervals = []
    for item in items:
        if not {'letter_or_symbol', 'polyphonic', 'configured_pronunciation'}.intersection(item['categories']):
            continue
        signature = (item['term'], item['reference_reading'], tuple(sorted(item['minimax_rules_sent'].items())))
        if 'viewer_feedback' in item['categories']:
            signature += (item['cue'],)
        if signature in seen:
            continue
        seen.add(signature)
        intervals.append((max(0, item['start'] - .65), item['end'] + .65, item))
    clips = []
    for start, end, item in sorted(intervals, key=lambda entry: entry[0]):
        word = {'term': item['term'], 'reading': item['reference_reading'], 'cue': item['cue']}
        if clips and start <= clips[-1]['source_end']:
            clips[-1]['source_end'] = max(end, clips[-1]['source_end'])
            clips[-1]['terms'].append(word)
        else:
            clips.append({'source_start': start, 'source_end': end, 'terms': [word]})
    target = folder / 'term-reel.wav'
    if clips:
        import tempfile
        with wave.open(str(Path(project) / 'narration.wav'), 'rb') as source, tempfile.TemporaryDirectory(dir=folder) as tmp:
            rate = source.getframerate()
            frames = source.getnframes()
            pause = round(.35 * rate)
            cursor = 0
            partial = Path(tmp) / target.name
            with wave.open(str(partial), 'wb') as out:
                out.setparams(source.getparams())
                for clip in clips:
                    lo = round(clip['source_start'] * rate)
                    hi = min(frames, round(clip['source_end'] * rate))
                    if hi <= lo:
                        raise ValueError('读音清单时间超出当前配音，请按同一版本重建时间轴。')
                    source.setpos(lo)
                    if cursor:
                        out.writeframes(bytes(pause * source.getnchannels() * source.getsampwidth()))
                        cursor += pause
                    clip['reel_start'] = round(cursor / rate, 3)
                    out.writeframes(source.readframes(hi - lo))
                    cursor += hi - lo
                    clip['source_end'] = round(hi / rate, 3)
                    clip['reel_end'] = round(cursor / rate, 3)
            partial.replace(target)
    else:
        target.unlink(missing_ok=True)
    manifest = {'audio': str(target.resolve()) if clips else None, 'status': 'pending_listening' if clips else 'no_matches', 'clips': clips}
    (folder / 'term-reel.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--strict',action='store_true');a=p.parse_args()
    report=audit(a.project);print(json.dumps(report,ensure_ascii=False))
    if a.strict and strict_findings(report):raise SystemExit(1)

def strict_findings(report):
    return [*report.get('warnings',[]),*report.get('classroom_delivery',[])]

if __name__=='__main__':main()
