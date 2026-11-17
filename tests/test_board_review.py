import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

from board_review import check
from course import compile_lesson, prepare
from course_outline import check_lesson, timing_report
from layout import audit_lesson
from lesson_review import approve, prepare_review, require
from teaching import audit


class BoardReviewTests(unittest.TestCase):
    def fixture(self,root):
        source=json.loads((ROOT/'assets/dimension-board.json').read_text())
        source['opening']={'author':'示例作者','school':'示例学校'}
        (root/'讲义.md').write_text('样例讲义正文。\n')
        return source

    def draft(self,root,source):
        lesson,pages=compile_lesson(root,source)
        data,_,_=prepare(root,lesson,pages,argparse.Namespace(draft=True,fps=24,backend=None,voice=None))
        return lesson,pages,data

    def test_measured_board_carries_geometry_and_timings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            lesson,pages,data=self.draft(root,self.fixture(root))
            self.assertEqual(data['pages'][0]['duration'],3)
            self.assertEqual(data['pages'][0]['id'],'opening-card')
            self.assertEqual(audit_lesson(pages)['warnings'],[])
            self.assertEqual(check(lesson,pages,data)['warnings'],[])
            self.assertEqual(check_lesson(root,lesson,pages)[1],[])
            inherited=[s for s in data['pages'][2]['strokes'] if s.get('carried')]
            self.assertTrue(any(s['board_id']=='candidate' and s['end']==0 for s in inherited))
            self.assertTrue(any(s['board_group']=='cart' for s in inherited))
            result=timing_report(root,lesson,data)
            self.assertEqual(result['units'][0]['stages'][1]['planned_minutes'],.6)

    def test_motion_penetration_reports_time_and_blocks_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=self.fixture(root)
            source['pages'][0]['layout']['motion_boxes']=[
                {'cue':'compare','fraction':.5,'objects':{'block':[215,372,270,412],'track':[150,403,390,418]},
                 'disjoint':[['block','track']]}]
            lesson,pages,data=self.draft(root,source)
            report=check(lesson,pages,data)
            finding=next(x for x in report['warnings'] if x['code']=='motion-penetration')
            self.assertEqual(finding['page'],'p01')
            self.assertGreater(finding['time'],3)
            prepare_review(root,lesson,pages,report,audit_lesson(pages),audit(root,lesson,pages))
            with self.assertRaisesRegex(ValueError,'排版检查项'):
                approve(root,lesson,'测试用确认')

    def test_model_is_complete_before_first_spoken_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source={
                'title':'模型', 'opening':{'author':'示例作者'},
                'pages':[
                    {'id':'p01','layout':{'prewritten':['circuit'],'checkpoints':[
                        {'cue':'introduce','at':'start','visible':['circuit']}]},
                     'cues':[{'id':'introduce','tts':'看 A 点。','actions':[
                         {'type':'line','from':[190,220],'to':[330,220],'board_group':'circuit'},
                         {'type':'math','latex':'A','x':170,'y':195,'board_group':'circuit'},
                         {'type':'math','latex':'V_A=V_0','x':540,'y':190,'id':'voltage'}]}]},
                    {'id':'p02','layout':{'carry':['circuit']},
                     'cues':[{'id':'reuse','tts':'还是这张图。'}]},
                ],
            }
            lesson,pages,data=self.draft(root,source)
            first,second=data['pages'][-2:]
            diagram=[s for s in first['strokes'] if s.get('board_group')=='circuit']
            self.assertTrue(diagram and all(s['end']==0 for s in diagram))
            self.assertTrue(all(s['start']>=first['cues'][0]['start']
                                for s in first['strokes'] if s.get('board_id')=='voltage'))
            self.assertEqual(len(diagram),sum(s.get('carried',False) for s in second['strokes']))
            self.assertEqual(check(lesson,pages,data)['warnings'],[])

            del source['pages'][0]['layout']['prewritten']
            lesson,pages,data=self.draft(root,source)
            self.assertEqual(check(lesson,pages,data)['warnings'][0]['missing'],['circuit'])

    def test_approval_invalidated_when_script_or_cover_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=self.fixture(root)
            lesson,pages,data=self.draft(root,source)
            prepare_review(root,lesson,pages,check(lesson,pages,data),audit_lesson(pages),audit(root,lesson,pages))
            with self.assertRaisesRegex(ValueError,'等待人审'):
                require(root,lesson)
            approve(root,lesson,'测试用确认')
            require(root,lesson)
            source['pages'][0]['cues'][0]['tts']+=' 我们接着用图来判断。'
            edited,_=compile_lesson(root,source)
            with self.assertRaisesRegex(ValueError,'已更新'):
                require(root,edited)
            lesson['opening']['author']='改过的作者'
            with self.assertRaisesRegex(ValueError,'已更新'):
                require(root,lesson)


if __name__=='__main__':
    unittest.main()
