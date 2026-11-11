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
    for page in pages:
        offset = page.get('start', 0)
        cues = page['cues']
        for before, after in zip(cues, cues[1:]):
            if before.get('pause_reason') in TEACHING_PAUSES or after.get('pause_reason') in TEACHING_PAUSES:
                continue
            join = offset + (before['end'] + after['start']) / 2
            index = bisect_right(starts, join) - 1
            if index < 0:
                continue
            pause = pauses[index]
            if join >= pause['end'] or pause['duration'] >= 1.8:
                continue
            findings.append({
                'code': 'audible-cue-gap', 'cue': after['id'], 'related_cues': [before['id'], after['id']],
                'start': pause['start'], 'end': pause['end'], 'quiet_seconds': pause['duration'],
                'message': '这两段之间有一段实测静音。连着回听，判断这个停顿能否让学生跟上当前思路。',
            })
    return findings

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
    pauses=_silences(samples,rate,min_seconds=.85)
    long_silence=[span for span in pauses if span['duration']>=1.8];planned=[]
    for span in long_silence:
        intentional=any(c.get('pause_reason') in TEACHING_PAUSES and span['start']<=p.get('start',0)+c['end']<=span['end'] for p in data['pages'] for c in p['cues'])
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
    timed_script = []
    for page in data['pages']:
        offset = page.get('start', 0)
        for cue in page['cues']:
            timed_script.append({**cue, 'start': offset + cue['start'], 'end': offset + cue['end']})
    report={
        'status':'pass' if not warnings else 'attention','duration':round(len(samples)/rate,3),'sample_rate':rate,
        'peak_dbfs':round(_db(peak),2),'rms_dbfs':round(_db(rms),2),'clipping_ratio':round(clip,7),
        'long_silences':long_silence,'planned_silences':planned,'cues':len(cues),'word_timing_coverage':round(timed/max(1,len(cues)),3),
        'warnings':warnings,'terminology':terminology,
        'classroom_delivery':review_narration(timed_script)+_review_joins(data['pages'],pauses),
    }
    (project/'voice-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report

def export_listening_clip(project, cue_id):
    """Extract one whole cue from the already mastered narration for audition."""
    project = Path(project)
    data = json.loads((project / 'timeline.json').read_text())
    for page_index, page in enumerate(data['pages'], 1):
        for cue_index, cue in enumerate(page['cues'], 1):
            if cue['id'] != cue_id:
                continue
            offset = page.get('start', 0)
            output = project / 'review-audio' / f'cue-{page_index:03d}-{cue_index:03d}.wav'
            output.parent.mkdir(exist_ok=True)
            with wave.open(str(project / 'narration.wav'), 'rb') as source:
                rate = source.getframerate()
                start = max(0, round((offset + cue['start'] - .2) * rate))
                end = min(source.getnframes(), round((offset + cue['end'] + .2) * rate))
                source.setpos(start)
                with wave.open(str(output), 'wb') as clip:
                    clip.setparams(source.getparams())
                    clip.writeframes(source.readframes(end - start))
            return str(output.resolve())
    raise ValueError(f'Cue not found in timeline: {cue_id}')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--strict',action='store_true');a=p.parse_args()
    report=audit(a.project);print(json.dumps(report,ensure_ascii=False))
    if a.strict and report['warnings']:raise SystemExit(1)

if __name__=='__main__':main()
