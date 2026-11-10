import copy,hashlib,json,math,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from intake import register
from pursuit import setup,state
from models import bind_cues,motion_report
from cards import source_image,problem_latex,problem_card
from course import compile_lesson
from teaching import audit

class ProblemWorkflowTests(unittest.TestCase):
    def fixture(self,p):
        problem=p/'problem.md';solution=p/'solution.md';problem.write_text('目标点沿水平直线运动，追逐点始终朝向目标。');solution.write_text('沿视线和水平方向分别作速度投影。')
        register(p,[problem],self_solve=True)
        manifest=json.loads((p/'input-manifest.json').read_text());manifest.update(statement_file='problem.md',solution_file='solution.md',recognition_reviewed=True,formulas_reviewed=True,solution_reviewed=True,diagram={'mode':'redrawn','sources':[]})
        (p/'input-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False))
        return {'kind':'problem','title':'追逐投影','camera':'static','pages':[{'id':'p1','problem_id':'q1','problem':{'text':'目标点沿水平直线运动，追逐点始终朝向目标。'},'demonstration':{'kind':'pursuit','segments':[{'start_cue':'c1','end_cue':'c1','from':0,'to':.5}]},'cues':[{'id':'c1','tts':'看两点移动，再沿视线作投影。','actions':[{'id':'radial','type':'math','latex':r'\dot r=v_F\cos\theta-v_D','x':665,'y':260,'size':28}]}], 'derivation_steps':[{'id':'s1','depends_on':[],'reason':'沿视线作速度投影','cue_id':'c1','action_id':'radial','result':r'\dot r=v_F\cos\theta-v_D'}]}]}

    def test_intake_preserves_sources_and_records_pending_recognition(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'question.txt';source.write_text('原始题目')
            report=register(p,[source]);manifest=json.loads((p/'input-manifest.json').read_text())
            self.assertIn('参考解答',report['reminder']);self.assertFalse(manifest['recognition_reviewed'])
            self.assertEqual(manifest['solution_origin'],'not_supplied')
            self.assertEqual(manifest['problem_sources'][0]['sha256'],hashlib.sha256(source.read_bytes()).hexdigest())

    def test_problem_card_motion_and_linked_derivation_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);lesson=self.fixture(p);current,pages=compile_lesson(p,lesson);report=audit(p,current,pages)
            self.assertEqual(report['status'],'pass',report);self.assertEqual(report['motion_scenes'],1)
            self.assertTrue(pages[0]['problem_card']['data'].startswith('data:image/png;base64,'))
            timed=bind_cues(pages[0]['demonstration'],[{'id':'c1','start':2,'end':5}]);self.assertEqual(timed['segments'][0]['start'],2)

    def test_gate_rejects_stationary_scene_and_missing_derivation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);lesson=self.fixture(p);lesson['pages'][0]['demonstration']['segments'][0]['to']=0;lesson['pages'][0]['derivation_steps']=[]
            current,pages=compile_lesson(p,lesson);codes={x['code'] for x in audit(p,current,pages)['errors']}
            self.assertIn('motion-required',codes);self.assertIn('derivation-required',codes)

    def test_gate_detects_skipped_dependency_and_result_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);lesson=self.fixture(p);step=lesson['pages'][0]['derivation_steps'][0]
            step['depends_on']=['missing'];step['result']='wrong'
            current,pages=compile_lesson(p,lesson);codes={x['code'] for x in audit(p,current,pages)['errors']}
            self.assertIn('step-order',codes);self.assertIn('step-result',codes)

    def test_formula_review_is_required_before_problem_narration(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);lesson=self.fixture(p);manifest=json.loads((p/'input-manifest.json').read_text())
            manifest['formulas_reviewed']=False;(p/'input-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False))
            current,pages=compile_lesson(p,lesson)
            self.assertIn('formula-review',{x['code'] for x in audit(p,current,pages)['errors']})

    def test_every_problem_has_motion_and_derivation_with_continuation_pages(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);lesson=self.fixture(p);second=copy.deepcopy(lesson['pages'][0]);second['id']='p2'
            second.pop('problem');second.pop('demonstration');second['derivation_steps']=[];second['cues'][0]['id']='c2';lesson['pages'].append(second)
            current,pages=compile_lesson(p,lesson)
            self.assertEqual(audit(p,current,pages)['status'],'pass')
            second['problem_id']='q2';second['problem']={'text':'第二道题的题目。'}
            current,pages=compile_lesson(p,lesson);report=audit(p,current,pages)
            errors={(x['code'],x['message'].split(':')[0]) for x in report['errors']}
            self.assertIn(('motion-required','q2'),errors);self.assertIn(('derivation-required','q2'),errors)

    def test_crop_uses_original_pixel_coordinates(self):
        from PIL import Image
        import base64,io
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);image=Image.new('RGB',(20,10),'white');image.paste('red',(10,0,20,10));image.save(p/'scan.png')
            result=source_image(p,{'file':'scan.png','crop':[10,0,20,10],'x':150,'y':250,'w':50,'h':50})
            cropped=Image.open(io.BytesIO(base64.b64decode(result['data'].split(',')[1])))
            self.assertEqual(cropped.size,(10,10));self.assertEqual(cropped.getpixel((5,5)),(255,0,0))
            with self.assertRaises(ValueError):source_image(p,{'file':'scan.png','crop':[10,0,21,10]})

    def test_latex_preserves_math_structure_and_escapes_prose(self):
        text=r'速率 $v_D>v_F$，求 $\frac{d\vec r}{dt}$；长度误差 1% & 2%。'
        body,formulas=problem_latex(text)
        self.assertEqual(formulas,[r'v_D>v_F',r'\frac{d\vec r}{dt}'])
        self.assertIn(r'1\% \& 2\%',body)
        with self.assertRaises(ValueError):problem_latex('夹角 θ 为变量。')
        with self.assertRaises(ValueError):problem_latex(r'求 $\frac{dr}{dt}')

    def test_actual_latex_card_keeps_editable_source_and_rejects_overflow(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);font=Path('/System/Library/Fonts/Supplemental/Songti.ttc')
            if not font.exists():self.skipTest('Set up the Chinese font for the integration render')
            result=problem_card({'text':r'求 $\frac{d\vec r}{dt}$，已知 $v_D>v_F$。'},font,p/'tex')
            self.assertEqual(result['renderer'],'xelatex');self.assertIn(r'\frac{d\vec r}{dt}',result['latex_source'])
            self.assertEqual(len(list((p/'tex').glob('*/problem.pdf'))),1)
            with self.assertRaisesRegex(ValueError,'fit|width|page'):
                problem_card({'text':'给定条件。'*150,'rect':[145,100,1035,125]},font,p/'tex')

    def test_pursuit_matches_speed_direction_and_weighted_invariant(self):
        m=setup({'kind':'pursuit'});u,v,L=m['vF'],m['vD'],m['L']
        for q in (.1,.3,.5,.8):
            t,fox,dog,y=state(m,q);r=math.hypot(fox-dog,y)
            self.assertAlmostEqual(v*r+u*(fox-dog),v*L-(v*v-u*u)*t,places=6)
            h=1e-5;a=state(m,q-h);b=state(m,q+h);dt=b[0]-a[0];velocity=[(b[2]-a[2])/dt,(b[3]-a[3])/dt]
            self.assertAlmostEqual(math.hypot(*velocity),v,places=3)
            self.assertAlmostEqual(velocity[0]/v,(fox-dog)/r,places=3)
            self.assertAlmostEqual(velocity[1]/v,-y/r,places=3)
        end=state(m,1);self.assertAlmostEqual(end[1],end[2]);self.assertEqual(end[3],0)
        self.assertTrue(motion_report(m)['moving'])

    @unittest.skipUnless(shutil.which('node'),'Node is needed for HTML model parity')
    def test_html_and_python_sample_identical_pursuit_states(self):
        m=setup({'kind':'pursuit'});fractions=[0,.1,.45,.87,1]
        script="const vm=require('vm'),fs=require('fs');const c={};vm.createContext(c);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),c);const p=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(p.f.map(f=>c.pursuitState(p.m,f))));"
        run=subprocess.run(['node','-e',script,str(ROOT/'assets/models.js')],input=json.dumps({'m':m,'f':fractions}),text=True,capture_output=True,check=True)
        for a,b in zip(json.loads(run.stdout),[state(m,f) for f in fractions]):
            for x,y in zip(a,b):self.assertAlmostEqual(x,y,places=12)

    @unittest.skipUnless(os.environ.get('PHYSICS_MANIM_PYTHON') and shutil.which('ffmpeg'),'Manim runtime is needed for the pixel regression render')
    def test_manim_preserves_the_visible_time_derivative_dot(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);Image.new('RGB',(1280,720),'white').save(p/'paper.png')
            payload={'width':1280,'height':720,'fps':12,'background':str(p/'paper.png'),'page':{'camera':'static','frames':12,'strokes':[{'points':[[640,350],[640.01,350]],'color':'#205b96','width':3,'start':0,'end':.05},{'points':[[635,374],[635,362],[638,360],[642,362]],'color':'#205b96','width':3,'start':0,'end':.05}]}}
            (p/'payload.json').write_text(json.dumps(payload))
            subprocess.run([os.environ['PHYSICS_MANIM_PYTHON'],str(ROOT/'scripts/manim_renderer.py'),'--input',str(p/'payload.json'),'--output',str(p/'dot.mp4')],check=True,capture_output=True,text=True)
            subprocess.run(['ffmpeg','-v','error','-y','-ss','0.5','-i',str(p/'dot.mp4'),'-frames:v','1',str(p/'frame.png')],check=True,capture_output=True)
            crop=Image.open(p/'frame.png').convert('RGB').crop((635,345,646,356))
            blue=sum(b>r+30 and b>g+15 for r,g,b in crop.getdata())
            self.assertGreaterEqual(blue,4,'The time derivative dot disappeared from the actual Manim video')

if __name__=='__main__':unittest.main()
