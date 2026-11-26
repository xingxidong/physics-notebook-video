"""Make portable physics pronunciation cards from classroom phrasing and term glossaries."""
from collections import defaultdict
from contextlib import closing
from hashlib import sha256
from functools import lru_cache
import argparse
import json
import tempfile
from pathlib import Path
import re
import sqlite3

from pronunciation import HAN_TERM, SYLLABLE

NOTES = Path(__file__).resolve().parents[1] / 'references'
ARCHIVE = NOTES.parent / 'assets' / 'classroom-cards.json'
CARD_COLUMNS = {'词义与语境': 'sense', '例句': 'example', '连读': 'flow', '易混': 'contrast'}
TERM_HEADERS = {'词语', '词或短语', '词或词组', '术语', '物理术语'}
READING_HEADERS = {'拼音', '读音', '讲课读音', '建议拼音', '带调拼音'}
TIME = re.compile(r'(?<!\d)(?:\d{1,2}:)?\d{1,2}:\d{2}(?:\.\d+)?(?!\d)')


@lru_cache(maxsize=96)
def _table_rows(path, mtime_ns, size):
    rows = []
    columns = None
    topic = ''
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith(('## ', '### ')):
            topic = line.lstrip('# ').strip()
        if not line.startswith('|'):
            columns = None
            continue
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if TERM_HEADERS.intersection(cells) and READING_HEADERS.intersection(cells):
            columns = cells
            continue
        if not columns or len(columns)!=len(cells):
            continue
        record = dict(zip(columns,cells))
        term = next(record[k] for k in columns if k in TERM_HEADERS)
        if not HAN_TERM.fullmatch(term):
            continue
        reading = next(record[k] for k in columns if k in READING_HEADERS)
        syllables = reading.lower().replace('v','ü').split()
        valid = len(syllables)==len(term) and all(SYLLABLE.fullmatch(s) for s in syllables)
        rows.append((term, dict(reading=' '.join(syllables) if valid else None, topic=topic,
                                usage=record.get('题目或用法') or record.get('用法',''),
                                **{key:record[col] for col,key in CARD_COLUMNS.items() if record.get(col)})))
    return rows


def note_sources(directory=None):
    root = directory or NOTES
    notes = [*root.glob('ying-xiaolv-*.md'), *(root/'term-glossaries').rglob('*.md')]
    stamps = []
    for path in sorted(notes):
        info = path.stat()
        stamps.append((path, info.st_mtime_ns, info.st_size))
    return _note_source_index(root, tuple(stamps))


@lru_cache(maxsize=16)
def _note_source_index(root, stamps):
    index = defaultdict(list)
    for path, modified, size in stamps:
        name = path.relative_to(root).as_posix()
        for term, entry in _table_rows(path, modified, size):
            index[term].append(dict(entry, note=name))
    return index


@lru_cache(maxsize=96)
def _examples(path, mtime_ns, size):
    """Keep complete classroom phrasing, without media references or speaker metadata."""
    examples = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith(('|', '#')):
            continue
        for phrase in re.findall(r'“([^“”\n]{5,100})”', line):
            if TIME.search(phrase) or any(s in phrase for s in ('.mp4', '原片', '截图', '老师', '://')):
                continue
            examples.add(phrase.strip())
    return sorted(examples, key=lambda phrase: (not re.search(r'等于|得到|越|保持|增大|减小|取决于|决定|相同|产生|抵消|沿着|经过|对准|测出|表示', phrase), len(phrase), phrase))


def reusable(text):
    return bool(text and not TIME.search(text) and not any(s in text for s in ('.mp4', '原片', '://', '/Users/')))


def assemble(refs):
    """Each field must be usable when neither teaching notes nor recordings are present."""
    readings = {row['reading'] for row in refs}
    card = {'readings': sorted(readings, key=lambda reading: reading or '')}
    for key in CARD_COLUMNS.values():
        value = next((row[key] for row in refs if reusable(row.get(key))), None)
        if value:
            card[key] = value
    usages = []
    for field in ('usage', 'topic'):
        for row in refs:
            value = row[field]
            if (reusable(value) and value not in usages and value != card.get('sense')
                    and not any(word in value for word in ('词表', '拼音', '词条', '核对', '录音', '读音', '词组'))):
                usages.append(value)
    if usages and 'sense' not in card:
        card['contexts'] = usages[:2]
    return card


@lru_cache(maxsize=8)
def _read_archive(path, mtime_ns, size):
    archive = json.loads(path.read_text(encoding='utf-8'))
    if archive.get('schema') != 1 or not isinstance(archive.get('cards'), dict):
        raise ValueError(f'课堂读音卡格式不正确：{path}')
    return archive['cards']


def saved_cards(path):
    if not path.is_file():
        return {}
    info = path.stat()
    return _read_archive(path, info.st_mtime_ns, info.st_size)


def collect(directory, archive, requested=None):
    saved = saved_cards(archive)
    cards = dict(saved) if requested is None else {term:saved[term] for term in requested if term in saved}
    for term, refs in note_sources(directory).items():
        if requested is not None and term not in requested:
            continue
        card = assemble(refs)
        if 'example' not in card:
            for note in dict.fromkeys(row['note'] for row in refs):
                path = directory / note
                info = path.stat()
                phrases = _examples(path, info.st_mtime_ns, info.st_size)
                phrase = next((p for p in phrases if term in p and len(p) >= len(term) + 4), None)
                if phrase:
                    card['example'] = phrase
                    break
        cards[term] = {**cards.get(term, {}), **card}
    return cards


def note_readings(directory=None):
    index = note_sources(directory)
    words = {term:set(card['readings']) for term,card in saved_cards(ARCHIVE).items()}
    words.update({term:{row['reading'] for row in refs} for term,refs in index.items()})
    return words


@lru_cache(maxsize=1)
def practice():
    path = Path(__file__).resolve().parents[1] / 'assets' / 'reading-practice.json'
    return json.loads(path.read_text(encoding='utf-8'))


def context_sense(term, text, offset):
    for reading, rule in practice()['senses'].get(term, {}).items():
        for phrase in rule['phrases']:
            start = offset - phrase.index(term)
            if start >= 0 and text.startswith(phrase, start):
                return reading
    return None


def letter_card(symbol):
    from feedback_bank import catalog
    from pronunciation import symbol_reading
    key = symbol.upper()
    sentence = practice()['letters'].get(key)
    if not sentence:
        return None
    note = catalog()['letters'].get(key, {})
    guidance = practice()['letter_listening'].get(key,'按英文字母名连读，随后接回中文原句。')
    card = dict(symbol=key,expected=symbol_reading(key),example=sentence,listen_for=guidance)
    if note.get('observed'):
        card['listen_for'] += ' 已有反馈：' + note['observed']
    return card


def feedback_cards(rules=None):
    from feedback_bank import catalog
    rules = catalog() if rules is None else rules
    cards = {}
    for term, row in rules['polyphones'].items():
        if len(term) > 1:
            cards[term] = dict(feedback=row['observed'])
            if row.get('example'):
                cards[term]['feedback_example'] = row['example']
            if row.get('expected') and not row.get('context_required'):
                cards[term]['feedback_reading'] = row['expected']
    for key, row in rules['issues'].items():
        if not (key == 'term-flow' or key.startswith('term-flow-')):
            continue
        if row.get('scope', 'all') != 'all' or row.get('only_this_lesson'):
            continue
        for term in ([row['match']] if row.get('match') else row.get('review_phrases', [])):
            if not HAN_TERM.fullmatch(term):
                continue
            card = cards.setdefault(term, {})
            card['feedback'] = row['observed']
            if row.get('card_flow'):
                card['flow'] = row['card_flow']
            if row.get('card_reading'):
                card['feedback_reading'] = row['card_reading']
            if row.get('example'):
                card['feedback_example'] = row['example']
    return cards


def learning_cards(occurrences):
    groups = defaultdict(list)
    for row in occurrences:
        groups[row['term']].append(row)
    saved = collect(NOTES, ARCHIVE, set(groups))
    feedback = feedback_cards()
    cards = {}
    for term, uses in sorted(groups.items()):
        sentences = [r for r in uses if r.get('text')]
        readings = sorted({r['expected'] for r in uses if r.get('expected')})
        if term in saved:
            card = dict(saved[term], scope='classroom')
        elif term in feedback:
            card = dict(scope='feedback', readings=readings)
        elif sentences:
            card = dict(scope='this_lesson', readings=readings)
        else:
            continue
        card.update(feedback.get(term, {}))
        if card.get('feedback_reading') and not card['readings']:
            card['readings'] = [card['feedback_reading']]
        pairs = [line for line, targets in practice()['pairs'] if any(t == term for t, _ in targets)]
        if pairs:
            card['contrast_sentences'] = pairs
        if sentences:
            card['lesson_example'] = sentences[0]['text']
            if readings != card['readings']:
                card['lesson_readings'] = readings
        cards[term] = card
    return cards


def _compile_cards(directory, archive):
    cards = collect(directory, archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=archive.parent, delete=False) as file:
        tmp = Path(file.name)
    try:
        fields = (json.dumps(term, ensure_ascii=False) + ': ' + json.dumps(card, ensure_ascii=False)
                  for term,card in sorted(cards.items()))
        tmp.write_text('{"schema":1,"cards":{\n' + ',\n'.join(fields) + '\n}}\n', encoding='utf-8')
        tmp.replace(archive)
    finally:
        tmp.unlink(missing_ok=True)
    return cards


def compile_cards(directory, archive):
    # Serialize independent learning sessions updating the same permanent collection.
    key = sha256(str(archive.resolve()).encode()).hexdigest()
    lock = Path(tempfile.gettempdir()) / f'physics-classroom-cards-{key}.sqlite3'
    with closing(sqlite3.connect(lock, timeout=45)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        return _compile_cards(directory, archive)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='保存独立的课堂读音卡，或查看某个词的读法和语境。')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--compile',action='store_true')
    mode.add_argument('--show',metavar='术语')
    args = parser.parse_args()
    if args.compile:
        print(f'已保存 {len(compile_cards(NOTES, ARCHIVE))} 张读音卡。')
    else:
        if len(args.show) == 1 and letter_card(args.show):
            print(json.dumps(letter_card(args.show), ensure_ascii=False, indent=2))
            parser.exit()
        cards = learning_cards([{'term':args.show}])
        if args.show not in cards:
            parser.exit(1, f'还没有“{args.show}”的课堂读音卡。\n')
        print(json.dumps(cards[args.show], ensure_ascii=False, indent=2))
