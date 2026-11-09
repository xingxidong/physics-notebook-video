#!/usr/bin/env python3
"""Install, package, and verify physics-notebook-video across Agent Skills hosts."""
import argparse,json,os,shutil,sys,zipfile
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[1]
NAME='physics-notebook-video'
SKIP_DIRS={'.git','__pycache__','node_modules','cache','.runtime'}
SKIP_FILES={'.env','runtime-local.json','.DS_Store'}
LIMITS={
    'universal':(500,50*1024*1024,25*1024*1024),
    'claude':(500,50*1024*1024,25*1024*1024),
    'doubao':(1024,16*1024*1024,2*1024*1024),
}

def source_files():
    for path in sorted(ROOT.rglob('*')):
        rel=path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):continue
        if path.is_symlink():raise ValueError(f'Symlinks are not packaged: {rel}')
        if path.is_file() and path.name not in SKIP_FILES and path.suffix!='.pyc':yield path,rel

def version():return (ROOT/'VERSION').read_text().strip()

def inspect(target='universal'):
    files=list(source_files());count=len(files);total=sum(p.stat().st_size for p,_ in files);largest=max((p.stat().st_size for p,_ in files),default=0)
    errors=[]
    if not (ROOT/'SKILL.md').exists():errors.append('Missing SKILL.md')
    if not (ROOT/'skill.json').exists():errors.append('Missing skill.json')
    if not (ROOT/'assets/icon.png').exists():errors.append('Missing assets/icon.png')
    if target in LIMITS:
        max_count,max_total,max_file=LIMITS[target]
        if count>max_count:errors.append(f'{count} files exceeds {target} limit {max_count}')
        if total>max_total:errors.append(f'{total} bytes exceeds {target} total limit {max_total}')
        if largest>max_file:errors.append(f'Largest file {largest} bytes exceeds {target} per-file limit {max_file}')
    return {'ok':not errors,'target':target,'name':NAME,'version':version(),'files':count,'bytes':total,'largest_file_bytes':largest,'errors':errors}

def destination(target,scope,project,explicit):
    if explicit:return Path(explicit).expanduser().resolve()
    if scope=='project':
        if not project:raise ValueError('--project is required for project scope')
        base=Path(project).expanduser().resolve()
        roots={'codex':base/'.codex/skills','claude':base/'.claude/skills','agents':base/'.agents/skills'}
    else:
        codex_root=Path(os.environ.get('CODEX_HOME',Path.home()/'.codex')).expanduser()
        roots={'codex':codex_root/'skills','claude':Path.home()/'.claude/skills','agents':Path.home()/'.agents/skills'}
    return (roots[target]/NAME).resolve()

def copy_install(dest,update):
    if dest==ROOT.resolve():raise ValueError('Source and destination are the same directory')
    if dest.exists() and not update:raise ValueError(f'{dest} already exists; use --update to merge an update')
    preserved=[name for name in ('.env','runtime-local.json') if (dest/name).exists()]
    dest.mkdir(parents=True,exist_ok=True)
    copied=0
    for src,rel in source_files():
        out=dest/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out);copied+=1
    return copied,preserved

def install(args):
    dest=destination(args.target,args.scope,args.project,args.dest);copied,preserved=copy_install(dest,args.update)
    report={'ok':True,'target':args.target,'scope':args.scope,'destination':str(dest),'files_copied':copied,'version':version(),'preserved':preserved}
    print(json.dumps(report,ensure_ascii=False,indent=2))

def package(args):
    report=inspect(args.target)
    if not report['ok']:raise ValueError('; '.join(report['errors']))
    output=Path(args.output).expanduser().resolve();output.parent.mkdir(parents=True,exist_ok=True)
    if output==ROOT.resolve() or ROOT.resolve() in output.parents:raise ValueError('Write package output outside the skill source directory')
    files=list(source_files())
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for src,rel in files:z.write(src,PurePosixPath(NAME)/PurePosixPath(rel.as_posix()))
    checked=verify_zip(output,args.target,quiet=True)
    print(json.dumps({**checked,'output':str(output)},ensure_ascii=False,indent=2))

def verify_zip(path,target,quiet=False):
    path=Path(path).expanduser().resolve();errors=[]
    if not path.exists():raise ValueError(f'Missing ZIP: {path}')
    with zipfile.ZipFile(path) as z:
        members=[x for x in z.infolist() if not x.is_dir()]
        names=[PurePosixPath(x.filename) for x in members]
        if PurePosixPath(NAME)/'SKILL.md' not in names:errors.append(f'ZIP must contain {NAME}/SKILL.md')
        for name in names:
            if name.is_absolute() or '..' in name.parts:errors.append(f'Unsafe ZIP path: {name}')
            if any(part in SKIP_DIRS for part in name.parts) or name.name in SKIP_FILES or name.suffix=='.pyc':errors.append(f'Excluded file is present: {name}')
        if target in LIMITS:
            max_count,max_total,max_file=LIMITS[target];total=sum(x.file_size for x in members);largest=max((x.file_size for x in members),default=0)
            if len(members)>max_count:errors.append(f'{len(members)} files exceeds {target} limit {max_count}')
            if total>max_total:errors.append(f'{total} bytes exceeds {target} total limit {max_total}')
            if largest>max_file:errors.append(f'Largest file {largest} bytes exceeds {target} per-file limit {max_file}')
        else:total=sum(x.file_size for x in members);largest=max((x.file_size for x in members),default=0)
    report={'ok':not errors,'target':target,'zip':str(path),'files':len(members),'uncompressed_bytes':total,'largest_file_bytes':largest,'errors':errors}
    if not quiet:print(json.dumps(report,ensure_ascii=False,indent=2))
    if errors:raise ValueError('; '.join(errors))
    return report

def info():
    print(json.dumps({'format':'Agent Skills','skill':NAME,'version':version(),'hosts':{
        'codex':'native SKILL.md; user or project directory',
        'claude':'native SKILL.md in Claude Code; ZIP upload in claude.ai',
        'doubao':'Skill ZIP upload and review in Doubao Work; execution tools may require a connector/MCP',
        'deepseek':'use as the model inside an Agent Skills host; no native official-chat Skill directory',
        'agents':'explicit destination for other agentskills.io-compatible hosts',
    }},ensure_ascii=False,indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('info')
    p=sub.add_parser('check');p.add_argument('--target',choices=LIMITS,default='universal')
    p=sub.add_parser('install');p.add_argument('--target',choices=['codex','claude','agents'],required=True);p.add_argument('--scope',choices=['user','project'],default='user');p.add_argument('--project');p.add_argument('--dest');p.add_argument('--update',action='store_true')
    p=sub.add_parser('package');p.add_argument('--target',choices=LIMITS,default='universal');p.add_argument('--output',required=True)
    p=sub.add_parser('verify');p.add_argument('zip');p.add_argument('--target',choices=LIMITS,default='universal')
    args=parser.parse_args()
    if args.command=='info':info()
    elif args.command=='check':
        report=inspect(args.target);print(json.dumps(report,ensure_ascii=False,indent=2));sys.exit(0 if report['ok'] else 1)
    elif args.command=='install':install(args)
    elif args.command=='package':package(args)
    else:verify_zip(args.zip,args.target)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,zipfile.BadZipFile) as e:print(f'ERROR: {e}',file=sys.stderr);sys.exit(1)
