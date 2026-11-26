"""Small, repeatable checks based on user-reported classroom failures. No synthesis or paid API."""
import argparse
import copy
import json
from pathlib import Path

from knowledge_board import inspect_sources
from step_review import inspect
from term_flow import identify


def run(baseline=None):
    cue={'id':'derive','tts':'力矩等于力乘力臂','start':1,'end':3,
         'words':[{'text':'力矩','start':0,'end':.5},{'text':'等于力乘力臂','start':.5,'end':2}]}
    step={'id':'moment','cue_id':'derive','action_id':'eq','spoken_anchor':'等于力乘力臂','requires_visible':['arm']}
    lesson={'pages':[{'id':'p','derivation_steps':[step]}]}
    def pen(key,begin,end):
        return {'cue':'derive','board_id':key,'start':begin,'end':end}
    data={'pages':[{'id':'p','start':0,'cues':[cue],'strokes':[pen('arm',0,.9),pen('eq',1.6,2.8)]}]}
    rows=[]
    def case(key,expected,actual):
        rows.append({'case':key,'expected':expected,'observed':actual,'pass':actual==expected,
                     'evidence':'controlled-fixture'})
    def codes(l,t):
        return sorted({i['code'] for i in inspect(l,t)[0]})
    case('先标力臂再推力矩',[],codes(lesson,data))
    late=copy.deepcopy(data);late['pages'][0]['strokes'][0]['end']=1.55
    case('还没标好就指图',['step-diagram'],codes(lesson,late))
    wrong=copy.deepcopy(lesson);wrong['pages'][0]['derivation_steps'][0]['spoken_anchor']='动量守恒'
    case('口播未提到所写关系',['step-speech'],codes(wrong,data))
    early=copy.deepcopy(data);early['pages'][0]['strokes'][1].update(start=1,end=1.2)
    case('写完才念相应公式',['step-ink'],codes(lesson,early))
    both=copy.deepcopy(lesson);both['pages'][0]['derivation_steps'].append(dict(step,id='second',action_id='next'))
    together=copy.deepcopy(data);together['pages'][0]['strokes'].append(pen('next',1.8,2.1))
    case('两行公式同时书写',['parallel-formulas'],codes(both,together))
    _,errors=inspect_sources({'kind':'concept','knowledge_points':[]},[])
    case('定律缺少结论板书',['knowledge-points-required'],[e['code'] for e in errors])
    targets=identify({'pages':[{'id':'p','cues':[dict(cue,tts='观察电压差，再测一次电压差。')]}]})
    case('同一术语重复两次逐处列出',2,sum(r['term']=='电压差' for r in targets))
    prior={r['case']:r for r in (baseline or {}).get('cases',[])}
    return {'status':'pass' if all(r['pass'] for r in rows) else 'failed','cases':rows,
            'regressions':[r['case'] for r in rows if not r['pass'] and prior.get(r['case'],{}).get('pass')],
            'manual_reference':{'source':'作者对第43届第二题原版的反馈','scope':'课堂节奏',
                                'new_recording_audition':'pending'}}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=run(json.loads(args.baseline.read_text()) if args.baseline else None)
    message=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output:
        args.output.write_text(message)
    print(message,end='')
    raise SystemExit(report['status']!='pass')
