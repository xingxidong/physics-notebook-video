"""Check what students can actually see at the moments it is used."""
from collections import defaultdict
import math

from board_flow import bounds, references
from concept_units import stage_anchors


def overlap(a,b):
    return min(a[2],b[2])-max(a[0],b[0])>0 and min(a[3],b[3])-max(a[1],b[1])>0


def hits_segment(a,b,box):
    start,end=0.,1.
    for x,y,lower,upper in zip(a,b,box[:2],box[2:]):
        shift=y-x
        if not shift:
            if not lower<=x<=upper:
                return False
            continue
        enter,leave=sorted(((lower-x)/shift,(upper-x)/shift))
        start,end=max(start,enter),min(end,leave)
        if start>end:
            return False
    return True


def check(lesson,pages,timeline):
    from course import anchor
    from models import strokes as motion_strokes

    prepared={page['id']:page for page in timeline['pages']}
    source={page['id']:page for page in pages}
    managed=set(source)
    cues={cue['id']:(p,cue) for p in timeline['pages'] for cue in p['cues']}
    warnings, checkpoints = [], []
    pending=defaultdict(list)

    for unit in lesson.get('concept_units',[]):
        for question in unit.get('questions',[]):
            pending[question['answer_cue']].append(('question-before-answer','start',question['action_ids']))
        for label in unit.get('scene_labels',[]):
            pending[label['first_use_cue']].append(('label-at-use',label.get('first_use_at','end'),[label['action_id']]))
    units_by_point={key:unit for unit in lesson.get('concept_units',[]) for key in unit.get('knowledge_point_ids',[])}
    for point in lesson.get('knowledge_points',[]):
        unit=units_by_point.get(point['id'])
        if not unit or point['page_id'] not in managed:
            continue
        page=prepared[point['page_id']]
        ids=point['statement_action_ids']+point.get('formula_action_ids',[])
        if point.get('name_action_id'):
            ids=ids+[point['name_action_id']]
        # An application on a later page may legitimately use a different diagram.
        cue_id=next((cue for purpose, cue in stage_anchors(unit)
                     if purpose == 'apply' and isinstance(cue, str)), None)
        if cue_id not in cues or cues[cue_id][0]['id']!=page['id']:
            cue_id=page['cues'][-1]['id']
            pending[cue_id].append(('complete-conclusion','end',ids))
        else:
            pending[cue_id].append(('complete-conclusion','start',ids))

    closure=lesson.get('closure')
    if isinstance(closure,dict):
        recap=closure.get('recap_cues')
        visible=closure.get('visible_action_ids')
        if isinstance(recap,list) and recap and isinstance(visible,list) and visible:
            # A closing narration is useful only when it refers to work students
            # can still see.  Check the first recap sentence, before it begins.
            pending[recap[0]].append(('lesson-closure','start',visible))

    for page_id in managed:
        page=prepared[page_id]
        board=source[page_id]
        layout=board.get('layout',{})
        record_cues={c['id']:c for c in page['cues']}
        for item in layout.get('checkpoints',[]):
            if not isinstance(item,dict) or item.get('cue') not in record_cues or not isinstance(item.get('visible'),list):
                raise ValueError(f'{page_id}: layout.checkpoints 需要本页 cue 和 visible ID 列表。')
            pending[item['cue']].append(('planned-board',item.get('at','end'),item['visible']))

        strokes_by_id=defaultdict(list)
        for stroke in page['strokes']:
            for key in (stroke.get('board_id'),stroke.get('board_group'),stroke.get('component_id')):
                if key:
                    strokes_by_id[key].append(stroke)
        for cue_id,cue in record_cues.items():
            for code,at,ids in pending.get(cue_id,[]):
                if at in ('start','end'):
                    when=cue[at]
                else:
                    duration=cue['end']-cue['start']
                    offset,_=anchor(at,cue,{'duration':duration,'words':cue.get('words',[])})
                    when=cue['start']+offset
                missing=[key for key in ids if not strokes_by_id.get(key)
                         or max(s['end'] for s in strokes_by_id[key])>when+.001]
                item={'code':code,'page':page_id,'cue':cue_id,'time':round(page['start']+when,3),
                      'local_time':round(when,3),'missing':missing,'visible':ids}
                checkpoints.append(item)
                if missing:
                    warnings.append({**item,'message':f'{page_id} / {cue_id} 此时须呈现：{", ".join(missing)}。'})

        groups=defaultdict(list)
        for event in page['strokes']:
            groups[(event['cue'],event['action'])].append(event)
        label_blocks=[]
        for cue in board['cues']:
            for block in cue['blocks']:
                if block['kind'] in ('text','math') and not block.get('allow_overlap'):
                    drawn=groups[(cue['id'],block['action'])]
                    if drawn:
                        label_blocks.append((block,drawn,bounds(drawn)))
        label_blocks.extend((block,[{'end':0}],bounds(block['strokes']))
                            for block in board.get('carry_blocks',[])
                            if block['kind'] in ('text','math') and not block.get('allow_overlap'))
        motion=page.get('demonstration')
        witnessed=set()
        if motion:
            times={motion['start'],motion['stop'],motion['vector_start']}
            for segment in motion.get('segments',[]):
                times.update((segment['start'],segment['stop']))
            count=max(1,int((motion['stop']-motion['start'])*4))
            times.update(motion['start']+(motion['stop']-motion['start'])*i/count for i in range(count+1))
            for time in sorted(times):
                pieces=motion_strokes(motion,time)
                for block,drawn,box in label_blocks:
                    key=(block.get('id') or id(block),'motion-label')
                    if key in witnessed or min(s['end'] for s in drawn)>time:
                        continue
                    if any(overlap(bounds([piece]),box) and any(hits_segment(a,b,box)
                           for a,b in zip(piece['points'],piece['points'][1:])) for piece in pieces):
                        witnessed.add(key)
                        warnings.append({'code':'motion-label','page':page_id,'time':round(page['start']+time,3),
                                         'message':f'{page_id} 运动图经过板书 {block.get("id") or block["action"]}。'})

        # Custom scenes can export time-stamped object bounds from their preview.
        # Each sample carries the objects' measured [x1,y1,x2,y2] boxes.
        for sample in layout.get('motion_boxes',[]):
            if not isinstance(sample,dict) or sample.get('cue') not in record_cues or not isinstance(sample.get('objects'),dict):
                raise ValueError(f'{page_id}: motion_boxes 须列出本页 cue 和 objects。')
            cue=record_cues[sample['cue']]
            fraction=float(sample.get('fraction',0))
            boxes=sample['objects']
            if not 0<=fraction<=1 or any(not isinstance(b,list) or len(b)!=4 or
                       any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in b)
                       or not (b[0]<b[2] and b[1]<b[3])
                       for b in boxes.values()):
                raise ValueError(f'{page_id}: motion_boxes 需要 0..1 的 fraction 和有效边界。')
            time=cue['start']+fraction*(cue['end']-cue['start'])
            def finding(code,message):
                warnings.append({'code':code,'page':page_id,'cue':cue['id'],'time':round(page['start']+time,3),
                                 'message':f'{page_id} {message}'})
            for pair in sample.get('disjoint',[]):
                if not isinstance(pair,list) or len(pair)!=2 or any(name not in boxes for name in pair):
                    raise ValueError(f'{page_id}: disjoint 中须引用两个对象。')
                if overlap(boxes[pair[0]],boxes[pair[1]]):
                    finding('motion-penetration',f'「{pair[0]}」与「{pair[1]}」的边界重叠，请核对真实接触。')
            for name,box in boxes.items():
                for block,drawn,label_box in label_blocks:
                    if references(block).intersection(sample.get('label_allow',[])):
                        continue
                    if min(s['end'] for s in drawn)<=time and overlap(box,label_box):
                        finding('motion-label',f'「{name}」挡住板书 {block.get("id") or block["action"]}。')

    from step_review import inspect as inspect_steps
    issues, evidence = inspect_steps(lesson,timeline)
    warnings.extend(issues)
    order=lambda item:(item['time'],item['page'],item['code'])
    coverage=[{'page':p['id'],
               'visibility_checkpoints':sum(c['page']==p['id'] for c in checkpoints),
               'motion_geometry':('sampled-model' if prepared[p['id']].get('demonstration')
                                  else 'sampled-boxes' if p.get('layout',{}).get('motion_boxes')
                                  else 'needs-viewing' if p.get('native_scenes') else 'none')}
              for p in pages]
    return {'status':'attention' if warnings else 'pass' if managed else 'not_applicable',
            'timing':'estimated' if timeline.get('draft') else 'measured',
            'derivation_evidence':evidence,'managed_pages':len(managed),'checkpoints':sorted(checkpoints,key=order),
            'coverage':coverage,
            'warnings':sorted(warnings,key=order)}
