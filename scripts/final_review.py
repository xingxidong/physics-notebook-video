"""Bind producer reviews and the delivery decision to the actual exported lesson."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from handout_bundle import digest
from lesson_review import fingerprint


def load(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def save(path,data):
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as out:
        json.dump(data,out,ensure_ascii=False,indent=2)
    os.replace(out.name,path)


def token(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def binding(project,lesson,video):
    receipt=project/'handout-delivery/receipt.json'
    return {'source_sha256':fingerprint(project,lesson),'media_sha256':digest(video),
            'timeline_sha256':digest(project/'timeline.json'),
            'handout_receipt_sha256':digest(receipt) if receipt.is_file() else None}


def invalidate(project):
    (project/'delivery-files.json').unlink(missing_ok=True)


def attach(project,lesson,result):
    """Unresolved heuristics need explicit observations; hard errors cannot be waived."""
    video=Path(result.get('coverage',{}).get('media',{}).get('file',''))
    if not video.is_absolute():video=project/video
    if not video.is_file() or not result.get('source_sha256'):
        return result
    bound=binding(project,lesson,video)
    tasks=list(dict.fromkeys(result['manual_review']['tasks']))
    tasks.extend('复核检查提示：'+row['message'] for row in result['findings'] if row['severity']!='error')
    for row in result.get('coverage',{}).get('derivation_evidence',[]):
        tasks.append(f"核对 {row['page']}/{row['cue']} 的推导 {row['step']}：实际口播中的运算与落笔顺序逐步对应。")
    stored=load(project/'final-review-records.json').get('records',{})
    items=[]
    for task in dict.fromkeys(tasks):
        identity=token(task)[:16]
        stamp=token([bound,task])
        previous=stored.get(identity,{})
        passed=(previous.get('token')==stamp and previous.get('reviewer') and previous.get('evidence'))
        items.append({'id':identity,'task':task,'token':stamp,'status':'reviewed' if passed else 'pending',
                      **({'reviewer':previous['reviewer'],'evidence':previous['evidence']} if passed else {})})
    result['review_binding']=bound
    result['manual_review']={'status':'complete' if all(i['status']=='reviewed' for i in items) else 'pending',
                             'tasks':tasks,'items':items}
    if not any(f['severity']=='error' for f in result['findings']) and result['manual_review']['status']=='complete':
        result['status']='reviewed'
    return result


def record(project,lesson,task,stamp,reviewer,evidence):
    report=load(project/'quality-report.json')
    if report.get('stage')!='final' or not report.get('review_binding'):
        raise ValueError('先对当前成片运行 quality-check --stage final。')
    video=Path(report['coverage']['media']['file'])
    if not video.is_absolute():video=project/video
    if binding(project,lesson,video)!=report['review_binding']:
        raise ValueError('课程、录音、画面或讲义已改变，请重新生成本版检查清单。')
    row=next((r for r in report['manual_review'].get('items',[]) if r['id']==task),None)
    if not row or row['token']!=stamp:
        raise ValueError('使用本版实际检查项的 id 和 token 登记。')
    if not reviewer.strip() or not evidence.strip() or evidence.strip().lower() in {'pass','ok','通过','已听','完成'}:
        raise ValueError('写明实际复核者和观察结果，包括相应句子、画面或时间位置。')
    path=project/'final-review-records.json'
    data=load(path);data.setdefault('records',{})[task]={'token':stamp,'reviewer':reviewer.strip(),'evidence':evidence.strip()}
    save(path,data)
    updated=attach(project,lesson,report)
    save(project/'quality-report.json',updated)
    return {'recorded':task,'remaining':sum(r['status']!='reviewed' for r in updated['manual_review']['items'])}


def require(project,lesson,video):
    if lesson.get('kind') in ('concept','problem'):
        if not lesson.get('review_required'):
            raise ValueError('正式习题课与新授课须启用教案审阅，再生成本版交付记录。')
        from lesson_review import require as require_plan
        require_plan(project,lesson)
    report=load(project/'quality-report.json')
    if report.get('stage')!='final' or report.get('review_binding')!=binding(project,lesson,video):
        raise ValueError('交付前须检查同一版视频、时间轴、课程源和讲义。')
    report=attach(project,lesson,report)
    if any(row['severity']=='error' for row in report.get('findings',[])):
        raise ValueError('成片还有未解决的检查错误，保留为待审件。')
    if report.get('manual_review',{}).get('status')!='complete' or report.get('status')!='reviewed':
        raise ValueError('制作端观看与试听尚未逐项完成，保留为待审件。')
    return report


def register(subs):
    parser=subs.add_parser('review-final',help='Record one actually reviewed final-video item')
    parser.add_argument('project')
    for name in ('task','token','reviewer','evidence'):parser.add_argument('--'+name,required=True)
    parser=subs.add_parser('finalize',help='Publish delivery manifest only after final checks and producer review')
    parser.add_argument('project');parser.add_argument('--video-file',default='video.mp4')


def dispatch(args):
    from production_workflow import effective
    from lesson_review import export_delivery
    project=Path(args.project).resolve();lesson=effective(project)
    if args.command=='review-final':
        return record(project,lesson,args.task,args.token,args.reviewer,args.evidence)
    export_delivery(project,lesson,video_file=args.video_file)
    from lesson_quality import run
    run(project,'final',video_file=args.video_file)
    return export_delivery(project,lesson,publish=True,video_file=args.video_file)
