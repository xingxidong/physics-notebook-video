#!/usr/bin/env python3
"""Deterministic Chinese oralization for the LaTeX subset used by this skill.

This helper does not call a model.  It is deliberately conservative: course
authors can replace any generated reading in speech-plan.json.
"""
import argparse,json,re
from pathlib import Path

DEFAULT_LEXICON={
    '∫':'积分','∮':'闭合积分','·':'乘','×':'乘','→':'趋向','∞':'无穷大',
}
OPERATORS={'=':'等于','+':'加','-':'减','/':'除以','<':'小于','>':'大于','≤':'小于等于','≥':'大于等于','≈':'约等于'}
NUMBER={'0':'零','1':'一','2':'二','3':'三','4':'四','5':'五','6':'六','7':'七','8':'八','9':'九'}
TRIG = {'sin': '正弦', 'cos': '余弦', 'tan': '正切'}


def _small_integer(node):
    tokens = node[1:] if isinstance(node, list) and node[0] == 'row' else [node]
    if not 1 <= len(tokens) <= 2 or not all(isinstance(t, str) and t in NUMBER for t in tokens):
        return None
    digits = ''.join(tokens)
    if digits.startswith('0'):
        return None
    if len(digits) == 1:
        return NUMBER[digits]
    tens = '' if digits[0] == '1' else NUMBER[digits[0]]
    units = '' if digits[1] == '0' else NUMBER[digits[1]]
    return tens + '十' + units


def _trig_function(node):
    if isinstance(node, str) and node in TRIG:
        return node, None
    if isinstance(node, list) and node[0] == 'sup':
        name, power = node[1:]
        if isinstance(name, str) and name in TRIG and power in ('2', '3'):
            return name, power
    return None, None


def _spoken_trig(children, i, lexicon):
    name, power = _trig_function(children[i])
    if not name:
        return None
    j = i + 1
    while j < len(children) and isinstance(children[j], str) and children[j].isspace():
        j += 1
    if j == len(children):
        return None
    arg = children[j]
    end = j + 1
    if arg == '(':
        depth = 1
        while end < len(children) and depth:
            if children[end] == '(':
                depth += 1
            elif children[end] == ')':
                depth -= 1
            end += 1
        if depth or end <= j + 2:
            return None
        args = children[j + 1:end - 1]
    elif isinstance(arg, str) and (arg in OPERATORS or arg in (')', '·', '×')):
        return None
    else:
        args = arg[1:] if isinstance(arg, list) and arg[0] == 'row' else [arg]
        if isinstance(arg, str) and arg.isdigit() and end < len(children):
            symbol = children[end]
            if isinstance(symbol, str) and len(symbol) == 1 and symbol.isalpha():
                args = [arg, symbol]
                end += 1
    if len(args) > 2 and args[0] == '(' and args[-1] == ')' and not any(x in ('(', ')') for x in args[1:-1]):
        args = args[1:-1]
    if len(args) == 1:
        angle = _speak(args[0], lexicon)
    elif len(args) == 2 and isinstance(args[0], str) and args[0].isdigit():
        angle = _speak(args[0], lexicon) + '倍' + _speak(args[1], lexicon)
    else:
        angle = '括号' + _speak(['row', *args], lexicon) + '括号结束'
    value = angle + '的' + TRIG[name]
    if power:
        value += '值的' + ('平方' if power == '2' else '立方')
    return value, end


def _plain(node):
    if isinstance(node,str):return node
    if not isinstance(node,list) or not node:return ''
    kind=node[0]
    if kind=='row':return ''.join(_plain(x) for x in node[1:])
    if kind in ('sub','sup'):return _plain(node[1])+_plain(node[2])
    if kind in ('vec','hat','dot','sqrt'):return _plain(node[1])
    if kind=='frac':return _plain(node[1])+'/'+_plain(node[2])
    return ''.join(_plain(x) for x in node[1:])

def _complex(node):
    return isinstance(node,list) and node and (node[0] in ('frac','row') and len(_plain(node))>5)

def _speak_token(token,lexicon):
    from pronunciation import LETTER_IPA, GREEK
    if token == 'ℓ':
        return 'l'
    if token.upper() in LETTER_IPA or token.lower() in GREEK:
        return token
    if token in lexicon:return lexicon[token]
    if token in OPERATORS:return OPERATORS[token]
    if token.isdigit():
        if len(token)==1:return NUMBER[token]
        return ''.join(NUMBER.get(c,c) for c in token)
    return token

def _speak(node,lexicon):
    if isinstance(node,str):
        # Preserve familiar multi-letter function names.
        if node in ('sin','cos','tan','ln','exp'):return {'sin':'正弦','cos':'余弦','tan':'正切','ln':'自然对数','exp':'指数'}[node]
        return _speak_token(node,lexicon)
    kind=node[0]
    if kind=='row':
        children=node[1:];parts=[];i=0
        # Read f(x) as a function phrase instead of spelling out brackets.
        if len(children)>=4 and children[1]=='(' and ')' in children[2:] and not _trig_function(children[0])[0]:
            close=children.index(')',2);inside=['row',*children[2:close]]
            parts.append(f'{_speak(children[0],lexicon)}关于{_speak(inside,lexicon)}的函数');i=close+1
        previous_factor=bool(parts)
        while i<len(children):
            child=children[i]
            if child in ("'",'′') and previous_factor:
                parts.append('撇')
                i+=1
                continue
            if child == '!' and previous_factor:
                is_double = children[i + 1:i + 2] == ['!']
                parts.append('的双阶乘' if is_double else '的阶乘')
                i += 2 if is_double else 1
                continue
            trig=_spoken_trig(children,i,lexicon)
            if trig:
                value,i=trig
                if previous_factor:parts.append('乘')
                parts.append(value);previous_factor=True;continue
            if isinstance(child,str) and child in OPERATORS:
                word='负' if child=='-' and not previous_factor else OPERATORS[child]
                parts.append(f'，{word}，');previous_factor=False;i+=1;continue
            if child in ('(',')'):
                parts.append('括号' if child=='(' else '括号结束');previous_factor=(child==')');i+=1;continue
            value=_speak(child,lexicon)
            if value:
                if previous_factor:parts.append('乘')
                parts.append(value);previous_factor=True
            i+=1
        return ''.join(parts).strip('，')
    if kind=='frac':
        numerator,denominator=_small_integer(node[1]),_small_integer(node[2])
        if numerator and denominator:
            return denominator+'分之'+numerator
        top,bottom=_speak(node[1],lexicon),_speak(node[2],lexicon)
        if _complex(node[1]) or _complex(node[2]):return f'分子是{top}，分母是{bottom}'
        return f'{top}除以{bottom}'
    if kind=='sqrt':return f'根号{_speak(node[1],lexicon)}'
    if kind=='vec':return f'{_speak(node[1],lexicon)}矢量'
    if kind=='hat':return f'{_speak(node[1],lexicon)}方向的单位矢量'
    if kind=='dot':
        inner=node[1]
        if isinstance(inner,list) and inner[0]=='dot':
            return _speak(inner[1],lexicon)+'对时间的二阶导数'
        return _speak(inner,lexicon)+'对时间的变化率'
    if kind=='sub':
        base,index=node[1:]
        if base in ('v','V','a') and isinstance(index,list) and index[0]=='row' and len(index)==3:
            point,axis=index[1:]
            if isinstance(point,str) and re.fullmatch('[A-Z]',point) and axis in ('x','y','z'):
                return f'{base}下标{point} {axis}'
        return f'{_speak(base,lexicon)}下标{_speak(index,lexicon)}'
    if kind=='sup':
        base,power=_speak(node[1],lexicon),_plain(node[2])
        if power=='*':return f'{base}星'
        if power=='2':return f'{base}的平方'
        if power=='3':return f'{base}的立方'
        return f'{base}的{_speak(node[2],lexicon)}次方'
    return ''.join(_speak(x,lexicon) for x in node[1:])

def oralize_latex(latex,lexicon=None):
    """Return a speakable Chinese reading for supported LaTeX."""
    from mathparse import parse
    table={**DEFAULT_LEXICON,**(lexicon or {})}
    # A double time derivative and a prime are common in the spoken formula
    # track. Preserve the original LaTeX in the board and subtitle layers.
    spoken_latex=re.sub(r'\\ddot(?![A-Za-z])',lambda _:r'\dot\dot ',latex)
    spoken_latex=re.sub(r'\^(?:\{\\prime\}|\\prime(?![A-Za-z]))',"'",spoken_latex)
    text=_speak(parse(spoken_latex),table)
    text=text.replace('，，','，').strip('，')
    return text

def render_parts(parts,lexicon=None):
    """Render strings and {latex: ...} objects into one TTS string."""
    if not isinstance(parts,list):raise ValueError('tts_parts must be a list')
    out=[]
    for item in parts:
        if isinstance(item,str):out.append(item)
        elif isinstance(item,dict) and isinstance(item.get('latex'),str):out.append(oralize_latex(item['latex'],lexicon))
        else:raise ValueError('tts_parts items must be strings or {"latex":"..."}')
    return ''.join(out)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('latex');p.add_argument('--lexicon')
    a=p.parse_args();lexicon={}
    if a.lexicon:lexicon=json.loads(Path(a.lexicon).read_text())
    print(oralize_latex(a.latex,lexicon))

if __name__=='__main__':main()
