"""Collect reviewed classroom TeX inputs and prove the delivered archive builds in isolation."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from lesson_review import local_file

SOURCE_EXT = {'.tex', '.tikz', '.sty', '.cls', '.pgf'}
REQUEST = re.compile(r'\\(input|include|includegraphics|usepackage|RequirePackage|documentclass)(?:\[[^\]]*\])?\s*\{([^{}]+)\}')


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(part)
    return sha.hexdigest()


def main_source(project, lesson):
    if lesson.get('handout_source'):
        return local_file(project, lesson['handout_source'])
    handout = local_file(project, lesson.get('handout', '讲义.md'), required=False)
    if handout.suffix.lower() == '.tex':
        return local_file(project, str(handout.relative_to(project)))
    if handout.suffix.lower() in ('.pdf','.md','.markdown'):
        candidates = [handout.with_suffix('.tex'), project/'讲义.tex']
        if handout.is_file() and handout.suffix.lower() in ('.md','.markdown'):
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',handout.read_text()):
                name=target.strip().strip('<>').split('#',1)[0]
                if name.endswith('.tex') and not re.match(r'[A-Za-z][A-Za-z+.-]*:',name):
                    candidates.append(local_file(project,os.path.relpath(handout.parent/name,project),required=False))
        candidates.extend(local_file(project, p) for p in lesson.get('review_assets', []) if p.endswith('.tex'))
        for p in candidates:
            if p.is_file() and r'\documentclass' in tex_text(p):
                return p
        if handout.suffix.lower()=='.pdf':
            raise ValueError('学生讲义 PDF 需要可编辑的主文件，请设置 handout_source。')
    return None


def tex_text(path):
    return re.sub(r'(?<!\\)%[^\n]*', '', path.read_text(encoding='utf-8'))


def source_files(project, lesson, *, recorded=True):
    """Inputs for source fingerprint and clean build. Dynamic inputs can be declared explicitly."""
    main = main_source(project, lesson)
    if main is None:
        return set()
    assets = [local_file(project, name) for name in lesson.get('handout_assets', [])]
    receipt = project/'handout-delivery/receipt.json'
    if recorded and receipt.is_file():
        old=json.loads(receipt.read_text())
        if old.get('main')==str(main.relative_to(project)):
            for name in old.get('inputs',{}):
                item=local_file(project,name,required=False)
                if item.is_file():
                    assets.append(item)
    pending, files = [main, *assets], set()
    while pending:
        path = pending.pop()
        if path in files:
            continue
        files.add(path)
        if path.suffix.lower() not in SOURCE_EXT:
            continue
        for command, value in REQUEST.findall(tex_text(path)):
            for name in value.split(','):
                name = name.strip()
                if '\\' in name or '#' in name:
                    continue
                extensions = {'includegraphics': ('', '.pdf','.png','.jpg','.jpeg'),
                              'usepackage': ('.sty',), 'RequirePackage': ('.sty',),
                              'documentclass': ('.cls',)}.get(command, ('', '.tex'))
                for base in (main.parent, path.parent):
                    found = next((base/(name+ext) for ext in extensions if (base/(name+ext)).is_file()), None)
                    if found is not None:
                        pending.append(local_file(project, os.path.relpath(found, project)))
                        break
    return files


def compile_clean(root, main, work, *, discover=False):
    exe = shutil.which('xelatex') or '/Library/TeX/texbin/xelatex'
    env = {k:v for k,v in os.environ.items() if not k.startswith(('TEXINPUTS','TEXMF','OSFONTDIR','BIBINPUTS'))}
    env.update(TEXMFHOME=str(work/'unused-texmf'))
    for _ in range(1 if discover else 2):
        result = subprocess.run([exe, '-no-shell-escape', '-halt-on-error', '-interaction=nonstopmode',
                                 '-recorder', '-output-directory='+str(work), main.name],
                                cwd=main.parent, env=env, capture_output=True, timeout=150)
        if result.returncode:
            lines = result.stdout.decode(errors='replace').splitlines()
            raise ValueError('讲义在空目录编译失败。'+'\n'.join(lines[-18:]))
    pdf = work/(main.stem+'.pdf')
    if not pdf.is_file() or pdf.stat().st_size==0:
        raise ValueError('讲义未生成 PDF。')
    log = (work/(main.stem+'.log')).read_text(errors='replace')
    if not discover and re.search(r'(There were undefined references|Citation .+ undefined|multiply-defined labels)', log):
        raise ValueError('讲义交叉引用或标签有误，请检查编译日志。')
    # Absolute inputs can escape an empty folder. Check the engine's actual inputs.
    system = [Path(p).resolve() for p in ('/usr/local/texlive','/usr/share/texlive','/usr/share/texmf',
              '/etc/texmf','/var/lib/texmf','/usr/share/fonts','/usr/local/share/fonts','/System/Library/Fonts',
              '/Library/Fonts','/opt/homebrew/Cellar','/nix/store','/dev/null','/var/cache/fontconfig')]
    kpse = shutil.which('kpsewhich') or str(Path(exe).with_name('kpsewhich'))
    for var in ('TEXMFDIST','TEXMFSYSVAR','TEXMFSYSCONFIG'):
        val = subprocess.check_output([kpse, '-var-value='+var], env=env, text=True).strip()
        if val and Path(val).is_absolute():
            system.append(Path(val).resolve())
    local_inputs=set()
    for line in (work/(main.stem+'.fls')).read_text(errors='replace').splitlines():
        if line.startswith('INPUT '):
            path = (main.parent/line[6:]).resolve()
            if path.is_file() and path.is_relative_to(root) and not path.is_relative_to(work):
                local_inputs.add(path)
            if path.is_file() and not any(path.is_relative_to(p) for p in [root,work,*system]):
                raise ValueError(f'讲义使用了源码包以外的本地文件：{path.name}')
    return pdf,local_inputs


def build(project, lesson):
    project = project.resolve()
    main = main_source(project, lesson)
    if main is None:
        raise ValueError('请在 lesson.json 的 handout_source 指定讲义 LaTeX 主文件。')
    with tempfile.TemporaryDirectory(dir=project) as tmp:
        tmp = Path(tmp)
        discovery=tmp/'discovery'
        discovery.mkdir()
        _,actual=compile_clean(project,main,discovery,discover=True)
        files=source_files(project,lesson,recorded=False) | actual
        inputs={str(p.relative_to(project)):digest(p) for p in sorted(files)}
        archive = tmp/'学生讲义.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name in inputs:
                z.write(project/name,name)
        root, work = tmp/'source', tmp/'build'
        root.mkdir()
        work.mkdir()
        with zipfile.ZipFile(archive) as z:
            z.extractall(root)
        pdf,_ = compile_clean(root, root/main.relative_to(project), work)
        # The PDF and receipt belong to this verified build. Do not overwrite authored input.
        out = project/'handout-delivery'
        out.mkdir(exist_ok=True)
        receipt = {'main':str(main.relative_to(project)), 'inputs':inputs, 'pdf':'handout-delivery/学生讲义.pdf',
                   'archive':'handout-delivery/学生讲义.zip', 'pdf_sha256':digest(pdf),
                   'archive_sha256':digest(archive), 'verification':'clean-xelatex-two-passes'}
        staged = tmp/'receipt.json'
        staged.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
        for src, dest in [(pdf,project/receipt['pdf']), (archive,project/receipt['archive']), (staged,out/'receipt.json')]:
            os.replace(src,dest)
    return receipt


def verified(project, lesson):
    path = project/'handout-delivery/receipt.json'
    if not path.is_file():
        return False
    record = json.loads(path.read_text())
    inputs = {str(p.relative_to(project)):digest(p) for p in source_files(project,lesson)}
    return (record.get('main')==str(main_source(project,lesson).relative_to(project)) and
            record.get('inputs')==inputs and all((project/record[key]).is_file() and
            digest(project/record[key])==record[key+'_sha256'] for key in ('pdf','archive')))
