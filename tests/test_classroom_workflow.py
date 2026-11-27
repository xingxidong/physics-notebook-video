import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import classroom_workflow as flow
import final_review
import lesson_review
from handout_bundle import digest
from production_workflow import save, scope
from speech_context import inventory
from speech_packages import fingerprints
from trial_materials import lesson_stamp


class ClassroomWorkflowTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.project = Path(folder.name).resolve()
        self.lesson = {
            'title': '圆周运动', 'kind': 'concept', 'classroom_workflow_version': 1,
            'review_required': True, 'speech_review_version': 1, 'term_inventory_version': 2,
            'handout': '学生讲义.tex',
            'pages': [{'id': 'p', 'title': '圆周运动', 'cues': [
                {'id': 'a', 'tts': '这里先看小球的位置。', 'speech_group': 'motion'},
                {'id': 'b', 'tts': '再看下一刻小球的位置。', 'speech_group': 'motion'},
            ]}],
        }
        save(self.project / 'lesson.json', self.lesson)

    def write(self, name, text):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def prepare_packet(self):
        self.write('学生讲义.tex', r'\documentclass{article}')
        self.write('教案.md', '观察小球的运动。')
        self.write('review-preview/boards.pdf', 'board')
        self.write('handout-delivery/学生讲义.pdf', 'handout')
        self.write('draft-preview-manim.mp4', 'animation')
        audio = self.write('voice-trial/audio/sample.wav', 'sample')
        flow.write_drafts(self.project, self.lesson['pages'])
        save(self.project / 'voice-trial/trial-results.json', {
            'source_plan': {'project': str(self.project), 'lesson_files': lesson_stamp(self.project)},
            'items': [{'origin': 'lesson', 'text': '这里先看小球的位置。', 'duration': 3,
                       'audio': 'audio/sample.wav', 'audio_sha256': digest(audio)}],
        })
        revision = lesson_review.fingerprint(self.project, self.lesson)
        save(self.project / 'review-plan.json', {
            'workflow_run': flow.preflight(self.project, self.lesson)['run'],
            'fingerprint': revision, 'document_sha256': digest(self.project / '教案.md'),
            'native_preview': 'draft-preview-manim.mp4', 'estimated_seconds': 30,
            'pilot_sha256': flow.pilot_pace(self.project)[1], 'teaching_errors': 0, 'warnings': 0,
        })

    def test_one_packet_binds_all_artifacts_and_real_language_audit(self):
        project, lesson = self.project, self.lesson
        flow.start(project, 'concept')
        self.prepare_packet()
        with patch('lesson_review.native_preview', return_value='draft-preview-manim.mp4'), \
             patch('handout_bundle.verified', return_value=True), \
             patch('trial_review.require_target_voice', return_value=({}, {'trial_sha256': 'reviewed'})):
            with self.assertRaisesRegex(ValueError, '四份材料'):
                flow.packet(project, lesson)
            flow.humanize(project, lesson, {role: '已通读这一版对应物理内容。' for role in flow.EDIT_ROLES})
            pack = flow.packet(project, lesson)
            self.assertEqual(len(pack['files']), 6)
            with self.assertRaisesRegex(ValueError, '等待人审'):
                lesson_review.require(project, lesson)
            lesson_review.approve(project, lesson, '这整套可以开始做')
            self.assertEqual(lesson_review.require(project, lesson), pack)
            self.write('voice-trial/audio/sample.wav', 'different audio')
            with self.assertRaisesRegex(ValueError, '整套材料'):
                lesson_review.require(project, lesson)

    def test_finalize_with_skipped_stage_requires_new_run(self):
        with self.assertRaisesRegex(ValueError, '第 1 步'):
            flow.require_active(self.project, self.lesson)
        first = flow.start(self.project, 'concept')
        self.write('video.mp4', 'video')
        with self.assertRaisesRegex(ValueError, '从第 1 步完整重做'):
            flow.before_finalize(self.project, self.lesson, 'video.mp4')
        with self.assertRaisesRegex(ValueError, '重新制作'):
            flow.require_active(self.project, self.lesson)
        second = flow.start(self.project, 'concept')
        self.assertNotEqual(first['run'], second['run'])
        self.assertFalse(flow.require_active(self.project, self.lesson)['first_take'])

    def test_lost_words_and_unmeasured_ink_fail_timeline_validation(self):
        flow.start(self.project, 'concept')
        self.prepare_packet()
        project, lesson = self.project, self.lesson
        guide = self.write('classroom-pronunciation-plan.json', '{}')
        packet = {'run': 'active', 'packet_sha256': 'approved', 'script_sha256': final_review.token(
            flow.scoped_script(lesson)), 'trial': {'trial_sha256': 'sample'}}
        timeline = {
            'classroom_run': 'active', 'classroom_packet': 'approved', 'pages': [
                {'id': 'p', 'cues': [dict(cue, timing='measured', start=i, end=i+1)
                                     for i, cue in enumerate(lesson['pages'][0]['cues'])]}],
            'pronunciation_packages': fingerprints(), 'pronunciation_plan_sha256': digest(guide),
            'retake_sha256': final_review.token({}), 'target_voice': {'matched_takes': 1, **packet['trial']},
        }
        with patch('classroom_workflow.require_packet', return_value=packet):
            self.assertEqual(flow.verify_timeline(project, lesson, timeline), packet)
            timeline['pages'][0]['cues'][1]['timing'] = 'estimated'
            with self.assertRaisesRegex(ValueError, '实测时间'):
                flow.verify_timeline(project, lesson, timeline)
            timeline['pages'][0]['cues'][1]['tts'] = '再看位置。'
            with self.assertRaisesRegex(ValueError, '完整讲稿'):
                flow.verify_timeline(project, lesson, timeline)

    def test_whole_paragraph_and_ordinary_sentence_review(self):
        self.assertEqual(scope(self.lesson, {}, ['a'])['changed'], ['p/a', 'p/b'])
        rows = inventory(self.lesson, self.lesson)
        self.assertTrue(all('complete' in {target['id'] for target in row['targets']} for row in rows))
        self.assertFalse(flow.duration_difference(1200, 1260))
        self.assertTrue(flow.duration_difference(1200, 1320))


if __name__ == '__main__':
    unittest.main()
