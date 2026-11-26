"""Review concrete narration patterns before speech synthesis; no AI-authorship score."""
import argparse,json,re,statistics
from pathlib import Path
from classroom_language import review_narration
from pronunciation import reference_readings, LISTEN_TERMS, spoken_symbols, symbol_reading, tone_targets

SYMBOL_PHRASES=('带下标零的时间','带下标零的质量字母','普通的时间字母','质量字母')
META_PHRASES=('整道推导都围绕','连成了一条线','接下来我们将','通过以上分析我们可以看出','两个物理量已经配上了')
PAUSE_REASONS={'phrase','read_formula','observe_motion','think','transition'}

def inspect_script(lesson, backend=None):
    from card_speech import lesson_inputs
    decisions=lesson_inputs(lesson)
    indexed=[((str(p.get('id',pi)),str(c.get('id',ci))),c) for pi,p in enumerate(lesson.get('pages',[]),1)
             for ci,c in enumerate(p.get('cues',[]),1)]
    cues=[c for _,c in indexed];warnings=[]
    speech=lesson.get('speech',{})
    backend=backend or speech.get('backend','glm')
    pronunciation=[]
    inputs=[]
    reference=reference_readings()
    for key,c in indexed:
        text=c.get('tts','')
        decision=decisions[key]
        terms=decision['pinyin']
        for term, reading in terms.items():
            expected = reference.get(term)
            if expected and expected != reading:
                warnings.append({'code':'term-tone-conflict','cue':c['id'],
                                 'message':f'“{term}”配置为 {reading}，物理词表读作 {expected}，配音前核对本句。'})
        targets = tone_targets(c.get('spoken_tts', text), speech.get('minimax_pronunciation'), c.get('minimax_pronunciation'),decision['targets'])
        for item in targets:
            for bad in item['conflicts']:
                if item['term'] not in reference:
                    warnings.append({'code':'term-tone-conflict','cue':c['id'],
                                     'message':f"“{bad['word']}”中的“{bad['char']}”应读 {bad['expected']}，实际配置为 {bad['configured']}。"})
        listen=[word for word in LISTEN_TERMS if word in text]
        symbols={match.group():symbol_reading(match.group()) for match in spoken_symbols(text)}
        spoken = c.get('spoken_tts', text)
        inputs.append({'cue': c['id'], 'text': decision['local_text'] if backend == 'user' else decision['provider_text'] if backend == 'minimax' else spoken,
                       'script':text, 'card_targets':decision['targets'], 'letter_sequence':decision['symbols'],
                       'dictionary_conflicts':decision['conflicts'] + (decision['provider_exclusions'] if backend=='minimax' else []), 'pinyin': terms, 'letters': symbols, 'tone_targets': targets})
        if terms or listen or symbols:
            pronunciation.append({'cue':c['id'],'terms':terms,'listen_for':listen,'symbols':symbols})
        for phrase in SYMBOL_PHRASES+META_PHRASES:
            if phrase in c.get('tts',''):warnings.append({'code':'indirect-or-meta-language','cue':c['id'],'message':f'直接说物理量或运算，改写“{phrase}”。'})
        reason=c.get('pause_reason')
        if reason is not None and reason not in PAUSE_REASONS:raise ValueError(f'{c["id"]}: unknown pause_reason')
        if max(c.get('pause',0),c.get('pause_before',0))>1.2 and reason not in PAUSE_REASONS-{'phrase'}:
            warnings.append({'code':'unmotivated-pause','cue':c['id'],'message':'较长停顿请对应读式、观察、思考或转场，记录 pause_reason。'})
    lengths=[len(re.sub(r'\s','',c.get('tts',''))) for c in cues]
    if len(lengths)>=6 and min(lengths)>80 and statistics.pstdev(lengths)/max(1,statistics.mean(lengths))<.18:
        warnings.append({'code':'uniform-paragraphs','message':'连续长段长度接近；按实际思考与指图动作重新分组，保留必要推导。'})
    warnings.extend(review_narration(cues))
    return {'status':'review' if warnings else 'pass','cues':len(cues),'warnings':warnings,
            'tts_inputs':inputs,
            'pronunciation':{'backend':backend,'apply_dictionary':backend=='minimax','cues':pronunciation},
            'meaning':'具体文稿与停顿检查线索，不证明真人感；还需实际观看和试听。'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('--strict',action='store_true');a=p.parse_args()
    from course import compile_lesson
    lesson,_=compile_lesson(a.project);report=inspect_script(lesson)
    (Path(a.project)/'delivery-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
    if a.strict and report['warnings']:raise SystemExit(1)

if __name__=='__main__':main()
