"""Check each physics term against the syllables actually decoded in its own sentence."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
import tempfile

from feedback_bank import save_report
from pronunciation import classroom_syllables
from tone_review import _digest


def decode_sentence(pcm, start, end, net):
    """Decode two contexts per sentence, independent of how many overlapping terms it contains."""
    import numpy as np
    from term_flow import RATE
    windows=[]
    for pad in (.16,.42):
        tokens=[]
        lo=start
        while lo < end:
            hi=min(end,lo+18)
            left=max(0,lo-pad)
            first,last=round(left*RATE),round((hi+pad)*RATE)
            pcm.seek(2*first)
            raw=pcm.read(2*(last-first))
            if len(raw)/2 < round((hi-left-.08)*RATE):
                raise ValueError('本句超出成片音轨。')
            decoded=net.decode(np.frombuffer(raw,dtype='<i2').astype('float32')/32768)
            for sound,t in decoded:
                if lo <= left+t < hi:
                    tokens.append((sound,round(left+t,4)))
            lo=hi
        windows.append(tokens)
    return windows


def locate(rows,windows):
    """Match without tones. Repeated or homophonous words must have distinct supported positions."""
    from speech_probe import phonetic_form
    def stem(p):
        return phonetic_form(p).rstrip('12345')
    groups=defaultdict(list)
    results={}
    for row in rows:
        results[row['id']] = dict(id=row['id'], term=row['term'], expected=row['expected'],
                                  offset=row['offset'], page=row['page'],cue=row['cue'], time=row['start'],
                                  heard_windows=[], status='needs_listening')
        if row['split_in_script']:
            results[row['id']]['reason']='split_in_script'
        elif not row['expected']:
            results[row['id']]['reason']='reading_unresolved'
        else:
            groups[tuple(map(stem,row['expected'].split()))].append(row)
    for wanted, group in groups.items():
        group.sort(key=lambda r:r['offset'])
        n=len(wanted)
        for seq in windows:
            stems=[stem(sound) for sound,_ in seq]
            candidates=[seq[i:i+n] for i in range(len(seq)-n+1) if tuple(stems[i:i+n])==wanted]
            for rank,row in enumerate(group):
                choice=[]
                if row['timing']=='word':
                    # A coarse context can contain several copies of the same word.
                    near=[part for part in candidates if row['start']-.035<=part[0][1] and part[-1][1]<=row['end']+.035]
                    if len(near)==1:
                        choice=near[0]
                    elif not near:
                        bounded=[part for part in seq if row['start']<=part[1]<row['end']]
                        if len(bounded)==n:
                            choice=bounded
                elif len(candidates)==len(group):
                    choice=candidates[rank]
                results[row['id']]['heard_windows'].append(dict(
                    syllables=[phonetic_form(v) for v,_ in choice], times=[t for _,t in choice]))
            # Distinct written occurrences cannot share decoded syllables.
            assigned=defaultdict(list)
            for row in group:
                w=results[row['id']]['heard_windows'][-1]
                for t in w['times']:
                    assigned[t].append(w)
            for matches in assigned.values():
                if len(matches)>1:
                    for w in matches:
                        w.update(syllables=[],times=[])
        for row in group:
            item=results[row['id']]
            a,b=item['heard_windows']
            if not a['times'] or not b['times'] or any(abs(x-y)>.18 for x,y in zip(a['times'],b['times'])):
                item['reason']='uncertain_location'
                continue
            expected = ' '.join(phonetic_form(s) for s in row['expected'].split())
            ok=[all(classroom_syllables(row['term'],expected,' '.join(w['syllables']))) for w in (a,b)]
            item['time']=a['times'][0]
            item['status']=('supports_target' if all(ok) else 'possible_mismatch'
                            if a['syllables']==b['syllables'] else 'needs_listening')
            if item['status']=='needs_listening':
                item['reason']='windows_disagree'
    return [results[r['id']] for r in rows]


def probe_terms(project, report, media, model_root):
    from speech_probe import model, model_signature
    from speech_context import digest
    if report.get('status')=='blocked' or 'items' not in report:
        raise ValueError('术语清单未生成完整，请重新运行成片术语审查。')
    rows=report['items']
    if media.resolve()!=Path(report['file']).resolve() or (rows and report.get('sha256')!=_digest(media)):
        raise ValueError('术语清单与本次交付文件不匹配。')
    by_sentence=defaultdict(list)
    for row in rows:
        sentence=row['id'].split('.',2)[:2]
        by_sentence[tuple(sentence)].append(row)
    cache=project/'review-audio'
    cache.mkdir(exist_ok=True)
    signature=None
    results=[]
    with tempfile.TemporaryFile() as pcm:
        decoded=False
        for group in by_sentence.values():
            first=group[0]
            eligible=any(r['expected'] and not r['split_in_script'] for r in group)
            if eligible and signature is None:
                signature=digest([model_signature(model_root,'zh'),_digest(Path(__file__))])
            key=digest([signature,[(r['id'],r['token'],r['cue_start'],r['cue_end'],r['start'],r['end']) for r in group]])
            path=cache/f'classroom-probe-{key}.json'
            if path.is_file():
                checked=json.loads(path.read_text())
            else:
                end=max(r['cue_end'] for r in group if not r['split_in_script']) if eligible else first['cue_end']
                windows=[[],[]]
                if eligible:
                    # Cache the independent transcript, so adding a new term does not run the model again.
                    audio_key=digest([signature, first.get('cue_audio_sha256') or report['sha256'],first['cue_start'],end])
                    transcript=cache/f'classroom-syllables-{audio_key}.json'
                    if transcript.is_file():
                        windows=json.loads(transcript.read_text())
                    else:
                        if not decoded:
                            subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(media),'-map','0:a:0','-ac','1',
                                            '-ar','16000','-f','s16le','pipe:1'],stdout=pcm,check=True)
                            decoded=True
                        windows=decode_sentence(pcm,first['cue_start'],end,model(model_root,'zh'))
                        save_report(transcript,windows)
                checked=locate(group,windows)
                save_report(path,checked)
            for item,row in zip(checked,group,strict=True):
                results.append(dict(item,heard_in_final=row['passed']))
    if len(results)!=len(rows) or len({r['id'] for r in results})!=len(rows):
        raise ValueError('声学检查与术语出现次数不一致。')
    from term_comparison import review_repetitions
    comparison = review_repetitions(results,rows)
    return dict(**comparison,file=str(media.resolve()),sha256=report.get('sha256'),terms=len(report['terms']),total=len(rows),
                statuses=dict(Counter(r['status'] for r in results)),listened=sum(r['heard_in_final'] for r in results),
                items=results,classroom_cards=report.get('classroom_cards',{}))
