#!/usr/bin/env python3
"""Replay the immutable PDF-to-video example with bundled audio; no speech API calls."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import wave

ROOT=Path(__file__).resolve().parents[1]
SAMPLE=ROOT/'assets/starter-kit/incline'


def verify():
    manifest=json.loads((SAMPLE/'manifest.json').read_text())
    for name,expected in manifest['files'].items():
        path=SAMPLE/name
        if not path.resolve().is_relative_to(SAMPLE.resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Bundled example has changed: '+name+'. Copy it as a new lesson and use the review workflow.')
    return manifest


def render(output,engine='notebook',width=1280):
    verify();output=output.resolve()
    if output.exists() and any(output.iterdir()):raise ValueError('Choose an empty output directory so an existing lesson is preserved.')
    output.mkdir(parents=True,exist_ok=True)
    for name in ('lesson.json','source.pdf','source.tex','student.tex','student.pdf','incline.tikz','forces.tikz','transcription.json','statement.md','input-manifest.json','script.md','audio','hanzi'):
        p=SAMPLE/name
        if not p.exists():continue
        if p.is_dir():shutil.copytree(p,output/('cache/hanzi' if name=='hanzi' else name))
        else:shutil.copy2(p,output/name)
    import course
    lesson,pages=course.compile_lesson(output)
    from teaching import audit
    teaching=audit(output,lesson,pages)
    course.write_json(output/'teaching-report.json',teaching)
    if teaching['errors']:raise ValueError('Bundled source check: '+json.dumps(teaching['errors'],ensure_ascii=False))
    args=SimpleNamespace(backend=None,voice=None,draft=False,fps=15)
    data,pcm,stats=course.prepare(output,lesson,pages,args)
    font=course.font_path(lesson,output)
    with wave.open(str(output/'narration.wav'),'wb') as w:
        w.setparams((1,2,course.SR,0,'NONE','not compressed'));w.writeframes(pcm)
    course.write_json(output/'timeline.json',data);course.export_boards(output,data,font)
    if engine=='notebook':stats.update(course.video(output,data,font,width))
    else:
        from engine_render import render as native
        stats.update(native(output,data,font,width,engine))
    audio='data:audio/wav;base64,'+base64.b64encode((output/'narration.wav').read_bytes()).decode()
    template=(ROOT/'assets/player.html').read_text().replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/')).replace('__AUDIO__',audio).replace('__MODELS__',(ROOT/'assets/models.js').read_text())
    (output/'preview.html').write_text(template)
    receipt={'status':'example_replay','duration':data['duration'],'backend':'bundled_recordings',
             'renderer':engine,'speech_api_calls':0,'video_sha256':hashlib.sha256((output/'video.mp4').read_bytes()).hexdigest(),
             'source_manifest':hashlib.sha256((SAMPLE/'manifest.json').read_bytes()).hexdigest(),
             'note':'Fixed distributed example replay. New lessons use review-plan, final QA and finalize.',**stats}
    course.write_json(output/'demo-replay.json',receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['verify','render'])
    parser.add_argument('output',type=Path,nargs='?');parser.add_argument('--renderer',choices=['notebook','motion-canvas','manim'],default='notebook');parser.add_argument('--width',type=int,default=1280)
    args=parser.parse_args()
    if args.command=='verify':print(json.dumps({'ok':True,'files':len(verify()['files'])}));return
    if not args.output:parser.error('render needs an empty output directory')
    print(json.dumps(render(args.output,args.renderer,args.width),ensure_ascii=False))


if __name__=='__main__':main()
