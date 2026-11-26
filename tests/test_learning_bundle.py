from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from feedback_bank import applicable_issues, catalog, check, history, preparation, record
from feedback_review import decide, decisions
from learning_bundle import DB_REL, ROOT, merge, resolve_sample, sync_cards


class PortableLearning(unittest.TestCase):
    def test_move_then_update_preserves_scope_sound_and_what_to_check_next_time(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'first'/'feedback.sqlite3'
            dest=root/'moved'/'feedback.sqlite3'
            sample=root/'original.wav'
            sample.write_bytes(b'short listening comparison')
            voice={'model':'fixture','reference_sha256':'e'*64}
            with patch.dict(os.environ,PHYSICS_NOTEBOOK_FEEDBACK_DB=str(source)):
                record('issues','label-direction','这张图上一处箭头画反了',lesson='原题',
                       only_this_lesson=True,takeaway='对照图中正方向和推导第一行的符号。')
                record('letters','F','字母和后面的中文断开')
                decide('letters','F','adopted','all','整句比较','已在该音色试听',sample=sample,**voice)
            with patch.dict(os.environ,PHYSICS_NOTEBOOK_FEEDBACK_DB=str(dest)):
                record('issues','keep-on-update','已有独立反馈')
                result=merge(source,dest)
                self.assertEqual(result,{'reports_added':2,'decisions_added':1})
                self.assertEqual(merge(source,dest),{'reports_added':0,'decisions_added':0})
                shutil.rmtree(source.parent)
                sample.unlink()
                lesson={'kind':'concept','title':'另一课','pages':[{'id':'p','cues':[
                        {'id':'v','tts':'用 F 表示这个力。'}]}],'speech':{'feedback_voice':voice}}
                brief=preparation(root,lesson)
                self.assertIn('推导第一行',(root/brief['file']).read_text())
                self.assertNotIn('这张图上一处箭头画反了',(root/brief['file']).read_text())
                self.assertEqual(history(lesson='原题')[0]['lesson'],'原题')
                item=next(i for i in check(root,lesson)['replay'] if i['key']=='F')
                self.assertEqual(item['status'],'apply_and_check')
                self.assertEqual(hashlib.sha256(Path(item['reference_sample']).read_bytes()).hexdigest(),
                                 decisions(dest)[0]['sample_sha256'])
                self.assertIn('keep-on-update',catalog()['issues'])
                self.assertTrue(resolve_sample(dest,decisions(dest)[0]['sample']).is_relative_to(dest.parent))

    def test_previously_reported_sound_and_writing_errors_apply_to_both_lesson_types(self):
        common={'stalled-speech','rushed-noisy-join','letter-in-sentence',
                'simultaneous-formula-writing','formula-without-speaking'}
        with patch.dict(os.environ,PHYSICS_NOTEBOOK_FEEDBACK_DB=str(ROOT/DB_REL)):
            for kind in ('concept','problem'):
                active={r['key'] for r in applicable_issues({'kind':kind})}
                self.assertTrue(common <= active, common-active)

    def test_both_card_collections_travel_with_update(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=(Path(folder)/n for n in ('a.json','b.json'))
            a.write_text(json.dumps({'schema':1,'cards':{'质量':{'contexts':['甲']}}}))
            b.write_text(json.dumps({'schema':1,'cards':{'位矢':{},'质量':{'contexts':['乙']}}}))
            sync_cards(a,b)
            cards=json.loads(b.read_text())['cards']
            self.assertIn('位矢',cards)
            self.assertEqual(set(cards['质量']['contexts']),{'甲','乙'})
