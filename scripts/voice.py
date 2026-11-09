"""Speech adapters. Credentials stay in environment or the lesson's own .env.
Protocols reviewed against edulab at 805fdc5dd6bdf942290a7791924bf0ee08f26632.
Paid services are used only when explicitly selected in the lesson or CLI.
"""
import asyncio,base64,hashlib,json,os,subprocess,urllib.request,urllib.error,uuid,wave
from pathlib import Path

DEFAULTS={'glm':'chuichui','doubao':'zh_male_youyoujunzi_uranus_bigtts','minimax':'Chinese (Mandarin)_Gentleman','edge':'zh-CN-YunxiNeural','user':''}
KEYS={'glm':'GLM_API_KEY','doubao':'DOUBAO_API_KEY','minimax':'MINIMAX_API_KEY'}
def environment(project):
    values={};p=Path(project)/'.env'
    if p.exists():
        for line in p.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1);values[k.strip()]=v.strip().strip('\"\'')
    values.update(os.environ);return values

def http(url,payload,headers=None):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json',**(headers or {})})
    try:
        with urllib.request.urlopen(req,timeout=55) as r:return r.read()
    except urllib.error.HTTPError as e:
        # Never print request headers, credentials or arbitrary server echoes.
        raise RuntimeError(f'Speech request failed: HTTP {e.code}; selected provider was retained.') from None

def parse_doubao(raw):
    audio=[];words=[]
    for line in raw.decode().splitlines():
        if line.startswith('data:'):line=line[5:].strip()
        if not line.strip() or line.strip()=='[DONE]':continue
        d=json.loads(line)
        if d.get('code') not in (None,0,20000000):raise RuntimeError(f'Doubao response code {d.get("code")}')
        if d.get('data'):audio.append(base64.b64decode(d['data']))
        for w in (d.get('sentence') or {}).get('words',[]):words.append({'text':w['word'],'start':w['startTime'],'end':w['endTime']})
    if not audio:raise RuntimeError('Doubao returned no audio')
    return b''.join(audio),words

def parse_minimax(d):
    code=(d.get('base_resp') or {}).get('status_code',0)
    if code:raise RuntimeError(f'MiniMax response code {code}')
    body=d.get('data') or {}
    if not body.get('audio'):raise RuntimeError('MiniMax returned no audio')
    return bytes.fromhex(body['audio']),body.get('subtitle_file')

def synth(project,cfg,cue):
    project=Path(project);env=environment(project);backend=cfg.get('backend','glm')
    if backend not in DEFAULTS:raise ValueError(f'Unknown speech backend {backend}')
    voice=cfg.get('voice') or env.get(backend.upper()+'_VOICE') or DEFAULTS[backend]
    speed=float(cue.get('speed',cfg.get('speed',1.0)));pitch=cue.get('pitch',cfg.get('pitch','+0Hz'))
    if not .5<=speed<=2:raise ValueError('Speech speed must be between 0.5 and 2')
    text=cue.get('tts',cue.get('text',''));audio_path=cue.get('audio')
    model=cfg.get('model') or env.get('MINIMAX_MODEL','speech-2.8-hd') if backend=='minimax' else cfg.get('model','')
    signature={'backend':backend,'voice':voice,'model':model,'speed':speed,'pitch':pitch,'tts':text,'adapter':1}
    signature.update(resource_id=cfg.get('resource_id',env.get('DOUBAO_RESOURCE_ID','seed-tts-2.0')),host=env.get('MINIMAX_API_HOST','https://api.minimaxi.com'),emotion=cue.get('emotion'))
    if backend=='user':
        if not audio_path:raise ValueError(f'Cue {cue["id"]} needs an explicit audio file')
        source=(project/audio_path).resolve();signature['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    key=hashlib.sha256(json.dumps(signature,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
    cache=project/'cache/audio';cache.mkdir(parents=True,exist_ok=True);wav=cache/(key+'.wav');meta=cache/(key+'.json')
    if wav.exists() and meta.exists():
        d=json.loads(meta.read_text());d.update(file=str(wav),cache_hit=True);return d
    if backend in KEYS and not env.get(KEYS[backend]):
        raise ValueError(f'{KEYS[backend]} is needed for selected backend {backend}. Draft generation remains available.')
    words=[];ext='mp3'
    if backend=='user':raw=source.read_bytes();ext=source.suffix.lstrip('.')
    elif backend=='edge':
        import edge_tts
        async def run():
            data=[];timings=[]
            talk=edge_tts.Communicate(text,voice,rate=f'{round((speed-1)*100):+d}%',pitch=pitch,boundary='WordBoundary',receive_timeout=40)
            async for m in talk.stream():
                if m['type']=='audio':data.append(m['data'])
                elif m['type']=='WordBoundary':timings.append({'text':m['text'],'start':m['offset']/1e7,'end':(m['offset']+m['duration'])/1e7})
            return b''.join(data),timings
        raw,words=asyncio.run(run())
    elif backend=='glm':
        raw=http('https://open.bigmodel.cn/api/paas/v4/audio/speech',{'model':'glm-tts','input':text,'voice':voice,'response_format':'wav','speed':speed},{'Authorization':'Bearer '+env['GLM_API_KEY']});ext='wav'
        if not raw.startswith(b'RIFF'):raise RuntimeError('GLM returned a non-WAV response')
    elif backend=='doubao':
        raw=http('https://openspeech.bytedance.com/api/v3/tts/unidirectional',{'user':{'uid':'physics-notebook-video'},'req_params':{'text':text,'speaker':voice,'audio_params':{'format':'mp3','sample_rate':24000,'speech_rate':round((speed-1)*100),'enable_subtitle':True}}},{'X-Api-Key':env['DOUBAO_API_KEY'],'X-Api-Resource-Id':cfg.get('resource_id',env.get('DOUBAO_RESOURCE_ID','seed-tts-2.0')),'X-Api-Request-Id':str(uuid.uuid4())})
        raw,words=parse_doubao(raw)
    elif backend=='minimax':
        host=env.get('MINIMAX_API_HOST','https://api.minimaxi.com').rstrip('/')
        if not host.startswith('https://'):raise ValueError('MiniMax endpoint must use HTTPS')
        payload={'model':model,'text':text,'stream':False,'voice_setting':{'voice_id':voice,'speed':speed,'vol':1,'pitch':0},'audio_setting':{'format':'mp3','sample_rate':32000,'bitrate':128000,'channel':1},'subtitle_enable':True,'subtitle_type':'word','output_format':'hex'}
        if cue.get('emotion'):payload['voice_setting']['emotion']=cue['emotion']
        raw,url=parse_minimax(json.loads(http(host+'/v1/t2a_v2',payload,{'Authorization':'Bearer '+env['MINIMAX_API_KEY']})))
        if url and url.startswith('https://'):
            try:
                with urllib.request.urlopen(url,timeout=30) as r:subs=json.load(r)
                if isinstance(subs,dict):subs=next((x for x in subs.values() if isinstance(x,list)),[])
                for segment in subs:
                    for w in segment.get('timestamped_words',[segment]):words.append({'text':w.get('word',w.get('text','')),'start':w.get('time_begin',0)/1000,'end':w.get('time_end',0)/1000})
            except (OSError,ValueError):words=[]
    if not raw:raise RuntimeError('Speech service returned empty audio')
    temp=cache/(key+'.input.'+ext);part=cache/(key+'.part.wav');temp.write_bytes(raw)
    try:
        subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(temp),'-ac','1','-ar','24000','-c:a','pcm_s16le',str(part)],check=True)
        part.replace(wav)
    finally:temp.unlink(missing_ok=True)
    with wave.open(str(wav)) as w:duration=w.getnframes()/w.getframerate()
    d={'duration':duration,'words':words,'signature':signature};meta.write_text(json.dumps(d,ensure_ascii=False))
    d.update(file=str(wav),cache_hit=False);return d
