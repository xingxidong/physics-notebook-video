import json
import math
import os
from array import array
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from feedback_bank import check, record
from term_flow import RATE, acoustic_gap, identify, inspect, refresh_manifest, term_counts


class TermFlowTest(unittest.TestCase):
    def test_word_boundary_keeps_genuine_and_excludes_cross_word_readings(self):
        from pronunciation import matched_pronunciations, term_pattern
        terms = {'三相交流电':'san1 xiang4 jiao1 liu2 dian4', '相交':'xiang1 jiao1',
                 '偏转角':'pian1 zhuan3 jiao3', '转角':'zhuan4 jiao3'}
        sentence = '接入三相交流电。两条线相交，标出偏转角和转角。'
        lesson = dict(pages=[dict(cues=[dict(id='a',tts=sentence)])])
        targets = [r for r in identify(lesson) if r['term'] in terms]
        self.assertCountEqual([(r['term'], r['expected']) for r in targets], terms.items())
        self.assertEqual(matched_pronunciations(sentence,False,terms), terms)
        self.assertEqual(len(list(term_pattern(['相交']).finditer('三相交于一点。两相交流供电。六相交流供电。'))), 1)
        from card_speech import lesson_inputs
        generated = lesson_inputs(lesson)['1','a']
        self.assertCountEqual([(r['term'], r['expected']) for r in generated['targets']
                               if r['term'] in terms], terms.items())

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = patch.dict(os.environ, PHYSICS_NOTEBOOK_FEEDBACK_DB=str(self.root/'memory.db'))
        env.start()
        self.addCleanup(env.stop)

    def test_inventory_finds_repeat_known_new_and_nested(self):
        cues = [dict(id='a',tts='电压差和电压差；这个长度称为“德拜长度”。'),
                dict(id='b',tts='在桥接支路比较双折射和克尔效应。')]
        self.lesson = dict(pages=[dict(cues=cues)],knowledge_points=[dict(name='双折射')],
                           speech=dict(physics_terms={'克尔效应':'ke4 er3 xiao4 ying4'}))
        record('issues','term-flow-克尔效应','词内收住',match='克尔效应')
        rows = identify(self.lesson)
        counts = term_counts(rows)
        self.assertEqual([counts[k] for k in ('电压差','桥接','支路','德拜长度','双折射','克尔效应')], [2,1,1,1,1,1])
        self.assertEqual(len({r['id'] for r in rows}),len(rows))
        self.assertTrue(next(r for r in rows if r['term']=='克尔效应')['priority'])

    def test_later_lectures_and_future_reading_feed_both_stages(self):
        from pronunciation import PHYSICS_PINYIN
        words = {'热力学温标':'re4 li4 xue2 wen1 biao1', '奥托循环':'ao4 tuo1 xun2 huan2',
                 '表面张力':'biao3 mian4 zhang1 li4', '接触角':'jie1 chu4 jiao3',
                 '峰值波长':'feng1 zhi2 bo1 chang2', '物质的量':'wu4 zhi4 de5 liang4',
                 '速度分量':'su4 du4 fen1 liang4', '瞬态阻抗':'shun4 tai4 zu3 kang4'}
        with patch.dict(PHYSICS_PINYIN, {'瞬态阻抗':words['瞬态阻抗']}):
            for kind in ('problem','concept'):
                cue = dict(id='c',tts='。'.join([*words,'接触角','应该'])+'。')
                lesson = dict(kind=kind,pages=[dict(id='p',cues=[cue])])
                pre = check(self.root,lesson,enforce=True)
                timeline = dict(pages=[dict(id='p',cues=[dict(cue,start=1,end=9)])])
                final = identify(timeline, lesson)
                self.assertEqual([(r['id'],r['expected']) for r in pre['term_occurrences']],
                                 [(r['id'],r['expected']) for r in final])
                for term, reading in words.items():
                    matched = [r for r in final if r['term']==term]
                    self.assertEqual([r['expected'] for r in matched],
                                     [reading]*(2 if term=='接触角' else 1))
                self.assertNotIn('应该',pre['physics_terms'])

    def test_note_only_terms_conflicts_and_new_file_in_same_process(self):
        refs = self.root/'notes'
        refs.mkdir()
        first = refs/'ying-xiaolv-101.md'
        first.write_text('| 词语 | 讲课读音 | 原片位置 |\n| --- | --- | --- |\n'
                         '| 合成波阻抗 | he2 cheng2 bo1 zu3 kang4 | 00:02 |\n'
                         '| 模态驻距 | 待听 | 00:03 |\n')
        cue = dict(id='a',tts='测量合成波阻抗。模态驻距。')
        lesson = dict(pages=[dict(id='p',cues=[cue])])
        with patch('classroom_terms.NOTES',refs):
            first_pass = check(self.root,lesson)
            self.assertEqual(set(first_pass['terms_needing_readings']),{'模态驻距'})
            self.assertEqual(first_pass['physics_terms']['合成波阻抗'],1)
            # An independent lesson may supply another reading, in a different column order.
            folder = refs/'term-glossaries'
            folder.mkdir()
            (folder/'optics.md').write_text('| 拼音 | 术语 |\n| --- | --- |\n'
                                            '| he2 cheng2 bo1 zu3 gang4 | 合成波阻抗 |\n')
            report = check(self.root,lesson)
            self.assertEqual(set(report['terms_needing_readings']),{'合成波阻抗','模态驻距'})
            with self.assertRaises(ValueError):
                check(self.root,lesson,enforce=True)
            lesson['speech'] = {'physics_terms':{'合成波阻抗':'he2 cheng2 bo1 zu3 kang4',
                                                  '模态驻距':'mo2 tai4 zhu4 ju4'}}
            self.assertFalse(check(self.root,lesson,enforce=True)['terms_needing_readings'])

    def test_unknown_compound_suggested_then_tracked_even_before_its_definition(self):
        cue = dict(id='a', tts='求出校样条纹长度。校样条纹长度随密度改变。')
        lesson = dict(pages=[dict(id='p',cues=[cue])])
        pending = check(self.root,lesson)
        self.assertEqual(len(pending['term_candidates']['校样条纹长度']),2)
        cue['tts'] += '这个距离简称校样条纹长度，代入上式。'
        pending = check(self.root,lesson)
        self.assertEqual(len(pending['terms_needing_readings']['校样条纹长度']),3)
        lesson['speech'] = {'physics_terms':{'校样条纹长度':'jiao4 yang4 tiao2 wen2 chang2 du4'}}
        ready = check(self.root,lesson,enforce=True)
        self.assertEqual(ready['physics_terms']['校样条纹长度'],3)
        self.assertNotIn('校样条纹长度',ready['term_candidates'])

    def test_cut_in_word_blocks_before_synthesis_in_both_kinds(self):
        for kind in ('concept','problem'):
            lesson = dict(kind=kind,pages=[dict(cues=[
                dict(id='a',tts='图中的电'),dict(id='b',tts='压差。桥 接支路。')])])
            with self.assertRaises(ValueError):
                check(self.root,lesson,enforce=True)
            info = json.loads((self.root/'feedback-check.json').read_text())
            self.assertEqual({r['term'] for r in info['term_occurrences'] if r['split_in_script']},
                             {'电压差','电压','桥接'})
            lesson['pages'][0]['cues'] = [dict(id='a',tts='图中的电压差。桥接支路。')]
            self.assertNotEqual(check(self.root,lesson,enforce=True)['status'],'blocked')

    def test_word_in_formula_reading_and_no_cross_punctuation(self):
        rows = identify(dict(pages=[dict(cues=[dict(id='q', tts='式子',spoken_tts='电压差。桥，接着算。')])]))
        self.assertIn('电压差',term_counts(rows))
        self.assertNotIn('桥接',term_counts(rows))

    @unittest.skipUnless(shutil.which('ffmpeg'),'requires FFmpeg')
    def test_same_words_different_sound_independent_status_and_invalidation(self):
        media = self.root/'video.mp4'
        wav = self.root/'fixture.wav'
        def render(freq):
            signal = array('h',(round(2500*math.sin(i*2*math.pi*freq/RATE)) for i in range(RATE*2)))
            signal[round(1.32*RATE):round(1.61*RATE)] = array('h',[0])*(round(1.61*RATE)-round(1.32*RATE))
            with wave.open(str(wav),'wb') as out:
                out.setparams((1,2,RATE,0,'NONE','not compressed'))
                out.writeframes(signal.tobytes())
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-c:a','aac',str(media)],check=True)
        render(320)
        cue = dict(id='c',start=0,end=2,tts='桥接，桥接。',words=[
            dict(text='桥接',start=.1,end=.8),dict(text='桥接',start=1.15,end=1.9)])
        timeline = dict(pages=[dict(cues=[cue])])
        report = inspect(self.root,timeline,media,clips=True)
        a,b = report['items']
        self.assertEqual(a['clip'],b['clip'])
        self.assertEqual([a['pause_candidate'],b['pause_candidate']],[False,True])
        self.assertEqual(report['remaining'],2)
        evidence = {a['id']:[a['token'],'qiao2 jie1','joined'], b['id']:[b['token'],'qiao2 jie1','broken']}
        report = inspect(self.root,timeline,media,hearings=evidence)
        self.assertEqual(report['remaining'],1)
        manifest = self.root/'delivery-files.json'
        manifest.write_text(json.dumps({'video':'video.mp4'}))
        refresh_manifest(self.root,report)
        self.assertEqual(json.loads(manifest.read_text())['term_review']['remaining'],1)
        evidence[b['id']] = [b['token'],'qiao2 jie4','joined']
        self.assertFalse(inspect(self.root,timeline,media,hearings=evidence)['items'][1]['passed'])
        cue['words'] = []
        fallback = inspect(self.root,timeline,media)['items'][0]
        self.assertIsNone(fallback['interior_quiet_ms'])
        self.assertFalse(fallback['passed'])
        cue['words'] = [dict(text='桥接',start=.1,end=.8),dict(text='桥接',start=1.15,end=1.9)]
        render(380)
        with self.assertRaises(ValueError):
            inspect(self.root,timeline,media,hearings=evidence)
        self.assertEqual(inspect(self.root,timeline,media)['remaining'],2)

    def test_only_interior_silence_counts(self):
        voice = array('h',[1600])*(RATE//4)
        quiet = array('h',[0])*(RATE//4)
        for syllables in (2,3):
            self.assertEqual(acoustic_gap((quiet+voice*syllables+quiet).tobytes()),0)
            self.assertGreaterEqual(acoustic_gap((voice*(syllables-1)+quiet+voice).tobytes()),240)


if __name__ == '__main__':
    unittest.main()
