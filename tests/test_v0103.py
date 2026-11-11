import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from delivery import inspect_script
from pronunciation import matched_pronunciations
from speech_plan import apply
from voice import synth


class PronunciationTests(unittest.TestCase):
    def test_physics_terms_match_whole_phrases_and_cue_overrides_reach_report(self):
        sentence = '相乘之后，再看相位和相长干涉。电荷的轨迹是切线。'
        lesson = {'speech': {'backend': 'minimax', 'minimax_pronunciation': {'切线': None}},
                  'pages': [{'id': 'p01', 'cues': [{'id': 'c01', 'text': sentence}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            plan = {'version': 1, 'cues': {'c01': {'minimax_pronunciation': {'切线': 'qie1 xian4'}}}}
            (Path(tmp) / 'speech-plan.json').write_text(json.dumps(plan))
            resolved, _ = apply(tmp, lesson)
            report = inspect_script(resolved)['pronunciation']
        self.assertTrue(report['apply_dictionary'])
        entry, = report['cues']
        self.assertEqual(entry['terms'], {'切线': 'qie1 xian4', '电荷': 'dian4 he4',
                                          '相位': 'xiang4 wei4', '相长干涉': 'xiang1 zhang3 gan1 she4'})
        self.assertEqual(entry['listen_for'], ['相乘'])
        self.assertEqual(resolved['pages'][0]['cues'][0]['tts'], sentence)
        with self.assertRaisesRegex(ValueError, '相位'):
            matched_pronunciations(sentence, {'相位': 'xiang4'})

    def test_minimax_request_and_cache_change_only_for_matching_cues(self):
        sound = io.BytesIO()
        with wave.open(sound, 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\x00\x00' * 2400)
        response = json.dumps({'data': {'audio': sound.getvalue().hex(),
                                       'subtitle_file': 'https://example.invalid/subtitles'}}).encode()
        provider_words = [{'word': 'xiang4wei4', 'time_begin': 0, 'time_end': 60}]
        provider_subtitle = json.dumps([{'timestamped_words': provider_words}]).encode()
        before = {'backend': 'minimax', 'minimax_pronunciation': False}
        after = {'backend': 'minimax'}
        affected = {'tts': '相位发生了变化。'}
        unaffected = {'tts': '两条曲线都发生了变化。'}
        with tempfile.TemporaryDirectory() as tmp, \
             patch('voice.environment', return_value={'MINIMAX_API_KEY': 'test-key'}), \
             patch('voice.http', return_value=response) as http, \
             patch('voice.urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(provider_subtitle)):
            old = synth(tmp, before, affected)
            synth(tmp, before, unaffected)
            new = synth(tmp, after, affected)
            self.assertFalse(new['cache_hit'])
            self.assertNotEqual(old['file'], new['file'])
            request = http.call_args.args[1]
            self.assertEqual(request['text'], affected['tts'])
            self.assertEqual(request['pronunciation_dict'], {'tone': ['相位/(xiang4)(wei4)']})
            self.assertEqual(new['words'], [])
            self.assertTrue(synth(tmp, after, unaffected)['cache_hit'])
            self.assertTrue(synth(tmp, after, affected)['cache_hit'])
            self.assertEqual(http.call_count, 3)


if __name__ == '__main__':
    unittest.main()
