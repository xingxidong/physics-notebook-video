#!/usr/bin/env python3
"""Local narration quality report: levels, silence, pacing and script hygiene."""
import argparse,array,json,math,re,wave
from pathlib import Path

TEMPLATE_PHRASES=('首先我们来','接下来我们将','综上所述','通过以上分析我们可以看出','这道题告诉我们')
DEFENSIVE_PHRASES=('不表示','不代表','不意味着','不能据此认为','并不是说')

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
    long_silence=_silences(samples,rate)
    for span in long_silence:warnings.append({'code':'long-silence','message':f'{span["start"]:.2f}—{span["end"]:.2f} 秒存在较长静音。'})
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
    report={
        'status':'pass' if not warnings else 'attention','duration':round(len(samples)/rate,3),'sample_rate':rate,
        'peak_dbfs':round(_db(peak),2),'rms_dbfs':round(_db(rms),2),'clipping_ratio':round(clip,7),
        'long_silences':long_silence,'cues':len(cues),'word_timing_coverage':round(timed/max(1,len(cues)),3),
        'warnings':warnings,
    }
    (project/'voice-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--strict',action='store_true');a=p.parse_args()
    report=audit(a.project);print(json.dumps(report,ensure_ascii=False))
    if a.strict and report['warnings']:raise SystemExit(1)

if __name__=='__main__':main()
