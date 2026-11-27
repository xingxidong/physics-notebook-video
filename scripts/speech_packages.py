"""The two portable sources of classroom pronunciation requirements."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = Path('assets/pronunciation-cards/classroom-cards.json')
CONTEXT = CARDS.with_name('context.json')
TARGET = Path('assets/target-voice/reading-practice.json')
OLD_CARDS = Path('assets/classroom-cards.json')
OLD_TARGET = Path('assets/reading-practice.json')


def available(root, path, old):
    return root / (path if (root / path).is_file() else old)


def reference_record(row):
    """Keep the classroom reading and omit the old playback position."""
    reading = {key: value for key, value in row.items() if key != 'at'}
    for key in ('evidence', 'flow'):
        if key in reading:
            reading[key] = re.sub(r'(?<![0-9])(?:[0-9]{1,2}:)?[0-9]{1,2}:[0-9]{2}(?:[.,][0-9]{1,3})?(?![0-9])',
                                  '', reading[key]).strip()
    if not reading.get('evidence'):
        reading['evidence'] = '课堂内容整理'
    return reading


def practice_data(root=ROOT):
    target = json.loads(available(root, TARGET, OLD_TARGET).read_text(encoding='utf-8'))
    context = root / CONTEXT
    if context.is_file():
        target.update(json.loads(context.read_text(encoding='utf-8')))
    if 'reference_examples' in target:
        target['reference_examples'] = {
            kind: [reference_record(row) for row in rows]
            for kind, rows in target['reference_examples'].items()
        }
    return target


def migrate_practice(root):
    """Split legacy vocabulary context from recorded letter and formula guidance."""
    legacy = json.loads((root / OLD_TARGET).read_text(encoding='utf-8'))
    context = {key: legacy.pop(key) for key in ('pairs', 'senses')}
    for path, data in ((CONTEXT, context), (TARGET, legacy)):
        destination = root / path
        if not destination.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fingerprints():
    from handout_bundle import digest
    words = [ROOT / CARDS, ROOT / CONTEXT]
    symbols = ROOT / TARGET
    if not all(path.is_file() and path.stat().st_size for path in [*words, symbols]):
        raise ValueError('正式配音需要随技能安装的读音卡包和目标音色包。')
    return {'pronunciation_cards': {path.name: digest(path) for path in words},
            'target_voice': {symbols.name: digest(symbols)}}


def merge_practice(incoming, destination, *, prefer_incoming=True):
    """Retain classroom examples learned on either installation."""
    if not incoming.is_file():
        return
    remote = json.loads(incoming.read_text(encoding='utf-8'))
    local = json.loads(destination.read_text(encoding='utf-8')) if destination.is_file() else {}
    low, high = (local, remote) if prefer_incoming else (remote, local)
    result = {**low, **high}
    for key in ('letters', 'letter_listening', 'senses'):
        if key in result:
            result[key] = {**low.get(key, {}), **high.get(key, {})}
    def unique(rows):
        return list({json.dumps(row, ensure_ascii=False, sort_keys=True): row for row in rows}.values())
    if 'pairs' in result:
        result['pairs'] = unique(high.get('pairs', []) + low.get('pairs', []))
    if 'reference_examples' in result:
        first, second = high.get('reference_examples', {}), low.get('reference_examples', {})
        result['reference_examples'] = {}
        for kind in dict.fromkeys([*first, *second]):
            examples = {}
            for row in first.get(kind, []) + second.get(kind, []):
                example = reference_record(row)
                key = (example['source'], example['formula'], example['text'])
                examples.setdefault(key, example)
            result['reference_examples'][kind] = list(examples.values())
    if local != result:
        import os
        import tempfile
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=destination.parent, delete=False) as out:
            json.dump(result, out, ensure_ascii=False, indent=2)
        os.replace(out.name, destination)
