"""Connect reasoning steps to the actual spoken cue, visible diagram, handwriting and handout."""
from collections import defaultdict
import re

from terminology_review import _clean, _word_windows


def steps(lesson):
    for i, page in enumerate(lesson.get('pages',[]), 1):
        for step in page.get('derivation_steps', []):
            yield page.get('id',f'p{i:02d}'), step


def enabled(lesson, step):
    return lesson.get('workflow_version') == 1 or 'spoken_anchor' in step or 'handout_label' in step


def formula_text(value):
    value = re.sub(r'\\(?:label|tag)\s*\{[^{}]*\}', '', value)
    value = re.sub(r'\\(?:left|right|displaystyle|notag|nonumber)\b|\\[,;! ]', '', value)
    return re.sub(r'\s+|&', '', value)


def pen_conflicts(timeline):
    """Check every written stroke, including unregistered equations and text."""
    events=[]
    for page in timeline['pages']:
        for index,stroke in enumerate(page.get('strokes', [])):
            if stroke.get('prewritten') or stroke['end'] <= stroke['start'] or stroke['start'] < 0:
                continue
            key=(page['id'],stroke.get('cue',''),str(stroke.get('board_id',stroke.get('action',index))))
            events.append((page.get('start',0)+stroke['start'],page.get('start',0)+stroke['end'],key,index))
    active=[]; reported=set(); warnings=[]
    for begin,end,key,index in sorted(events):
        active=[event for event in active if event[0]>begin+.001]
        for _,other in active:
            pair=tuple(sorted((key,other)))
            if pair in reported:
                continue
            reported.add(pair)
            warnings.append({'code':'parallel-formulas','page':key[0],'cue':key[1],
                             'time':begin,'message':'两处笔迹同时书写：'+'、'.join('/'.join(k) for k in pair)})
        active.append((end,key))
    return warnings


def source_check(project, lesson):
    from handout_bundle import source_files, tex_text
    selected = [(p,s) for p,s in steps(lesson) if enabled(lesson,s)]
    if not selected:
        return []
    labels = []
    equations = {}
    for path in source_files(project, lesson):
        if path.suffix.lower() in ('.tex','.tikz'):
            body=tex_text(path)
            labels.extend(re.findall(r'\\label\s*\{([^{}]+)\}',body))
            pattern=r'\\begin\{(equation\*?|align\*?|gather\*?|multline\*?)\}(.*?)\\end\{\1\}'
            for environment,equation in re.findall(pattern,body,flags=re.S):
                # A label in align/gather belongs to its row, not the other equations.
                rows=re.split(r'\\\\(?:\[[^\]]*\])?',equation) if environment.rstrip('*') in ('align','gather') else [equation]
                for row in rows:
                    for key in re.findall(r'\\label\s*\{([^{}]+)\}',row):
                        equations[key]=formula_text(row)
    issues = []
    seen = set()
    for page,s in steps(lesson):
        for key in s.get('upstream_steps',[]):
            if key not in seen:
                issues.append({'code':'step-upstream','page':page,'cue':s.get('cue_id'),
                               'message':f'{page}/{s.get("id")} 需要引用前面已定义的步骤：{key}'})
        seen.add(page+'/'+str(s.get('id')))
    for page,s in selected:
        def issue(code,message):
            issues.append({'code':code,'page':page,'cue':s.get('cue_id'), 'message':f'{page}/{s.get("id")} {message}'})
        for name in ('question','spoken_anchor','handout_label'):
            if not isinstance(s.get(name),str) or not s[name].strip():
                issue('step-field','缺少 '+name)
        if labels.count(s.get('handout_label')) != 1:
            issue('step-handout','讲义需要一个与本步对应的唯一 LaTeX 标签。')
        elif s.get('result'):
            key=s['handout_label']
            formula=formula_text(s.get('handout_result',s['result']))
            if key not in equations or formula != equations[key]:
                issue('step-handout-equation','请把标签放在对应公式内，并核实讲义与板书表达式。')
        for key in s.get('uses_conventions',[]):
            if key not in lesson.get('conventions',{}):
                issue('step-convention','找不到物理约定 '+key)
    return issues


def inspect(lesson, timeline):
    warnings, evidence = pen_conflicts(timeline), []
    pages = {p['id']:p for p in timeline['pages']}
    by_page = defaultdict(list)
    for page,step in steps(lesson):
        by_page[page].append(step)
    for pid, declared in by_page.items():
        if pid not in pages:
            continue
        page = pages[pid]
        cues = {c['id']:c for c in page['cues']}
        ink = defaultdict(list)
        legacy_ids = {}
        raw_page = next((p for i,p in enumerate(lesson.get('pages',[]),1) if p.get('id',f'p{i:02d}')==pid),{})
        for c in raw_page.get('cues',[]):
            actions = c.get('actions',[])
            # Older timelines identify strokes by ordinal. Only accept a complete one-to-one sequence.
            ordinals = {e.get('action') for e in page['strokes'] if e.get('cue')==c.get('id')}
            simple = {'line','dashed_line','math','text','stroke','arrow','circle','dot','arc','rect'}
            if ordinals == set(range(len(actions))) and all(a.get('type') in simple and not a.get('prewritten') for a in actions):
                legacy_ids.update({(c.get('id'),i):a.get('id') for i,a in enumerate(actions)})
        for e in page['strokes']:
            board_id=e.get('board_id') or legacy_ids.get((e.get('cue'),e.get('action')))
            for k in {board_id,e.get('board_group'),e.get('component_id')} - {None}:
                ink[k].append(e)
        for s in declared:
            if not enabled(lesson,s):
                continue
            cue = cues.get(s.get('cue_id'))
            if not cue:
                continue  # validated by teaching.audit
            anchor = _clean(s.get('spoken_anchor',''))
            text = cue.get('tts',cue.get('text',''))
            idx = _clean(text).find(anchor)
            drawing = [e for e in ink[s.get('action_id')] if e.get('cue')==cue['id']]
            item = {'page':pid,'step':s.get('id'),'cue':cue['id'],'code':'derivation',
                    'time':page.get('start',0)+cue['start'],'handout_label':s.get('handout_label')}
            def issue(code,reason):
                warnings.append({**item,'code':code,'message':reason})
            if not anchor or idx<0 or _clean(text).count(anchor)!=1:
                issue('step-speech','这句口播需要一个能唯一定位本步推导的短语。')
                continue
            words = _word_windows(cue,text) if not timeline.get('draft') else []
            begin = cue['start'] + (words[idx][0] if words else 0)
            end = cue['start'] + words[idx+len(anchor)-1][1] if words else cue['end']
            missing = [key for key in s.get('requires_visible',[]) if not ink[key] or max(e['end'] for e in ink[key])>begin+.001]
            if missing:
                issue('step-diagram','口播引用前应画完并标注：'+', '.join(missing))
            if not drawing or not any(e['end']>=begin and e['start']<=end for e in drawing):
                issue('step-ink','本步的口播时间内没有对应公式的笔迹。')
            evidence.append({**item,'speech_window':[begin,end],
                             'alignment':'word-timestamps' if words else 'cue-only',
                             'requires_listening':not bool(words)})
    return warnings,evidence
