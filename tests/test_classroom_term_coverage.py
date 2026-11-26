import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from classroom_probe import locate, probe_terms
from classroom_terms import compile_cards, learning_cards, note_readings
from feedback_bank import check
from term_flow import identify, inspect, term_counts
from tone_review import _digest
from term_inventory import text_digest


class ClassroomTermCoverageTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)

    def test_learned_reference_types_and_missing_terms_in_ordinary_sentence(self):
        notes=self.root/'notes'
        notes.mkdir()
        (notes/'ying-xiaolv-042.md').write_text('# 热学课\n## 做量热实验\n'
            '| 词语 | 拼音 | 原片时间 |\n|---|---|---|\n| 比热容 | bi3 re4 rong2 | 00:17:09 |\n\n'
            '| 词语 | 建议拼音 | 题目或用法 |\n|---|---|---|\n| 量热器 | liang2 re4 qi4 | 装水的容器 |\n')
        data={'pages':[{'id':'p','cues':[{'id':'c','tts':'把试样放入量热器，标出焓轮，再求比热容和比热容。',
                                           'actions':[{'type':'text','text':'焓轮'}]}]}]}
        with patch('classroom_terms.NOTES', notes):
            report=check(self.root,data)
            self.assertIn('焓轮',report['term_candidates'])
            self.assertIn('焓轮',''.join(x['text'] for x in report['term_script_inventory'][0]['unmatched']))
            with self.assertRaisesRegex(ValueError,'反馈检查'):
                check(self.root,data,enforce=True)
            data['speech']={'physics_terms':{'焓轮':'han2 lun2'}}
            report=check(self.root,data,enforce=True)
            self.assertEqual(report['physics_terms']['比热容'],2)
            self.assertEqual(report['classroom_cards']['焓轮']['scope'],'this_lesson')
            self.assertIn('焓轮',report['classroom_cards']['焓轮']['lesson_example'])
            cards=report['classroom_cards']
            self.assertEqual(cards['比热容']['readings'], ['bi3 re4 rong2'])
            self.assertIn('装水的容器',cards['量热器']['contexts'])
            self.assertNotIn('00:17:09',json.dumps(cards,ensure_ascii=False))

    def test_cards_outlive_the_learning_material_and_still_work_in_new_sentences(self):
        notes=self.root/'references'
        notes.mkdir()
        entry=notes/'ying-xiaolv-101.md'
        entry.write_text('# 老师的课\n视频已整理，位置 00:10:44。\n'
            '| 术语 | 拼音 | 例句 | 连读 | 原片位置 |\n|---|---|---|---|---|\n'
            '| 试验磁环 | shi4 yan4 ci2 huan2 | 试验磁环穿过线圈。 | 磁环连读。 | 00:10:44 |\n')
        archive=self.root/'cards.json'
        compiled=compile_cards(notes, archive)
        entry.unlink()
        self.assertEqual(compile_cards(notes, archive),compiled)
        with patch('classroom_terms.NOTES',notes),patch('classroom_terms.ARCHIVE',archive):
            self.assertEqual(note_readings()['试验磁环'],{'shi4 yan4 ci2 huan2'})
            data={'pages':[{'id':'p','cues':[{'id':'c','tts':'取试验磁环，再取一个试验磁环。'}]}]}
            report=check(self.root,data)
            self.assertEqual(report['physics_terms']['试验磁环'],2)
            card=report['classroom_cards']['试验磁环']
            self.assertEqual((card['example'],card['flow']),('试验磁环穿过线圈。','磁环连读。'))
            for value in ('00:10:44','ying-xiaolv',str(self.root)):
                self.assertNotIn(value,archive.read_text())

    def test_one_context_exclusion_expires_with_rewritten_spoken_text(self):
        text='绿线电流为负，三相线电流要单独计算。'
        cue={'id':'c','tts':text}
        data={'pages':[{'id':'p','cues':[cue]}]}
        (self.root/'term-inventory.json').write_text(json.dumps({'items':[
            dict(page='p',cue='c',sha256=text_digest(text),extra_terms=[],
                 exclude=[dict(term='线电流',offset=1,reason='指绿线中的电流')])]}))
        first=check(self.root,data)
        self.assertEqual(first['physics_terms']['线电流'],1)
        self.assertTrue(first['term_script_inventory'][0]['reviewed'])
        cue['tts'] += '再比较。'
        updated=check(self.root,data)
        self.assertEqual(updated['physics_terms']['线电流'],2)
        self.assertFalse(updated['term_script_inventory'][0]['reviewed'])

    def test_updated_card_reopens_only_its_own_hearing(self):
        media=self.root/'video.mp4'
        media.write_bytes(b'unchanged final audio fixture')
        data={'pages':[{'id':'p','cues':[dict(id='c',tts='桥接，电压差。',start=0,end=1)]}]}
        cards=learning_cards(identify(data))
        def decode(*args,stdout,**kwargs):
            stdout.write(bytes(32000))
        with patch('term_flow.subprocess.run',side_effect=decode),patch('term_flow.learning_cards',return_value=cards):
            initial=inspect(self.root,data,media,clips=True)
            verdicts={r['id']:[r['token'],r['expected'],'joined'] for r in initial['items']}
            self.assertEqual(inspect(self.root,data,media,hearings=verdicts)['remaining'],0)
            cards['桥接']['flow']='听“桥”到“接”的衔接，留意词内重新起音。'
            again=inspect(self.root,data,media)
            self.assertEqual([r['term'] for r in again['items'] if not r['passed']],['桥接'])

    def test_same_spelling_per_occurrence_in_the_same_sentence(self):
        data={'pages':[{'id':'p','cues':[{'id':'c','tts':'沿轴的分量与日常说的分量。'}]}],
              'speech':{'term_uses':[dict(page='p',cue='c',term='分量',occurrence=2,reading='fen4 liang5')]}}
        found=[r['expected'] for r in identify(data) if r['term']=='分量']
        self.assertEqual(found,['fen1 liang4','fen4 liang5'])
        data['speech']['term_uses'][0]['occurrence']=3
        with self.assertRaisesRegex(ValueError,'词次'):
            identify(data)

    def test_repeated_terms_checked_independently_without_target_tones_for_alignment(self):
        cue=dict(id='c',tts='加速度和加速度。',start=0,end=2)
        data={'pages':[{'id':'p','cues':[cue]}]}
        rows=[r for r in identify(data) if r['term']=='加速度']
        phones=[('jia1',.10),('su4',.26),('du4',.40),('he2',.60),('jia1',.93),('su3',1.08),('du4',1.20)]
        checked=locate(rows,[phones,phones])
        self.assertEqual([r['status'] for r in checked],['supports_target','possible_mismatch'])
        self.assertEqual(checked[1]['heard_windows'][0]['syllables'],['jia1','su3','du4'])
        self.assertEqual([r['status'] for r in locate(rows,[phones,phones[:4]])],['needs_listening']*2)
        rate=dict(rows[0],term='速率',expected='su4 lü4')
        phones_rate=[('su4',.1),('lv4',.2)]
        self.assertEqual(locate([rate],[phones_rate,phones_rate])[0]['status'],'supports_target')
        for r in rows:r.update(timing='word',start=0,end=.50)
        self.assertEqual([r['status'] for r in locate(rows,[phones,phones])],['needs_listening']*2)

    def test_probes_cover_every_occurrence_with_one_decoding_per_cue_and_verified_cache(self):
        data={'pages':[{'id':'p','cues':[dict(id='c',tts='加速度和加速度。',start=0,end=1.7)]}]}
        rows=identify(data)
        for i,r in enumerate(rows):r.update(passed=(i==0),token=str(i))
        media=self.root/'fixture'
        media.write_bytes(b'bound to this delivery')
        terms=dict(items=rows,terms=term_counts(rows),file=str(media),sha256=_digest(media),
                   classroom_cards=learning_cards(rows))
        tokens=[('jia1',.1),('su4',.3),('du4',.5),('he2',.7),('jia1',1.0),('su4',1.2),('du4',1.4)]
        with patch('classroom_probe.subprocess.run'),patch('speech_probe.model_signature',return_value='m'),patch('speech_probe.model'),\
             patch('classroom_probe.decode_sentence',return_value=[tokens,tokens]) as decode:
            first=probe_terms(self.root,terms,media,self.root)
            self.assertEqual(first['total'],len(rows))
            self.assertEqual({r['id'] for r in first['items']},{r['id'] for r in rows})
            self.assertEqual(first['listened'],1)
            self.assertEqual(probe_terms(self.root,terms,media,self.root),first)
            self.assertEqual(decode.call_count,1)
            rows[0]['token']='new'
            probe_terms(self.root,terms,media,self.root)
            self.assertEqual(decode.call_count,1)
            media.write_bytes(b'replaced')
            with self.assertRaisesRegex(ValueError,'不匹配'):
                probe_terms(self.root,terms,media,self.root)
