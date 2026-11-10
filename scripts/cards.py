"""Deterministic on-screen problem text and source-image cropping."""
import base64,copy,hashlib,io,math,re,shutil,subprocess,tempfile
from pathlib import Path

def _png(image):
    stream=io.BytesIO();image.save(stream,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode()

def problem_latex(text):
    """Escape prose and preserve explicitly delimited LaTeX math verbatim."""
    tokens=[];formulas=[];plain=[];i=0
    escapes={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    def flush():
        value=''.join(plain);plain.clear()
        if re.search(r'[Α-Ωα-ω₀-₉⁰-⁹]|\\(?:frac|sqrt|vec|dot|int|sum)\b',value):raise ValueError('Put every problem formula inside $...$, \\( ... \\) or \\[ ... \\]')
        tokens.append(''.join(escapes.get(c,c) for c in value).replace('\n',r'\par '))
    while i<len(text):
        if text.startswith(r'\$',i):plain.append('$');i+=2;continue
        opening=next((s for s in ('$$',r'\[',r'\(','$') if text.startswith(s,i)),None)
        if not opening:plain.append(text[i]);i+=1;continue
        flush();closing={'$$':'$$',r'\[':r'\]',r'\(':r'\)','$':'$'}[opening];end=text.find(closing,i+len(opening))
        if end<0:raise ValueError('Unclosed LaTeX formula in the problem statement')
        formula=text[i+len(opening):end].strip()
        if not formula:raise ValueError('Empty LaTeX formula in the problem statement')
        if re.search(r'\\(?:input|include|write|openout|openin|read|usepackage|documentclass|def|edef|gdef|let|csname|catcode|newcommand)\b',formula):raise ValueError('Problem math accepts formulas, not TeX file or macro commands')
        formulas.append(formula);tokens.append((r'\['+formula+r'\]') if opening in ('$$',r'\[') else '$'+formula+'$');i=end+len(closing)
    flush();return ''.join(tokens),formulas

def _compile_card(folder,tex,font):
    from PIL import Image
    try:import fitz
    except ImportError as e:raise ValueError('Install PyMuPDF from assets/requirements.txt for LaTeX problem cards') from e
    compiler=shutil.which('xelatex')
    if not compiler and Path('/Library/TeX/texbin/xelatex').exists():compiler='/Library/TeX/texbin/xelatex'
    if not compiler:raise ValueError('LaTeX problem cards need XeLaTeX, xeCJK and amsmath; run course.py doctor')
    key=hashlib.sha256(tex.encode()+Path(font).read_bytes()).hexdigest();target=folder/key;target.mkdir(parents=True,exist_ok=True)
    source=target/'problem.tex';png=target/'problem.png'
    if not png.exists():
        source.write_text(tex)
        try:run=subprocess.run([compiler,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error','problem.tex'],cwd=target,capture_output=True,text=True,timeout=60)
        except subprocess.TimeoutExpired as e:raise ValueError('Problem LaTeX compilation exceeded 60 seconds') from e
        if run.returncode:raise ValueError('Problem LaTeX compilation failed:\n'+'\n'.join(run.stdout.splitlines()[-14:]))
        if 'Missing character:' in run.stdout:raise ValueError('The selected font cannot display every problem character; choose a complete Chinese font or correct its LaTeX source')
        if 'Overfull \\hbox' in run.stdout:raise ValueError('A problem formula exceeds the card width; split the expression or enlarge its rect')
        height=re.search(r'PHYSICS-CONTENT-HEIGHT:([\d.]+)pt',run.stdout)
        limit=re.search(r'PHYSICS-CONTENT-LIMIT:([\d.]+)pt',run.stdout)
        if not height or not limit or float(height[1])>float(limit[1])+.1:raise ValueError('Problem text and formulas do not fit their card; enlarge rect or reflow the statement')
        with fitz.open(target/'problem.pdf') as doc:
            if len(doc)!=1:raise ValueError('Problem statement spills onto another page; enlarge rect or reflow it')
            pix=doc[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False);image=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        image.save(png)
    with Image.open(png) as picture:return picture.copy()

def problem_card(value,font,cache=None):
    from PIL import ImageDraw
    if not isinstance(value,(str,dict)):raise ValueError('page.problem must be recognized text or an object')
    spec={'text':value} if isinstance(value,str) else copy.deepcopy(value)
    text=spec.get('text','')
    if not isinstance(text,str) or not text.strip():raise ValueError('page.problem needs recognized text')
    rect=spec.get('rect',[145,100,1035,125])
    if not isinstance(rect,list) or len(rect)!=4 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in rect):raise ValueError('problem.rect must be [x,y,w,h]')
    x,y,w,h=rect
    if x<120 or y<95 or w<=0 or h<=0 or x+w>1200 or y+h>655:raise ValueError('Problem card leaves the writing area')
    size=float(spec.get('font_size',21));padding=10;gap=6
    if not 14<=size<=32:raise ValueError('Problem font_size must be 14..32')
    body,formulas=problem_latex(text);font=Path(font).resolve()
    if any(c in str(font) for c in '{}%#'):raise ValueError('The Chinese font path contains unsupported TeX path characters')
    tex=r'''% !TEX program = xelatex
\documentclass{article}
\usepackage{geometry,fontspec,xeCJK,amsmath,amssymb,xcolor}
\geometry{paperwidth=@@WIDTH@@pt,paperheight=@@HEIGHT@@pt,margin=@@PADDING@@pt,noheadfoot}
\setmainfont{lmroman10-regular.otf}
\setCJKmainfont[Path={@@FONTDIR@@/},FontIndex=0]{@@FONTFILE@@}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\pagecolor[HTML]{FFFEF9}\color[HTML]{29333C}
\newsavebox{\problemBox}
\begin{document}
\fontsize{@@SIZE@@pt}{@@LEADING@@pt}\selectfont
\begin{lrbox}{\problemBox}\begin{minipage}{\textwidth}
@@BODY@@
\end{minipage}\end{lrbox}
\typeout{PHYSICS-CONTENT-HEIGHT:\the\dimexpr\ht\problemBox+\dp\problemBox\relax}
\typeout{PHYSICS-CONTENT-LIMIT:@@LIMIT@@pt}
\noindent\usebox{\problemBox}
\end{document}
'''
    for key,value in {'WIDTH':w,'HEIGHT':h,'PADDING':padding,'FONTDIR':font.parent.as_posix(),'FONTFILE':font.name,'SIZE':size,'LEADING':size+gap,'LIMIT':h-2*padding,'BODY':body}.items():tex=tex.replace('@@'+key+'@@',str(value))
    if cache is None:
        with tempfile.TemporaryDirectory() as d:image=_compile_card(Path(d),tex,font)
    else:image=_compile_card(Path(cache),tex,font)
    draw=ImageDraw.Draw(image);draw.rounded_rectangle((0,0,image.width-1,image.height-1),radius=12,outline='#c8d2cd',width=2)
    return {'text':text,'latex_formulas':formulas,'latex_source':tex,'renderer':'xelatex','font_size':size,'x':x,'y':y,'w':w,'h':h,'data':_png(image)}

def source_image(project,value):
    from PIL import Image
    spec=copy.deepcopy(value);source=(Path(project)/spec.pop('file')).resolve();raw=source.read_bytes()
    with Image.open(io.BytesIO(raw)) as picture:
        image=picture.convert('RGB');source_size=list(image.size);crop=spec.get('crop')
        if crop is not None:
            if not isinstance(crop,list) or len(crop)!=4 or any(not isinstance(x,int) for x in crop):raise ValueError('image.crop must use four integer source-pixel coordinates')
            a,b,c,d=crop
            if not 0<=a<c<=image.width or not 0<=b<d<=image.height:raise ValueError('image.crop leaves the original image')
            image=image.crop(tuple(crop))
        spec.update(data=_png(image),source_sha256=hashlib.sha256(raw).hexdigest(),source_size=source_size)
    return spec
