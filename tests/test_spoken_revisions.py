import array
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from classroom_language import review_narration
from lesson_quality import handout_language
from pronunciation import ENGLISH_NAMES, letter_bindings, resolve_readings
from voice_quality import _review_short_joins


class SpokenRevisions(unittest.TestCase):
    def test_alphabet_and_units(self):
        for symbol in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            self.assertEqual(resolve_readings(symbol.lower()), ENGLISH_NAMES[symbol])
            self.assertTrue(ENGLISH_NAMES[symbol].isascii())
        self.assertEqual(resolve_readings('点 P，4 V，8 W，沿 x 轴。', {'x':'艾克斯'}),
                         '点 pea，4 V，8 W，沿 ex 轴。')
        self.assertEqual(resolve_readings('把 q 写在 S 旁边。'), '把 queue 写在 ess 旁边。')

    def test_classroom_references(self):
        for text, expected in [('这是论文里说的。','source-in-narration'),('按文章最后建议的办法。','source-in-narration'),
                               ('截图中给出一条线。','source-in-narration'),('从手势看这个量。','unseen-gesture')]:
            self.assertIn(expected,{r['code'] for r in review_narration([{'id':'one','tts':text}])})
        self.assertFalse(review_narration([{'id':'one','tts':'箭头越短，阻力越小。'}]))

    def test_teacher_editing_flags_both_media_without_flagging_physical_conditions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'讲义.md').write_text('在惯性系中，合力为零时速度保持不变。\n本题的主线已经建立。\n这不意味着物块停下。')
            for kind in ('concept','problem'):
                report, scanned=handout_language(root,{'kind':kind})
                self.assertTrue(scanned)
                self.assertEqual([row['line'] for row in report],[2,3])
            cues=[{'id':'a','tts':'本题的主线已经建立。这不意味着物块停下。'}]
            self.assertEqual({r['code'] for r in review_narration(cues)},{'editorial-language','defensive-language'})

    def test_short_gaps_and_clicks(self):
        rate = 10000
        cues = [{'id':'a','start':0,'end':.5,'tts':'球落地了。'},
                {'id':'b','start':.8,'end':1.2,'tts':'现在看速度图。'}]
        samples = array.array('h', [1200]*5000+[0]*3000+[1200]*4000)
        self.assertFalse(_review_short_joins(cues,samples,rate))
        samples[6500:6520] = array.array('h',[4000]*20)
        self.assertEqual(_review_short_joins(cues,samples,rate)[0]['code'],'join-transient')
        cues[1]['start']=.55
        self.assertEqual(_review_short_joins(cues,array.array('h',[1200]*5000+[0]*500+[1200]*6500),rate)[0]['code'],'tight-sentence-join')
