"""Mandarin physics terminology for MiniMax and the narration review."""
import re


PHYSICS_PINYIN = {
    '长度': 'chang2 du4',
    '重量': 'zhong4 liang4',
    '质量': 'zhi4 liang4',
    '相乘': 'xiang1 cheng2',
    '相除': 'xiang1 chu2',
    '相干': 'xiang1 gan1',
    '增长': 'zeng1 zhang3',
    '长短': 'chang2 duan3',
    '测量': 'ce4 liang2',
    '矢量': 'shi3 liang4',
    '重复': 'chong2 fu4',
    '伸长': 'shen1 chang2',
    '波长': 'bo1 chang2',
    '长轴': 'chang2 zhou2',
    '相位': 'xiang4 wei4',
    '相位差': 'xiang4 wei4 cha1',
    '相角': 'xiang4 jiao3',
    '同相': 'tong2 xiang4',
    '反相': 'fan3 xiang4',
    '相长干涉': 'xiang1 zhang3 gan1 she4',
    '相消干涉': 'xiang1 xiao1 gan1 she4',
    '行波': 'xing2 bo1',
    '电荷': 'dian4 he4',
    '载流': 'zai4 liu2',
    '负载': 'fu4 zai4',
    '折射': 'zhe2 she4',
    '切线': 'qie1 xian4',
    '切向': 'qie1 xiang4',
    '重心': 'zhong4 xin1',
    '重合': 'chong2 he2',
    '重叠': 'chong2 die2',
    '重力': 'zhong4 li4',
    '薄膜': 'bo2 mo2',
    '屏蔽': 'ping2 bi4',
    '弹簧': 'tan2 huang2',
    '弹性': 'tan2 xing4',
    '角动量': 'jiao3 dong4 liang4',
    '转动惯量': 'zhuan4 dong4 guan4 liang4',
}

# These words can come up alongside the fixed terms. Their context guides audition.
LISTEN_TERMS = ('相乘', '相除', '相差', '相干', '重叠', '薄膜', '载荷', '转一圈', '质量数')
HAN_TERM = re.compile(r'[\u3400-\u9fff]+')
SYLLABLE = re.compile(r'[a-zü]+[1-5]')
# Written math is oralized structurally before the plain narration reaches here.
# Protect identifiers, English words and ASCII subscript tokens in ordinary prose.
FREE_SYMBOL = re.compile(r'(?<![A-Za-z_Α-Ωα-ω])[A-Za-zΑ-Ωα-ωϕϵϑ](?![A-Za-z_0-9Α-Ωα-ω])')
LETTER_IPA = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', (
    'eɪ', 'biː', 'siː', 'diː', 'iː', 'ɛf', 'dʒiː', 'eɪtʃ', 'aɪ', 'dʒeɪ',
    'keɪ', 'ɛl', 'ɛm', 'ɛn', 'oʊ', 'piː', 'kjuː', 'ɑːr', 'ɛs', 'tiː',
    'juː', 'viː', 'ˈdʌbəljuː', 'ɛks', 'waɪ', 'ziː',
)))
# Use unambiguous English words for these names when sending mixed-language
# plain text. The lesson, subtitles and timing anchors keep the source symbol.
ENGLISH_NAMES = {'X': 'ex', 'Y': 'why', 'I': 'eye'}
GREEK = dict(zip('αβγδεζηθικλμνξοπρστυφχψω',
                 '阿尔法 贝塔 伽马 德尔塔 艾普西隆 泽塔 伊塔 西塔 约塔 卡帕 拉姆达 缪 纽 克西 奥密克戎 派 柔 西格玛 陶 宇普西隆 斐 希 普赛 欧米伽'.split()))
GREEK.update({'ϕ': '斐', 'ϵ': '艾普西隆', 'ϑ': '西塔', 'ς': '西格玛'})
# A lone m as the denominator or numerator of a written unit is not a variable.
# Recognize units only in measurement context so e.g. "取 m 为质量" keeps M.
UNIT = r'(?:kg|mol|Hz|Pa|Wb|cd|[mgsANKJWVCHFST])'
MEASUREMENT = re.compile(r'(?:[0-9]|单位(?:是|为)?[：:]?)\s*' + UNIT +
                         r'(?:[²³]|\^[23])?(?:\s*[/·]\s*' + UNIT + r'(?:[²³]|\^[23])?)*(?![A-Za-z])')
UNIT_RATIO = re.compile(r'(?<![A-Za-z])' + UNIT + r'(?:\s*/\s*' + UNIT + r')+(?![A-Za-z])')


GEOMETRY_LABEL = re.compile(r'(?:线段|直线|射线|三角形|四边形|斜边|边长)\s*([A-Z]{2,4})(?![A-Za-z0-9_])')
CAPITAL = re.compile('[A-Z]')


def spoken_symbols(text):
    units = [m.span() for pattern in (MEASUREMENT, UNIT_RATIO) for m in pattern.finditer(text)]
    matches = [m for m in FREE_SYMBOL.finditer(text) if not any(a <= m.start() < b for a, b in units)]
    for label in GEOMETRY_LABEL.finditer(text):
        matches.extend(CAPITAL.finditer(text, *label.span(1)))
    return sorted(matches, key=lambda m: m.start())


def symbol_reading(symbol):
    upper = symbol.upper()
    if upper in LETTER_IPA:
        return f'{upper} /{LETTER_IPA[upper]}/'
    return GREEK.get(symbol.lower(), symbol)


def letter_bindings(text, requested=None):
    if requested is None:
        requested = {}
    if not isinstance(requested, dict) or any(
        not isinstance(k, str) or not FREE_SYMBOL.fullmatch(k) or not isinstance(v, str) or not v.strip()
        for k, v in requested.items()
    ):
        raise ValueError('symbol_readings 应填单个字母和字母名。')
    symbols = {m.group() for m in spoken_symbols(text)}
    absent = requested.keys() - symbols - {m.group() for m in FREE_SYMBOL.finditer(text)}
    if absent:
        raise ValueError(f'句中找不到独立变量符号 {sorted(absent)}。')
    result = {}
    for symbol in symbols:
        upper = symbol.upper()
        default = ENGLISH_NAMES.get(upper, upper) if upper in LETTER_IPA else symbol_reading(symbol)
        # Older lessons bound a letter to its quantity. Upgrade those aliases to
        # the letter name. Only a known phonetic rendering may change the sound.
        variant = requested.get(symbol)
        if upper == 'X' and variant in ('艾克斯', '埃克斯'):
            default = variant
        result[symbol] = default
    return result


def resolve_readings(text, readings=None):
    names = letter_bindings(text, readings)
    pieces = []
    last = 0
    for m in spoken_symbols(text):
        name = names[m.group()]
        if name.isascii():
            left = ' ' if m.start() and text[m.start()-1].isalnum() and not (pieces and pieces[-1].endswith(' ')) else ''
            right = ' ' if m.end() < len(text) and text[m.end()].isalnum() else ''
            name = left + name + right
        pieces.extend([text[last:m.start()], name])
        last = m.end()
    return ''.join([*pieces, text[last:]])


def display_words(text, readings, words):
    """Keep provider timing at whole-word boundaries outside a spoken alias."""
    if not readings or not words:
        return words
    clean = lambda value: ''.join(c.lower() for c in value if c.isalnum())
    boundaries = {0: 0}
    printed = []
    spoken = []
    offset = 0
    last = 0

    def append(unit, reading):
        nonlocal offset
        printed.append(unit)
        spoken.append(reading)
        offset += len(reading)
        boundaries[offset] = len(printed)

    for match in spoken_symbols(text):
        if match.group() not in readings:
            continue
        for char in text[last:match.start()]:
            if char.isalnum():
                append(char, char.lower())
        append(match.group(), clean(readings[match.group()]))
        last = match.end()
    for char in text[last:]:
        if char.isalnum():
            append(char, char.lower())
    if ''.join(spoken) != ''.join(clean(w['text']) for w in words):
        return []
    result = []
    consumed = start_index = 0
    start_time = None
    for word in words:
        token = clean(word['text'])
        if not token:
            continue
        if start_time is None:
            start_time = word['start']
        consumed += len(token)
        if consumed in boundaries:
            end = boundaries[consumed]
            result.append({'text': ''.join(printed[start_index:end]), 'start': start_time, 'end': word['end']})
            start_index, start_time = end, None
    return result


def matched_pronunciations(text, course_overrides=None, cue_overrides=None):
    """Use built-in terms, then course and cue overrides. False clears inherited rules."""
    terms = PHYSICS_PINYIN.copy()
    for overrides in (course_overrides, cue_overrides):
        if overrides is None:
            continue
        if overrides is False:
            terms.clear()
            continue
        if not isinstance(overrides, dict):
            raise ValueError('minimax_pronunciation must be a mapping of Chinese terms to numbered pinyin, or false')
        for term, pinyin in overrides.items():
            if not isinstance(term, str) or not HAN_TERM.fullmatch(term):
                raise ValueError(f'Pronunciation term must contain Chinese characters: {term!r}')
            if pinyin is None:
                terms.pop(term, None)
                continue
            syllables = pinyin.lower().split() if isinstance(pinyin, str) else []
            if len(syllables) != len(term) or not all(SYLLABLE.fullmatch(s) for s in syllables):
                raise ValueError(f'{term}: provide one pinyin syllable with a tone number 1–5 per character')
            terms[term] = ' '.join(syllables)
    return {m.group(): terms[m.group()] for m in term_pattern(terms).finditer(text)} if terms else {}


def term_pattern(terms):
    choices = []
    for term in sorted(terms, key=lambda t: (-len(t), t)):
        pattern = re.escape(term)
        if term in ('同相', '反相'):
            pattern += '(?!干|位|乘|除)'
        choices.append(pattern)
    return re.compile('|'.join(choices))


# Plain-text local synthesizers have no portable pinyin API. Use same-sound
# characters only for the documented trouble spots and only in the TTS input.
PLAIN_HINTS = {'长度': ('chang2 du4', '常度'), '相位': ('xiang4 wei4', '向位'),
               '相位差': ('xiang4 wei4 cha1', '向位差')}


def local_tts_text(text, terms, course=None, cue=None):
    hints = {term: replacement for term, (reading, replacement) in PLAIN_HINTS.items()
             if terms.get(term) == reading}
    for overrides in (course, cue):
        if overrides is None:
            continue
        if overrides is False:
            hints.clear()
            continue
        if not isinstance(overrides, dict):
            raise ValueError('plain_pronunciation 应填原词与同音提示的对应表。')
        for term, hint in overrides.items():
            if not isinstance(term, str) or not HAN_TERM.fullmatch(term):
                raise ValueError(f'原词应使用完整中文词语：{term!r}')
            if hint is None:
                hints.pop(term, None)
            elif isinstance(hint, str) and HAN_TERM.fullmatch(hint) and len(hint) == len(term):
                hints[term] = hint
            else:
                raise ValueError(f'“{term}”的同音提示应与原词汉字数相同。')
    vocabulary = set(terms) | hints.keys()
    if not vocabulary:
        return text
    return term_pattern(vocabulary).sub(lambda m: hints.get(m.group(), m.group()), text)


def minimax_dictionary(matches):
    return {'tone': [term + '/' + ''.join(f'({syllable})' for syllable in pinyin.split())
                     for term, pinyin in matches.items()]}
