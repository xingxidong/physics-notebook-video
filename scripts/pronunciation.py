"""Mandarin physics terminology for MiniMax and the narration review."""
import re


PHYSICS_PINYIN = {
    '相位': 'xiang4 wei4',
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
    '弹簧': 'tan2 huang2',
    '弹性': 'tan2 xing4',
    '角动量': 'jiao3 dong4 liang4',
    '转动惯量': 'zhuan4 dong4 guan4 liang4',
}

# These words can come up alongside the fixed terms. Their context guides audition.
LISTEN_TERMS = ('相乘', '相除', '相差', '相干', '重叠', '薄膜', '载荷', '转一圈', '质量数')
HAN_TERM = re.compile(r'[\u3400-\u9fff]+')
SYLLABLE = re.compile(r'[a-zü]+[1-5]')


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
    return {term: terms[term] for term in sorted(terms) if term in text}


def minimax_dictionary(matches):
    return {'tone': [term + '/' + ''.join(f'({syllable})' for syllable in pinyin.split())
                     for term, pinyin in matches.items()]}
