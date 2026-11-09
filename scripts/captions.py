"""Make cue/word-timed subtitles; optionally burn them into a course video."""
import argparse,json,math,re,subprocess
from pathlib import Path

def burn_pillow(source,target,root,events,W,H,duration):
    """Portable caption overlay for FFmpeg installations without libass."""
    from PIL import Image,ImageDraw,ImageFont
    folder=root/'cache'/'captions';folder.mkdir(parents=True,exist_ok=True)
    strip_h=round(H/12);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Songti.ttc',round(W/60))
    blank=folder/'blank.png';Image.new('RGBA',(W,strip_h)).save(blank)
    frames=[(0.,blank)]
    for i,(s,e,text) in enumerate(events):
        im=Image.new('RGBA',(W,strip_h));draw=ImageDraw.Draw(im)
        box=draw.textbbox((0,0),text,font=font);tw,th=box[2]-box[0],box[3]-box[1]
        x=(W-tw)/2;y=strip_h-round(H/60)-th
        draw.rounded_rectangle((x-10,y-5,x+tw+10,y+th+5),radius=5,fill=(20,26,22,220))
        draw.text((x-box[0],y-box[1]),text,font=font,fill='white')
        file=folder/f'{i:04d}.png';im.save(file);frames.extend([(s,file),(e,blank)])
    frames.append((duration,blank));frames.sort(key=lambda a:a[0]);listing=[]
    for i,(s,file) in enumerate(frames[:-1]):
        span=frames[i+1][0]-s
        if span>0:listing.extend([f"file '{file.name}'",f'duration {span:.6f}'])
    listing.append("file 'blank.png'");manifest=folder/'frames.txt';manifest.write_text('\n'.join(listing)+'\n')
    subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(source),'-f','concat','-safe','0','-i',str(manifest),'-filter_complex','[1:v]fps=24,format=rgba[sub];[0:v][sub]overlay=0:H-h:eof_action=pass[out]','-map','[out]','-map','0:a:0','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','copy','-t',str(duration),'-movflags','+faststart',str(target)],check=True)

def chunks(cue,base,limit=28):
    words=cue.get('words',[]);source=cue['tts'];clean=lambda s:''.join(c.lower() for c in s if c.isalnum())
    indices=[i for i,c in enumerate(source) if c.isalnum()];joined=''.join(clean(w['text']) for w in words)
    if not words:
        pieces=[source[i:i+limit] for i in range(0,len(source),limit)]
        return [(base+(cue['end']-cue['start'])*i/len(pieces),base+(cue['end']-cue['start'])*(i+1)/len(pieces),s) for i,s in enumerate(pieces)]
    exact=joined==clean(source)
    if exact and indices:
        # Prefer spoken clause boundaries so a caption does not start halfway through a phrase.
        natural={len(clean(source[:a.end()])) for a in re.finditer(r'[，。！？；：]',source)}
        starts=[];ends=[]
        for word in words:
            count=len(clean(word['text']))
            for j in range(count):
                starts.append(word['start']+(word['end']-word['start'])*j/count)
                ends.append(word['start']+(word['end']-word['start'])*(j+1)/count)
        cuts=[0]
        while cuts[-1]<len(indices):
            lo=cuts[-1];cap=min(lo+limit,len(indices))
            choices=[v for v in natural if lo+8<=v<=cap]
            cuts.append(len(indices) if cap==len(indices) else max(choices) if choices else cap)
        out=[]
        for lo,hi in zip(cuts,cuts[1:]):
            end=indices[hi-1]+1
            while end<len(source) and not source[end].isalnum():end+=1
            out.append((base+starts[lo],base+ends[hi-1],source[indices[lo]:end].strip()))
        return out
    groups=[];current=[];length=0;used=0;start_index=0
    for w in words:
        count=len(clean(w['text']))
        if current and length+count>limit:
            groups.append((current,start_index,used));current=[];length=0;start_index=used
        current.append(w);length+=count;used+=count
    if current:groups.append((current,start_index,used))
    out=[]
    for group,lo,hi in groups:
        if exact and hi>lo:
            end=indices[hi-1]+1
            while end<len(source) and not source[end].isalnum():end+=1
            text=source[indices[lo]:end].strip()
        else:text=''.join(w['text'] for w in group)
        out.append((base+group[0]['start'],base+group[-1]['end'],text))
    return out

def stamp(t,ass=False):
    q=round(t*(100 if ass else 1000));unit=100 if ass else 1000;sec,rem=divmod(q,unit);h,sec=divmod(sec,3600);m,s=divmod(sec,60)
    return f'{h}:{m:02d}:{s:02d}.{rem:02d}' if ass else f'{h:02d}:{m:02d}:{s:02d},{rem:03d}'

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project');ap.add_argument('--burn',action='store_true');ap.add_argument('--output');a=ap.parse_args();root=Path(a.project).resolve();data=json.loads((root/'timeline.json').read_text());events=[]
    for p in data['pages']:
        for c in p['cues']:events.extend(chunks(c,p['start']+c['start']))
    events.sort()
    normalized=[]
    for i,(s,e,text) in enumerate(events):
        end=min(e+.13,events[i+1][0]-.01) if i+1<len(events) else e+.13
        normalized.append((s,max(s+.05,end),text))
    srt='\n\n'.join(f'{i+1}\n{stamp(s)} --> {stamp(e)}\n{text}' for i,(s,e,text) in enumerate(normalized));(root/'subtitles.srt').write_text(srt+'\n')
    source=root/'video.mp4';size=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(source)],text=True))['streams'][0];W,H=size['width'],size['height']
    header=f'''[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Songti SC,{round(W/60)},&H00FFFFFF,&H00FFFFFF,&H00181D18,&H95000000,0,0,0,0,100,100,0,0,3,1,0,2,60,60,{round(H/60)},1\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'''
    for s,e,text in normalized:header+=f'Dialogue: 0,{stamp(s,True)},{stamp(e,True)},Default,,0,0,0,,{text.replace(chr(10)," ")}\n'
    ass=root/'subtitles.ass';ass.write_text(header)
    if a.burn:
        target=Path(a.output).resolve() if a.output else root/'video-captioned.mp4'
        if target==source:raise ValueError('Choose a different output filename from video.mp4')
        filters=subprocess.check_output(['ffmpeg','-hide_banner','-filters'],text=True,stderr=subprocess.DEVNULL)
        if re.search(r'\s+ass\s+V->V',filters):
            # Use a relative subtitle filename so filter escaping is independent of project paths.
            subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(source),'-vf','ass=subtitles.ass','-c:v','libx264','-preset','fast','-crf','19','-c:a','copy','-movflags','+faststart',str(target)],cwd=root,check=True)
        else:burn_pillow(source,target,root,normalized,W,H,data['duration'])
        print(target)
    print(json.dumps({'caption_events':len(events),'srt':str(root/'subtitles.srt')},ensure_ascii=False))
if __name__=='__main__':main()
