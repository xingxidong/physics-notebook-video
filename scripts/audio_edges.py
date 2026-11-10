"""Trim provider padding locally while retaining timed words and internal pauses."""
import array,copy,math

def trim(clip,audio,rate=24000,settings=True):
    meta=copy.deepcopy(audio)
    if not settings:return clip,meta,{'enabled':False,'start':0,'end':0}
    cfg={} if settings is True else settings
    if not isinstance(cfg,dict):raise ValueError('speech.trim_edges must be true, false or an object')
    threshold=float(cfg.get('threshold_db',-48));limit=float(cfg.get('max_trim_seconds',1.5))
    if not -60<=threshold<=-35 or not 0<=limit<=3:raise ValueError('trim_edges threshold or maximum trim is outside the supported range')
    samples=array.array('h',clip);duration=len(samples)/rate;width=max(1,round(rate*.01));active=[]
    for start in range(0,len(samples),width):
        block=samples[start:start+width];rms=math.sqrt(sum(x*x for x in block)/max(1,len(block)))
        if 20*math.log10(max(1,rms)/32768)>threshold:active.append(start)
    if not active:return clip,meta,{'enabled':True,'start':0,'end':0,'silent_input':True}
    start=max(0,active[0]/rate-.08);end=min(duration,(active[-1]+width)/rate+.16)
    words=[w for w in meta.get('words',[]) if any(c.isalnum() for c in str(w.get('text','')))]
    if words:
        start=min(start,max(0,min(w['start'] for w in words)-.06))
        end=max(end,min(duration,max(w['end'] for w in words)+.08))
    start=min(start,limit);end=max(end,duration-limit)
    a=max(0,round(start*rate));b=min(len(samples),round(end*rate));start=a/rate;end=b/rate
    meta['duration']=(b-a)/rate
    for word in meta.get('words',[]):
        word['start']=min(meta['duration'],max(0,word['start']-start))
        word['end']=min(meta['duration'],max(word['start'],word['end']-start))
    report={'enabled':True,'start':round(start,6),'end':round(duration-end,6),'original_duration':duration}
    return clip[a*2:b*2],meta,report
