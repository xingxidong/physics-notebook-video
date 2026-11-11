from pathlib import Path
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from delivery import inspect_script
from voice_quality import audit


class ClassroomLanguageTests(unittest.TestCase):
    def test_preflight_quotes_specific_problems_and_leaves_direct_narration_alone(self):
        cues = [
            {'id': 'a', 'tts': '接下来，副边感应电动势，等于负的 M 乘原边电流变化率。'},
            {'id': 'b', 'tts': '接下来采用理想变压器模型 忽略漏磁。'},
            {'id': 'c', 'tts': '接下来原边二百二十伏，副边一百一十伏，副边十安，原边五安，折算电阻四十四欧。'},
            {'id': 'd', 'tts': '看蓝线。磁通到顶时，斜率是零，所以副边感应电动势也过零。'},
        ]
        findings = inspect_script({'pages': [{'cues': cues}]})['warnings']
        by_code = {item['code']: item for item in findings}
        self.assertEqual(by_code['predicate-break']['excerpt'], '感应电动势，等于')
        self.assertIn('模型 忽略', by_code['unmarked-pause']['excerpt'])
        self.assertEqual(by_code['repeated-opening']['related_cues'], ['a', 'b', 'c'])
        self.assertEqual(by_code['dense-measurements']['cue'], 'c')
        self.assertNotIn('d', [item['cue'] for item in findings])

    def test_audio_audit_locates_an_unplanned_gap_and_respects_teaching_pause(self):
        before = {'id': 'a', 'tts': '看左边的图。', 'start': .1, 'end': .6}
        after = {'id': 'b', 'tts': '速度，等于位移除以时间。', 'start': 1.6, 'end': 2.2}
        data = {'pages': [{'id': 'p1', 'start': .1, 'cues': [before, after]}]}
        with tempfile.TemporaryDirectory() as tmp:
            with wave.open(str(Path(tmp) / 'narration.wav'), 'wb') as wav:
                wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                wav.writeframes(b'\x00\x10' * 16800 + b'\x00\x00' * 24000 + b'\x00\x10' * 14400)
            findings = {item['code']: item for item in audit(tmp, data)['classroom_delivery']}
            self.assertAlmostEqual(findings['predicate-break']['start'], 1.7)
            self.assertEqual(findings['audible-cue-gap']['related_cues'], ['a', 'b'])
            self.assertAlmostEqual(findings['audible-cue-gap']['quiet_seconds'], 1)
            before['pause_reason'] = 'observe_motion'
            codes = {item['code'] for item in audit(tmp, data)['classroom_delivery']}
            self.assertNotIn('audible-cue-gap', codes)


if __name__ == '__main__':
    unittest.main()
