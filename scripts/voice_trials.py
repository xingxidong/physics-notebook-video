#!/usr/bin/env python3
"""Run the same complete classroom sentences with a selected local/API/recorded voice."""
import argparse
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import urllib.parse
from voice import synth
from card_speech import merged_provider
from trial_materials import build_plan, check_plan, make_case, write_plan
from trial_review import evidence_token, import_review, judgment_template, speech_identity, run_status

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'assets/starter-kit/voice-trial'


def run(config,output,ids=None,plan_file=None,project=None,max_extra=16):
    speech=json.loads(config.read_text());output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    if speech.get('backend')=='qwen':
        from qwen_voice import config as qwen_config
        # Relative example assets travel with the config, independently of output location.
        for name in ('python','model','reference_audio'):
            raw=speech.get('qwen',{}).get(name)
            if raw:
                path=Path(raw).expanduser()
                speech['qwen'][name]=str(path if path.is_absolute() else config.resolve().parent/path)
        speech['qwen']=qwen_config(output,speech)
    material=json.loads(plan_file.read_text()) if plan_file else build_plan(project,max_extra=max_extra)
    check_plan(material)
    if material.get('project'):
        from production_workflow import read
        started=read(Path(material['project'])/'classroom-start.json')
        if started and not started.get('first_take',True):
            speech['_classroom_take']=started['run']
    source=material['items']
    wanted=set(ids or (x['id'] for x in source))
    missing=wanted-{x['id'] for x in source}
    if missing:raise ValueError('Unknown trial sentence IDs: '+', '.join(sorted(missing)))
    rows=[x for x in source if x['id'] in wanted]
    records=[]
    identity=speech_identity(speech)
    result={'schema':2,'backend':speech['backend'],'speech_fingerprint':identity,
            'source_plan':{k:material[k] for k in ('project','lesson_files','coverage','final_review')},
            'not_requested':[x['id'] for x in source if x['id'] not in wanted],
            'status':'pending','items':records}
    folder=output/'audio';folder.mkdir(exist_ok=True)
    for row in rows:
        context=json.loads(json.dumps(row['context']))
        context['speech']={**{k:v for k,v in speech.items() if k in (
            'physics_terms','term_uses','non_terms','plain_pronunciation','minimax_pronunciation')},**context.get('speech',{})}
        row=make_case(row['id'],row['text'],row['origin'],context=context,flow=row['flow'],
                      fallback=row.get('fallback',()),sources=row['sources'])
        cue={'id':row['id'],'tts':row['text'],'speed':speech.get('speed',1)}
        plan=row['planned_input']
        if plan['conflicts'] or plan.get('provider_exclusions') or any(not t['pinyin'] for t in row['targets']):
            raise ValueError('本句有待确定的读法，请先补充语境：'+row['id'])
        if speech['backend']=='qwen':cue['_qwen_input']=plan['local_text']
        if speech['backend']=='minimax':cue['_card_provider']=merged_provider([plan])
        if speech['backend']=='user':
            base=Path(speech['recordings_dir']).expanduser()
            if not base.is_absolute():base=config.resolve().parent/base
            path=next((base/(row['id']+ext) for ext in ('.wav','.mp3','.m4a') if (base/(row['id']+ext)).is_file()),None)
            if path is None:raise ValueError('Missing complete recording: '+row['id'])
            cue['audio']=str(path)
        audio=synth(output,speech,cue)
        dest=folder/(row['id']+'.wav');shutil.copy2(audio['file'],dest)
        entry={**row,'audio':'audio/'+dest.name,'duration':audio['duration'],
                        'audio_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
                        'synthesis_signature':audio.get('signature',{}),'synthesis':audio.get('synthesis'),
                        'planned_input':plan,'review_status':'pending'}
        entry['review_token']=evidence_token(entry,identity)
        records.append(entry)
        (output/'trial-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    with (output/'scorecard.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(['sentence','text','check','expected','status','note'])
        for row in records:
            targets={t['id']:t for t in row['targets']}
            for check in row['checks']:
                target=targets.get(check.get('target'),{})
                writer.writerow([row['id'],row['text'],check['id'],target.get('pinyin',''),'pending',''])
    (output/'listening-template.json').write_text(json.dumps(judgment_template(result),ensure_ascii=False,indent=2))
    compare([output],output/'listen.html')
    return {'sentences':len(records),'results':str(output/'trial-results.json'),'review_status':'pending',
            'not_requested':len(result['not_requested']),'deferred':len(material['coverage']['deferred'])}


def compare(runs,output):
    output=output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    data=[(p,json.loads((p/'trial-results.json').read_text())) for p in runs]
    rows={}
    for p,run in data:
        for x in run['items']:rows.setdefault(x['id'],x)
    esc=html.escape
    body=['<!doctype html><meta charset="utf-8"><title>固定课堂句试音</title><style>body{max-width:1100px;margin:36px auto;font:18px/1.7 sans-serif}section{padding:20px;border-bottom:1px solid #ddd}audio{display:block;width:100%}small{color:#555}table{width:100%}td{vertical-align:top;padding:10px}</style>',
          '<h1>课堂句试音与历史错例</h1><p>按目标听声调、字母、整词与接缝。每次重新生成的声音独立判断；试音不代替成片逐处检查。</p>']
    for id,row in rows.items():
        body.append('<section><h2>'+esc(id)+'</h2><p>'+esc(row['text'])+'</p><p>'+esc(row['flow'])+'</p><small>'+esc('; '.join(f"{x['term']}@{x['offset']} {x['pinyin']}" for x in row['targets']))+'</small><table><tr>')
        for p,run in data:
            found=next((x for x in run['items'] if x['id']==id),None)
            body.append('<td>'+esc(p.name)+'<br>')
            if found:
                link=urllib.parse.quote(os.path.relpath(p/found['audio'],output.parent),safe='/')
                body.append('<audio controls preload="none" src="'+link+'"></audio>')
            else:body.append('本轮未录')
            body.append('</td>')
        body.append('</tr></table></section>')
    output.write_text(''.join(body))


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('--project',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-extra',type=int,default=16);p.add_argument('--rotation',type=int,default=0)
    p=sub.add_parser('run');p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--ids',nargs='+');p.add_argument('--plan',type=Path);p.add_argument('--project',type=Path);p.add_argument('--max-extra',type=int,default=16)
    p=sub.add_parser('compare');p.add_argument('runs',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True)
    p=sub.add_parser('review');p.add_argument('run',type=Path);p.add_argument('--judgments',type=Path,required=True)
    p=sub.add_parser('status');p.add_argument('run',type=Path)
    args=parser.parse_args()
    if args.command=='plan':
        plan=write_plan(args.output,project=args.project,max_extra=args.max_extra,rotation=args.rotation)
        print(json.dumps({'file':str(args.output),'sentences':len(plan['items']),'extra':plan['coverage']['selected_extra'],
                          'deferred':len(plan['coverage']['deferred']),'needs_material':len(plan['coverage']['needs_material'])},ensure_ascii=False))
    elif args.command=='run':print(json.dumps(run(args.config,args.output,args.ids,args.plan,args.project,args.max_extra),ensure_ascii=False))
    elif args.command=='review':
        print(json.dumps(import_review(args.run,json.loads(args.judgments.read_text())),ensure_ascii=False))
        compare([args.run],args.run/'listen.html')
    elif args.command=='status':print(json.dumps(run_status(args.run),ensure_ascii=False,indent=2))
    else:compare(args.runs,args.output);print(args.output)


if __name__=='__main__':main()
