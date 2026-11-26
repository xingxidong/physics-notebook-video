import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from feedback_bank import catalog, check, history, record
from feedback_review import compare_audio, decide, decisions


class LearningBetweenLessons(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.db = self.root/'private'/'feedback.sqlite3'
        env = patch.dict(os.environ, PHYSICS_NOTEBOOK_FEEDBACK_DB=str(self.db))
        env.start()
        self.addCleanup(env.stop)
        self.lesson = {'kind':'concept', 'title':'电场力的功', 'pages':[{'id':'p1','cues':[
            {'id':'a','text':'看这条虚线，这是电场强度的水平分量。'},
            {'id':'b','text':'把电场力的功记作 W。'}]}]}
        self.wav = self.root/'A.wav'
        with wave.open(str(self.wav),'wb') as clip:
            clip.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            clip.writeframes(b'\x00\x10' * 2400)
        self.voice = {'model':'local-tts','reference_sha256':'2'*64}

    def review(self, state='adopted', **kwargs):
        data = dict(kind='letters', key='w', state=state, scope='all', action='选 A',
                    before='B 拆开了', example='记作 W', evidence='作者听过完整句', **self.voice)
        data.update(kwargs)
        if state == 'adopted':
            data.setdefault('sample', self.wav)
        return decide(**data)

    def test_selection_scope_history_retry_and_changed_or_missing_sample(self):
        first = self.review()
        self.assertEqual(self.review(), dict(id=first['id'], recorded=False))
        self.assertEqual(history(), [])  # a decision on an installed seed can be the first DB write
        report = check(self.root, self.lesson)
        self.assertEqual([(i['status'], i['cues']) for i in report['replay']],
                         [('audition_voice', [{'page':'p1','cue':'b'}])])
        self.assertNotIn('reference_sample', report['replay'][0])
        self.lesson['speech'] = {'feedback_voice':dict(self.voice)}
        entry = check(self.root, self.lesson)['replay'][0]
        sample=Path(entry['reference_sample'])
        self.assertEqual(entry['status'],'apply_and_check')
        self.assertEqual(sample.read_bytes(),self.wav.read_bytes())
        self.review('trial', action='再比较 C')
        self.assertEqual([i['status'] for i in check(self.root, self.lesson)['replay']], ['apply_and_check','compare'])
        self.wav.unlink()
        self.assertEqual(check(self.root,self.lesson)['replay'][0]['status'],'apply_and_check')
        sample.write_bytes(b'changed')
        self.assertEqual(check(self.root, self.lesson)['replay'][0]['status'], 'restore_or_audition')
        sample.unlink()
        self.assertNotIn('reference_sample', check(self.root, self.lesson)['replay'][0])
        self.lesson['speech']['feedback_voice']['model'] = 'new-tts'
        self.assertEqual(check(self.root, self.lesson)['replay'][0]['status'], 'audition_voice')
        self.review('withdrawn', evidence='作者撤回该选择')
        self.assertEqual(check(self.root, self.lesson)['replay'], [])
        self.assertEqual([i['state'] for i in decisions(self.db)], ['adopted', 'trial', 'withdrawn'])

    def test_next_lesson_refers_to_real_frame_and_vector_word(self):
        record('issues','visible-referent','原课的手势没有出现在画面上',lesson='平抛')
        decide('issues','visible-referent','adopted','concept','首次提及时虚线已画出','逐帧对照')
        report = check(self.root, self.lesson)
        self.assertEqual(report['replay'][0]['cues'], [{'page':'p1','cue':'a'}])
        self.assertTrue(any(i['key']=='分量' and i['cue']=='a' and i['expected']=='fen1 liang4' for i in report['listen']))
        self.lesson['kind'] = 'problem'
        self.assertEqual(check(self.root, self.lesson)['replay'], [])

    def test_one_off_feedback_and_decision_stay_in_one_lesson(self):
        title = self.lesson['title']
        record('issues','one-diagram','改这幅图',lesson=title,only_this_lesson=True,match='虚线')
        decide('issues','one-diagram','trial','lesson','把两点移开','这一页标签重叠',lesson=title)
        self.assertNotIn('one-diagram',catalog()['issues'])
        self.assertEqual(check(self.root,self.lesson)['replay'][0]['key'],'one-diagram')
        self.lesson['title']='下一课'
        other=check(self.root,self.lesson)
        self.assertEqual(other['replay'], [])
        self.assertNotIn('one-diagram',{i['key'] for i in other['findings']})
        with self.assertRaises(ValueError):
            decide('issues','one-diagram','adopted','all','总是移点','本课图例')

    def test_narrow_decision_wins_and_can_be_withdrawn(self):
        base = dict(kind='issues', key='visible-referent', state='adopted', evidence='作者确认')
        decide(**base, scope='all', action='标清两端')
        decide(**base, scope='lesson', lesson=self.lesson['title'], action='先画这两条辅助线')
        self.assertEqual([r['action'] for r in check(self.root,self.lesson)['replay']], ['先画这两条辅助线'])
        decide('issues','visible-referent','withdrawn','lesson','恢复一般做法','换图',lesson=self.lesson['title'])
        self.assertEqual([r['action'] for r in check(self.root,self.lesson)['replay']], ['标清两端'])

    @unittest.skipUnless(shutil.which('ffmpeg'), 'requires ffmpeg')
    def test_audio_comparison_keeps_speed_order_and_inputs(self):
        b = self.root/'B.wav'
        with wave.open(str(b),'wb') as clip:
            clip.setparams((1,2,24000,0,'NONE',''))
            clip.writeframes(b'\x00\x20' * 4800)
        old_hash = hashlib.sha256(self.wav.read_bytes()).digest()
        pair = self.root/'AB.wav'
        subprocess.run([sys.executable,str(SCRIPTS/'feedback_bank.py'),'compare-audio',str(self.wav),str(b),
                        '--output',str(pair)], check=True,capture_output=True)
        with wave.open(str(pair),'rb') as result:
            self.assertEqual(result.getnframes(), 2400+15600+4800)
            self.assertEqual(result.readframes(2400), b'\x00\x10' * 2400)
            self.assertEqual(result.readframes(15600), b'\x00\x00' * 15600)
            self.assertEqual(result.readframes(4800), b'\x00\x20' * 4800)
        with self.assertRaises(FileExistsError):
            compare_audio(self.wav,b,pair)
        self.assertEqual(hashlib.sha256(self.wav.read_bytes()).digest(),old_hash)
