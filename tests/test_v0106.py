import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from course import compile_lesson, prepare
from knowledge_board import inspect_sources, inspect_timeline


class KnowledgeBoardTests(unittest.TestCase):
    def fixture(self):
        return {'kind': 'concept', 'title': 'law', 'knowledge_points': [{
            'id': 'law', 'name': 'Law', 'page_id': 'p1', 'name_action_id': 'law-name',
            'statement': 'Force equals mass times acceleration.',
            'statement_action_ids': ['line1', 'line2'], 'formula_action_ids': ['formula'],
            'read_seconds': 4,
        }], 'pages': [{'id': 'p1', 'cues': [{'id': 'c', 'tts': 'The force determines acceleration.',
            'actions': [
                {'id': 'law-name', 'type': 'text', 'text': 'Law', 'x': 200, 'y': 140},
                {'id': 'line1', 'type': 'text', 'text': 'Force equals mass ', 'x': 200, 'y': 200},
                {'id': 'line2', 'type': 'text', 'text': 'times acceleration.', 'x': 200, 'y': 260},
                {'id': 'formula', 'type': 'math', 'latex': 'F=ma', 'x': 200, 'y': 330},
            ]}]}]}

    def test_declared_statement_must_exist_as_matching_board_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = self.fixture()
            lesson, pages = compile_lesson(tmp, source)
            records, errors = inspect_sources(lesson, pages)
            self.assertFalse(errors)
            self.assertEqual(len(records[0]['actions']), 4)
            lesson['knowledge_points'][0]['statement'] = 'Different words.'
            _, errors = inspect_sources(lesson, pages)
            self.assertIn('knowledge-statement-content', {item['code'] for item in errors})
            lesson.pop('knowledge_points')
            self.assertIn('knowledge-points-required', {item['code'] for item in inspect_sources(lesson, pages)[1]})

    def test_measured_board_must_have_strokes_and_time_after_the_last_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            lesson, pages = compile_lesson(tmp, self.fixture())
            records, errors = inspect_sources(lesson, pages)
            self.assertFalse(errors)
            timeline, _, _ = prepare(Path(tmp), lesson, pages, SimpleNamespace(backend=None, voice=None, fps=24, draft=True))
            early = inspect_timeline(records, timeline)
            self.assertIn('knowledge-reading-time', {item['code'] for item in early['errors']})
            timeline['pages'][0]['duration'] += 5
            self.assertEqual(inspect_timeline(records, timeline)['status'], 'pass')
            timeline['pages'][0]['strokes'] = [event for event in timeline['pages'][0]['strokes'] if event['action'] != 2]
            missing = inspect_timeline(records, timeline)
            self.assertIn('knowledge-strokes-missing', {item['code'] for item in missing['errors']})


if __name__ == '__main__':
    unittest.main()
