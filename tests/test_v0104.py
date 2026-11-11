import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from terminology_review import inspect_terminology
from voice_quality import audit, export_listening_clip


class TerminologyReviewTests(unittest.TestCase):
    def test_repeated_term_uses_each_word_interval_and_global_page_offset(self):
        words = [{'text': text, 'start': start, 'end': end} for text, start, end in [
            ('相', .2, .4), ('位差', .4, .9), ('等于', 1, 1.4),
            ('两个', 1.4, 1.6), ('相位', 1.6, 2), ('相减', 2, 2.6),
        ]]
        cue = {'id': 'phase', 'tts': '相位差等于两个相位相减。', 'start': 1, 'end': 4,
               'words': words, 'minimax_tone_entries': ['相位/(xiang1)(wei4)']}
        data = {'pages': [{'id': 'p2', 'start': 20, 'cues': [cue]}]}
        review, warnings = inspect_terminology(data)
        self.assertEqual(warnings, [])
        self.assertEqual(review['status'], 'pending_listening')
        first, second = review['items']
        self.assertEqual((first['term'], first['start'], first['end']), ('相位差', 21.2, 21.9))
        self.assertEqual((second['term'], second['start'], second['end']), ('相位', 22.6, 23.0))
        self.assertEqual(second['timing'], 'provider-word')
        self.assertTrue(first['dictionary_differs'])
        self.assertTrue(second['dictionary_differs'])
        self.assertEqual(review['physics_term_occurrences'], 2)
        self.assertEqual(review['polyphonic_occurrences'], 2)

    def test_audit_warns_about_spelling_and_falls_back_to_the_whole_cue(self):
        cue = {'id': 'coherence', 'start': .5, 'end': 1.5,
               'tts': '不同相干条件下的感应电动事。',
               'words': [{'text': '相干', 'start': .2, 'end': .5}]}
        data = {'pages': [{'id': 'p1', 'start': 0, 'cues': [cue]}]}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'timeline.json').write_text(json.dumps(data))
            with wave.open(str(root / 'narration.wav'), 'wb') as wav:
                wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                wav.writeframes(b'\x08\x10' * 48000)
            report = audit(root)
            term, = report['terminology']['items']
            self.assertEqual((term['term'], term['timing'], term['start'], term['end']),
                             ('相干', 'cue', .5, 1.5))
            self.assertTrue(any(w['code'] == 'physics-term-spelling' for w in report['warnings']))
            with wave.open(export_listening_clip(root, cue['id']), 'rb') as wav:
                self.assertEqual(wav.getnframes(), 33600)


if __name__ == '__main__':
    unittest.main()
