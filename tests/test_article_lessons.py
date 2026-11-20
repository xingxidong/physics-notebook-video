import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from article_coverage import audit
from course import compile_lesson, digest
from feedback_bank import check, record
from lesson_duration import minimum_seconds, spoken_budget
from lesson_quality import run
from lesson_review import fingerprint
from pronunciation import local_tts_text, matched_pronunciations, resolve_readings


class ArticleLessons(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        db = patch.dict(os.environ, PHYSICS_NOTEBOOK_FEEDBACK_DB=str(self.root / 'author.sqlite'))
        db.start()
        self.addCleanup(db.stop)

    def test_author_minimum_follows_article_and_current_brief(self):
        article = {'kind': 'concept', 'source_type': 'article'}
        self.assertIsNone(minimum_seconds(self.root, article))
        record('issues', 'full-article', '完整讲不够30分钟', source_type='article', minimum_minutes=30)
        self.assertEqual(minimum_seconds(self.root, article), 1800)
        self.assertIsNone(minimum_seconds(self.root, {'kind':'concept'}))
        self.assertIsNone(minimum_seconds(self.root, {**article, 'duration_plan':{'requested_minutes':8}}))
        self.assertEqual(minimum_seconds(self.root, {**article, 'duration_plan':{'minimum_minutes':40}}), 2400)

    def test_reference_pace_counts_speech_once_and_skips_opening_and_empty_holds(self):
        previous = {'draft':False, 'pages':[{'id':'intro', 'cues':[
            {'tts':'甲乙丙丁。', 'start':0, 'end':1}, {'tts':'', 'start':1, 'end':15}]}]}
        current = {'pages':[{'id':'opening-card','cues':[{'tts':'片头'}]},
                            {'id':'p', 'cues':[{'tts':'在图中画两条直线。'}]}]}
        budget = spoken_budget(previous, current)
        self.assertEqual(budget['units_per_second'], 4)
        self.assertEqual(budget['estimated_spoken_seconds'], 2)
        with self.assertRaises(ValueError):
            spoken_budget({**previous,'draft':True}, current)

    def test_article_map_needs_spoken_and_visible_evidence(self):
        lesson = {'source_type':'article', 'article_coverage':'source.json', 'pages':[{'cues':[
            {'id':'a', 'tts':'从垂足读速率', 'actions':[{'id':'op'}]},
            {'id':'b', 'tts':'', 'actions':[{'id':'trajectory'}]}]}]}
        row = {'source_ref':'图3b', 'student_task':'找垂足', 'cues':['a'], 'actions':['op']}
        def findings(items):
            (self.root/'source.json').write_text(json.dumps({'source':'原文', 'items':items}))
            return [f['code'] for f in audit(self.root, lesson)]
        self.assertEqual(findings([row]), [])
        self.assertEqual(findings([{**row, 'actions':['trajectory']}]), ['article-source-gap'])
        self.assertEqual(findings([{**row, 'cues':['b']}]), ['article-source-gap'])
        self.assertEqual(findings([{'kind':'background','source_ref':'文献','note':'来源说明'}]), ['article-source-map'])

    def test_letter_names_units_and_component_context(self):
        self.assertEqual(resolve_readings('取 k 和 m，长度 3 m。'), '取 kay 和 em，长度 3 m。')
        self.assertEqual(matched_pronunciations('速度分量'), {'速度分量':'su4 du4 fen1 liang4'})
        line = '水平分量。掂一掂分量。'
        self.assertEqual(local_tts_text(line, matched_pronunciations(line)), '水平分亮。掂一掂分量。')
        self.assertNotIn('分量', matched_pronunciations('掂一掂分量'))
        result = check(self.root, {'pages':[{'id':'p','cues':[{'id':'c','tts':'水平分量。掂一掂分量。'}]}]})
        words = [r for r in result['listen'] if r['key']=='分量']
        self.assertEqual([r['expected'] for r in words], ['fen1 liang4', None])

    def test_final_media_floor_independent_of_timeline_and_display_rounding(self):
        source = json.loads((ROOT/'assets/dimension-board.json').read_text())
        (self.root/'lesson.json').write_text(json.dumps(source))
        (self.root/'讲义.md').write_text('学生讲义')
        cooked, pages = compile_lesson(self.root)
        timeline = {'draft':False, 'lesson_sha256':digest(cooked), 'review_sha256':fingerprint(self.root, cooked), 'duration':1800.1, 'pages':[]}
        (self.root/'timeline.json').write_text(json.dumps(timeline))
        (self.root/'video.mp4').touch()
        duration = {'issues':[], 'minimum_seconds':1800, 'timeline_status':'measured'}
        sound = {'duration':1800.1, 'listening_checks':[], 'terminology':{'items':[]}}
        from contextlib import ExitStack
        with ExitStack() as mocks:
            for target, value in [('lesson_duration.report',duration), ('voice_quality.audit',sound),
                                  ('voice_quality.strict_findings',[]), ('video_quality.review_points',[]),
                                  ('video_quality.extract_samples',[]), ('board_review.check',{'warnings':[]})]:
                mocks.enter_context(patch(target, return_value=value))
            for seconds, expected in [(1799.99, True), (1800., False)]:
                media = dict(duration_seconds=seconds, audio_codec='aac', video_codec='h264',
                             file='video.mp4', size_bytes=1000, fps=24, width=1280, height=720,
                             video_average_bps=72000, audio_average_bps=32000)
                with patch('video_quality.probe', return_value=media):
                    result = run(self.root, 'final', prepared=(cooked, pages, timeline))
                codes = [r['code'] for r in result['findings']]
                self.assertNotIn('check-incomplete', codes, result['findings'])
                self.assertEqual('media-below-minimum' in codes, expected)
                self.assertNotIn('duration-below-minimum', codes)
