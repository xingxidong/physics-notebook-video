import json,math,sys,tempfile,unittest
from array import array
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from audio_edges import trim
from speech_plan import apply

class ClassroomDeliveryTests(unittest.TestCase):
    def sound(self,seconds,rate=24000):
        return array('h',(round(7000*math.sin(2*math.pi*220*i/rate)) for i in range(round(seconds*rate)))).tobytes()

    def test_trim_preserves_internal_pause_and_moves_word_anchors(self):
        rate=24000;quiet=lambda s:b'\0'*round(s*rate)*2
        clip=quiet(.5)+self.sound(.3)+quiet(.2)+self.sound(.3)+quiet(.7)
        meta={'duration':2.,'words':[{'text':'前','start':.5,'end':.8},{'text':'后','start':1.,'end':1.3}]}
        out,updated,report=trim(clip,meta)
        self.assertGreater(report['start'],.3);self.assertGreater(report['end'],.4)
        shift=report['start'];self.assertAlmostEqual(updated['words'][0]['start'],.5-shift,places=5)
        a=round(shift*rate)*2;self.assertEqual(out,clip[a:a+len(out)])
        self.assertEqual(meta['words'][0]['start'],.5)
        self.assertLess(updated['words'][-1]['end'],updated['duration'])

    def test_timestamps_protect_quiet_timed_word_and_disable_is_identity(self):
        rate=24000;clip=self.sound(.3)+b'\0'*round(.7*rate)*2
        meta={'duration':1.,'words':[{'text':'尾音','start':.1,'end':.85}]}
        out,updated,report=trim(clip,meta)
        self.assertGreaterEqual(updated['duration'],.93-1/rate)
        same,unchanged,_=trim(clip,meta,settings=False)
        self.assertEqual(same,clip);self.assertEqual(unchanged,meta)

    def test_classroom_keeps_explicit_teaching_pause_and_classic_settings(self):
        lesson={'title':'x','speech':{'delivery_profile':'classroom'},'pages':[{'id':'p1','cues':[{'id':'c1','role':'derive','tts':'沿水平方向求导。'},{'id':'c2','role':'observe','tts':'看两份水之间的距离。','pause_after':1.4,'pause_reason':'think'}]}]}
        with tempfile.TemporaryDirectory() as d:
            value,_=apply(d,lesson);first,second=value['pages'][0]['cues']
            self.assertTrue(value['speech']['trim_edges']);self.assertEqual(first['pause'],.22)
            self.assertEqual(second['pause'],1.4);self.assertEqual(second['pause_reason'],'think')
            lesson['speech'].pop('delivery_profile');old,_=apply(d,lesson)
            self.assertEqual(old['pages'][0]['cues'][0]['pause'],.65)
            self.assertNotIn('trim_edges',old['speech'])

if __name__=='__main__':unittest.main()
