"""Resolve each spoken occurrence once, including homographs and ordered letter names."""
from collections import defaultdict
import re

from classroom_terms import learning_cards, letter_card, practice, reference_examples
from pronunciation import local_tts_text, matched_pronunciations, term_pattern
from term_flow import identify
from term_inventory import script_text, sentence_key

_SUB = re.compile(r'(?<=[a-zA-Zα-ω])(?:_\{[0-9a-zA-Z]+\}|_[0-9a-zA-Z]+|[0-9₀-₉]+)')
_SUFFIX = re.compile(r'(?:_\{[0-9a-zA-Z]+\}|_[0-9a-zA-Z]+|[0-9₀-₉]+|\s*下标\s*[零一二三四五六七八九0-9a-zA-Z]+|零)')


def symbols_in_order(text):
    from pronunciation import spoken_symbols, symbol_reading
    masked = _SUB.sub(lambda match: ' ' * len(match.group()), text)
    result = []
    for match in spoken_symbols(masked):
        symbol = match.group()
        suffix = _SUFFIX.match(text, match.end())
        end = suffix.end() if suffix else match.end()
        item = dict(symbol=symbol, offset=match.start(), core_end=match.end(), end=end,
                    expression=text[match.start():end], expected=symbol_reading(symbol))
        if suffix:
            item['subscript'] = re.sub(r'[_{}\s]|下标', '', suffix.group()).translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789'))
        card = letter_card(symbol)
        if card:
            item['listen_for'] = card['listen_for']
            item['example'] = card['example']
        result.append(item)
    return result


def cue_input(text, rows, cards, speech, cue, exclusions):
    course_dict, cue_dict = speech.get('minimax_pronunciation'), cue.get('minimax_pronunciation')
    base = matched_pronunciations(text, course_dict, cue_dict)
    # Dictionary overrides have always been allowed per course and per cue.
    disabled = False
    configured = {}
    for setting in (course_dict, cue_dict):
        if setting is False:
            disabled = True
            configured.clear()
        elif isinstance(setting, dict):
            configured.update(setting)
    targets = []
    options = dict(base)
    picked = {}
    for row in rows:
        term, offset = row['term'], row['offset']
        if row['split_in_script'] or not row['expected']:
            continue
        selected = row['expected']
        target = dict(term=term, offset=offset, expected=selected)
        if row.get('reading_source') or term in speech.get('physics_terms', {}):
            target['reading_source'] = row.get('reading_source','lesson')
        if cards[term].get('flow'):
            target['flow'] = cards[term]['flow']
        targets.append(target)
        if (disabled and term not in base) or (term in configured and configured[term] is None):
            continue
        options.setdefault(term, selected)
        picked[offset, term] = row
    parts = []
    # A rejected substring at one offset must not hide shorter valid terms there.
    rejected = {(x['offset'], x['term']) for x in exclusions}
    pattern = term_pattern(options) if options else None
    pos = 0
    while pattern and (m := pattern.search(text, pos)):
        start, end, term = m.start(), m.end(), m.group()
        if (start,term) in rejected:
            alternatives = [key for key in options if key != term and text.startswith(key,start)
                            and (start,key) not in rejected and term_pattern([key]).match(text,start)]
            if not alternatives:
                pos = start + 1
                continue
            term = max(alternatives,key=len)
            end = start + len(term)
        row = picked.get((start, term))
        sound = configured.get(term) or (row['expected'] if row else options[term])
        sounds = sound.split()
        surface = list(term)
        for inner in rows:
            off, word = inner['offset'], inner['term']
            if (inner.get('reading_source') or word in speech.get('physics_terms', {})) and inner['expected'] and start <= off and off+len(word) <= end:
                sounds[off-start:off-start+len(word)] = inner['expected'].split()
                if inner.get('spoken_as'):
                    surface[off-start:off-start+len(word)] = inner['spoken_as']
        parts.append((start, end, term, ' '.join(sounds), ''.join(surface)))
        pos = end
    variants = defaultdict(set)
    for _,_,term,sound,_ in parts:
        variants[term].add(sound)
    mapping = {}
    conflicts = []
    provider, local = [], []
    plain_course, plain_cue = speech.get('plain_pronunciation'), cue.get('plain_pronunciation')
    def local_gap(gap):
        return local_tts_text(gap, {}, plain_course, plain_cue) if gap and (plain_course or plain_cue) else gap
    last = 0
    for start,end,term,sound,surface in parts:
        provider.append(text[last:start])
        local.append(local_gap(text[last:start]))
        alias = practice()['senses'].get(term,{}).get(sound,{}).get('spoken_as', term)
        provider_term = surface if surface != term else alias if len(variants[term]) > 1 else term
        if provider_term in mapping and mapping[provider_term] != sound:
            conflicts.append(term)
        mapping[provider_term] = sound
        provider.append(provider_term)
        hint = local_tts_text(term, {term:sound}, speech.get('plain_pronunciation'), cue.get('plain_pronunciation'))
        local.append(surface if surface != term else alias if alias != term and hint == term else hint)
        last = end
    provider.append(text[last:])
    local.append(local_gap(text[last:]))
    local_text = ''.join(local)
    # A producer may have approved a spelling for a full phrase crossing two terms.
    overrides = {}
    for setting in (plain_course, plain_cue):
        if setting is False:
            overrides.clear()
        elif isinstance(setting,dict):
            overrides.update(setting)
    if overrides:
        rendered = list(local_text)
        for hit in term_pattern(overrides).finditer(text):
            rendered[hit.start():hit.end()] = overrides[hit.group()] or hit.group()
        local_text = ''.join(rendered)
    # A global provider dictionary cannot express a word boundary excluded only at one site.
    exclusion_conflicts = set()
    for _, term in rejected:
        if term in mapping:
            # One unqualified backend entry would apply even at the excluded site.
            exclusion_conflicts.add(term)
            mapping.pop(term)
    return dict(source=text, provider_text=''.join(provider), pinyin=mapping, local_text=local_text,
                targets=targets, conflicts=sorted(set(conflicts)), provider_exclusions=sorted(exclusion_conflicts), symbols=symbols_in_order(cue.get('tts',text)))


def contextual_targets(data, lesson=None):
    """Look up course-specific choices for auxiliary character and sentence reviews."""
    source = lesson if lesson is not None else data
    speech = source.get('speech',{})
    groups = defaultdict(list)
    if speech.get('term_uses') or speech.get('physics_terms'):
        for row in identify(data,source):
            if not row['split_in_script'] and (row.get('reading_source') or row['term'] in speech.get('physics_terms',{})):
                groups[str(row['page']),str(row['cue'])].append(dict(row,reading_source=row.get('reading_source','lesson')))
    return groups


def formula_examples(cue, text):
    """Use exact expressions first, then examples that explain the same operation."""
    actions = cue.get('resolved_actions', cue.get('actions', []))
    formulas = {re.sub(r'\s+', '', action['latex']) for action in actions if action.get('latex')}
    commands = {r'\frac', r'\sqrt', r'\sin', r'\cos', r'\tan', r'\arctan', r'\exp',
                r'\log', r'\ln', r'\int', r'\sum', r'\lim', r'\dot', r'\ddot'}
    result = []
    for kind in ('physics_formula', 'math_formula', 'math_function', 'greek'):
        candidates = []
        for example in reference_examples():
            if example['kind'] != kind:
                continue
            expression = re.sub(r'\s+', '', example['formula'])
            exact = expression in formulas
            nearby = sum(len(word) for word in example['keywords'] if word in text)
            similar = any(cmd in expression and any(cmd in formula for formula in formulas) for cmd in commands)
            score = 500 * exact + 40 * similar + nearby
            if score and (exact or similar or nearby >= 3):
                candidates.append((score, example))
        if candidates:
            _, example = max(candidates, key=lambda pair: pair[0])
            result.append({key: example[key] for key in ('kind', 'formula', 'text', 'flow')})
    return result


def lesson_inputs(lesson, occurrences=None, *, include_references=False):
    rows = identify(lesson) if occurrences is None else occurrences
    cards = learning_cards(rows)
    groups = defaultdict(list)
    for row in rows:
        groups[str(row['page']),str(row['cue'])].append(row)
    results = {}
    for pi,page in enumerate(lesson.get('pages',[]),1):
        pid = str(page.get('id',pi))
        for ci,cue in enumerate(page.get('cues',page.get('beats',[])),1):
            cid = str(cue.get('id',ci))
            exclusions = lesson.get('_term_inventory',{}).get(sentence_key(pid,cid),{}).get('exclude',[])
            text = script_text(cue)
            planned = cue_input(text, groups[pid,cid], cards, lesson.get('speech',{}), cue, exclusions)
            if include_references:
                planned['formula_examples'] = formula_examples(cue, text)
            results[pid,cid] = planned
    return results


def restore_script_words(audio, provider_text, script):
    """Map same-length spelling hints back to the script without moving timed words."""
    if provider_text == script or not audio.get('words'):
        return audio
    def letters(text):
        return ''.join(c for c in text if c.isalnum())
    sent, printed = letters(provider_text), letters(script)
    words = audio['words']
    if len(sent) != len(printed) or ''.join(letters(w['text']) for w in words).lower() != sent.lower():
        return dict(audio,words=[])
    offset = 0
    mapped = []
    for word in words:
        n = len(letters(word['text']))
        if n:
            mapped.append(dict(word,text=printed[offset:offset+n]))
        offset += n
    return dict(audio,words=mapped)


def merged_provider(inputs):
    """Group only cues whose complete word mappings are valid over the entire utterance."""
    mapping = {}
    for entry in inputs:
        if entry['conflicts']:
            raise ValueError('同句异读需要可区分的配音词形：'+', '.join(entry['conflicts']))
        if entry.get('provider_exclusions'):
            raise ValueError('请为当前句有效术语的出现位置指定独立配音词形：'+', '.join(entry['provider_exclusions']))
        for term, target in entry['pinyin'].items():
            if term in mapping and mapping[term] != target:
                raise ValueError(f'相邻两句的“{term}”读法不同。')
            mapping[term] = target
    if len(inputs) > 1 and mapping:
        pattern = term_pattern(mapping)
        for entry in inputs:
            for match in pattern.finditer(entry['provider_text']):
                if match.group() not in entry['pinyin']:
                    raise ValueError(f'相邻两句的“{match.group()}”需要各自的读音设置。')
    return {'provider_text':' '.join(entry['provider_text'] for entry in inputs), 'pinyin':mapping}
