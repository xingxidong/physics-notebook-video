import argparse
import array
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from captions import chunks
from course import anchor, prepare, schedule
from delivery import inspect_script
from lesson_duration import compare_pace, estimate, markdown, report
from pronunciation import display_words, resolve_readings
from speech_plan import apply
from terminology_review import inspect_terminology
from video_quality import extract_samples, probe, review_points
from voice_quality import export_term_reel


class TeachingMediaTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg is required for actual audio checks')
    def test_continuity_checks_embedded_audio_and_respects_punctuation(self):
        from speech_continuity import inspect
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            rate=8000
            audio=array.array('h')
            for duration,value in ((.30,3800),(.38,0),(.44,3800),(.03,0),(.50,3800)):
                audio.extend(array.array('h',[value]*8+[-value]*8)*(round(rate*duration)//16))
            with wave.open(str(path/'test.wav'),'wb') as out:
                out.setparams((1,2,rate,0,'NONE','not compressed'))
                out.writeframes(audio.tobytes())
            video=path/'test.mp4'
            subprocess.run(['ffmpeg','-v','error','-i',str(path/'test.wav'),'-c:a','aac',str(video)],check=True)
            first={'id':'first','tts':'宽高比。','start':0,'end':1.12,'words':[
                {'text':'宽','start':.02,'end':.30},{'text':'高','start':.68,'end':.87},
                {'text':'比','start':.87,'end':1.1}]}
            second={'id':'second','tts':'继续。','start':1.15,'end':1.63}
            timeline={'pages':[{'id':'page','cues':[first,second]}]}
            report=inspect(video,timeline)
            self.assertEqual(report['aligned_cues'],1)
            self.assertEqual([r['kind'] for r in report['candidates']],['split-phrase','tight-join'])
            first['tts']='宽，高比。'
            first['pause_reason']='observe_motion'
            self.assertEqual(inspect(video,timeline)['candidates'],[])

    def test_extended_edition_compares_only_matching_material(self):
        subjects = [{'title': '径向方程', 'pages': ['p'], 'mode': 'derive', 'reason': '列式', 'spoken_chars': 160},
                    {'title': '单位矢量', 'pages': ['q'], 'mode': 'explain', 'reason': '由图求导', 'spoken_chars': 120,
                     'extension': {'outcome': '能对动基矢求导', 'used_in': '计算径向加速度'}}]
        source = {'audience':'竞赛学生', 'sections':subjects, 'reference_timeline':'old.json'}
        plan = estimate(source)
        self.assertEqual(plan['base_seconds'], 53)
        self.assertGreater(plan['extension_seconds'], 0)
        self.assertIn('计算径向加速度', markdown(plan))

        def page(pid, speech, end):
            return {'id':pid, 'duration':end, 'cues':[{'id':'c'+pid,'tts':speech,'start':0,'end':end}],
                    'strokes':[{'cue':'c'+pid,'action':0,'start':1,'end':end,'points':[[0,0],[5,6]]}]}
        old = {'draft':False,'pages':[page('p','同一句话',30)]}
        new = {'draft':False,'duration':90,'pages':[page('p','同一句话',40),page('q','增加一项推导',50)]}
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            (project/'old.json').write_text(json.dumps(old))
            info = report(project, {'duration_plan':source}, new)
        comparison = info['pace_comparison']
        self.assertEqual(comparison['spoken_seconds'], [30,40])
        self.assertEqual(comparison['matched_actions'], 1)
        self.assertEqual(len(comparison['issues']), 2)
        new['pages'][0]['strokes'][0]['points'][1] = [9,9]
        self.assertEqual(compare_pace(old,new)['matched_actions'],0)
        del subjects[-1]['extension']['used_in']
        with self.assertRaisesRegex(ValueError,'used_in'):
            estimate(source)

    def test_pen_writes_contiguously_until_the_next_word_anchor(self):
        def block(at=None):
            return {'at':at,'strokes':[{'points':[[1,1],[30,1]]}]}
        cue={'id':'a','tts':'现在画线','pause':.3,'blocks':[block(),block(),block(.75)]}
        audio={'duration':30}
        events=schedule(cue,audio,classroom=True)
        self.assertLess(events[1]['start'],.5)
        self.assertAlmostEqual(events[2]['start'],22.5)
        self.assertGreater(schedule(cue,audio)[1]['start'],5)

    def test_contextual_symbols_do_not_replace_identifiers(self):
        self.assertEqual(resolve_readings('沿 x 轴看 exp 和 x_0，X 不变。',{'x':'横坐标'}),
                         '沿 ex 轴看 exp 和 x_0，ex 不变。')
        with self.assertRaises(ValueError):
            resolve_readings('写出 exp 和 x_0',{'x':'压缩量'})
        with self.assertRaises(ValueError):
            resolve_readings('沿 x 轴',{'x':' '})

    def test_local_voice_gets_letter_names_and_contextual_tones(self):
        sentence = '用 x 表示长度，长度增长时，相位差改变。取 5 m，速率单位是 m/s。'
        lesson = {'speech':{'backend':'user'},'pages':[{'id':'p','cues':[{'id':'c','tts':sentence}]}]}
        with tempfile.TemporaryDirectory() as folder:
            cooked,_ = apply(folder,lesson)
        entry, = inspect_script(cooked)['tts_inputs']
        self.assertEqual(entry['script'],sentence)
        self.assertEqual(entry['text'],'用 ex 表示常度，常度增长时，向位差改变。取 5 m，速率单位是 m/s。')
        self.assertEqual(entry['letters'],{'x':'X /ɛks/'})
        self.assertEqual(entry['pinyin']['长度'],'chang2 du4')
        self.assertEqual(entry['pinyin']['增长'],'zeng1 zhang3')
        self.assertNotIn('相位',entry['pinyin'])
        from pronunciation import matched_pronunciations,LETTER_IPA
        self.assertEqual(len(LETTER_IPA),26)
        self.assertEqual(resolve_readings('直线AB与DNA。'),'直线 ay bee 与DNA。')
        from pronunciation import local_tts_text
        terms = matched_pronunciations('相位差与重合')
        self.assertEqual(local_tts_text('相位差与重合', terms, {'重合':'崇合'}), '向位差与崇合')
        self.assertEqual(local_tts_text('相位差与重合', terms, {'重合':'崇合'}, {'重合':None}), '向位差与重合')
        self.assertEqual(matched_pronunciations('不同相干条件'),{'相干':'xiang1 gan1'})
        self.assertEqual(resolve_readings('x，y，F。'), 'ex，why，eff。')
        self.assertEqual(resolve_readings('x', {'x':'艾克斯'}), 'ex')

    def test_formula_variables_survive_legacy_quantity_aliases(self):
        from oralize import render_parts
        raw = render_parts([{'latex':r'x_0^2=2gh'}],{'x':'横坐标','g':'重力加速度'})
        self.assertIn('x下标零的平方',raw)
        self.assertIn('g乘h',raw)
        self.assertIn('ex 下标零的平方',resolve_readings(raw))

    def test_pronunciation_reel_uses_the_original_audio_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            samples=array.array('h',range(4000))
            with wave.open(str(root/'narration.wav'),'wb') as wav:
                wav.setparams((1,2,1000,0,'NONE','not compressed'))
                wav.writeframes(samples.tobytes())
            cue={'id':'c','start':1,'end':2,'tts':'x 与长度','symbol_readings':{'x':'压缩量'}}
            terms,_ = inspect_terminology({'pages':[{'id':'p','cues':[cue]}]})
            result=export_term_reel(root,terms['items'])
            self.assertEqual(result['status'],'pending_listening')
            self.assertEqual(len(result['clips']),1)
            self.assertEqual([t['reading'] for t in result['clips'][0]['terms']],['X /ɛks/','chang2 du4'])
            with wave.open(result['audio'],'rb') as wav:
                self.assertEqual(wav.readframes(5),samples[350:355].tobytes())
            self.assertIsNone(export_term_reel(root,[])['audio'])
            self.assertFalse(Path(result['audio']).exists())

    def test_synthesis_gets_the_reading_but_captions_and_anchors_keep_x(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=Path(tmp)
            wav=project/'fake.wav'
            with wave.open(str(wav),'wb') as handle:
                handle.setparams((1,2,24000,0,'NONE','not compressed'))
                handle.writeframes(bytes(24000*2))
            cues=[{'id':'a','tts':'看x','symbol_readings':{'x':'横坐标'},'speech_group':'g'},
                  {'id':'b','tts':'看相位','minimax_pronunciation':{'相位':'xiang4 wei4'},'speech_group':'g'}]
            lesson,_=apply(project,{'title':'测试','pages':[{'id':'p','cues':cues}],'speech':{'backend':'minimax'}})
            self.assertEqual(inspect_script(lesson)['tts_inputs'][0]['text'],'看 ex')
            page=lesson['pages'][0]
            page.update(index=0,title='图',camera='static')
            for cue in page['cues']:
                cue.update(text=cue['tts'],blocks=[])
            calls=[]
            def fake(project, cfg, cue):
                text=cue['tts']
                calls.append((text,cue.get('minimax_pronunciation')))
                words=[{'text':c,'start':i/len(text),'end':(i+1)/len(text)} for i,c in enumerate(text)]
                return {'file':str(wav),'duration':1.,'words':words,'cache_hit':False}
            with patch('voice.synth',side_effect=fake):
                timeline,_,_=prepare(project,lesson,[page],argparse.Namespace(backend=None,voice=None,draft=False,fps=24))
            self.assertEqual(calls,[('看 ex',None),('看相位',{'相位':'xiang4 wei4'})])
            cue=timeline['pages'][0]['cues'][0]
            self.assertEqual(''.join(e[2] for e in chunks(cue,0)),'看x')
            self.assertEqual(anchor({'word':'x'},cue,{'duration':1,'words':cue['words']}),(.5,'provider-word'))
            self.assertEqual(display_words('x',{'x':'横坐标'},[{'text':'异常'}]),[])

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'needs FFmpeg and ffprobe')
    def test_mp4_metadata_and_original_resolution_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);video=root/'delivery.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=160x96:r=12',
                            '-f','lavfi','-i','sine=frequency=440','-t','2','-c:v','libx264',
                            '-c:a','aac',str(video)],check=True)
            media=probe(video)
            self.assertEqual((media['video_codec'],media['audio_codec'],media['fps']),('h264','aac',12))
            self.assertEqual(media['size_bytes'],video.stat().st_size)
            timeline=[{'id':'p','duration':2,'strokes':[{'cue':'c','action':0,'start':.3,'end':.9}],
                       'scene_tracks':{'events':[{'start':.2,'end':1.2,'from':0,'to':1}]}}]
            pages=[{'id':'p','cues':[{'id':'c','blocks':[{'kind':'math','size':24}]}]}]
            points=review_points(timeline,pages)
            results=extract_samples(video,media,points,root/'samples')
            self.assertEqual([s['kind'] for s in results],['formula','writing','motion'])
            from PIL import Image
            for sample in results:
                with Image.open(sample['image']) as image:
                    self.assertEqual(image.size,(160,96))
