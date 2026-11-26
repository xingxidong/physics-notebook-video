"""Offline checks of the portable trial/feedback loop; no real listening is claimed."""
from contextlib import closing
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from feedback_bank import catalog, history, record
from learning_bundle import merge, resolve_sample, verify_contents, DB_REL
from trial_materials import build_plan, check_plan, make_case, refresh, lesson_stamp
from trial_review import (evidence_token, import_review, judgment_template, run_status,
                          speech_identity, validate_run)
from voice_trials import run


def wav(path):
    with wave.open(str(path), 'wb') as f:
        f.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        f.writeframes(b'\0\0' * 2400)


class TrialLearning(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'skill/assets/learning/feedback.sqlite3'
        env = patch.dict(os.environ, PHYSICS_NOTEBOOK_FEEDBACK_DB=str(self.db))
        env.start()
        self.addCleanup(env.stop)

    def fixture_run(self, text='这里把位移记为 x。'):
        folder = self.root / 'trial'
        folder.mkdir(exist_ok=True)
        sample = folder / 'sample.wav'
        wav(sample)
        row = make_case('fixture', text, 'fixed')
        row.update(audio='sample.wav', audio_sha256=hashlib.sha256(sample.read_bytes()).hexdigest(),
                   synthesis_signature={'model': 'fixture'}, synthesis=None)
        identity = speech_identity({'model': 'fixture'})
        row['review_token'] = evidence_token(row, identity)
        data = dict(schema=2, speech_fingerprint=identity, items=[row], source_plan={}, status='pending')
        (folder / 'trial-results.json').write_text(json.dumps(data, ensure_ascii=False))
        answers = judgment_template(data)
        answers.update(reviewer='automated test fixture', evidence='synthetic test data, not a listening claim')
        return folder, data, answers

    def test_three_sources_and_fixed_sixteen(self):
        text = '磁通量先保持不变，再观察磁通量的变化。'
        record('polyphones', '磁通量', '测试：错误音节', example=text)
        lesson = {'pages': [{'id': 'p', 'cues': [{'id': 'c', 'tts': '这个量记作 Q，再比较质量。'}]}]}
        plan = build_plan(lesson=lesson, max_extra=3)
        self.assertEqual(sum(r['origin'] == 'fixed' for r in plan['items']), 16)
        self.assertEqual(plan['coverage']['selected_by_source'], {'history': 1, 'lesson': 1, 'card': 1})
        row = next(r for r in plan['items'] if r['text'] == text)
        hits = [t for t in row['targets'] if t['term'] == '磁通量']
        self.assertEqual(len(hits), 2)
        self.assertNotEqual(hits[0]['id'], hits[1]['id'])
        self.assertTrue(plan['coverage']['deferred'])
        self.assertEqual(plan['status'], 'planned_not_listened')
        check_plan(plan)

    def test_per_sentence_readings_survive_extraction(self):
        lesson = {'speech': {'term_uses': [
            dict(page='p', cue='a', term='分量', occurrence=1, reading='fen1 liang4'),
            dict(page='p', cue='b', term='分量', occurrence=1, reading='fen4 liang5')]},
            'pages': [{'id': 'p', 'cues': [{'id': 'a', 'tts': '计算力的分量。'},
                                         {'id': 'b', 'tts': '这句话很有分量。'}]}]}
        plan = build_plan(lesson=lesson, max_extra=5)
        rows = {r['text']: r for r in plan['items'] if r['origin'] == 'lesson'}
        self.assertEqual(next(t['pinyin'] for t in rows['计算力的分量。']['targets'] if t['term'] == '分量'), 'fen1 liang4')
        self.assertEqual(next(t['pinyin'] for t in rows['这句话很有分量。']['targets'] if t['term'] == '分量'), 'fen4 liang5')

    def test_unresolved_term_is_visible(self):
        context = {'speech': {'physics_terms': {'试音新词': None}},
                   'pages': [{'id': 'p', 'cues': [{'id': 'a', 'tts': '现在引入试音新词。'}]}]}
        row = make_case('new', '现在引入试音新词。', 'lesson', context=context)
        hit = next(t for t in row['targets'] if t['term'] == '试音新词')
        self.assertFalse(hit['pinyin'])

    def test_card_feedback_invalidates_only_relevant_sentence(self):
        a = make_case('a', '求出切向分量。', 'fixed')
        b = make_case('b', '小球到达圆心。', 'fixed')
        record('issues', 'term-flow-切向分量', '词内断开', match='切向分量',
               card_flow='整词连读，词内无停顿。', example='求出切向分量。')
        self.assertNotEqual(a['material_fingerprint'], refresh(a)['material_fingerprint'])
        self.assertEqual(b['material_fingerprint'], refresh(b)['material_fingerprint'])

    def test_no_example_remains_pending_and_zero_budget_does_not_claim_coverage(self):
        record('polyphones', '未附例句新术语', '需要检查读音')
        plan = build_plan(max_extra=0)
        self.assertEqual(len(plan['items']), 16)
        self.assertTrue(any(r['key'] == '未附例句新术语' for r in plan['coverage']['needs_material']))
        self.assertTrue(plan['coverage']['deferred'])

    def test_sampling_change_changes_voice_identity_credentials_do_not(self):
        a = {'model': 'test', 'max_tokens': 200, 'api_key': 'fixture-a'}
        self.assertEqual(speech_identity(a), speech_identity({**a, 'api_key': 'fixture-b'}))
        self.assertNotEqual(speech_identity(a), speech_identity({**a, 'max_tokens': 201}))
        sample = self.root / 'ref.wav'
        sample.write_bytes(b'one')
        cfg = {'qwen': {'reference_audio': str(sample)}}
        before = speech_identity(cfg)
        sample.write_bytes(b'two')
        self.assertNotEqual(before, speech_identity(cfg))

    def test_changed_audio_and_wrong_evidence_cannot_pass(self):
        folder, data, answers = self.fixture_run()
        answers['basis'] = 'asr'
        with self.assertRaises(ValueError):
            import_review(folder, answers)
        answers['basis'] = 'producer_listening'
        answers['items'][0]['token'] = 'wrong'
        with self.assertRaises(ValueError):
            import_review(folder, answers)
        (folder / 'sample.wav').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            validate_run(folder, data)
        self.assertEqual(run_status(folder)['items'][0]['status'], 'stale')

    def test_pending_and_uncertain_checks_cannot_pass(self):
        folder, _, answers = self.fixture_run()
        result = import_review(folder, answers)
        self.assertEqual(result['passed_sentences'], 0)
        for value in answers['items'][0]['checks'].values():
            value['status'] = 'ok'
        answers['items'][0]['checks']['continuity']['status'] = 'unsure'
        self.assertEqual(import_review(folder, answers)['passed_sentences'], 0)

    def test_lesson_change_invalidates_trial(self):
        folder, data, _ = self.fixture_run()
        lesson = self.root / 'lesson.json'
        lesson.write_text('{"title":"first"}')
        data['source_plan'] = {'project': str(self.root), 'lesson_files': lesson_stamp(self.root)}
        validate_run(folder, data)
        lesson.write_text('{"title":"second"}')
        with self.assertRaises(ValueError):
            validate_run(folder, data)

    def test_bundle_checks_trial_recordings(self):
        folder, _, answers = self.fixture_run()
        import_review(folder, answers)
        with closing(sqlite3.connect(self.db)) as db:
            row = json.loads(db.execute('SELECT payload FROM voice_trial_reviews').fetchone()[0])
        for broken in (False, True):
            package = self.root / ('broken.zip' if broken else 'good.zip')
            with zipfile.ZipFile(package, 'w') as z:
                z.write(self.db, 'skill/' + DB_REL.as_posix())
                z.writestr('skill/assets/classroom-cards.json', '{"schema":1,"cards":{}}')
                source = resolve_sample(self.db, row['sample'])
                z.writestr('skill/' + (DB_REL.parent / row['sample']).as_posix(),
                           b'broken' if broken else source.read_bytes())
            with zipfile.ZipFile(package) as z:
                if broken:
                    with self.assertRaises(ValueError):
                        verify_contents(z, 'skill')
                else:
                    result = verify_contents(z, 'skill')
                    self.assertEqual(result['trial_reviews'], 1)
                    self.assertEqual(result['samples'], 1)

    def test_completed_review_travels_with_audio_after_original_deleted(self):
        folder, _, answers = self.fixture_run()
        for value in answers['items'][0]['checks'].values():
            value['status'] = 'ok'
        result = import_review(folder, answers)
        self.assertEqual(result['status'], 'passed_for_recorded_sentences')
        dest = self.root / 'moved/feedback.sqlite3'
        self.assertEqual(merge(self.db, dest)['trial_reviews_added'], 1)
        self.assertEqual(merge(self.db, dest)['trial_reviews_added'], 0)
        shutil.rmtree(folder)
        shutil.rmtree(self.db.parent)
        with closing(sqlite3.connect(dest)) as db:
            payload = json.loads(db.execute('SELECT payload FROM voice_trial_reviews').fetchone()[0])
        audio = resolve_sample(dest, payload['sample'])
        self.assertEqual(hashlib.sha256(audio.read_bytes()).hexdigest(), payload['sample_sha256'])
        self.assertEqual(payload['status'], 'passed')

    def test_wrong_term_and_continuity_join_next_plan(self):
        folder, data, answers = self.fixture_run()
        term = next(c for c in data['items'][0]['checks'] if c['id'].startswith('flow:term@'))
        answers['items'][0]['checks'][term['id']] = {'status': 'wrong', 'note': '词内有多余断点'}
        answers['items'][0]['checks']['continuity'] = {'status': 'wrong', 'note': '句末出现重复起音'}
        import_review(folder, answers)
        records = history()
        self.assertTrue(any(r['key'].startswith('term-flow-') for r in records))
        self.assertTrue(any(r['key'].startswith('speech-trial-continuity-') for r in records))
        plan = build_plan(max_extra=3)
        row = next(r for r in plan['items'] if r['text'] == data['items'][0]['text'])
        self.assertTrue(any(s['key'].startswith('speech-trial-') for s in row['sources']))

    def test_existing_recording_run_records_each_target_without_a_paid_call(self):
        recordings = self.root / 'recordings'
        recordings.mkdir()
        wav(recordings / 'mixed-q.wav')
        config = self.root / 'voice.json'
        config.write_text(json.dumps({'backend': 'user', 'recordings_dir': 'recordings', 'speed': .9}))
        output = self.root / 'rendered'
        result = run(config, output, ids=['mixed-q'], max_extra=0)
        self.assertEqual(result['review_status'], 'pending')
        data = json.loads((output / 'trial-results.json').read_text())
        self.assertEqual(len(data['not_requested']), 15)
        self.assertEqual(data['items'][0]['synthesis_signature']['speed'], .9)
        self.assertTrue(any(t['kind'] == 'letter' for t in data['items'][0]['targets']))
        self.assertTrue((output / 'scorecard.csv').is_file())
        validate_run(output, data)


if __name__ == '__main__':
    unittest.main()
