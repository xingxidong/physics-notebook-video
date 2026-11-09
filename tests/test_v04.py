import copy,json,math,shutil,subprocess,sys,tempfile,unittest,wave
from array import array
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from oralize import oralize_latex,render_parts
from speech_plan import apply,externalize
from voice import master
from voice_quality import audit
from voice_clone import apply_voice,inspect_audio
from layout import page_spec,expand_actions,place_action,focus_spec,focus_state,audit_lesson


class VoiceV04Tests(unittest.TestCase):
    def test_formula_oralizer_handles_physics_structure(self):
        value=oralize_latex(r'E(r)=\frac{Q}{4\pi\varepsilon_0 r^2}')
        self.assertIn('电场强度关于距离r的函数',value)
        self.assertIn('分子是电荷量Q',value)
        self.assertIn('距离r的平方',value)
        self.assertNotIn('\\frac',value)
        self.assertEqual(render_parts(['所以，',{'latex':r'\vec F=q\vec E'},'。']).count('所以'),1)

    def test_external_speech_plan_and_role_resolution(self):
        lesson={'title':'test','speech':{'backend':'user'},'pages':[{'id':'p01','cues':[{'id':'turn','tts':'旧口语','pause':1.1,'actions':[]}]}]}
        with tempfile.TemporaryDirectory() as folder:
            legacy,_=apply(folder,lesson);self.assertEqual(legacy['pages'][0]['cues'][0]['role'],'legacy');self.assertNotIn('speed',legacy['pages'][0]['cues'][0])
        clean,plan=externalize(lesson)
        self.assertNotIn('tts',clean['pages'][0]['cues'][0]);self.assertEqual(plan['cues']['turn']['pause_after'],1.1)
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);(project/'speech-plan.json').write_text(json.dumps({'version':1,'cues':{'turn':{'role':'key_turn','tts_parts':['由图可得，',{'latex':r'v^2=2gh'},'。'],'emphasis':['由图可得']}}},ensure_ascii=False))
            clean['speech_plan']='speech-plan.json';merged,meta=apply(project,clean);cue=merged['pages'][0]['cues'][0]
            self.assertEqual(cue['role'],'key_turn');self.assertEqual(cue['speed'],.92);self.assertEqual(cue['pause_before'],.28)
            self.assertIn('速度v的平方',cue['tts']);self.assertEqual(meta['source'],'speech-plan.json')

    @unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg is required')
    def test_mastering_preserves_duration_and_audit_writes_report(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);source=project/'narration.wav';rate=24000;duration=2.0
            samples=array('h',(round(7000*math.sin(2*math.pi*220*i/rate)) for i in range(round(rate*duration))))
            with wave.open(str(source),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(samples.tobytes())
            info=master(project,{'audio_mastering':True},source,duration);self.assertTrue(info['enabled'])
            with wave.open(str(source)) as w:self.assertAlmostEqual(w.getnframes()/w.getframerate(),duration,places=3)
            data={'pages':[{'cues':[{'id':'c1','tts':'由图可得，速度方向沿斜面向下。','start':0,'end':2,'words':[]}]}]}
            report=audit(project,data);self.assertEqual(report['duration'],2.0);self.assertTrue((project/'voice-report.json').exists())

    @unittest.skipUnless(shutil.which('ffprobe'),'ffprobe is required')
    def test_clone_input_validation_and_local_voice_application(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);source=project/'teacher.wav';rate=24000;duration=10.1
            samples=array('h',(round(4000*math.sin(2*math.pi*180*i/rate)) for i in range(round(rate*duration))))
            with wave.open(str(source),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(samples.tobytes())
            self.assertGreater(inspect_audio(source)['duration'],10)
            (project/'lesson.json').write_text(json.dumps({'title':'x','pages':[]},ensure_ascii=False));apply_voice(project,'PhysicsTeacher01')
            lesson=json.loads((project/'lesson.json').read_text());self.assertEqual(lesson['speech']['voice'],'PhysicsTeacher01')

    def test_semantic_layout_formula_steps_and_focus(self):
        spec=page_spec('one-page-problem');actions=expand_actions([{'type':'formula_steps','id':'energy','steps':[r'E_k=\frac{1}{2}mv^2',r'E_k+E_p=C']}],spec)
        self.assertEqual(sum(a['type']=='math' for a in actions),2);self.assertFalse(any(a['type']=='arrow' for a in actions))
        placed=place_action({'type':'text','text':'方向','zone':'explanation','place':{'line':1}},spec,{})
        self.assertGreater(placed['x'],140);self.assertGreater(placed['y'],500)
        focus=focus_spec('diagram',spec);page={'focus':[{**focus,'start':1,'end':3}]}
        self.assertGreater(focus_state(page,2)['zoom'],1);self.assertEqual(focus_state(page,8)['zoom'],1)
        report=audit_lesson([{'id':'p1','problem_id':'same','cues':[]},{'id':'p2','problem_id':'same','cues':[]}]);self.assertEqual(report['warnings'][0]['code'],'problem-spans-pages')

    @unittest.skipUnless(shutil.which('ffmpeg') and Path('/System/Library/Fonts/Supplemental/Songti.ttc').exists(),'formal build needs ffmpeg and a Chinese font')
    def test_formal_course_build_runs_mastering_and_voice_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);rate=24000;duration=2.2;source=project/'input.wav'
            samples=array('h',(round(5000*math.sin(2*math.pi*200*i/rate)) for i in range(round(rate*duration))))
            with wave.open(str(source),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(samples.tobytes())
            lesson={'title':'正式构建测试','show_titles':False,'speech':{'backend':'user','audio_mastering':True},'speech_plan':'speech-plan.json','pages':[{'id':'p01','title':'内部页名','layout':'one-page-problem','problem_id':'motion-01','cues':[{'id':'c1','text':'速度方向沿斜面向下。','audio':'input.wav','focus':{'zone':'derivation','zoom':1.05},'actions':[{'type':'formula_steps','id':'velocity','zone':'derivation','steps':['v=v_0+at','v^2=v_0^2+2ax'],'color':'blue'}]}]}]}
            plan={'version':1,'cues':{'c1':{'role':'conclusion','tts':'所以，速度方向沿斜面向下。','emphasis':['速度方向']}}}
            (project/'lesson.json').write_text(json.dumps(lesson,ensure_ascii=False));(project/'speech-plan.json').write_text(json.dumps(plan,ensure_ascii=False))
            run=subprocess.run([sys.executable,str(ROOT/'scripts/course.py'),'build',str(project),'--video','--fps','12'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr);self.assertTrue((project/'voice-report.json').exists());self.assertTrue((project/'prosody.json').exists());self.assertTrue((project/'video.mp4').exists())
            report=json.loads((project/'build-report.json').read_text());self.assertTrue(report['audio_mastering']['enabled']);self.assertEqual(report['layout_quality'],'pass')


if __name__=='__main__':unittest.main()
