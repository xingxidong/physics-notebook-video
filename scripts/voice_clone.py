#!/usr/bin/env python3
"""Create a reusable MiniMax voice_id from an authorized local recording."""
import argparse,json,mimetypes,re,secrets,subprocess,urllib.error,urllib.request
from pathlib import Path
from voice import environment

FORMATS={'.mp3','audio/mpeg','.m4a','audio/mp4','.wav','audio/wav','audio/x-wav'}

def inspect_audio(path):
    path=Path(path).resolve()
    if not path.is_file():raise ValueError(f'Audio file does not exist: {path}')
    if path.suffix.lower() not in ('.mp3','.m4a','.wav'):raise ValueError('MiniMax clone audio must be MP3, M4A or WAV')
    if path.stat().st_size>20*1024*1024:raise ValueError('MiniMax clone audio must be 20 MB or smaller')
    result=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],capture_output=True,text=True)
    if result.returncode:raise ValueError('ffprobe could not read the clone audio')
    duration=float(result.stdout.strip())
    if not 10<=duration<=300:raise ValueError('MiniMax clone audio must be 10 seconds to 5 minutes long')
    return {'path':path,'duration':duration,'bytes':path.stat().st_size,'mime':mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}

def _multipart(fields,file):
    boundary='----physics-'+secrets.token_hex(12);chunks=[]
    for key,value in fields.items():
        chunks.extend([f'--{boundary}\r\n'.encode(),f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()])
    chunks.extend([f'--{boundary}\r\n'.encode(),f'Content-Disposition: form-data; name="file"; filename="{file["path"].name}"\r\n'.encode(),f'Content-Type: {file["mime"]}\r\n\r\n'.encode(),file['path'].read_bytes(),b'\r\n',f'--{boundary}--\r\n'.encode()])
    return b''.join(chunks),f'multipart/form-data; boundary={boundary}'

def _request(url,key,body,content_type):
    request=urllib.request.Request(url,data=body,headers={'Authorization':'Bearer '+key,'Content-Type':content_type})
    try:
        with urllib.request.urlopen(request,timeout=120) as response:return json.loads(response.read())
    except urllib.error.HTTPError as error:raise RuntimeError(f'MiniMax voice cloning failed with HTTP {error.code}') from None

def _ok(data,stage):
    code=(data.get('base_resp') or {}).get('status_code',0)
    if code:raise RuntimeError(f'MiniMax {stage} returned status {code}')
    return data

def apply_voice(project,voice_id,model='speech-2.8-hd'):
    project=Path(project).resolve();lesson_path=project/'lesson.json'
    if not lesson_path.exists():raise ValueError('Applying a voice needs an existing lesson.json')
    lesson=json.loads(lesson_path.read_text());lesson.setdefault('speech',{}).update(backend='minimax',voice=voice_id,model=model);lesson_path.write_text(json.dumps(lesson,ensure_ascii=False,indent=2));return lesson_path

def clone(project,audio,voice_id,preview_text=None,model='speech-2.8-hd',noise_reduction=False,normalize=True,update_project=False):
    project=Path(project).resolve();project.mkdir(parents=True,exist_ok=True);info=inspect_audio(audio);env=environment(project);key=env.get('MINIMAX_API_KEY')
    if not key:raise ValueError('MINIMAX_API_KEY is required in the environment or project .env')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{6,254}[A-Za-z0-9]',voice_id):raise ValueError('voice_id must be 8-256 characters, start with a letter, and use letters, digits, _ or -')
    host=env.get('MINIMAX_API_HOST','https://api.minimaxi.com').rstrip('/')
    if not host.startswith('https://'):raise ValueError('MiniMax endpoint must use HTTPS')
    body,kind=_multipart({'purpose':'voice_clone'},info);uploaded=_ok(_request(host+'/v1/files/upload',key,body,kind),'upload')
    file_id=(uploaded.get('file') or {}).get('file_id')
    if not isinstance(file_id,int):raise RuntimeError('MiniMax upload did not return an integer file_id')
    payload={'file_id':file_id,'voice_id':voice_id,'need_noise_reduction':bool(noise_reduction),'need_volume_normalization':bool(normalize)}
    if preview_text:payload.update(text=preview_text,model=model)
    cloned=_ok(_request(host+'/v1/voice_clone',key,json.dumps(payload,ensure_ascii=False).encode(),'application/json'),'clone')
    preview=None;url=cloned.get('demo_audio')
    if isinstance(url,str) and url.startswith('https://'):
        preview=project/'voice-clone-preview.mp3'
        with urllib.request.urlopen(url,timeout=60) as response:preview.write_bytes(response.read())
    if update_project:
        apply_voice(project,voice_id,model)
    report={'voice_id':voice_id,'file_id':file_id,'source':str(info['path']),'duration':round(info['duration'],3),'bytes':info['bytes'],'model':model,'noise_reduction':bool(noise_reduction),'volume_normalization':bool(normalize),'preview':str(preview) if preview else None,'project_updated':bool(update_project)}
    (project/'voice-clone-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('audio',nargs='?');p.add_argument('--project',required=True);p.add_argument('--voice-id');p.add_argument('--apply-voice-id');p.add_argument('--preview-text');p.add_argument('--model',default='speech-2.8-hd');p.add_argument('--noise-reduction',action='store_true');p.add_argument('--no-normalize',action='store_true');p.add_argument('--update-project',action='store_true');p.add_argument('--confirm-rights',action='store_true')
    a=p.parse_args()
    if a.apply_voice_id:
        print(apply_voice(a.project,a.apply_voice_id,a.model));return
    if not a.audio or not a.voice_id:raise SystemExit('Audio and --voice-id are required when creating a clone.')
    if not a.confirm_rights:raise SystemExit('Add --confirm-rights only for your own voice or a voice you are authorized to clone.')
    print(json.dumps(clone(a.project,a.audio,a.voice_id,a.preview_text,a.model,a.noise_reduction,not a.no_normalize,a.update_project),ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError) as error:raise SystemExit(f'ERROR: {error}')
