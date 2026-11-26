"""Checks for portable text cards; these tests make no claims about synthesized audio."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from classroom_terms import ARCHIVE, NOTES, compile_cards, saved_cards
from pronunciation import SYLLABLE
from term_flow import identify


class ClassroomLibraryQualityTests(unittest.TestCase):
    def test_distributed_cards_have_complete_portable_material(self):
        cards = saved_cards(ARCHIVE)
        self.assertTrue(cards)
        for term, card in cards.items():
            with self.subTest(term=term):
                self.assertTrue(card['readings'])
                for reading in card['readings']:
                    self.assertIsInstance(reading, str)
                    self.assertEqual(len(reading.split()), len(term))
                    self.assertTrue(all(SYLLABLE.fullmatch(s) for s in reading.split()))
                for key in ('sense', 'example', 'flow', 'contrast'):
                    self.assertTrue(card.get(key, '').strip(), key)
                self.assertIn(term, card['example'])
                self.assertIn(card['example'][-1], '。！？')
                self.assertNotIn('出现在板书或讲解语境中的标准配音', card['sense'])
                self.assertNotIn('/Users/', card['example'])

    def test_rebuilding_from_notes_preserves_edited_fields(self):
        saved = saved_cards(ARCHIVE)
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'cards.json'
            shutil.copyfile(ARCHIVE, archive)
            rebuilt = compile_cards(NOTES, archive)
        self.assertEqual(set(saved), set(rebuilt))
        for term, card in saved.items():
            with self.subTest(term=term):
                for key in ('readings', 'sense', 'example', 'flow', 'contrast'):
                    self.assertEqual(card.get(key), rebuilt[term].get(key), key)

    def test_corrected_reading_reaches_every_occurrence(self):
        text = '切换电流表的档位，再检查所选档位。'
        lesson = {'pages': [{'id': 'p', 'cues': [{'id': 'c', 'tts': text}]}]}
        # Isolate the distributed defaults from a local user's private feedback.
        rows = [r for r in identify(lesson, rules={'polyphones': {}, 'letters': {}, 'issues': {}})
                if r['term'] == '档位']
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['expected'] for r in rows], ['dang4 wei4', 'dang4 wei4'])


if __name__ == '__main__':
    unittest.main()
