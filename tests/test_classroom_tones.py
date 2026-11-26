import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from delivery import inspect_script
from feedback_bank import check, record
from pronunciation import local_tts_text, matched_pronunciations, minimax_dictionary, tone_targets
import tone_review


class ClassroomTones(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name)
        env = patch.dict(os.environ, PHYSICS_NOTEBOOK_FEEDBACK_DB=str(self.project/'personal.db'))
        env.start()
        self.addCleanup(env.stop)

    def test_reading_in_the_actual_input_and_preserved_student_script(self):
        sentence = '从哪里测量？从地心量起。测量的量，是一个物理量。'
        for kind in ('concept', 'problem'):
            lesson = {'kind': kind, 'speech': {'backend': 'user'}, 'pages': [
                {'cues': [{'id': 'c', 'tts': sentence}]}]}
            inputs = inspect_script(lesson)['tts_inputs'][0]
            self.assertEqual(inputs['text'], '从哪里测梁？从地心梁起。测梁的亮，是一个物理量。')
            self.assertEqual(inputs['script'], sentence)
            plan = check(self.project, lesson)['tone_targets']
            self.assertEqual([t['expected'].split()[-1] for t in plan],
                             ['liang2', 'liang2', 'liang2', 'liang4', 'liang4'])
            self.assertEqual(len({t['offset'] for t in plan}), 5)
        self.assertIn('测量/(ce4)(liang2)', minimax_dictionary(inputs['pinyin'])['tone'])

    def test_z_and_liang_are_checked_together_in_each_sentence(self):
        sentences = ['角度从正 z 轴朝右量。', '磁矩的 z 分量。']
        cues = [dict(id=str(i), tts=s) for i, s in enumerate(sentences)]
        plan = check(self.project, {'kind': 'problem', 'pages': [dict(id='p', cues=cues)]})
        z_cues = {h['cue'] for h in plan['listen'] if h['bank']=='letters' and h['key']=='Z'}
        self.assertEqual(z_cues, {'0', '1'})
        tones = {(h['cue'], h['term']): h['expected'] for h in plan['tone_targets']}
        self.assertEqual(tones['0','朝右量'], 'chao2 you4 liang2')
        self.assertEqual(tones['1','分量'], 'fen1 liang4')
        self.assertEqual(tone_targets('这句话的分量很重。')[0]['expected'],'fen4 liang5')
        self.assertIsNone(tone_targets('再看这个分量。')[0]['expected'])

    def test_boundary_and_recurrence(self):
        sentence = '从这个频率量出频差。能量出现变化。用新的量筒。预测量子态。'
        text = local_tts_text(sentence, matched_pronunciations(sentence))
        self.assertEqual(text, '从这个频率梁出频差。能量出现变化。用新的梁筒。预测量子态。')
        self.assertIsNone(tone_targets('这里量一下。')[0]['expected'])
        self.assertEqual(matched_pronunciations('系数清楚，数清个数。'),
                         {'系数':'xi4 shu4', '数清':'shu3 qing1', '个数':'ge4 shu4'})
        record('polyphones','从原点量','说了第四声',expected='cong2 yuan2 dian3 liang2')
        phrase = '从原点量'
        self.assertEqual(local_tts_text(phrase, matched_pronunciations(phrase)), '从原点梁')
        self.assertEqual(local_tts_text(phrase, matched_pronunciations(phrase), cue={phrase: None}), phrase)
        self.assertEqual(tone_targets('速度分量，取一个分量。')[1]['expected'], None)
        record('polyphones','行列式','第一字发音有误',expected='hang2 lie4 shi4')
        self.assertEqual(tone_targets('行列式的行列式')[1]['expected'], 'hang2 lie4 shi4')

    def test_unreported_terms_new_context_and_feedback_generalization(self):
        sentence = '矩阵第一行和行波。重力与重合。相位与相乘。'
        expected = ['ju3 zhen4 di4 yi1 hang2','xing2 bo1','zhong4 li4','chong2 he2','xiang4 wei4','xiang1 cheng2']
        self.assertEqual([r['expected'] for r in tone_targets(sentence)], expected)
        record('polyphones','停泊','作者指出泊读音有误',expected='ting2 bo2',focus='泊')
        self.assertEqual([(r['term'],r['expected']) for r in tone_targets('停泊，湖泊。')],
                         [('停泊','ting2 bo2'),('泊',None)])
        self.assertEqual(local_tts_text('湖泊',matched_pronunciations('湖泊')), '湖泊')
        record('polyphones','停泊','另存一次定位',focus='停')
        self.assertEqual([x['term'] for x in tone_targets('湖泊，停下。')], ['泊','停'])
        with self.assertRaises(ValueError):
            record('polyphones','停泊','记录错字',focus='湖')
        self.assertEqual(tone_targets('湖泊',cue_overrides={'湖泊':'hu2 po1'})[0]['expected'],'hu2 po1')
        self.assertEqual(tone_targets('倒数。')[0]['expected'],None)
        self.assertEqual([h['expected'] for h in tone_targets('求倒数，倒数第二。')],
                         ['qiu2 dao4 shu4', 'dao4 shu3 di4 er4'])
        self.assertEqual(matched_pronunciations('两条曲线。')['曲线'],'qu1 xian4')
        for k, hint in [('chu1 xiang4 wei4','初向位'),('chu1 xiang1 wei4','初相位')]:
            self.assertEqual(local_tts_text('初相位',{'初相位':k}),hint)
        self.assertEqual(local_tts_text('初相位',{'初相位':'chu1 xiang4 wei4'},cue={'相位':None}), '初相位')

    def test_same_inventory_at_both_stages_and_official_conflict_before_synthesis(self):
        sentences = ['频率、功率、曲率。','这里要调一下。','两条曲线相交。','看载流导线。','从哪里测量？',
                     '重合的位置。','数清次数。','弹簧的长度。','两根切线。','矩阵第一行。']
        cues = [dict(id=str(i),tts=t,start=i,end=i+1) for i,t in enumerate(sentences)]
        lesson = {'kind':'concept','pages':[{'id':'p','cues':cues}]}
        report = check(self.project,lesson)
        final = tone_review.targets(lesson)
        self.assertEqual([(x['term'],x['expected']) for x in report['tone_targets']],
                         [(x['term'],x['expected']) for x in final])
        self.assertLessEqual(len(report['pronunciation_trial']), 6)
        self.assertGreater(len(report['pronunciation_trial']), 0)
        self.assertTrue(all(x['context'] in sentences for x in report['pronunciation_trial']))
        cues[0]['minimax_pronunciation'] = {'频率':'pin2 shuai4'}
        with self.assertRaises(ValueError):
            check(self.project,lesson,enforce=True)

    def test_word_specific_characters_in_classroom_prose(self):
        sentence = '应该处理此处的反应；还原后还有奇数个。'
        rows = tone_targets(sentence)
        chars = [(x['char'], x['reading']) for row in rows for x in row['characters']]
        self.assertEqual(chars, [('应','yīng'),('处','chǔ'),('处','chù'),('应','yìng'),
                                 ('还','huán'),('还','hái'),('奇','jī'),('数','shù')])
        for row in rows:
            for x in row['characters']:
                self.assertEqual(sentence[x['offset']], x['char'])
        self.assertEqual(tone_targets('矩阵的行和列')[0]['characters'][0]['reading'], 'háng')
        self.assertNotIn('矩阵的行', matched_pronunciations('矩阵的行为随参数变化'))
        self.assertEqual(tone_targets('暂且还给谁？')[0]['characters'][0]['reading'], None)
        self.assertEqual(tone_targets('两个相似的图形。')[0]['term'],'相似')

    def test_nested_wrong_character_blocks_both_course_kinds(self):
        text = '先处理数据'
        for kind in ('concept','problem'):
            c = dict(id='read',tts=text,start=0,end=2,
                     minimax_pronunciation={text:'xian1 chu4 li3 shu4 ju4'})
            lesson = dict(kind=kind,pages=[{'id':'p','cues':[c]}])
            with self.assertRaises(ValueError):
                check(self.project,lesson,enforce=True)
            row, = tone_review.targets(lesson)
            self.assertEqual(row['conflicts'],[dict(word='处理',char='处',offset=1,
                                                   expected='chu3',configured='chu4')])
            self.assertEqual(row['expected'],'xian1 chu3 li3 shu4 ju4')
            self.assertEqual(inspect_script(lesson)['tts_inputs'][0]['tone_targets'][0]['conflicts'], row['conflicts'])
            c['minimax_pronunciation'][text] = 'xian1 chu3 li3 shu4 ju4'
            self.assertFalse(tone_review.targets(lesson)[0]['conflicts'])
            self.assertNotEqual(check(self.project, lesson, enforce=True)['status'], 'blocked')

    @unittest.skipUnless(shutil.which('ffmpeg'), 'requires FFmpeg')
    def test_review_uses_the_selected_media_and_each_occurrence(self):
        media = self.project/'sample.mp4'
        def make_media(frequency):
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i',
                            f'sine=frequency={frequency}:duration=2', '-c:a', 'aac', str(media)], check=True)
        make_media(750)
        timeline = {'pages': [{'id':'p','start':0,'cues':[
            {'id':'c','start':0,'end':2,'tts':'测量，测量。'}]}]}
        data = tone_review.inspect(self.project, timeline, media)
        self.assertEqual(data['remaining'], 2)
        first, second = (r['id'] for r in data['items'])
        self.assertEqual(data['producer_queue'], [dict(page='p', cue='c', listen_id=first,
                                                      items=[first, second], needs_retake=False)])
        data = tone_review.inspect(self.project, timeline, media, select=first, clip=True, heard='ce4 liang4')
        self.assertTrue(Path(data['clip']).is_file())
        self.assertEqual(data['items'][0]['status'], 'needs_retake')
        self.assertTrue(data['producer_queue'][0]['needs_retake'])
        self.assertEqual(data['items'][0]['character_results'],
                         [dict(char='量',offset=1,expected='liang2',heard='liang4',matches=False)])
        self.assertEqual(data['remaining'], 2)
        data = tone_review.inspect(self.project, timeline, media, select=first, cue_clip=True,
                                   hearings={first:{'heard':'ce4 liang2'}})
        self.assertEqual(data['remaining'], 1)
        self.assertEqual(data['producer_queue'][0]['items'], [second])
        self.assertEqual([x['id'] for x in data['cue_items']], [first, second])
        self.assertTrue(Path(data['clip']).is_file())
        with self.assertRaises(ValueError):
            tone_review.inspect(self.project, timeline, media, select=second,
                                hearings={'other':{'heard':'ce4 liang2'}})
        data = tone_review.inspect(self.project, timeline, media, select=second,
                                   hearings={second:{'heard':'ce4 liang2'}})
        self.assertEqual(data['remaining'], 0)
        self.assertEqual(data['producer_queue'], [])
        make_media(850)
        self.assertEqual(tone_review.inspect(self.project, timeline, media)['remaining'], 2)
        timeline['pages'][0]['cues'][0]['tts'] = '量一下。'
        item = tone_review.inspect(self.project, timeline, media)['items'][0]
        with self.assertRaises(ValueError):
            tone_review.inspect(self.project, timeline, media, select=item['id'], heard='liang2')
        data = tone_review.inspect(self.project, timeline, media, select=item['id'], heard='liang2', intended='liang2')
        self.assertEqual(data['remaining'], 0)


if __name__ == '__main__':
    unittest.main()
