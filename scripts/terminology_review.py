"""Locate physics terms in measured narration and check the written script."""
import math
import re

from pronunciation import term_pattern, LISTEN_TERMS, PHYSICS_PINYIN, spoken_symbols, symbol_reading


PHYSICS_TERMS = {
    '质心': 'zhi4 xin1', '速度': 'su4 du4', '加速度': 'jia1 su4 du4',
    '动量': 'dong4 liang4', '冲量': 'chong1 liang4', '力矩': 'li4 ju3',
    '动量守恒': 'dong4 liang4 shou3 heng2', '角动量守恒': 'jiao3 dong4 liang4 shou3 heng2',
    '动能': 'dong4 neng2', '势能': 'shi4 neng2', '机械能': 'ji1 xie4 neng2',
    '角速度': 'jiao3 su4 du4', '简谐振动': 'jian3 xie2 zhen4 dong4',
    '库仑定律': 'ku4 lun2 ding4 lü4', '高斯定理': 'gao1 si1 ding4 li3',
    '安培环路定律': 'an1 pei2 huan2 lu4 ding4 lü4', '洛伦兹力': 'luo4 lun2 zi1 li4',
    '楞次定律': 'leng2 ci4 ding4 lü4', '电势差': 'dian4 shi4 cha1',
    '电动势': 'dian4 dong4 shi4', '感应电动势': 'gan3 ying4 dian4 dong4 shi4',
    '磁通': 'ci2 tong1', '磁通量': 'ci2 tong1 liang4', '磁通链': 'ci2 tong1 lian4',
    '励磁电流': 'li4 ci2 dian4 liu2', '磁芯': 'ci2 xin1',
    '自感': 'zi4 gan3', '互感': 'hu4 gan3', '互感系数': 'hu4 gan3 xi4 shu4',
    '耦合系数': 'ou3 he2 xi4 shu4', '理想变压器': 'li3 xiang3 bian4 ya1 qi4',
    '变压器': 'bian4 ya1 qi4', '相位差': 'xiang4 wei4 cha1',
    '波长': 'bo1 chang2', '驻波': 'zhu4 bo1', '波节': 'bo1 jie2', '波腹': 'bo1 fu4',
    '折射率': 'zhe2 she4 lü4', '散射': 'san3 she4', '相干': 'xiang1 gan1',
    '等温过程': 'deng3 wen1 guo4 cheng2', '绝热过程': 'jue2 re4 guo4 cheng2',
    '熵增': 'shang1 zeng1', '光电效应': 'guang1 dian4 xiao4 ying4',
    '载荷': 'zai4 he4', '质量数': 'zhi4 liang4 shu4',
    **PHYSICS_PINYIN,
}

POLYPHONIC_TERMS = frozenset(PHYSICS_PINYIN) | frozenset(LISTEN_TERMS) | {
    '动量', '冲量', '动量守恒', '角动量守恒', '磁通量', '互感系数', '耦合系数',
    '相位差', '波长', '折射率', '散射', '感应电动势', '光电效应',
}

REFERENCE_PINYIN = {
    '相乘': 'xiang1 cheng2', '相除': 'xiang1 chu2',
    '相差': 'xiang1 cha1', '重叠': 'chong2 die2', **PHYSICS_TERMS,
}

SPELLING_FIXES = {
    '感应电动事': '感应电动势', '库仑定率': '库仑定律',
    '高斯定率': '高斯定理', '楞次定率': '楞次定律',
    '动量守横': '动量守恒', '历磁电流': '励磁电流',
}

BUILTIN_TERMS = frozenset(PHYSICS_TERMS) | POLYPHONIC_TERMS




def _clean(text):
    return ''.join(char.lower() for char in text if char.isalnum())


def _word_windows(cue, text):
    """Return word intervals indexed by the alphanumeric characters of the script."""
    normalized = []
    intervals = []
    duration = cue['end'] - cue['start']
    for word in cue.get('words', []):
        chars = _clean(word.get('text', ''))
        if not chars:
            continue
        start, end = word.get('start'), word.get('end')
        if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end)):
            return []
        if not 0 <= start <= end or start >= duration:
            return []
        normalized.append(chars)
        intervals.extend([(start, min(end, duration))] * len(chars))
    return intervals if ''.join(normalized) == _clean(text) else []


def inspect_terminology(data):
    from feedback_bank import catalog
    banks = catalog()
    historical_words = banks['polyphones']
    vocabulary = BUILTIN_TERMS | historical_words.keys()
    references = {**REFERENCE_PINYIN, **{word: entry['expected'] for word, entry in historical_words.items()
                                         if entry.get('expected') and not entry.get('context_required')}}
    default_pattern = term_pattern(vocabulary)
    occurrences = []
    warnings = []
    for page_index, page in enumerate(data['pages'], 1):
        page_id = page.get('id', f'p{page_index:02d}')
        for cue in page['cues']:
            text = cue['tts']
            start = page.get('start', 0) + cue['start']
            end = page.get('start', 0) + cue['end']
            rules = {}
            for entry in cue.get('minimax_tone_entries', []):
                term, _, pronunciation = entry.partition('/')
                if term:
                    rules[term] = ' '.join(re.findall(r'\(([^()]+)\)', pronunciation))
            extra = rules.keys() - vocabulary
            pattern = term_pattern(vocabulary | extra) if extra else default_pattern
            matches = sorted([*pattern.finditer(text), *spoken_symbols(text)], key=lambda match: match.start())
            windows = _word_windows(cue, text) if matches else []
            for match in matches:
                term = match.group()
                applied_rules = {word: reading for word, reading in rules.items() if word in term}
                categories = []
                if term in PHYSICS_TERMS:
                    categories.append('physics_term')
                if term in POLYPHONIC_TERMS or term in historical_words:
                    categories.append('polyphonic')
                if applied_rules:
                    categories.append('configured_pronunciation')
                is_symbol = not categories
                if is_symbol:
                    categories.append('letter_or_symbol')
                if is_symbol:
                    known_issue = (term.upper() if term.isascii() else term) in banks['letters']
                else:
                    known_issue = any(word in term for word in historical_words)
                if known_issue:
                    categories.append('viewer_feedback')
                if windows:
                    offset = len(_clean(text[:match.start()]))
                    selected = windows[offset:offset + len(term)]
                    term_start = start + min(w[0] for w in selected)
                    term_end = start + max(w[1] for w in selected)
                else:
                    term_start, term_end = start, end
                reference = references.get(term)
                differs = False
                if reference:
                    syllables = reference.split()
                    for word, reading in applied_rules.items():
                        index = term.index(word)
                        expected = ' '.join(syllables[index:index + len(word)])
                        differs |= reading.replace('v', 'ü') != expected
                if differs:
                    warnings.append({'code':'term-tone-conflict','cue':cue['id'],'term':term,
                                     'start':round(term_start,3),'end':round(term_end,3),
                                     'message':f'“{term}”发送的读音与 {reference} 不同，请回听这一句。'})
                occurrences.append({
                    'page': page_id, 'cue': cue['id'], 'term': term, 'categories': categories,
                    'context': text[max(0, match.start() - 20):match.end() + 20],
                    'reference_pinyin': reference, 'minimax_rules_sent': applied_rules,
                    'reference_reading': symbol_reading(term) if is_symbol else reference,
                    'dictionary_differs': differs,
                    'start': round(term_start, 3), 'end': round(term_end, 3),
                    'timing': 'provider-word' if windows else 'cue', 'status': 'listen',
                })
            for typo, standard in SPELLING_FIXES.items():
                if typo in text or typo in cue.get('text', ''):
                    warnings.append({'code': 'physics-term-spelling', 'cue': cue['id'],
                                     'start': round(start, 3), 'end': round(end, 3),
                                     'message': f'术语“{typo}”建议写作“{standard}”。'})
    return {
        'status': 'pending_listening' if occurrences else 'no_matches',
        'physics_term_occurrences': sum('physics_term' in item['categories'] for item in occurrences),
        'polyphonic_occurrences': sum('polyphonic' in item['categories'] for item in occurrences),
        'symbol_occurrences': sum('letter_or_symbol' in item['categories'] for item in occurrences),
        'items': occurrences,
    }, warnings
