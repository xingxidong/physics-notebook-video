"""Locate continuity problems in the audio actually embedded in a delivered video."""
import argparse
from bisect import bisect_right
import json
from pathlib import Path
import re
import subprocess

from pronunciation import spoken_symbols, term_pattern
from terminology_review import BUILTIN_TERMS, _word_windows
from voice_quality import TEACHING_PAUSES

PUNCTUATION = '，、,。！？!?；;：:'
SENTENCE_END = '。！？!?'
PROTECTED = {'下标', '乘以', '除以', '正弦', '余弦', '的平方', '的平方根', '的绝对值', '之差', '的和', '相减', '分子', '分母', '宽高比'}
SILENCE_EVENT = re.compile(r'silence_(start|end):\s*([\d.eE+-]+)')
SUBTITLE_TIME = re.compile(r'(\d+):(\d+):(\d+)[,.](\d+)')


def quiet_spans(video):
    result = subprocess.run(['ffmpeg','-nostdin','-hide_banner','-v','info','-i',str(video),
        '-map','0:a:0','-vn','-sn','-dn','-af','silencedetect=noise=-43dB:d=0.075',
        '-f','null','-'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
    start = None
    spans = []
    for kind, number in SILENCE_EVENT.findall(result.stderr):
        time = float(number)
        if kind == 'start':
            start = time
        elif start is not None:
            if time > start:
                spans.append((start, time))
            start = None
    return spans


def subtitle_timeline(video):
    output = subprocess.check_output(['ffmpeg','-nostdin','-v','error','-i',str(video),
        '-map','0:s:0','-f','srt','pipe:1'], text=True)
    def seconds(match):
        h, m, s, fraction = match.groups()
        return int(h)*3600 + int(m)*60 + int(s) + float('0.' + fraction)
    cues = []
    for block in re.split(r'\r?\n\s*\r?\n', output.strip()):
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        times = list(SUBTITLE_TIME.finditer(lines[1]))
        if len(times) != 2:
            continue
        cues.append(dict(id=lines[0], start=seconds(times[0]), end=seconds(times[1]), tts=''.join(lines[2:])))
    return {'pages':[{'id':'captions','start':0,'cues':cues}]}


def inspect(video, timeline=None):
    video = Path(video).resolve()
    if timeline is None:
        timeline = subtitle_timeline(video)
    spans = quiet_spans(video)
    offsets = [a for a,_ in spans]
    terms = term_pattern(BUILTIN_TERMS | PROTECTED)
    candidates = []
    cues = []
    aligned_cues = 0
    for page in timeline['pages']:
        origin = page.get('start', 0)
        for cue in page.get('cues', []):
            line = cue.get('tts') or cue.get('text') or cue.get('say')
            if not line or cue['end'] <= cue['start']:
                continue
            a, b = origin+cue['start'], origin+cue['end']
            cues.append((a, b, line, page.get('id'), cue))
            windows = _word_windows(cue, line)
            if not windows:
                continue
            masks = [*terms.finditer(line), *spoken_symbols(line)]
            chars = [(i,c) for i,c in enumerate(line) if c.isalnum()]
            aligned_cues += 1
            for i, ((li,lc),(ri,rc)) in enumerate(zip(chars,chars[1:])):
                if any(p in line[li+1:ri] for p in PUNCTUATION):
                    continue
                left = origin+cue['start']+windows[i][1]
                right = origin+cue['start']+windows[i+1][0]
                if right-left < .13:
                    continue
                protected = next((m.group() for m in masks if m.start()<=li<ri<m.end()),None)
                if protected is None and (lc in '的乘除减加负正是等为' or rc in '和差积商'):
                    protected = lc + rc
                for x,y in spans[max(0,bisect_right(offsets,left)-1):bisect_right(offsets,right)]:
                    if y-x < (.24 if protected else .52) or min(y,right+.04)-max(x,left-.04) < (y-x)*.65:
                        continue
                    candidates.append(dict(kind='split-phrase',page=page.get('id'),cue=cue['id'],
                        start=x,end=y,quiet_seconds=round(y-x,3),phrase=protected or lc+rc,
                        text=line,cut_offset=ri))
    cues.sort(key=lambda row:row[0])
    for previous, following in zip(cues,cues[1:]):
        a,b,line,page,left=previous
        c,d,next_line,next_page,right=following
        if left.get('pause_reason') in TEACHING_PAUSES or right.get('pause_reason') in TEACHING_PAUSES or c-b>2:
            continue
        edge=(b+c)/2
        active = spans[max(0,bisect_right(offsets,edge-.16)-1):bisect_right(offsets,edge+.16)]
        quiet=max((y-x for x,y in active if x<=edge+.12 and y>=edge-.12),default=0)
        kind=None
        if line.rstrip().endswith(tuple(SENTENCE_END)) and quiet<.115 and c-b<.16:
            kind='tight-join'
        elif page==next_page and not line.rstrip().endswith(tuple(SENTENCE_END)) and quiet>=.74:
            kind='long-join'
        if kind:
            candidates.append(dict(kind=kind,page=next_page,cue=right['id'],start=round(edge,3),end=round(edge,3),
                quiet_seconds=round(quiet,3),text=line+'｜'+next_line,previous=left['id']))
    from handout_bundle import digest
    candidates.sort(key=lambda row:row['start'])
    return dict(file=str(video),sha256=digest(video),spoken_cues=len(cues),
                aligned_cues=aligned_cues,
                quiet_spans=len(spans), candidates=candidates)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path)
    parser.add_argument('--timeline',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    timeline=json.loads(args.timeline.read_text()) if args.timeline else None
    report=json.dumps(inspect(args.video,timeline),ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(report+'\n',encoding='utf-8')
    else:
        print(report)


if __name__=='__main__':
    main()
