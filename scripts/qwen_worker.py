"""Run in the configured local MLX environment, with network model loading disabled."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import re
import wave


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--describe',action='store_true');parser.add_argument('--request',type=Path)
    args=parser.parse_args()
    if args.describe:
        print(json.dumps({name:importlib.metadata.version(name) for name in ('mlx-audio','mlx')}));return
    data=json.loads(args.request.read_text())
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load
    with wave.open(data['reference_audio'],'rb') as sample:
        if (sample.getnchannels(),sample.getsampwidth(),sample.getframerate())!=(1,2,24000):
            raise ValueError('音色参考需要 24 kHz 单声道 PCM16 WAV。')
        reference=mx.array(np.frombuffer(sample.readframes(sample.getnframes()),dtype='<i2').astype(np.float32)/32768)
    text=data['text']
    if data.get('letter_style','names')=='names':
        names=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                   ['Ay','Bee','See','Dee','E','Eff','Gee','Aitch','Eye','Jay','Kay','Ell','Em','En','Oh','Pee','Cue','Are','Ess','Tee','You','Vee','double you','Ex','Why','Zee']))
        text=re.sub(r'(?<![A-Za-z])([A-Za-z])(?![A-Za-z])',lambda m:' '+names[m[1].upper()]+' ',text)
    elif data['letter_style']!='literal':
        raise ValueError('letter_style 使用 names 或 literal。')
    mx.random.seed(data.get('seed',281762));mx.set_cache_limit(120*1024**2)
    model=load(data['model'])
    chunks=[np.asarray(part.audio,np.float32).reshape(-1) for part in model.generate(text,
            lang_code='chinese',ref_audio=reference,ref_text=data['reference_text'],
            max_tokens=min(2048,max(122,round(len(text)*4.1+55))),temperature=data.get('temperature',.53),
            top_k=30,top_p=.9,repetition_penalty=1.10,verbose=False)]
    if not chunks:raise ValueError('本地模型未返回音频。')
    audio=np.concatenate(chunks)
    if not np.isfinite(audio).all() or np.max(np.abs(audio))<.01:raise ValueError('本地音频为空或含无效数值。')
    pcm=np.int16(np.rint(np.clip(audio,-.995,.995)*32767))
    with wave.open(data['output'],'wb') as out:
        out.setparams((1,2,24000,0,'NONE','not compressed'));out.writeframes(pcm.tobytes())
    Path(data['metadata']).write_text(json.dumps({'actual_input':text,'source_text':data['source_text'],
                'duration':len(pcm)/24000,'rate_multiplier':1,'alignment':'unmeasured'},ensure_ascii=False))


if __name__=='__main__':main()
