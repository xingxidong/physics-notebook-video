"""Identify spoken physics terms before synthesis and review each use in the delivered audio."""
import argparse
from array import array
from collections import Counter, defaultdict
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import wave

from classroom_terms import learning_cards, note_readings, context_sense, feedback_cards
from feedback_bank import applicable_issues, lesson_catalog, save_report
from pronunciation import classroom_syllables, DISCIPLINE_TERMS, HAN_TERM, PHYSICS_PINYIN, SYLLABLE, term_pattern
from terminology_review import _clean, _word_windows
from tone_review import _digest
from term_inventory import apply as apply_inventory, sentence_key, text_digest

RATE = 16000
# Contextual pronunciation phrases such as “应该” belong to tone_review. Include
# physical quantities from that dictionary without treating all prose as a term.
QUANTITIES = """质量 长度 重量 电荷 势能 重力 弹力 弹簧 弹性 角动量 转动惯量 分量 水平分量
竖直分量 切向分量 径向分量 相位 同相 反相 相长干涉 相消干涉 角频率 频率 功率 矢量
标量 量纲 速率 平均速率 方均根速率 物理量 量子 数密度 切向 径向 电偶极矩 磁矩
波矢 波数 电流密度 电磁波 转矩 位移电流 光速 等离子体 分子力 摩尔质量 热量""".split()
# These expressions disambiguate tones in prose. Keep them in tone_review;
# newly learned subject terms enter the per-occurrence review by default.
TONE_CONTEXT_ONLY = frozenset("""应该 应当 分别 觉得 感觉 睡觉 方便 便于 此处 各处 到处 处于 相处
处理 还有 还是 归还 应对 对应 好奇 奇特 似的 沿着 接着 着手 着急 露面 银行 步行 模样
差不多 进行 运行 重新 率先 参差 记载 角色 长短 从地心量 从地表量 哪里量 从哪量 怎么量
用尺量 从原点量 朝右量 朝左量 往前量 往后量 从径向量起 量起 量出 量距离 的量 这个量
那个量 数清 倒数第二 矩阵的行 内能的改变量 力的两个分量 加速度的两个分量 动量的改变量
势能的增量 厚度的增长率 可逆的过程 方向的分量 水平方向的分量 真空中的光速 竖直方向的分量""".split())
NAMED_AT_CLAUSE_END = re.compile(r'(?:称为|称作|叫作|叫做|简称为?|名为)([\u3400-\u9fff]{2,12})(?=[。，；！？,;!?]|$)')
QUOTED_DEFINITION = re.compile(r'(?:称为|称作|叫作|叫做|简称为?|名为|定义为)[“「‘]([\u3400-\u9fff]{2,20})[”」’]')


def vocabulary(lesson, rules=None):
    rules = lesson_catalog(lesson) if rules is None else rules
    words = dict(DISCIPLINE_TERMS)
    words.update((term, reading) for term, reading in PHYSICS_PINYIN.items()
                 if term not in TONE_CONTEXT_ONLY)
    for term in QUANTITIES:
        words.setdefault(term, PHYSICS_PINYIN.get(term))
    words.update({'分量':'fen1 liang4', '切向分量':'qie1 xiang4 fen1 liang4', '径向':'jing4 xiang4',
                  '径向分量':'jing4 xiang4 fen1 liang4', '位移电流':'wei4 yi2 dian4 liu2',
                  '分子力':'fen1 zi3 li4', '电流密度':'dian4 liu2 mi4 du4', '波数':'bo1 shu4',
                  '波矢':'bo1 shi3', '电偶极矩':'dian4 ou3 ji2 ju3', '磁矩':'ci2 ju3',
                  '等离子体':'deng3 li2 zi3 ti3', '转矩':'zhuan4 ju3'})
    priority = set()
    for rule in applicable_issues(lesson, rules):
        if rule['key'] == 'term-flow' or rule['key'].startswith(('term-flow-', 'connected-physics-term-')):
            priority.update([rule['match']] if rule.get('match') else rule.get('review_phrases', []))
    words.update({'电阻网络':'dian4 zu3 wang3 luo4','非线性电阻':'fei1 xian4 xing4 dian4 zu3',
                  '非线性电阻网络':'fei1 xian4 xing4 dian4 zu3 wang3 luo4','等效电阻':'deng3 xiao4 dian4 zu3',
                  '电压降':'dian4 ya1 jiang4','端口电压':'duan1 kou3 dian4 ya1','工作电压':'gong1 zuo4 dian4 ya1',
                  '总电流':'zong3 dian4 liu2','支路电流':'zhi1 lu4 dian4 liu2','电源':'dian4 yuan2',
                  '电路':'dian4 lu4','参考方向':'can1 kao3 fang1 xiang4','元件方程':'yuan2 jian4 fang1 cheng2',
                  '立方律':'li4 fang1 lü4','电荷守恒':'dian4 he4 shou3 heng2','伏安特性':'fu2 an1 te4 xing4'})
    for term, entry in rules['polyphones'].items():
        if len(term) > 1 and entry.get('expected') and not entry.get('context_required'):
            words[term] = entry['expected']
    # Merge all notes before course-specific decisions. A disagreement has
    # a location to review, but no automatic target until the producer resolves it.
    for term, readings in note_readings().items():
        options = readings | ({words[term]} if words.get(term) else set())
        words[term] = next(iter(options)) if len(options) == 1 else None
    for term, card in feedback_cards(rules).items():
        words.setdefault(term, None)
        if card.get('feedback_reading'):
            words[term] = card['feedback_reading']
    for word in priority:
        words.setdefault(word, PHYSICS_PINYIN.get(word))
    for point in lesson.get('knowledge_points', []):
        word = point.get('name', '')
        if HAN_TERM.fullmatch(word):
            words.setdefault(word, PHYSICS_PINYIN.get(word))
    for entry in lesson.get('_term_inventory',{}).values():
        for word in entry['extra_terms']:
            words.setdefault(word,PHYSICS_PINYIN.get(word))
    custom = lesson.get('speech', {}).get('physics_terms', {})
    if not isinstance(custom, dict):
        raise ValueError('speech.physics_terms 按术语填写带调拼音，待定读法可填 null。')
    for term, reading in custom.items():
        if not HAN_TERM.fullmatch(term) or (reading is not None and (
            not isinstance(reading, str) or len(reading.split()) != len(term)
            or not all(SYLLABLE.fullmatch(s) for s in reading.split()))):
            raise ValueError(f'术语 {term} 需要完整中文词和逐字带调拼音。')
        words[term] = reading
    return words, priority


def occurrence_readings(lesson):
    configured=lesson.get('speech',{}).get('term_uses',[])
    if not isinstance(configured,list):
        raise ValueError('speech.term_uses 以列表逐处注明同形词的本句读音。')
    readings={}
    for entry in configured:
        if not isinstance(entry,dict):
            raise ValueError('逐处读音需要 page、cue、term、occurrence、reading。')
        page,cue,word,n,sound=(entry.get(k) for k in ('page','cue','term','occurrence','reading'))
        if (not all(isinstance(v,str) and v for v in (page,cue,word,sound)) or not HAN_TERM.fullmatch(word)
                or type(n) is not int or n<1):
            raise ValueError('逐处读音需要页、句、完整词及从 1 起算的出现序号。')
        sound=' '.join(sound.lower().replace('v','ü').split())
        if len(sound.split())!=len(word) or not all(SYLLABLE.fullmatch(s) for s in sound.split()):
            raise ValueError(f'“{word}”须按字填写带调拼音。')
        key=(page,cue,word,n)
        if key in readings:
            raise ValueError(f'“{word}”同一处有两条读音，请按本句词义选定一种。')
        alias=entry.get('spoken_as')
        if alias is not None and (not isinstance(alias,str) or not HAN_TERM.fullmatch(alias) or len(alias)!=len(word)):
            raise ValueError('逐处配音提示须为与原词等长的中文词形。')
        readings[key]=(sound,alias)
    return readings


def identify(data, lesson=None, rules=None):
    lesson = data if lesson is None else lesson
    vocabulary_map, priority = vocabulary(lesson, rules)
    uses = occurrence_readings(lesson)
    for _,_,term,_ in uses:
        vocabulary_map.setdefault(term,None)
    seen = Counter()
    applied = set()
    cues, positions, stream = [], [], []
    for pi, page in enumerate(data['pages'], 1):
        for ci, cue in enumerate(page.get('cues', page.get('beats', [])), 1):
            text = cue.get('spoken_tts', cue.get('tts', cue.get('say', cue.get('text', ''))))
            for word in QUOTED_DEFINITION.findall(text) + NAMED_AT_CLAUSE_END.findall(text):
                vocabulary_map.setdefault(word, PHYSICS_PINYIN.get(word))
            start = page.get('start', 0) + cue.get('start', 0)
            end = page.get('start', 0) + cue.get('end', 0)
            n = len(cues)
            cues.append((pi, ci, page.get('id', str(pi)), cue, text, start, end))
            for offset, char in enumerate(text):
                if not char.isspace() and char not in '|｜':
                    stream.append(char)
                    positions.append((n, offset))
    joined = ''.join(stream)
    result = []
    # Search independently, so a historical word inside a longer quantity is still checked.
    for term, reading in vocabulary_map.items():
        if term not in joined:
            continue
        for match in term_pattern([term]).finditer(joined):
            first, offset = positions[match.start()]
            last, stop = positions[match.end()-1]
            pi, ci, page, cue, text, start, end = cues[first]
            split = first != last or text[offset:stop+1] != term
            context = ' ｜ '.join(cues[i][4] for i in range(first, last+1))
            row = dict(id=f'{pi}.{ci}.{offset}.{term}', page=page, cue=cue.get('id', str(ci)),
                       term=term, expected=reading, priority=term in priority, offset=offset,
                       speaker=cue.get('voice') or (data.get('speech') or lesson.get('speech',{})).get('voice'),
                       text=context, split_in_script=split, start=start, end=cues[last][6],
                       cue_start=start, cue_end=cues[last][6], timing='cue', end_offset=stop+1,
                       end_location=[cues[last][0],cues[last][1]])
            semantic=lesson.get('_term_inventory',{}).get(sentence_key(page,row['cue']),{})
            if any(item['offset']==offset and item['term']==term for item in semantic.get('exclude',[])):
                continue
            location=(str(page),str(row['cue']),term)
            seen[location]+=1
            key=(*location,seen[location])
            sense = context_sense(term, text, offset) if not split else None
            if sense:
                row.update(expected=sense, reading_source='context')
            if key in uses:
                sound,alias=uses[key]
                row.update(expected=sound,reading_source='this_occurrence')
                if alias:
                    row['spoken_as']=alias
                applied.add(key)
            if first == last and 'end' in cue:
                windows = _word_windows(cue, text)
                pos = len(_clean(text[:offset]))
                spans = windows[pos:pos+len(term)]
                # A provider may return one interval for a complete sentence.
                # Only use an acoustic window if its endpoints actually bound the term.
                if (spans and not (pos and windows[pos-1] == spans[0])
                        and not (pos+len(term)<len(windows) and windows[pos+len(term)] == spans[-1])):
                    row.update(start=start+spans[0][0], end=start+spans[-1][1], timing='word')
                    if len(set(spans)) == len(term):
                        row['syllable_ms'] = [round(1000*(b-a)) for a,b in spans]
            result.append(row)
    if set(uses)-applied:
        raise ValueError('逐处读音对应的页、句或词次已改变：'+str(sorted(set(uses)-applied)))
    # A local choice for a syllable must hold in both the nested term and the longer one.
    chosen = defaultdict(dict)
    lesson_words = lesson.get('speech',{}).get('physics_terms',{})
    for row in result:
        level = {'this_occurrence':3,'context':2}.get(row.get('reading_source'), int(row['term'] in lesson_words))
        if not level or row['split_in_script'] or not row['expected']:
            continue
        by_offset = chosen[row['page'],row['cue']]
        for index, sound in enumerate(row['expected'].split(),row['offset']):
            previous = by_offset.get(index)
            if previous and previous[0] == level and previous[1] != sound:
                raise ValueError(f"{row['page']} / {row['cue']} 中重叠词的第 {index+1} 个字指定了两种读音。")
            if not previous or previous[0] <= level:
                by_offset[index] = (level,sound)
    for row in result:
        sounds = chosen.get((row['page'],row['cue']))
        if sounds and row['expected'] and not row['split_in_script']:
            row['expected'] = ' '.join(sounds.get(i,(0,sound))[1]
                                       for i,sound in enumerate(row['expected'].split(),row['offset']))
    return sorted(result, key=lambda r: (r['cue_start'], tuple(map(int,r['id'].split('.')[:3])), r['term']))


# Suggest possible compounds outside the glossary, with their original sentence.
# A technical suffix alone is not evidence of a term or its pronunciation.
_TERM_CLAUSE = re.compile(
    r'(?:^|[，。；：！？,;:!?])\s*(?:再看|先看|比较|测量|计算|求出|求|代入|考察|观察)?'
    r'(?P<word>[\u3400-\u9fff]{1,8}?(?:电势|密度|长度|系数|截面|阻抗|频率|效应|定理|定律|'
    r'温标|循环|张力|接触角|半径|势垒|能级|波长|常数|方程|振荡|近似|极化率))'
    r'(?=\s*(?:$|[，。；：！？,;:!?]|随|等于|记为|越|增大|减小))'
)


def script_inventory(lesson, occurrences):
    """Keep even unmatched sentences available to the producer for semantic term discovery."""
    groups=defaultdict(list)
    for r in occurrences:
        pi,ci=map(int,r['id'].split('.')[:2])
        groups[pi,ci].append(r)
    inventory=[]
    for pi,page in enumerate(lesson.get('pages',[]),1):
        for ci,cue in enumerate(page.get('cues',page.get('beats',[])),1):
            text=cue.get('spoken_tts',cue.get('tts',cue.get('say',cue.get('text',''))))
            if not text.strip():
                continue
            mask=list(text)
            found=groups[pi,ci]
            for row in found:
                if not row['split_in_script']:
                    a,b=row['offset'],row['end_offset']
                    mask[a:b]=[' ']*(b-a)
            unmatched=[dict(text=m.group(),offset=m.start()) for m in re.finditer(r'[㐀-鿿]+',''.join(mask))]
            pid,cid=page.get('id',str(pi)),cue.get('id',str(ci))
            reviewed=lesson.get('_term_inventory',{}).get(sentence_key(pid,cid))
            inventory.append(dict(page=pid,cue=cid,text=text,sha256=text_digest(text),reviewed=reviewed is not None,
                                  terms=[r['id'] for r in found],unmatched=unmatched))
    return inventory


def candidate_terms(lesson, occurrences, inventory=None):
    recognized = {row['term'] for row in occurrences}
    excluded=lesson.get('speech',{}).get('non_terms',[])
    if not isinstance(excluded,list) or any(not isinstance(x,str) or not HAN_TERM.fullmatch(x) for x in excluded):
        raise ValueError('speech.non_terms 填写已按本课语境辨明的普通中文短语。')
    skip=recognized | set(excluded)
    # A short figure label may name a new object with no predictable technical suffix.
    labels=set()
    for page in lesson.get('pages',[]):
        for cue in page.get('cues',page.get('beats',[])):
            for action in cue.get('actions',[]):
                for key in ('label','text'):
                    label=action.get(key)
                    if isinstance(label,str) and 1<len(label)<=16 and HAN_TERM.fullmatch(label):
                        labels.add(label)
    candidates=defaultdict(list)
    for entry in inventory if inventory is not None else script_inventory(lesson,occurrences):
        text=entry['text']
        hits={(m.start('word'),m['word']) for m in _TERM_CLAUSE.finditer(text) if '的' not in m['word']}
        for label in labels-skip:
            hits.update((m.start(),label) for m in re.finditer(re.escape(label),text))
        rejected={(x['term'],x['offset']) for x in lesson.get('_term_inventory',{}).get(
            sentence_key(entry['page'],entry['cue']),{}).get('exclude',[])}
        for offset,term in sorted(hits):
            if term not in skip and (term,offset) not in rejected:
                candidates[term].append(dict(page=entry['page'],cue=entry['cue'],offset=offset,text=text))
    return dict(candidates)


def term_counts(rows):
    return dict(sorted(Counter(r['term'] for r in rows).items()))


def flow_evidence(raw):
    """Interior silence and a voiced energy trough between two stronger portions of a word."""
    samples = array('h')
    samples.frombytes(raw)
    if sys.byteorder != 'little':
        samples.byteswap()
    size = RATE // 100
    levels = [math.sqrt(sum(x*x for x in samples[i:i+size])/size)
              for i in range(0, len(samples)-size+1, size)]
    threshold = max(35, max(levels, default=0)*.045)
    active = [i for i, level in enumerate(levels) if level > threshold]
    if len(active) < 2:
        return None, False
    gap = max(b-a-1 for a,b in zip(active, active[1:])) * 10
    # A voiced, sustained dip followed by a fresh onset can sound split even at zero silence.
    # Normal consonants can produce similar traces. Surface these cases for contextual listening.
    for i in range(active[0]+6,active[-1]-10):
        trough = levels[i:i+5]
        shoulders = min(sum(levels[i-6:i])/6, sum(levels[i+5:i+11])/6)
        if min(trough)>threshold and max(trough)*4<shoulders:
            return gap, True
    return gap, False


def acoustic_gap(raw):
    return flow_evidence(raw)[0]


def inspect(project, timeline, media, *, lesson=None, select=None, clip=False, verdict=None, clips=False, hearings=None):
    if not any(c.get('tts') or c.get('spoken_tts') or c.get('say') or c.get('text')
               for p in timeline['pages'] for c in p.get('cues',p.get('beats',[]))):
        raise ValueError('成片时间轴没有可定位的口播。')
    has_source = lesson is not None and lesson is not timeline
    lesson = apply_inventory(project, timeline if lesson is None else lesson)
    rows = identify(timeline, lesson)
    if has_source and lesson.get('pages'):
        planned_rows = identify(lesson)
        planned = Counter(r['term'] for r in planned_rows)
        missing = planned - Counter(r['term'] for r in rows)
        keys = {(p.get('id'),c.get('id')) for p in timeline['pages'] for c in p.get('cues',p.get('beats',[]))}
        old = Counter((r['page'],r['cue'],r['term']) for r in planned_rows if (r['page'],r['cue']) in keys)
        moved = old - Counter((r['page'],r['cue'],r['term']) for r in rows)
        if moved:
            raise ValueError('成片对应句缺少讲稿中的术语：'+str(dict(moved)))
        if missing:
            raise ValueError('成片时间轴缺少讲稿中的术语位置：'+str(dict(missing)))
    reviewed = lesson.get('_term_inventory',{})
    pending=[dict(page=p.get('id',str(pi)),cue=c.get('id',str(ci)))
             for pi,p in enumerate(lesson.get('pages',[]),1) for ci,c in enumerate(p.get('cues',p.get('beats',[])),1)
             if (c.get('spoken_tts') or c.get('tts') or c.get('say') or c.get('text'))
             and sentence_key(p.get('id',str(pi)),c.get('id',str(ci))) not in reviewed]
    report = dict(file=str(Path(media).resolve()), terms=term_counts(rows), items=rows, inventory_pending=pending,
                  classroom_cards=learning_cards(rows), remaining=0)
    chosen = next((r for r in rows if r['id'] == select), None)
    if (select is not None or clip or verdict) and chosen is None:
        raise ValueError('请从当前术语清单选择一个出现位置。')
    updates = {} if hearings is None else hearings
    location_ids = {r['id'] for r in rows}
    if not isinstance(updates,dict) or not location_ids.issuperset(updates):
        raise ValueError('批量记录须使用本片清单中的位置编号。')
    updates = dict(updates)
    if verdict:
        updates[select] = verdict
    if not rows:
        return dict(report, status='pending_inventory' if pending else 'no_matches')
    if timeline.get('draft'):
        raise ValueError('术语实听需要正式成片时间轴。')
    folder = Path(project)/'review-audio'
    folder.mkdir(exist_ok=True)
    report['sha256'] = _digest(media)
    with tempfile.TemporaryFile() as pcm, closing(sqlite3.connect(folder/'term-flow.sqlite3', timeout=20)) as db, db:
        subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(media),'-map','0:a:0',
                        '-ac','1','-ar',str(RATE),'-f','s16le','pipe:1'], stdout=pcm, check=True)
        length = pcm.tell() // 2
        verified_clips = set()
        db.execute('CREATE TABLE IF NOT EXISTS hearings (token TEXT PRIMARY KEY, pronunciation TEXT, flow TEXT)')
        for r in rows:
            a,b = (round(r[k]*RATE) for k in ('cue_start','cue_end'))
            if not 0 <= a < b <= length+round(.08*RATE):
                raise ValueError(f"{r['id']} 的句子超出音轨，请核对所选成片和时间轴。")
            lo, hi = max(0,a-RATE//2), min(length,b+RATE//2)
            pcm.seek(lo*2)
            excerpt = pcm.read(2*(hi-lo))
            start,end = (round(r[k]*RATE)-lo for k in ('start','end'))
            gap, restart = flow_evidence(excerpt[2*start:2*end]) if r['timing']=='word' else (None,False)
            r['possible_restart'] = restart
            r['interior_quiet_ms'] = gap
            r['pause_candidate'] = gap is not None and gap >= 140
            r['length_candidate'] = any(ms >= 480 for ms in r.get('syllable_ms', []))
            clip_hash = hashlib.sha256(excerpt).hexdigest()
            r['cue_audio_sha256'] = clip_hash
            signature = [r['id'], r['text'], r['expected'], start, end, r['timing'], clip_hash]
            card = report['classroom_cards'].get(r['term'], {})
            directions = {k:card[k] for k in ('sense', 'flow', 'contrast', 'feedback', 'feedback_reading') if card.get(k)}
            if directions:
                signature.append(directions)
            token = hashlib.sha256(json.dumps(signature,ensure_ascii=False).encode()).hexdigest()
            r['token'] = token
            path = folder/f'term-{clip_hash}.wav'
            if (r is chosen and clip) or (clips and not path.is_file()):
                with tempfile.NamedTemporaryFile(dir=folder,delete=False) as tmp:
                    temp = Path(tmp.name)
                try:
                    with wave.open(str(temp),'wb') as wav:
                        wav.setparams((1,2,RATE,0,'NONE','not compressed'))
                        wav.writeframes(excerpt)
                    temp.replace(path)
                finally:
                    temp.unlink(missing_ok=True)
            if path.is_file():
                r['clip'] = str(path)
                if r is chosen:
                    report['clip'] = str(path)
            if r['id'] in updates:
                entry = updates[r['id']]
                if not isinstance(entry, (list,tuple)) or len(entry) != 3 or not all(isinstance(v,str) for v in entry):
                    raise ValueError('每条记录填写 token、实际读音、连读结果。')
                previous, spoken, flow = entry
                if previous != token or not path.is_file():
                    raise ValueError('请先截取并听本版该处原句，再用对应 token 登记。')
                if path not in verified_clips:
                    with wave.open(str(path),'rb') as wav:
                        if ((wav.getnchannels(),wav.getsampwidth(),wav.getframerate()) != (1,2,RATE)
                            or wav.readframes(wav.getnframes()) != excerpt):
                            raise ValueError('试听文件已改变，请重新截取本版原句。')
                    verified_clips.add(path)
                spoken = ' '.join(spoken.lower().replace('v','ü').split())
                if (flow not in ('joined','broken','unsure') or (spoken != 'unsure' and
                        (len(spoken.split()) != len(r['term']) or not all(SYLLABLE.fullmatch(s) for s in spoken.split())))):
                    raise ValueError('逐字填写实际听到的带调拼音或 unsure，同时填写 joined、broken 或 unsure。')
                db.execute('INSERT OR REPLACE INTO hearings VALUES (?,?,?)',(token,spoken,flow))
            heard = db.execute('SELECT pronunciation,flow FROM hearings WHERE token=?',(token,)).fetchone()
            r['pronunciation'], r['flow'] = heard or ('pending','pending')
            r['passed'] = bool(r['expected'] and heard and heard[1]=='joined' and
                               all(classroom_syllables(r['term'],r['expected'],heard[0])) and not r['split_in_script'])
    report['remaining'] = sum(not r['passed'] for r in rows)
    report['status'] = 'pending' if report['remaining'] else 'pending_inventory' if pending else 'reviewed'
    return report


def manifest_entry(report):
    return dict(status=report['status'], remaining=report['remaining'], sha256=report.get('sha256'))


def refresh_manifest(project, report):
    path = project/'delivery-files.json'
    if path.is_file():
        record = json.loads(path.read_text())
        if record.get('video') and (project/record['video']).resolve() == Path(report['file']).resolve():
            record['term_review'] = manifest_entry(report)
            save_report(path,record)


def check_samples(manifest):
    """Replay locally saved word windows with known acoustic pause labels."""
    results = []
    cases = json.loads(manifest.read_text())
    if not cases:
        raise ValueError('对照样本清单为空。')
    for case in cases:
        path = manifest.parent / case['file']
        if _digest(path) != case['sha256']:
            raise ValueError(f'对照样本已改变：{path.name}')
        with wave.open(str(path), 'rb') as wav:
            if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate()) != (1,2,RATE):
                raise ValueError('样本使用原速 16 kHz 单声道 PCM16。')
            a,b = (round(case[k]*RATE) for k in ('start','end'))
            if not 0 <= a < b <= wav.getnframes():
                raise ValueError('样本词区间超出录音。')
            wav.setpos(a)
            gap = acoustic_gap(wav.readframes(b-a))
        if not isinstance(case['pause_candidate'],bool):
            raise ValueError('样本要注明是否有可检测的词内停顿。')
        result = dict(term=case['term'],file=case['file'],gap_ms=gap)
        result['passed'] = gap is not None and (gap>=140) == case['pause_candidate']
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project',type=Path)
    parser.add_argument('--check-samples', type=Path, help='重跑本地保留的词内停顿对照样本')
    parser.add_argument('--timeline',default='timeline.json',type=Path)
    parser.add_argument('--video-file',default='video.mp4',type=Path)
    parser.add_argument('--id')
    parser.add_argument('--clip',action='store_true')
    parser.add_argument('--clips', action='store_true', help='每句导出一条带上下文的原速试听，多处共用')
    parser.add_argument('--hearings', type=Path, help='批量登记位置编号到 [token, 实际拼音, 连读结果] 的映射')
    parser.add_argument('--heard',nargs=3,metavar=('TOKEN','PRONUNCIATION','FLOW'))
    parser.add_argument('--strict',action='store_true')
    args = parser.parse_args()
    project = args.project
    if args.check_samples:
        results = check_samples(project/args.check_samples)
        print(json.dumps(results,ensure_ascii=False,indent=2))
        raise SystemExit(int(not all(case['passed'] for case in results)))
    timeline = json.loads((project/args.timeline).read_text())
    lesson = timeline
    if (project/'lesson.json').is_file():
        from speech_plan import apply
        lesson, _ = apply(project,json.loads((project/'lesson.json').read_text()))
    report = inspect(project,timeline,project/args.video_file,lesson=lesson,select=args.id,
                     clip=args.clip,verdict=args.heard,clips=args.clips,
                     hearings=json.loads(args.hearings.read_text()) if args.hearings else None)
    output = project/'final-term-flow.json'
    save_report(output,report)
    refresh_manifest(project, report)
    if 'clip' in report:
        print(report['clip'])
    print(f"{len(report['terms'])} 个术语，{len(report['items'])} 处，待核实 {report['remaining']} 处。 {output}")
    if report['inventory_pending']:
        print(f"另有 {len(report['inventory_pending'])} 句待制作端盘点完整术语。")
    if args.strict and (report['remaining'] or report['inventory_pending']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
