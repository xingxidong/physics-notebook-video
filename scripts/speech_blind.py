"""Build anonymized original-speed audio trials and score real and injected cases separately."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import subprocess
import tempfile
import wave

from feedback_bank import save_report
from tone_review import _digest


def prepare(manifest, dest):
    cases=json.loads(manifest.read_text())
    if not isinstance(cases,list) or not cases:
        raise ValueError('请提供至少一段有来源的原声。')
    if dest.exists():
        raise ValueError('请为新一轮盲测选择新目录，以保留以前的答卷。')
    public=[]
    key={}
    unique=set()
    ordered=random.SystemRandom().sample(cases,len(cases))
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        work=Path(tmp)/'round'
        play=work/'clips'
        play.mkdir(parents=True)
        for n,case in enumerate(ordered,1):
            src=manifest.parent/case['file']
            label=case['label']
            if (label not in ('good','bad','unlabeled') or case['origin'] not in ('real','control')
                    or not case.get('basis') or _digest(src)!=case['sha256']):
                raise ValueError('每段需要原文件指纹、来源、听感标签及依据。')
            ident=f'{n:03d}'
            wav=play/f'{ident}.wav'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(src),'-map','0:a:0','-map_metadata','-1',
                            '-ac','1','-ar','16000','-c:a','pcm_s16le',str(wav)],check=True)
            sha=_digest(wav)
            identity=(sha,json.dumps(case.get('window')),case['target'])
            if identity in unique:
                raise ValueError('同一段音频的同一目标重复入选。')
            unique.add(identity)
            public.append(dict(id=ident,file=wav.name,sha256=sha,target=case['target'],
                               task=case['task'],window=case.get('window')))
            key[ident]=dict(label=label,origin=case['origin'],basis=case['basis'],sha256=sha)
        save_report(play/'trials.json',public)
        save_report(work/'key.json',key)
        work.rename(dest)
    return public


def score(folder,answers,author_requests=None):
    key=json.loads((folder/'key.json').read_text())
    trials=json.loads((folder/'clips/trials.json').read_text())
    if not isinstance(answers,dict) or answers.keys()-key.keys():
        raise ValueError('答卷编号与当前盲测不符。')
    if set(key)!={t['id'] for t in trials}:
        raise ValueError('本轮音频清单与答案表不符。')
    if author_requests is not None and (not isinstance(author_requests, list) or any(
            not isinstance(ident, str) or ident not in key for ident in author_requests)):
        raise ValueError('作者需裁定的样本须按本轮试听编号登记。')
    counts=defaultdict(Counter)
    by_task=defaultdict(Counter)
    for trial in trials:
        ident=trial['id']
        k=key[ident]
        if _digest(folder/'clips'/trial['file'])!=k['sha256'] or k['sha256']!=trial['sha256']:
            raise ValueError('试听样本发生变化。')
        ans=answers.get(ident,'unsure')
        if ans not in ('bad','good','unsure'):
            raise ValueError('每处填写 good、bad 或 unsure。')
        if k['label']=='unlabeled':
            outcome='unlabeled'
        elif ans=='unsure':
            outcome='undecided_'+k['label']
        elif ans==k['label']:
            outcome='correct_'+ans
        else:
            outcome='missed_bad' if ans=='good' else 'false_alarm'
        counts[k['origin']][outcome]+=1
        by_task[(k['origin'],trial['task'])][outcome]+=1
    real=counts.get('real',Counter())
    audit=dict(real_missed_bad=real['missed_bad'],real_false_alarm=real['false_alarm'],
               labeled_bad=sum(real[k] for k in ('correct_bad','missed_bad','undecided_bad')),
               labeled_good=sum(real[k] for k in ('correct_good','false_alarm','undecided_good')),
               undecided_labeled=real['undecided_bad']+real['undecided_good'],
               real_unlabeled=real['unlabeled'],
               author_requested=len(set(author_requests)) if author_requests is not None else None)
    return dict(metrics=audit,totals=dict(counts), by_task=[dict(origin=o,task=t,counts=c) for (o,t),c in by_task.items()])


def screen(play, model_root=None):
    """Read only anonymous files and linguistic targets. Never read the private answer key."""
    from term_flow import RATE, flow_evidence
    answers={}
    evidence={}
    for trial in json.loads((play/'trials.json').read_text()):
        ident=trial['id']
        src=play/trial['file']
        if _digest(src)!=trial['sha256']:
            raise ValueError('匿名样本指纹已变化。')
        answers[ident]='unsure'
        window=trial.get('window')
        if not window:
            evidence[ident]={'status':'needs_timing'}
            continue
        a,b=window
        with wave.open(str(src),'rb') as wav:
            lo,hi=round(a*RATE),round(b*RATE)
            if not 0<=lo<hi<=wav.getnframes():
                raise ValueError('目标区间超出原句。')
            wav.setpos(lo)
            raw=wav.readframes(hi-lo)
        if trial['task']=='flow':
            gap,restart=flow_evidence(raw)
            evidence[ident]=dict(quiet_ms=gap,possible_restart=restart)
            if (gap is not None and gap>=140) or restart:
                answers[ident]='bad'
        elif model_root and trial['task'] in ('tone','letter'):
            from speech_probe import measure
            result=measure(src,a,b,language='zh' if trial['task']=='tone' else 'en',
                           root=model_root,expected=trial['target'])
            evidence[ident]=result
            answers[ident]={'supports_target':'good','possible_mismatch':'bad'}.get(result['status'],'unsure')
        else:
            evidence[ident]={'status':'needs_context_listening'}
    return answers,evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    subs=parser.add_subparsers(dest='command',required=True)
    a=subs.add_parser('prepare')
    a.add_argument('manifest',type=Path)
    a.add_argument('dest',type=Path)
    a=subs.add_parser('screen')
    a.add_argument('clips',type=Path)
    a.add_argument('answers',type=Path)
    a.add_argument('--model-root',type=Path)
    a=subs.add_parser('score')
    a.add_argument('folder',type=Path)
    a.add_argument('answers',type=Path)
    a.add_argument('--author-requests',type=Path,help='实际需要作者判断的试听编号 JSON 列表')
    args=parser.parse_args()
    if args.command=='prepare':
        print(f'已生成 {len(prepare(args.manifest,args.dest))} 个匿名原速片段。')
    elif args.command=='screen':
        answers,evidence=screen(args.clips,args.model_root)
        save_report(args.answers,answers)
        save_report(args.answers.with_name(args.answers.stem+'-evidence.json'),evidence)
    else:
        result=score(args.folder,json.loads(args.answers.read_text()),
                     json.loads(args.author_requests.read_text()) if args.author_requests else None)
        save_report(args.folder/'score.json',result)
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
