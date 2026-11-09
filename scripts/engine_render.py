"""Shared page cache and audio assembly for native Motion Canvas / Manim renderers."""
import hashlib,importlib.metadata,json,os,shutil,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ENGINES=('notebook','motion-canvas','manim')

def local_config():
    p=ROOT/'runtime-local.json'
    return json.loads(p.read_text()) if p.exists() else {}

def manim_python():
    return os.environ.get('PHYSICS_MANIM_PYTHON') or local_config().get('manim_python') or sys.executable

def runtime_path(value=None):
    raw=value or os.environ.get('PHYSICS_ANIMATION_RUNTIME') or local_config().get('motion_canvas_runtime')
    return Path(raw).expanduser().resolve() if raw else None

def versions(engine,runtime=None):
    if engine=='manim':
        python=manim_python()
        if os.path.abspath(python)!=os.path.abspath(sys.executable):
            r=subprocess.run([python,'-c','import manim;print(manim.__version__)'],capture_output=True,text=True)
            if r.returncode:raise RuntimeError('Configured Manim Python is unavailable; rerun setup-renderers using the desired environment')
            return {'manim':r.stdout.strip()}
        try:return {'manim':importlib.metadata.version('manim')}
        except importlib.metadata.PackageNotFoundError:raise RuntimeError('Install Manim into this Python environment: python -m pip install manim==0.22.1') from None
    root=runtime_path(runtime)
    if root is None:raise ValueError('Motion Canvas needs --runtime PATH or PHYSICS_ANIMATION_RUNTIME; see references/renderers.md')
    out={}
    for name in ('@motion-canvas/core','@motion-canvas/2d','@motion-canvas/vite-plugin','vite','playwright-core'):
        p=root/'node_modules'/name/'package.json'
        if not p.exists():raise RuntimeError(f'Missing {name}; run setup-renderers --runtime {root}')
        out[name]=json.loads(p.read_text())['version']
    return out

def native_scene(page,project,engine):
    spec=(page.get('native_scenes') or {}).get(engine)
    if not spec:return None
    source=(project/spec['source']).resolve()
    if not source.is_relative_to(project) or not source.is_file():raise ValueError('Native scene source must be a file inside the course project')
    dependencies={}
    for name in spec.get('dependencies',[]):
        p=(project/name).resolve()
        if not p.is_relative_to(project) or not p.is_file():raise ValueError('Native scene dependencies must be files inside the course project')
        dependencies[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {**spec,'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'dependency_sha256':dependencies}

def render(project,data,font,width,engine,runtime=None):
    from course import digest,paper,write_json
    if data['draft']:raise ValueError('Final video requires measured audio')
    project=Path(project).resolve();runtime=runtime_path(runtime);info=versions(engine,runtime)
    root=project/'cache'/'video'/engine;root.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'scripts/engine_render.py',ROOT/'scripts/models.py',ROOT/'scripts/course.py',ROOT/'scripts/layout.py',ROOT/'scripts/components.py']
    sources += list((ROOT/'scripts/motion_canvas').glob('*')) if engine=='motion-canvas' else [ROOT/'scripts/manim_renderer.py']
    fingerprint=digest(b''.join(p.read_bytes() for p in sorted(sources) if p.is_file())+font.read_bytes())
    keys=[];new=reused=0
    for page in data['pages']:
        local={k:v for k,v in page.items() if k not in ('start','end')};native=native_scene(page,project,engine)
        key=digest([local,width,data['fps'],info,fingerprint,native]);target=root/(key+'.mp4');keys.append(key)
        if target.exists():reused+=1;continue
        folder=root/key;folder.mkdir(exist_ok=True)
        paper(page,font).save(folder/'paper.png')
        payload={'page':page,'fps':data['fps'],'width':width,'height':round(width*720/1280),'background':str((folder/'paper.png').resolve()),'engine_versions':info,'native_scene':native}
        if page.get('demonstration'):
            import models
            # Both engines use exactly the same analytic model samples, never inferred image motion.
            payload['dynamic_frames']=[models.strokes(page['demonstration'],i/data['fps']) for i in range(page['frames'])]
        path=folder/'payload.json';write_json(path,payload);part=root/(key+'.part.mp4')
        if engine=='manim':cmd=[manim_python(),str(ROOT/'scripts/manim_renderer.py'),'--input',str(path),'--output',str(part)]
        else:cmd=['node',str(ROOT/'scripts/motion_canvas/render.mjs'),'--input',str(path),'--output',str(part),'--runtime',str(runtime)]
        env=dict(os.environ)
        if engine=='manim' and Path('/Library/TeX/texbin').exists():env['PATH']='/Library/TeX/texbin:'+env.get('PATH','')
        tex_bin=os.environ.get('PHYSICS_TEX_BIN') or local_config().get('tex_bin')
        if engine=='manim' and tex_bin:
            env['PATH']=str(tex_bin)+os.pathsep+env.get('PATH','')
            if shutil.which('kpsewhich',path=env['PATH']):
                tex_root=subprocess.check_output(['kpsewhich','-var-value=TEXMFROOT'],env=env,text=True).strip()
                env['TEXMFROOT']=tex_root;env['TEXMFCNF']=tex_root+os.pathsep+str(Path(tex_root)/'texmf-dist/web2c')
        result=subprocess.run(cmd,capture_output=True,text=True,env=env)
        (folder/'render.log').write_text(result.stdout+'\n'+result.stderr)
        if result.returncode:raise RuntimeError(f'{engine}: {page["id"]} failed; see {folder/"render.log"}\n'+(result.stderr or result.stdout)[-1800:])
        # A cached segment is promoted only after a complete export with the expected frame count.
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=nb_frames,width,height','-of','json',str(part)],text=True))['streams'][0]
        if int(probe.get('nb_frames',0))!=page['frames']:raise RuntimeError(f'{engine}: expected {page["frames"]} frames, got {probe.get("nb_frames")}')
        part.replace(target);new+=1;print(f'{engine}: rendered {page["id"]}',flush=True)
    listing=root/'segments.txt';listing.write_text('\n'.join(f"file '{key}.mp4'" for key in keys))
    final=project/f'video-{engine}.mp4'
    subprocess.run(['ffmpeg','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-i',str(project/'narration.wav'),'-c:v','copy','-c:a','aac','-b:a','128k','-shortest','-movflags','+faststart',str(final)],check=True)
    shutil.copy2(final,project/'video.mp4')
    return {'video_new':new,'video_reused':reused,'renderer':engine,'renderer_versions':info,'video_file':str(final)}

def setup(runtime):
    root=runtime_path(runtime)
    if root is None:raise ValueError('Choose a workspace directory with --runtime PATH')
    root.mkdir(parents=True,exist_ok=True)
    for name in ('package.json','package-lock.json'):
        p=ROOT/'scripts/motion_canvas'/name
        if p.exists():shutil.copy2(p,root/name)
    subprocess.run(['npm','ci' if (root/'package-lock.json').exists() else 'install','--no-audit','--no-fund','--registry=https://registry.npmjs.org'],cwd=root,check=True)
    config=local_config();config.update(motion_canvas_runtime=str(root),manim_python=os.path.abspath(sys.executable))
    if (root.parent/'tex-tools/dvisvgm').exists():config['tex_bin']=str(root.parent/'tex-tools')
    (ROOT/'runtime-local.json').write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps({'motion_canvas_runtime':str(root),'versions':versions('motion-canvas',root)},ensure_ascii=False))

def doctor(runtime=None):
    result={'node':shutil.which('node'),'chrome':os.environ.get('CHROME_PATH') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app').exists() else shutil.which('chromium'))}
    for engine in ('manim','motion-canvas'):
        try:result[engine]=versions(engine,runtime)
        except (RuntimeError,ValueError) as e:result[engine]={'available':False,'reason':str(e)}
    return result
