from array import array
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pronunciation import classroom_syllables
from speech_blind import prepare, score, screen
from speech_context import inspect, inventory
from speech_probe import LETTER_PATTERNS
from term_flow import RATE, flow_evidence
from tone_review import _digest


class SpeechContextTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.p=Path(tmp.name)

    def test_terms_subscripts_context_and_units(self):
        text='测量的量，沿 z 轴，比较 u 乘 q 和负 v 乘 q，初速 v₀、v_0、v0。长度为 5 m。'
        items=inventory({'pages':[{'cues':[{'id':'c','tts':text}]}]})[0]['targets']
        self.assertEqual([s['expected'] for s in items if s['kind']=='tone' and s['text']=='量'],['liang2','liang4'])
        self.assertEqual([s['text'] for s in items if s['kind']=='symbol'],['z','u','q','v','q','v₀','v_0','v0'])
        self.assertEqual([s['subscript'] for s in items if 'subscript' in s],['0','0','0'])
        self.assertEqual(len(set(s['id'] for s in items)),len(items))

    def test_sandhi_restart_and_repeated_vowel(self):
        self.assertEqual(classroom_syllables('两种','liang3 zhong3','liang2 zhong3'),[True,True])
        self.assertEqual(classroom_syllables('测量','ce4 liang2','ce4 liang4'),[True,False])
        raw=b''.join((array('h',[v])*n).tobytes() for v,n in [(2000,3200),(230,1280),(2000,3200)])
        self.assertEqual(flow_evidence(raw),(0,True))
        self.assertTrue(LETTER_PATTERNS['Q'].fullmatch('k j uː'))
        self.assertFalse(LETTER_PATTERNS['Q'].fullmatch('k j uː u'))

    def wav(self,path,freq):
        import math
        with wave.open(str(path),'wb') as w:
            w.setparams((1,2,RATE,0,'NONE','not compressed'))
            w.writeframes(array('h',(round(1200*math.sin(freq*i/RATE)) for i in range(RATE*3))).tobytes())

    @unittest.skipUnless(shutil.which('ffmpeg'),'requires ffmpeg')
    def test_real_control_and_unlabelled_kept_separate(self):
        rows=[]
        for i,(label,origin) in enumerate([('good','real'),('bad','real'),('bad','control'),('unlabeled','real')]):
            file=self.p/f'{i}.wav'
            self.wav(file,200+i*175)
            rows.append(dict(file=file.name,sha256=_digest(file),label=label,origin=origin,basis='fixture',
                             target='桥接',task='flow',window=[.25,.65]))
        path=self.p/'source.json'
        path.write_text(json.dumps(rows))
        out=self.p/'blind'
        trials=prepare(path,out)
        self.assertTrue(all(set(t).isdisjoint({'label','origin','basis'}) for t in trials))
        self.assertEqual(len(screen(out/'clips')[0]),4)
        key=json.loads((out/'key.json').read_text())
        answers={i:'good' if k['origin']=='real' else 'unsure' for i,k in key.items()}
        result=score(out,answers)['totals']
        self.assertEqual(result['real'],{'missed_bad':1,'correct_good':1,'unlabeled':1})
        self.assertEqual(result['control'],{'undecided_bad':1})

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'requires ffmpeg')
    def test_changed_join_and_board_invalidate_receipt(self):
        wav=self.p/'in.wav'
        self.wav(wav,400)
        media=self.p/'delivery.mp4'
        def make(color):
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c='+color+':s=48x48:r=5:d=3',
                            '-i',str(wav),'-c:v','libx264','-c:a','aac','-shortest',str(media)],check=True)
        make('white')
        cues=[dict(id='a',tts='看图。',start=0,end=.8),dict(id='b',tts='u 乘 q。',start=.8,end=2),
              dict(id='c',tts='继续。',start=2,end=3)]
        timeline=dict(pages=[dict(id='p',cues=cues,strokes=[dict(cue='b',board_id='eq',start=1,end=1.4)])])
        row=inspect(self.p,timeline,media,clip_id='1.2')['items'][0]
        self.assertEqual(row['clip_range'],[0,3])
        self.assertTrue(Path(row['clip']).exists())
        result={'1.2':dict(token=row['token'],checks={'symbol@0':'ok','symbol@4':'ok','board':'ok','join':'ok'})}
        self.assertFalse(inspect(self.p,timeline,media,findings=result)['remaining'])
        make('black')
        revised=inspect(self.p,timeline,media,clip_id='1.2')['items'][0]
        self.assertTrue(revised['changed'])
        self.assertEqual(revised['status'],'pending')
        with self.assertRaises(ValueError):
            inspect(self.p,timeline,media,findings=result)
        result['1.2']['token']=revised['token']
        result['1.2']['checks']['join']='unsure'
        self.assertEqual(inspect(self.p,timeline,media,findings=result)['author_review'],['1.2'])
        self.wav(wav,800)
        make('black')
        self.assertEqual(len(inspect(self.p,timeline,media)['items']),3)


if __name__=='__main__':
    unittest.main()
