"""Bind the producer's semantic vocabulary pass to the exact spoken sentence."""
from hashlib import sha256
import json
from pathlib import Path

from pronunciation import HAN_TERM


def sentence_key(page,cue):
    return json.dumps([str(page),str(cue)],ensure_ascii=False)


def script_text(cue):
    return cue.get('spoken_tts',cue.get('tts',cue.get('say',cue.get('text',''))))


def text_digest(text):
    return sha256(text.encode()).hexdigest()


def context_digest(lesson,page,cue):
    data={'text':script_text(cue),'actions':cue.get('actions',[]),'problem':page.get('problem'),
          'symbols':lesson.get('symbols',{}),'knowledge_points':lesson.get('knowledge_points',[])}
    return text_digest(json.dumps(data,sort_keys=True,ensure_ascii=False))


def draft(project,lesson):
    from term_flow import identify
    uses=identify(lesson)
    rows=[]
    for pi,page in enumerate(lesson.get('pages',[]),1):
        for ci,cue in enumerate(page.get('cues',[]),1):
            pid,cid=page.get('id',str(pi)),cue.get('id',str(ci))
            text=script_text(cue)
            rows.append({'page':pid,'cue':cid,'text':text,'sha256':text_digest(text),
                         'context_sha256':context_digest(lesson,page,cue),
                         'board_actions':cue.get('actions',[]),
                         'terms':[{'term':r['term'],'offset':r['offset']} for r in uses if r['page']==pid and r['cue']==cid and not r['split_in_script']],
                         'extra_terms':[],'exclude':[],'reviewer':'','evidence':''})
    data={'schema':2,'readings':{},'items':rows}
    path=Path(project)/'term-inventory-draft.json'
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    return {'file':str(path),'sentences':len(rows),'status':'needs_semantic_review'}


def apply(project,lesson):
    path=Path(project)/'term-inventory.json'
    if not path.is_file():
        return lesson
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or not isinstance(data.get('items'),list):
        raise ValueError('term-inventory.json 需要逐句盘点的 items。')
    strict=lesson.get('term_inventory_version',1)>=2
    if strict and data.get('schema')!=2:
        return dict(lesson,_term_inventory={})
    contexts={sentence_key(p.get('id',str(pi)),c.get('id',str(ci))):context_digest(lesson,p,c)
              for pi,p in enumerate(lesson.get('pages',[]),1) for ci,c in enumerate(p.get('cues',[]),1)}
    known=[]
    if strict:
        from term_flow import identify
        known=identify({**lesson,'_term_inventory':{}})
    scripts={sentence_key(page.get('id',pi),cue.get('id',ci)):script_text(cue)
             for pi,page in enumerate(lesson.get('pages',[]),1)
             for ci,cue in enumerate(page.get('cues',page.get('beats',[])),1)}
    checked={}
    words=dict(lesson.get('speech',{}).get('physics_terms',{}))
    readings=data.get('readings',{})
    if not isinstance(readings,dict):
        raise ValueError('readings 应按整词列出带调拼音。')
    for row in data['items']:
        key=sentence_key(row['page'],row['cue'])
        text=scripts.get(key)
        if text is None or row.get('sha256')!=text_digest(text):
            continue  # New or rewritten sentences remain in the semantic review queue.
        if strict:
            if row.get('context_sha256')!=contexts.get(key) or not row.get('reviewer','').strip() or not row.get('evidence','').strip():
                continue
            if not isinstance(row.get('terms'),list):
                raise ValueError(f'{key} 须逐处列出物理术语，逐句阅读后记录词义判断依据。')
            for item in row['terms']:
                term,offset=item.get('term'),item.get('offset')
                if not isinstance(term,str) or not HAN_TERM.fullmatch(term) or type(offset) is not int or offset<0 or not text.startswith(term,offset):
                    raise ValueError(f'{key} 的术语需对应原句中的实际位置。')
        if key in checked:
            raise ValueError(f"句子 {key} 的盘点记录重复。")
        extras=row.get('extra_terms')
        if not isinstance(extras,list):
            raise ValueError(f'{key} 需要 extra_terms，本句已无漏词时填空列表。')
        if strict:
            extras=list(dict.fromkeys([*extras,*(i['term'] for i in row['terms'])]))
        for term in extras:
            if not isinstance(term,str) or not HAN_TERM.fullmatch(term) or term not in text:
                raise ValueError(f'{key} 的补词 {term} 需要与这句口播的原词一致。')
            if term in readings:
                if words.get(term) is not None and words[term]!=readings[term]:
                    raise ValueError(f'“{term}”的本课词表与逐句盘点读音有分歧。')
                words[term]=readings[term]
        exclusions=row.get('exclude',[])
        if not isinstance(exclusions,list):
            raise ValueError(f'{key} 按出现位置记录误匹配。')
        for item in exclusions:
            term,offset=item['term'],item['offset']
            if (not isinstance(term,str) or not HAN_TERM.fullmatch(term) or type(offset) is not int
                    or offset<0 or not text.startswith(term,offset) or not str(item.get('reason','')).strip()):
                raise ValueError(f'{key} 排除误匹配需要原词、字偏移和原因。')
        if strict:
            excluded={(r['term'],r['offset']) for r in exclusions}
            for found in known:
                if sentence_key(found['page'],found['cue'])!=key or found['split_in_script']:
                    continue
                start,end=found['offset'],found['offset']+len(found['term'])
                if (found['term'],start) not in excluded and not any(r['offset']<=start and r['offset']+len(r['term'])>=end for r in row['terms']):
                    raise ValueError(f"{key} 的逐句术语盘点漏掉了“{found['term']}”；按本句词义补入或说明排除依据。")
        checked[key]=dict(extra_terms=extras,exclude=exclusions)
    return dict(lesson,_term_inventory=checked,speech={**lesson.get('speech',{}),'physics_terms':words})
