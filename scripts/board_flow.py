"""Measured handwriting layout and continuity on a fixed notebook canvas."""
import copy
import re

import ink
from mathparse import parse


def bounds(strokes):
    """Include the thickness of the pen as well as the centreline."""
    if not strokes:
        return None
    outlines = [(x, y, stroke['width']/2)
                for stroke in strokes for x, y in stroke['points']]
    return [min(x-w for x, y, w in outlines), min(y-w for x, y, w in outlines),
            max(x+w for x, y, w in outlines), max(y+w for x, y, w in outlines)]


def text_lines(text, size, width):
    tokens = []
    for token in re.findall(r'[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*|\s+|[^\s]', text):
        if tokens and token in '，。；：！？、）】':
            tokens[-1] = tokens[-1].rstrip()+token
        else:
            tokens.append(token)
    lines = []
    line = ''
    for token in tokens:
        candidate = line + token
        if line.strip() and ink.measure(candidate.strip(), size) > width:
            lines.append(line.strip())
            line = token.lstrip()
        else:
            line = candidate
    if line.strip():
        lines.append(line.strip())
    return lines


def equation_parts(tree):
    parts = tree[1:] if isinstance(tree, list) and tree[0] == 'row' else [tree]
    groups = [[]]
    level = 0
    for token in parts:
        if isinstance(token, str) and token in ('=', '≈', '≤', '≥') and not level and groups[-1]:
            groups.append([])
        groups[-1].append(token)
        if isinstance(token, str):
            level += int(token in ('(', '[')) - int(token in (')', ']'))
    return groups


def equality_offset(actions, default_size=32):
    widths = []
    for action in actions:
        groups = equation_parts(parse(action['latex']))
        size = action.get('size', default_size)
        if len(groups) > 1 and isinstance(size, (int, float)):
            widths.append(ink.measure(['row', *groups[0]], size))
        else:
            widths.append(None)
    maximum = max((width for width in widths if width is not None), default=0)
    return [maximum-width if width is not None else 0 for width in widths]


def math_lines(tree, size, width):
    if ink.measure(tree, size) <= width:
        return [tree]
    grouped = equation_parts(tree)
    if len(grouped) == 1:
        raise ValueError('公式组宽于所在区域，请加宽推导区，或把长式分成有意义的独立等式。')
    lines = []
    line = []
    for group in grouped:
        if line and ink.measure(['row', *line, *group], size) > width:
            lines.append(['row', *line])
            line = []
        line.extend(group)
        if ink.measure(['row', *line], size) > width:
            raise ValueError('等式的一侧宽于区域，请单独安排整行板书。')
    return lines + [['row', *line]]


def draw(group, action, spec, occupied, size, color):
    name = action['zone']
    x, y, w, h = spec['zones'][name]
    padding = float(spec['padding'])
    left = x + padding + action.get('_align_dx', 0)
    top = max(y + padding, occupied.get(name, y))
    width = x + w - padding - left
    if action['type'] == 'text':
        lines = text_lines(action['text'], size, width - 3)
        render = ink.text
    else:
        tree = parse(action['latex']) if 'latex' in action else action['value']
        lines = math_lines(tree, size, width - 3)
        render = ink.formula
    for line in lines:
        offset = len(ink.groups[group])
        render(group, line, left, top, size, color)
        strokes = ink.groups[group][offset:]
        box = bounds(strokes)
        if not box:
            continue
        shift = top - box[1]
        for stroke in strokes:
            stroke['points'] = [[a, b+shift] for a, b in stroke['points']]
        if box[2] > x+w-padding+1 or top+box[3]-box[1] > y+h-padding:
            raise ValueError(f'{name} 区容不下「{action.get("text", action.get("latex","公式"))}」。保留字号并调整区域或续页。')
        top += box[3]-box[1] + float(spec.get('item_gap', 9))
    occupied[name] = top


def underline(group, color):
    points = ink.groups[group]
    box = bounds(points)
    if box:
        x1, _, x2, bottom = box
        ink.line(group, [x1+1,bottom+4], [x2-1,bottom+4], color, 2)


def reserve(occupied, block, spec):
    zone = block.get('zone')
    if zone and zone in spec['zones']:
        box = bounds(block['strokes'])
        if box:
            occupied[zone] = max(occupied.get(zone, 0), box[3]+float(spec.get('item_gap',9)))


def references(block):
    return {key for key in (block.get('id'), block.get('board_group'), block.get('component_id')) if key}


def carry(previous, keys, page_id):
    if not keys:
        return []
    available = previous.get('carry_blocks', []) + [
        block for cue in previous['cues'] for block in cue['blocks']] if previous else []
    missing = set(keys) - set().union(*(references(block) for block in available))
    if missing:
        raise ValueError(f'{page_id}: 前一页找不到续写笔迹 {", ".join(sorted(missing))}')
    return [copy.deepcopy(block) for block in available if references(block).intersection(keys)]


def initial_strokes(page, fps):
    carried = [dict(stroke, start=-1/fps, end=0, cue='', action=block['action'],
                 board_id=block.get('id'), board_group=block.get('board_group'),
                 component_id=block.get('component_id'), carried=True)
            for block in page.get('carry_blocks', []) for stroke in block['strokes']]
    prewritten = [
        dict(stroke, start=-1/fps, end=0, cue=cue['id'], action=block['action'],
             board_id=block.get('id'), board_group=block.get('board_group'),
             component_id=block.get('component_id'), prewritten=True)
        for cue in page['cues'] for block in cue['blocks'] if block.get('prewritten')
        for stroke in block['strokes']
    ]
    return carried + prewritten
