import os
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from feedback_bank import check,record
from feedback_review import decide
from learning_bundle import merge
from lesson_transfer import record_retest,trial_audit


class CrossLessonTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.db=self.root/'feedback.sqlite3'
        env=patch.dict(os.environ,PHYSICS_NOTEBOOK_FEEDBACK_DB=str(self.db))
        env.start()
        self.addCleanup(env.stop)

    def test_repeated_positions_case_and_word_boundary_in_both_lesson_types(self):
        record('issues','connected-physics-term-位矢','词内有停顿',match='位矢',failed_stage='synthesis')
        record('letters','Q','起音难辨',lesson='先前的一课')
        record('issues','formula-narration-sync','笔未跟到公式',scope='all')
        for kind in ('concept','problem'):
            lesson={'title':'另一课','kind':kind,'pages':[{'id':'p','cues':[{'id':'c',
                'tts':'位矢、单位矢量和位矢。q 乘 Q。','actions':[{'type':'math','id':'line','latex':'qQ'}]}]}]}
            report=check(self.root,lesson)
            work=report['learning_checks']
            for k,wanted in [('term',[0,9]),('letter',['q','Q']),('formula',['line'])]:
                rows=[r for r in work['occurrences'] if r['kind']==k]
                values=([r['offset'] for r in rows if r['text']=='位矢'] if k=='term' else
                        [r['text'] for r in rows] if k=='letter' else [r['action_id'] for r in rows])
                if k=='term':
                    self.assertEqual(values,[0,lesson['pages'][0]['cues'][0]['tts'].rindex('位矢')])
                else:self.assertEqual(values,wanted)
            lesson['pages'][0]['cues'][0]['tts']='单位矢量。'
            clean=check(self.root,lesson)
            self.assertFalse(any(r['key']=='connected-physics-term-位矢' for r in clean['findings']))

    def test_retest_preserves_voice_evidence_and_doesnt_adopt_or_leak_revisions(self):
        record('letters','Z','轴名的元音错',lesson='旧课')
        first=decide('letters','Z','trial','lesson','试读 Zee','作者报告',lesson='旧课')['id']
        wav=self.root/'sample.wav'
        with wave.open(str(wav),'wb') as f:
            f.setparams((1,2,24000,0,'NONE',''));f.writeframes(b'\x00\x01'*24000)
        kwargs=dict(lesson='新课',text='沿 z 轴投影',method='audio_probe',outcome='inconclusive',
                    evidence='两次音素识别给出不同的元音',sample=wav,model='测试音色',actual_input='沿 Zee 轴投影')
        with self.assertRaises(ValueError):record_retest(self.db,first,**{**kwargs,'lesson':'旧课'})
        self.assertTrue(record_retest(self.db,first,**kwargs)['recorded'])
        self.assertFalse(record_retest(self.db,first,**kwargs)['recorded'])
        other=self.root/'new'/'feedback.sqlite3'
        self.assertEqual(merge(self.db,other)['retests_added'],1)
        self.assertEqual(merge(self.db,other)['retests_added'],0)
        row=trial_audit(other)[0]
        self.assertEqual(row['state'],'trial')
        self.assertEqual((other.parent/row['cross_lesson_tests'][0]['sample']).read_bytes(),wav.read_bytes())
        decide('letters','Z','withdrawn','lesson','撤回本课试法','新句检查后撤回',lesson='旧课')
        latest=trial_audit(self.db)[0]
        self.assertEqual((len(latest['cross_lesson_tests']),len(latest['earlier_tests'])),(0,1))

