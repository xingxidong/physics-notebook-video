import array
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from classroom_language import review_narration
from lesson_duration import estimate, report
from voice_quality import audit


class DurationAndDeliveryTest(unittest.TestCase):
    def test_motion_overlaps_voice_but_a_separate_observation_adds_time(self):
        plan = {'audience': '能列节点方程', 'requested_minutes': 4, 'sections': [
            {'title': '消去桥电流', 'mode': 'derive', 'reason': '逐式移项',
             'spoken_chars': 320, 'visual_seconds': 45, 'observe_seconds': 2,
             'observe_reason': '指出共同的绿色支路', 'pages': ['p1']}]}
        initial = estimate(plan)
        self.assertEqual(initial['recommended_seconds'], 105)
        timed = {'draft': False, 'duration': 108, 'pages': [
            {'id': 'opening-card', 'duration': 3},
            {'id': 'p1', 'duration': 105, 'title': '消元'}]}
        actual = report(Path('.'), {'kind': 'problem', 'duration_plan': plan}, timed)
        self.assertEqual(actual['timeline_status'], 'measured')
        self.assertEqual(actual['sections'][0]['timeline_seconds'], 105)
        self.assertTrue(any('指定时长' in note for note in actual['issues']))

    def test_suspected_mid_cue_gap_and_cross_page_join_are_separate(self):
        with tempfile.TemporaryDirectory() as path:
            p = Path(path)
            rate = 8000
            signal = array.array('h', [2800]) * (rate * 7)
            for first, last in [(1.1, 1.87), (2.7, 3.84)]:
                start, end = round(first * rate), round(last * rate)
                signal[start:end] = array.array('h', [0]) * (end - start)
            with wave.open(str(p / 'narration.wav'), 'wb') as handle:
                handle.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
                handle.writeframes(signal.tobytes())
            timeline = {'pages': [
                {'start': 0, 'cues': [{'id': 'a', 'start': .35, 'end': 2.8, 'tts': '画出电流方向。'}]},
                {'start': 3.4, 'cues': [{'id': 'b', 'start': .4, 'end': 6.5-3.4, 'tts': '在这个节点列方程。'}]},
            ]}
            actual = audit(p, timeline)
            self.assertIn(('in-cue-hesitation', 'a'), {(x['code'], x['cue']) for x in actual['classroom_delivery']})
            self.assertIn(('audible-cue-gap', 'b'), {(x['code'], x['cue']) for x in actual['classroom_delivery']})
            self.assertEqual(actual['listening_checks'][1]['start'], .35)

    def test_script_flags_markup_and_vague_transitions(self):
        rows = review_narration([{'id': 'pivot', 'tts': '然后，然后，照着板书念 $x_0$。这样一来就行了。'}])
        self.assertEqual({row['code'] for row in rows}, {'readable-formula', 'vague-reference', 'stacked-transitions'})
