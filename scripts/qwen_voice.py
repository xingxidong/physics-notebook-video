"""Local Qwen/MLX adapter. Preserve the teacher reference and actual synthesis input."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import wave


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def config(project,speech):
    from engine_render import local_config
    from qwen_setup import managed_config, public_reference
    chosen={**managed_config(),**local_config().get('qwen',{}),**speech.get('qwen',{})}
    if not chosen.get('reference_audio') and not chosen.get('reference_text'):
        chosen.update(public_reference())
    for name in ('python','model','reference_audio'):
        value=chosen.get(name)
        if not isinstance(value,str) or not value:
            raise ValueError('本地 Qwen 配置缺少 '+name+'。可用 platform_install.py local-voice 安装，或设置 runtime-local.json 的 qwen。')
        path=Path(value).expanduser()
        if not path.is_absolute():path=project/path
        if not path.exists():raise ValueError('本地 Qwen 找不到 '+name+'，请恢复本机文件。')
        chosen[name]=str(path.absolute() if name=='python' else path.resolve())
    if not chosen.get('reference_text','').strip():
        raise ValueError('Qwen 音色参考需要与录音逐字一致的 reference_text。')
    if not Path(chosen['model']).is_dir() or not list(Path(chosen['model']).glob('*.safetensors')):
        raise ValueError('Qwen model 须为已下载的 MLX 模型目录；本地制课不会自动下载或切换模型。')
    return chosen


def synth(project,speech,cue):
    if float(cue.get('speed',speech.get('speed',1)))!=1:
        raise ValueError('本地 Qwen 使用原速。请把 speed 设为 1，用讲稿和句群安排节奏。')
    chosen=config(project,speech)
    worker=Path(__file__).with_name('qwen_worker.py')
    env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
    description=subprocess.run([chosen['python'],str(worker),'--describe'],capture_output=True,text=True,env=env,timeout=30)
    if description.returncode:
        raise ValueError('所选本地 Python 缺少可用的 mlx-audio；请检查 Qwen 运行环境。')
    runtime=json.loads(description.stdout)
    model=Path(chosen['model'])
    model_files={p.name:{'size':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,
                        **({'sha256':sha(p)} if p.suffix=='.json' else {})}
                 for p in model.iterdir() if p.suffix in ('.json','.safetensors')}
    text=cue.get('_qwen_input',cue.get('tts',cue.get('text','')))
    signature={'backend':'qwen','adapter':1,'runtime':runtime,'python':chosen['python'],
               'worker_sha256':sha(worker),'model':chosen['model'],'model_files':model_files,
               'reference_sha256':sha(chosen['reference_audio']),'reference_text':chosen['reference_text'],
               'tts':text,'source_text':cue.get('tts',''),'rate_multiplier':1,
               'seed':chosen.get('seed',281762),'temperature':chosen.get('temperature',.53),
               'letter_style':chosen.get('letter_style','names')}
    if cfg.get('_classroom_take'):
        signature['classroom_take']=cfg['_classroom_take']
    key=hashlib.sha256(json.dumps(signature,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
    cache=project/'cache/audio';cache.mkdir(parents=True,exist_ok=True)
    wav=cache/(key+'.wav');meta=cache/(key+'.json')
    if wav.is_file() and meta.is_file():
        old=json.loads(meta.read_text())
        if old.get('audio_sha256')==sha(wav):return {**old,'file':str(wav),'cache_hit':True}
    with tempfile.TemporaryDirectory(dir=cache) as folder:
        folder=Path(folder)
        request={**chosen,'text':text,'source_text':cue.get('tts',''),'output':str(folder/'audio.wav'),
                 'metadata':str(folder/'audio.json')}
        path=folder/'request.json';path.write_text(json.dumps(request,ensure_ascii=False))
        completed=subprocess.run([chosen['python'],str(worker),'--request',str(path)],env=env,
                                  capture_output=True,text=True,timeout=chosen.get('timeout',600))
        if completed.returncode:
            raise ValueError('Qwen 本地合成未完成；未切换音色或调用云端接口。'+completed.stderr[-1200:])
        source=folder/'audio.wav'
        with wave.open(str(source),'rb') as audio:
            if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,24000):
                raise ValueError('Qwen 输出应为原速 24 kHz 单声道 PCM16。')
            duration=audio.getnframes()/24000
        if duration<=.15:raise ValueError('Qwen 输出缺少有效课堂语音。')
        measured=json.loads((folder/'audio.json').read_text())
        data={'duration':duration,'words':[],'alignment_status':'needs_alignment_or_sentence_review',
              'signature':signature,'synthesis':measured,'audio_sha256':sha(source)}
        source.replace(wav)
        temp=folder/'meta.json';temp.write_text(json.dumps(data,ensure_ascii=False));temp.replace(meta)
    return {**data,'file':str(wav),'cache_hit':False}
