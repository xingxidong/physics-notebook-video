"""Concrete editing prompts for Chinese physics narration."""
import re


ANNOUNCEMENTS = re.compile(
    '下面我们就来|让我们一起来|我们不难发现|我们可以清楚地看到|'
    '需要特别强调的是|这一现象充分说明了|从这个角度来看|'
    '接下来我们将|通过以上分析我们可以看出|综上所述|值得一提的是|一句话总结一下'
)
UNCLEAR_REFERENCE = re.compile(
    r'(?:^|[。！？])\s*(?P<opening>这个东西|这个关系|这样一来|这部分|按照这个思路)'
    r'(?P<rest>[^。！？]{0,11})(?=[。！？]|$)'
)
SOURCE_TALK = re.compile(r'(?:论文|文章|讲义|截图|原文)(?:中|里|上|最后建议|的图|提到|指出|所述)')
UNSEEN_GESTURE = re.compile(r'(?:从|用|跟着|根据)手势(?:来)?看(?:这个|那个|这一个)?量')
READING_MARKUP = re.compile(r'\\(?:d?frac|sqrt|cdot|times|vec|sum|int|begin)\b|[A-Za-z][_^][{\w]|\$[^$]+\$')
REPEATED_TRANSITION = re.compile(r'^(?:然后|接下来|现在|所以|那么|于是)[，,、 ]+(?:然后|接下来|现在|所以|那么|于是)[，,、 ]*')
PREDICATE_BREAK = re.compile(
    r'(?P<label>感应电动势|端电压|线密度|加速度|电阻|电流|功率|动量|速度)'
    r'[，,]\s*(?P<relation>等于|正比于|反比于|满足|由此得到)'
)
UNMARKED_PAUSE = re.compile(r'(?<=[\u3400-\u9fff])[ \t]+(?=[\u3400-\u9fff])')
SENTENCE = re.compile(r'[^。！？!?；;\n]+')
CUE_OPENING = re.compile(r'首先|接下来|下面|然后|现在|因此|所以|于是|由此|最后|我们来|我们可以')
EMPTY_JUDGMENT = re.compile(r'显然|容易看出|不难看出|非常重要|至关重要|我们知道')
GENERIC_SUMMARY = re.compile(r'本节课到这里|这节课就讲到这里|希望大家|记住这个结论')
MEASUREMENT = re.compile(
    r'[0-9零〇一二三四五六七八九十百千万点两]+\s*'
    r'(?:千克|克|牛顿|伏特|伏|安培|安|欧姆|欧|焦耳|焦|瓦特|瓦|厘米|毫米|米|秒)'
)


def _audible_length(text):
    return sum(char.isalnum() for char in text)


def review_narration(cues):
    """Return source excerpts and editing prompts without rewriting the lesson."""
    findings = []
    recent_openings = {}

    def record(cue, code, excerpt, message, **extra):
        item = {'cue': cue['id'], 'code': code, 'excerpt': excerpt.strip(), 'message': message, **extra}
        if 'start' in cue and 'end' in cue:
            item.update(start=round(cue['start'], 3), end=round(cue['end'], 3))
        findings.append(item)

    for index, cue in enumerate(cues):
        text = cue.get('tts', '')
        match = ANNOUNCEMENTS.search(text)
        if match:
            record(cue, 'stock-phrase', match.group(), '直接说学生此刻要看的对象、要判断的关系或要做的运算。')

        match = EMPTY_JUDGMENT.search(text)
        if match:
            record(cue, 'empty-judgment', match.group(), '说出图中哪一项、哪条关系或哪一步运算给出这个判断。')
        match = GENERIC_SUMMARY.search(text)
        if match:
            record(cue, 'generic-ending', match.group(), '收束时回到模型、关键依据和结果，不用礼貌性结束语代替总结。')

        for pattern, code, message in (
            (SOURCE_TALK, 'source-in-narration', '直接点出图上的对象、已知条件或所求，资料出处保留在教师备课记录。'),
            (UNSEEN_GESTURE, 'unseen-gesture', '指出学生能看到的箭头、方向或读数，并说清要比较什么。'),
            (UNCLEAR_REFERENCE, 'vague-reference', '复读前后两段；若指代不够清楚，用点名、物理量或具体算式承接。'),
            (READING_MARKUP, 'readable-formula', 'LaTeX 留在板书，口播说清量名、分组、运算及其依据。'),
            (REPEATED_TRANSITION, 'stacked-transitions', '保留一个自然的接续词，随即说清当前动作或物理关系。'),
        ):
            match=pattern.search(text)
            if match:
                record(cue, code, match.group(), message)

        match = PREDICATE_BREAK.search(text)
        if match:
            record(cue, 'predicate-break', match.group(), '通读量名和关系词，看看停顿是否更适合放在完整关系之后。')

        match = UNMARKED_PAUSE.search(text)
        if match:
            excerpt = text[max(0, match.start() - 10):match.end() + 10]
            record(cue, 'unmarked-pause', excerpt, '用句意确定这里是连读、逗号还是句号，让停顿落在完整的意思上。')

        for sentence in SENTENCE.finditer(text):
            clause = sentence.group().strip()
            if _audible_length(clause) < 44:
                continue
            parts = re.split(r'[，,、：:]', clause)
            if len(parts) >= 4 or any(_audible_length(part) >= 40 for part in parts):
                record(cue, 'dense-sentence', clause, '按一组量、一次判断或一步运算分句，保留条件、方向和因果。')
                break

        values = list(MEASUREMENT.finditer(text))
        for first, last in zip(values, values[3:]):
            if last.end() - first.start() <= 65:
                excerpt = text[first.start():last.end()]
                record(cue, 'dense-measurements', excerpt, '把已知值和算出的量分开讲。每报一组值，接上它从哪条关系得到。')
                break

        opening = CUE_OPENING.match(text.lstrip(' \t\n“「'))
        if opening:
            word = opening.group()
            recent = [entry for entry in recent_openings.get(word, []) if index - entry[0] <= 3]
            recent.append((index, cue['id']))
            recent_openings[word] = recent
            if len(recent) == 3:
                record(cue, 'repeated-opening', word, '检查这几段的衔接，能用前一步所得、图中对象或当前运算直接开口时就直接说。',
                       related_cues=[entry[1] for entry in recent])
        # Several short generated clips in a row often sound like each sentence
        # was separately prompted.  Keep true question-answer turns separate;
        # otherwise mark a continuous teacher thought with speech_group.
        if 0 < index < len(cues)-1:
            trio=cues[index-1:index+2]
            if (all(_audible_length(item.get('tts',''))<23 for item in trio)
                    and len({item.get('role') for item in trio})==1
                    and not any('？' in item.get('tts','') or '?' in item.get('tts','') for item in trio)
                    and not any(item.get('speech_group') for item in trio)):
                record(cue, 'fragmented-thought', text, '这几句属于同一思路时，用 speech_group 连续配音；有提问、观察或转折时保留独立语气。')
    return findings
