import argparse
import array
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
import contextlib
import io

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from board_review import check
from course import compile_lesson,prepare
from lesson_duration import report
from lesson_quality import run
from lesson_review import fingerprint,require_unchanged
from teaching import audit as audit_teaching
from voice_quality import audit,strict_findings
from voice import split_group
import course
import platform_install


class QualityWorkflowTests(unittest.TestCase):
    def source(self,root):
        lesson=json.loads((ROOT/'assets/dimension-board.json').read_text())
        lesson['opening']={'author':'测试作者'}
        (root/'讲义.md').write_text('学生讲义正文')
        (root/'lesson.json').write_text(json.dumps(lesson))
        return lesson

    def test_question_visibility_is_checked_without_managed_layout(self):
        lesson={'concept_units':[{'questions':[{'answer_cue':'answer','action_ids':['question']}]}]}
        pages=[{'id':'p','cues':[{'id':'answer','blocks':[]}]}]
        timeline={'draft':True,'pages':[{'id':'p','start':0,
                   'cues':[{'id':'answer','start':1,'end':8}],
                   'strokes':[{'board_id':'question','cue':'answer','action':0,'start':1,'end':3}]}]}
        result=check(lesson,pages,timeline)
        self.assertEqual(result['managed_pages'],1)
        self.assertEqual(result['warnings'][0]['missing'],['question'])
        self.assertEqual(result['warnings'][0]['time'],1)

    def test_native_scene_geometry_is_reported_as_needing_viewing(self):
        result=check({},[{'id':'p','cues':[],'native_scenes':{'manim':{'source':'scene.py'}}}],
                     {'draft':True,'pages':[{'id':'p','start':0,'cues':[],'strokes':[]}]})
        self.assertEqual(result['coverage'][0]['motion_geometry'],'needs-viewing')

    def test_balanced_total_still_detects_rushed_and_padded_sections(self):
        plan={'audience':'竞赛学生','sections':[
            {'title':title,'mode':'derive','spoken_chars':320,'reason':'讲清本段依据','pages':[pid]}
            for title,pid in [('关键消元','p1'),('代数代入','p2')]]}
        info=report(Path('.'),{'duration_plan':plan},{'draft':False,'duration':203,'pages':[
            {'id':'opening-card','duration':3},{'id':'p1','duration':40},{'id':'p2','duration':160}]})
        self.assertEqual(info['recommended_seconds'],203)
        self.assertTrue(info['sections'][0]['issues'])
        self.assertTrue(info['sections'][1]['issues'])

    def test_audio_mid_cue_gap_fails_strict_without_long_silence_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rate=8000
            signal=array.array('h',[2500])*rate*9
            signal[rate:round(1.8*rate)]=array.array('h',[0])*round(.8*rate)
            with wave.open(str(root/'narration.wav'),'wb') as wav:
                wav.setparams((1,2,rate,0,'NONE','not compressed'));wav.writeframes(signal.tobytes())
            result=audit(root,{'pages':[{'id':'p','start':0,'cues':[
                {'id':'a','start':.2,'end':2.8,'tts':'从左边这个物体开始看。'},
                {'id':'b','start':3,'end':5.8,'tts':'长度给出的是这段距离。'},
                {'id':'c','start':6,'end':8.8,'tts':'再代入刚才得到的速度。'}]}]})
            self.assertEqual(result['warnings'],[])
            self.assertTrue(strict_findings(result))
            term=next(row for row in result['listening_checks'] if row['cue']=='b')
            self.assertTrue(any('长度' in reason for reason in term['reasons']))

    def test_preview_revision_catches_script_and_asset_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.source(root)
            lesson,_=compile_lesson(root)
            expected=fingerprint(root,lesson)
            require_unchanged(root,expected)
            (root/'讲义.md').write_text('改动过的讲义')
            with self.assertRaisesRegex(ValueError,'制作期间'):
                require_unchanged(root,expected)
            (root/'讲义.md').write_text('学生讲义正文')
            source=json.loads((root/'lesson.json').read_text())
            source['pages'][0]['cues'][0]['tts']+='看看红线。'
            (root/'lesson.json').write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,'制作期间'):
                require_unchanged(root,expected)

    def test_quality_check_preserves_source_and_does_not_synthesize(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.source(root)
            before=(root/'lesson.json').read_bytes()
            with patch('voice.synth',side_effect=AssertionError('must not call TTS')):
                result=run(root,'plan')
            self.assertNotEqual(result['status'],'blocked')
            self.assertEqual(before,(root/'lesson.json').read_bytes())
            self.assertEqual(result['manual_review']['status'],'pending')
            self.assertFalse((root/'review-approval.json').exists())
            self.assertTrue((root/'制作检查.md').is_file())
            self.assertTrue(any(x['code']=='duration-unplanned' for x in result['findings']))

    def test_closure_requires_teaching_points_and_a_real_final_cue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lesson=self.source(root)
            lesson.pop('closure')
            lesson['closure_required']=True
            (root/'lesson.json').write_text(json.dumps(lesson))
            parsed,pages=compile_lesson(root)
            report=audit_teaching(root,parsed,pages)
            self.assertIn('closure-required',[row['code'] for row in report['errors']])

            lesson['closure']={
                'recap_cues':['answer'],
                'visible_action_ids':['prompt','fix-length'],
                'points':[
                    {'kind':'opening_question','text':'检查候选式的两项。'},
                    {'kind':'conclusion','text':'相加前量纲相同。'},
                    {'kind':'application','text':'用量纲挑出时间幂次。'}]}
            (root/'lesson.json').write_text(json.dumps(lesson))
            parsed,pages=compile_lesson(root)
            report=audit_teaching(root,parsed,pages)
            self.assertFalse(any(row['code'].startswith('closure-') for row in report['errors']))

    def test_speech_group_uses_provider_word_boundaries_when_available(self):
        audio={'duration':2.4,'words':[
            {'text':'看','start':0.,'end':.2},{'text':'红点','start':.2,'end':.7},
            {'text':'再','start':.7,'end':.9},{'text':'看蓝点','start':.9,'end':1.5},
            {'text':'它们','start':1.5,'end':1.9},{'text':'靠近','start':1.9,'end':2.4},
        ]}
        pieces=split_group(audio,['看红点','再看蓝点它们靠近'])
        self.assertAlmostEqual(pieces[0]['end'],.7)
        self.assertEqual(pieces[0]['timing'],'provider-word')
        self.assertEqual(''.join(word['text'] for word in pieces[1]['words']),'再看蓝点它们靠近')

    def test_quality_final_rejects_an_old_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.source(root)
            (root/'timeline.json').write_text(json.dumps({'draft':False,'lesson_sha256':'old'}))
            result=run(root,'final')
            self.assertEqual(result['status'],'blocked')
            self.assertIn('时间轴',result['findings'][-1]['message'])

    def test_review_plan_runs_quality_and_links_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.source(root)
            with patch.object(sys,'argv',['course.py','review-plan',tmp]),contextlib.redirect_stdout(io.StringIO()):
                course.main()
            self.assertTrue((root/'quality-report.json').is_file())
            self.assertIn('(制作检查.md)',(root/'教案.md').read_text())
            self.assertEqual(json.loads((root/'review-plan.json').read_text())['quality_errors'],0)
            self.assertFalse((root/'narration.wav').exists())
            self.assertFalse((root/'review-approval.json').exists())

    def test_adaptive_review_plan_reports_real_stages_and_checks_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lesson = self.source(root)
            lesson['review_required'] = True
            unit = lesson['concept_units'][0]
            unit.pop('introduce_cue')
            unit.pop('explain_cue')
            unit.pop('emphasize_cue')
            unit.pop('apply_cue')
            unit['stages'] = [
                {'purpose': 'contrast', 'cue': 'question'},
                {'purpose': 'reason', 'cue': 'compare'},
                {'purpose': 'anchor', 'cue': 'repair'},
                {'purpose': 'apply', 'cue': 'try'},
            ]
            (root/'lesson.json').write_text(json.dumps(lesson))
            with patch.object(sys,'argv',['course.py','review-plan',tmp]), contextlib.redirect_stdout(io.StringIO()):
                course.main()
            plan = json.loads((root/'review-plan.json').read_text())
            self.assertEqual(plan['quality_errors'], 0)
            self.assertEqual(plan['warnings'], 0)
            timing = json.loads((root/'review-preview/course-timing-report.json').read_text())
            self.assertEqual([item['phase'] for item in timing['units'][0]['stages']],
                             ['contrast', 'reason', 'anchor', 'apply'])

    def test_portable_install_keeps_personal_author_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';dest=root/'dest'
            source.mkdir();dest.mkdir()
            for name in ('author-profile.local.json','runtime-local.json','.env'):
                (source/name).write_text('source-local')
                (dest/name).write_text('destination-local')
            (source/'SKILL.md').write_text('new instructions')
            with patch.object(platform_install,'ROOT',source):
                names=[rel.name for _,rel in platform_install.source_files()]
                self.assertEqual(names,['SKILL.md'])
                _,preserved=platform_install.copy_install(dest,True)
            self.assertIn('author-profile.local.json',preserved)
            self.assertEqual((dest/'author-profile.local.json').read_text(),'destination-local')
            self.assertEqual((dest/'SKILL.md').read_text(),'new instructions')


if __name__=='__main__':
    unittest.main()
