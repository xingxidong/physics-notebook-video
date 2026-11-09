#!/usr/bin/env python3
"""Deterministic Chinese oralization for the LaTeX subset used by this skill.

This helper does not call a model.  It is deliberately conservative: course
authors can replace any generated reading in speech-plan.json.
"""
import argparse,json,re
from pathlib import Path

DEFAULT_LEXICON={
    'E':'电场强度','F':'力','Q':'电荷量Q','q':'电荷量q','R':'半径R',
    'r':'距离r','S':'面积S','t':'时间t','v':'速度v','a':'加速度a',
    'g':'重力加速度g','m':'质量m','h':'高度h','x':'x','y':'y','d':'d',
    'ε':'真空介电常数','θ':'角度西塔','φ':'角度斐','π':'圆周率',
    'ρ':'电荷密度柔','λ':'线电荷密度拉姆达','σ':'面电荷密度西格玛',
    '∫':'积分','∮':'闭合积分','·':'乘','×':'乘','→':'趋向','∞':'无穷大',
}
OPERATORS={'=':'等于','+':'加','-':'减','/':'除以','<':'小于','>':'大于','≤':'小于等于','≥':'大于等于','≈':'约等于'}
NUMBER={'0':'零','1':'一','2':'二','3':'三','4':'四','5':'五','6':'六','7':'七','8':'八','9':'九'}

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
        if len(children)>=4 and children[1]=='(' and ')' in children[2:]:
            close=children.index(')',2);inside=['row',*children[2:close]]
            parts.append(f'{_speak(children[0],lexicon)}关于{_speak(inside,lexicon)}的函数');i=close+1
        previous_factor=bool(parts)
        while i<len(children):
            child=children[i]
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
        top,bottom=_speak(node[1],lexicon),_speak(node[2],lexicon)
        if _complex(node[1]) or _complex(node[2]):return f'分子是{top}，分母是{bottom}'
        return f'{top}除以{bottom}'
    if kind=='sqrt':return f'根号{_speak(node[1],lexicon)}'
    if kind=='vec':return f'{_speak(node[1],lexicon)}矢量'
    if kind=='hat':return f'{_speak(node[1],lexicon)}方向的单位矢量'
    if kind=='dot':return f'{_speak(node[1],lexicon)}对时间的变化率'
    if kind=='sub':return f'{_speak(node[1],lexicon)}下标{_speak(node[2],lexicon)}'
    if kind=='sup':
        base,power=_speak(node[1],lexicon),_plain(node[2])
        if power=='2':return f'{base}的平方'
        if power=='3':return f'{base}的立方'
        return f'{base}的{_speak(node[2],lexicon)}次方'
    return ''.join(_speak(x,lexicon) for x in node[1:])

def oralize_latex(latex,lexicon=None):
    """Return a speakable Chinese reading for supported LaTeX."""
    from mathparse import parse
    table={**DEFAULT_LEXICON,**(lexicon or {})}
    text=_speak(parse(latex),table)
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
