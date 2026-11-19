import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from feedback_bank import catalog, check, history, record
from pronunciation import local_tts_text, matched_pronunciations
from terminology_review import inspect_terminology


class ViewerFeedback(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root/'profile'/'feedback.sqlite3'
        env = patch.dict(os.environ, PHYSICS_NOTEBOOK_FEEDBACK_DB=str(self.db))
        env.start()
        self.addCleanup(env.stop)
        self.project = self.root/'second-course'
        self.project.mkdir()
        self.lesson = {'kind':'concept','title':'波的叠加','pages':[{'id':'p','cues':[
            {'id':'a','text':'看x、相位和长度。'}, {'id':'b','text':'取 X；单位是 m。'}]}]}
        (self.project/'lesson.json').write_text(json.dumps(self.lesson,ensure_ascii=False))

    def test_append_deduplicate_and_share_across_lessons_and_processes(self):
        self.assertFalse(self.db.exists())
        self.assertIn('X', catalog()['letters'])
        self.assertFalse(self.db.exists())
        def submit(location):
            return record('letters','x','字母含混',lesson='第一课',at=location)
        self.assertTrue(submit('01:01')['recorded'])
        self.assertFalse(submit('01:01')['recorded'])
        self.assertTrue(submit('02:02')['recorded'])
        self.assertEqual([e['at'] for e in history()], ['01:01','02:02'])
        record('issues','opening-copy','开场说套话',expected='从题图开始',match='看x')
        record('issues','problem-only','只涉及题卡',scope='problem')
        p = subprocess.run([sys.executable,str(SCRIPTS/'course.py'),'feedback-check',str(self.project)],
                           capture_output=True,text=True,check=True)
        result = json.loads(p.stdout)
        self.assertIn('opening-copy', {item['key'] for item in result['findings']})
        self.assertNotIn('problem-only', {item['key'] for item in result['manual_checks']})
        self.assertEqual([(h['key'],h['cue']) for h in result['listen'] if h['bank']=='letters'], [('X','a'),('X','b')])

    def test_new_term_enters_tts_and_recorded_voice_audit(self):
        term = '行程'
        record('polyphones',term,'第一字读错')
        self.assertNotIn(term,matched_pronunciations(term))
        record('polyphones',term,'读成 háng',expected='xing2 cheng2',hint='形程')
        terms = matched_pronunciations('行程和长度')
        self.assertEqual(terms[term],'xing2 cheng2')
        self.assertEqual(local_tts_text('行程和长度',terms),'形程和常度')
        data = {'pages':[{'id':'p','start':1,'cues':[{'id':'c','tts':'行程和x','start':0,'end':2}]}]}
        audit,_ = inspect_terminology(data)
        self.assertEqual([(x['term'],x['reference_reading'],x['start']) for x in audit['items']],
                         [('行程','xing2 cheng2',1),('x','X /ɛks/',1)])
        self.assertTrue(all('viewer_feedback' in x['categories'] for x in audit['items']))
        self.assertEqual(data['pages'][0]['cues'][0]['tts'],'行程和x')

    def test_conflict_in_external_script_blocks_formal_build_before_tts(self):
        (self.project/'speech-plan.json').write_text(json.dumps({'version':1,'cues':{
            'a':{'minimax_pronunciation':{'长度':'zhang3 du4'}}}}))
        for cmd in (['feedback-check'],['build'],['render']):
            args = [sys.executable,str(SCRIPTS/'course.py'),*cmd,str(self.project)]
            if cmd==['render']: args.extend(['--renderer','notebook'])
            result = subprocess.run(args,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            report = json.loads((self.project/'feedback-check.json').read_text())
            self.assertEqual(report['status'],'blocked')
            self.assertEqual(report['findings'][0]['cue'],'a')
            if cmd!=['feedback-check']: self.assertIn('feedback-check.json',result.stderr)
        self.assertFalse((self.project/'narration.wav').exists())

    def test_single_hanzi_never_forces_another_word_and_local_hint_conflicts_are_visible(self):
        with self.assertRaises(ValueError):
            record('polyphones','相','相位中读错',expected='xiang4',hint='向')
        record('polyphones','相','缺少上下文，待听')
        text = '相干光相遇后相乘。'
        self.assertEqual(local_tts_text(text,matched_pronunciations(text)),text)
        record('polyphones','衍射','第一字读错',expected='yan3 she4',hint='眼射')
        record('polyphones','衍射','另一课再发生',expected='yan3 she4')
        self.assertEqual(catalog()['polyphones']['衍射']['hint'],'眼射')
        self.lesson['pages'][0]['cues'][0]['text'] = '这里说的是衍射和衍射角。'
        self.lesson['speech'] = {'plain_pronunciation':{'衍射':'延射'}}
        (self.project/'lesson.json').write_text(json.dumps(self.lesson))
        report = check(self.project)
        self.assertEqual([(r['key'],r['severity']) for r in report['findings']], [('衍射','review')])
        self.assertIn('延射',report['findings'][0]['message'])

    def test_retimed_external_take_and_repeat_report_with_restored_tempo(self):
        self.lesson['pages'][0]['cues'][0]['audio'] = 'take.wav'
        (self.project/'lesson.json').write_text(json.dumps(self.lesson))
        meta = self.project/'take.json'
        meta.write_text('{"raw_file":"raw.wav","tempo":0.6}')
        self.assertEqual(check(self.project)['findings'][0]['key'],'pacing')
        meta.write_text('{"raw_file":"raw.wav","tempo":1}')
        self.assertNotEqual(check(self.project)['status'],'blocked')
        record('letters','X','发音含混',expected='X /ɛks/')
        with self.assertRaises(ValueError):
            record('letters','x','发音含混',expected='横坐标')

if __name__ == '__main__':
    unittest.main()
