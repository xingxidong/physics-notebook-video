"""Concrete editing prompts for Chinese physics narration."""
import re


ANNOUNCEMENTS = re.compile(
    '下面我们就来|让我们一起来|我们不难发现|我们可以清楚地看到|'
    '需要特别强调的是|这一现象充分说明了|从这个角度来看'
)
PREDICATE_BREAK = re.compile(
    r'(?P<label>感应电动势|端电压|线密度|加速度|电阻|电流|功率|动量|速度)'
    r'[，,]\s*(?P<relation>等于|正比于|反比于|满足|由此得到)'
)
UNMARKED_PAUSE = re.compile(r'(?<=[\u3400-\u9fff])[ \t]+(?=[\u3400-\u9fff])')
SENTENCE = re.compile(r'[^。！？!?；;\n]+')
CUE_OPENING = re.compile(r'首先|接下来|下面|然后|现在|因此|所以|于是|由此|最后|我们来|我们可以')
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
    return findings
