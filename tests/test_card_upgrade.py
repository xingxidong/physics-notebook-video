import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from card_speech import lesson_inputs, merged_provider, symbols_in_order, restore_script_words
from classroom_terms import ARCHIVE, learning_cards, letter_card, practice
from delivery import inspect_script
from feedback_bank import check, record
from speech_blind import score
from term_comparison import review_repetitions
from term_flow import identify
from tone_review import targets


def course(*lines):
    return {'pages':[{'id':'page','cues':[dict(id=str(i),tts=line,start=i,end=i+1)
                                          for i,line in enumerate(lines)]}]}


class ReadingCardTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        env=patch.dict(os.environ,{'PHYSICS_NOTEBOOK_FEEDBACK_DB':str(self.root/'private.sqlite3')})
        env.start()
        self.addCleanup(env.stop)

    def test_feedback_changes_live_card_and_does_not_publish_it(self):
        term='试验晶舟'
        data=course('取出试验晶舟。')
        record('issues','term-flow-'+term,'句中读断',match=term,example='取出试验晶舟。')
        self.assertIn(term,check(self.root,data)['terms_needing_readings'])
        record('issues','term-flow-'+term,'在舟前断开',match=term,card_reading='shi4 yan4 jing1 zhou1',
               card_flow='晶舟连读。',example='取出试验晶舟。')
        report=check(self.root,data)
        card=report['classroom_cards'][term]
        self.assertEqual((card['scope'],card['flow'],card['feedback_example']),('feedback','晶舟连读。','取出试验晶舟。'))
        self.assertEqual(report['synthesis_targets'][0]['pinyin'][term],card['feedback_reading'])
        self.assertEqual(identify(data)[-1]['expected'],card['feedback_reading'])
        self.assertNotIn(term,ARCHIVE.read_text())
        with self.assertRaises(ValueError):
            record('issues','term-flow-X2','读断',match='X2')

    def test_sentence_pairs_reach_synthesis_and_keep_display_text(self):
        for text,expected in practice()['pairs']:
            with self.subTest(text=text):
                data=course(text)
                entry=inspect_script(data,'minimax')['tts_inputs'][0]
                self.assertEqual(entry['script'],text)
                for word,sound in expected:
                    alias=practice()['senses'].get(word,{}).get(sound,{}).get('spoken_as',word)
                    self.assertEqual(entry['pinyin'][alias],sound)
                self.assertEqual(entry['dictionary_conflicts'],[])
        data=course('取速度的分量，这个结论很有分量。')
        data['speech']={'term_uses':[dict(page='page',cue='0',term='分量',occurrence=1,reading='fen1 liang4')]}
        flow=[r['expected'] for r in identify(data) if r['term']=='分量']
        self.assertEqual(flow,['fen1 liang4','fen4 liang5'])
        self.assertEqual(flow,[r['expected'] for r in targets(data) if r['term']=='分量'])
        self.assertIn('份量',inspect_script(data,'user')['tts_inputs'][0]['text'])

    def test_conflicting_homographs_block_and_alias_fixes_request(self):
        data=course('流过重合处，再观察重合处。')
        use=dict(page='page',cue='0',term='重合',occurrence=2,reading='zhong4 he2')
        data['speech']={'physics_terms':{'重合':'chong2 he2'},'term_uses':[use]}
        entry=lesson_inputs(data)['page','0']
        self.assertIn('重合',entry['conflicts'])
        self.assertEqual(check(self.root,data)['status'],'blocked')
        with self.assertRaises(ValueError):
            merged_provider([entry])
        use['spoken_as']='众合'
        entry=lesson_inputs(data)['page','0']
        request=merged_provider([entry])
        self.assertIn('再观察众合处',request['provider_text'])
        self.assertEqual(request['pinyin']['众合'],'zhong4 he2')
        self.assertEqual(entry['source'],'流过重合处，再观察重合处。')
        disabled=dict(entry,provider_text='重合',pinyin={})
        with self.assertRaises(ValueError):
            merged_provider([entry,disabled])

    def test_existing_plain_override_across_word_boundaries(self):
        data=course('请测量长度。')
        data['speech']={'plain_pronunciation':{'测量长度':'测梁常度'}}
        self.assertEqual(lesson_inputs(data)['page','0']['local_text'],'请测梁常度。')
        data['pages'][0]['cues'][0]['plain_pronunciation']={'测量长度':None}
        self.assertEqual(lesson_inputs(data)['page','0']['local_text'],'请测量长度。')

    def test_grouped_course_uses_card_at_the_synthesis_boundary(self):
        from course import prepare
        from speech_plan import apply
        sound=io.BytesIO()
        with wave.open(sound,'wb') as stream:
            stream.setparams((1,2,24000,0,'NONE','not compressed'))
            stream.writeframes(bytes(96000))
        original='取速度的分量，这个结论很有分量。'
        cues=[dict(id='a',tts=original,speech_group='g'),dict(id='b',tts='桥接支路。',speech_group='g')]
        data,_=apply(self.root,dict(title='课堂',speech={'backend':'minimax','audio_mastering':False},
                                    pages=[dict(id='p',cues=cues)]))
        page=data['pages'][0]
        page.update(index=0,title='课堂',camera='static')
        for c in page['cues']:
            c.update(text=c['tts'],blocks=[])
        response=json.dumps({'data':{'audio':sound.getvalue().hex()}}).encode()
        with patch('voice.environment',return_value={'MINIMAX_API_KEY':'fixture'}),patch('voice.http',return_value=response) as http:
            timeline,_,_=prepare(self.root,data,[page],argparse.Namespace(backend=None,voice=None,draft=False,fps=24))
        payload=http.call_args.args[1]
        self.assertEqual(http.call_count,1)
        self.assertEqual(payload['text'],'取速度的分量，这个结论很有份量。 桥接支路。')
        self.assertTrue({'分量/(fen1)(liang4)','份量/(fen4)(liang5)','桥接/(qiao2)(jie1)'}.issubset(payload['pronunciation_dict']['tone']))
        self.assertEqual(timeline['pages'][0]['cues'][0]['tts'],original)

    def test_provider_word_times_return_to_printed_formula(self):
        script='重合处很有分量。'
        words=[dict(text=w,start=i,end=i+1) for i,w in enumerate(('重合处','很有','份量'))]
        output=restore_script_words(dict(words=words),'重合处很有份量。',script)
        self.assertEqual(output['words'][-1],dict(text='分量',start=2,end=3))
        self.assertEqual(restore_script_words(dict(words=words),'只出现一次。',script)['words'],[])

    def test_symbols_and_subscripts_survive_chinese_context(self):
        seq=symbols_in_order('水平是 u 乘 q，竖直是负 v 乘 q，再看 v₀ 与 z 轴。')
        self.assertEqual([s['symbol'] for s in seq],list('uqvqvz'))
        self.assertEqual(seq[-2]['subscript'],'0')
        self.assertIn('q',seq[1]['example'])
        from speech_probe import LETTER_PATTERNS
        self.assertEqual(set(LETTER_PATTERNS),set('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        self.assertTrue(LETTER_PATTERNS['N'].fullmatch('ɛ n'))
        self.assertFalse(LETTER_PATTERNS['N'].fullmatch('ɛ m'))
        self.assertIn('/k/',letter_card('Q')['listen_for'])
        for symbol in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            self.assertTrue(letter_card(symbol)['expected'])
            self.assertIn(symbol.lower(),letter_card(symbol)['example'].lower())

    def test_one_strange_occurrence_and_consistently_wrong_others(self):
        rows=[];hits=[]
        for i,ms in enumerate((.18,.17,.18,.19,.52)):
            for j,term in enumerate(('桥接','电荷')):
                ident=f'1.{i+1}.{j}.{term}'
                rows.append(dict(id=ident,page='p',cue=i,text='桥接，电荷。',cue_start=i,cue_end=i+1))
                hits.append(dict(id=ident,term=term,expected='qiao2 jie1' if j==0 else 'dian4 he4',
                                 heard_in_final=False,status='supports_target' if j==0 else 'possible_mismatch',
                                 heard_windows=[dict(times=[i,i+ms])]*2))
        result=review_repetitions(hits,rows)
        self.assertEqual(len(result['producer_review']),5)
        self.assertEqual(result['repeated_terms'][0]['spacing_outliers'][0]['id'],'1.5.0.桥接')
        self.assertIsNone(result['repeated_terms'][1]['reference'])
        self.assertFalse(result['repeated_terms'][0]['reference_heard'])

    def test_blind_audit_counts_denominators_and_actual_author_requests(self):
        clips=self.root/'clips'; clips.mkdir()
        key={};trials=[]
        for i,label in enumerate(('bad','good','good','unlabeled')):
            k=str(i);raw=k.encode();(clips/k).write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
            key[k]=dict(label=label,origin='real',sha256=sha)
            trials.append(dict(id=k,file=k,task='tone',sha256=sha))
        (self.root/'key.json').write_text(json.dumps(key))
        (clips/'trials.json').write_text(json.dumps(trials))
        answers={'0':'good','1':'bad','2':'unsure'}
        audit=score(self.root,answers,['0','0','2'])['metrics']
        self.assertEqual(list(audit.values()),[1,1,1,2,1,1,2])
        self.assertIsNone(score(self.root,answers)['metrics']['author_requested'])
