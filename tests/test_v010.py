import copy,json,math,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from course import compile_lesson,prepare
from scene_events import bind,value,validate
from teaching import audit

class SemanticSceneTests(unittest.TestCase):
    def source(self):
        return {'scene_initial':{'phase':0},'scene_events':[{'id':'peak','track':'phase','cue_id':'c','at':{'word':'看'},'until':{'at':{'word':'最大'}},'to':math.pi/2}],
                'cues':[{'id':'c','tts':'看磁通达到最大'}]}
    def timed(self):
        return [{'id':'c','tts':'看磁通达到最大','start':2,'end':8,'words':[{'text':'看','start':.2,'end':.5},{'text':'磁通达到','start':.5,'end':3.8},{'text':'最大','start':4,'end':4.5}]}]
    def test_provider_word_anchors_and_peak_hold(self):
        tracks=bind(self.source(),self.timed(),9);e=tracks['events'][0]
        self.assertEqual(e['anchor_quality'],'provider-word');self.assertEqual(e['start'],2.2);self.assertEqual(e['end'],6)
        self.assertAlmostEqual(value(tracks,'phase',4.1),math.pi/4)
        self.assertAlmostEqual(math.cos(value(tracks,'phase',8.9)),0)
    def test_missing_words_and_overlaps_fail(self):
        p=self.source();p['scene_events'][0]['at']={'word':'missing'}
        with self.assertRaises(ValueError):validate(p)
        p=self.source();e=copy.deepcopy(p['scene_events'][0]);e['id']='overlap';p['scene_events'].append(e)
        with self.assertRaisesRegex(ValueError,'overlapping'):bind(p,self.timed(),9)
    def test_fallback_timing_is_labelled_and_continuous(self):
        timed=self.timed();timed[0]['words']=[];tracks=bind(self.source(),timed,9)
        self.assertEqual(tracks['events'][0]['anchor_quality'],'estimated-word')
        end=tracks['events'][0]['end'];self.assertAlmostEqual(value(tracks,'phase',end-1e-8),value(tracks,'phase',end+1e-8),places=7)
    def test_out_of_cue_offset_and_nonfinite_are_rejected(self):
        p=self.source();p['scene_events'][0]['at']['offset']=-5
        with self.assertRaises(ValueError):bind(p,self.timed(),9)
        p=self.source();p['scene_initial']['phase']=float('nan')
        with self.assertRaises(ValueError):validate(p)

class ConceptCoverageTests(unittest.TestCase):
    def fixture(self):
        return {'kind':'concept','title':'inductance','knowledge_points':[{'id':'identity','name':'Identity','page_id':'p','statement':'Identity holds.','statement_action_ids':['statement']}],
          'pages':[{'id':'p','motion_not_applicable':'This board derives a fixed algebraic identity.',
          'cues':[{'id':'c','tts':'The terms are equal.','actions':[{'id':'a','type':'math','latex':'x=x','x':200,'y':200},{'id':'statement','type':'text','text':'Identity holds.','x':200,'y':280}]}],
          'derivation_steps':[{'id':'s','depends_on':[],'reason':'Identity','cue_id':'c','action_id':'a','result':'x=x'}]}]}
    def test_concepts_require_recorded_math_links(self):
        with tempfile.TemporaryDirectory() as d:
            l,p=compile_lesson(d,self.fixture());r=audit(d,l,p);self.assertEqual(r['status'],'pass');self.assertEqual(r['derivation_steps'],1)
            l['pages'][0]['derivation_steps']=[]
            self.assertIn('concept-step-required',{e['code'] for e in audit(d,l,p)['errors']})
    def test_concept_cannot_silently_skip_motion(self):
        with tempfile.TemporaryDirectory() as d:
            source=self.fixture();source['pages'][0].pop('motion_not_applicable')
            l,p=compile_lesson(d,source);self.assertIn('concept-motion-required',{e['code'] for e in audit(d,l,p)['errors']})
    def test_reviewed_native_motion_is_counted(self):
        with tempfile.TemporaryDirectory() as d:
            source=self.fixture();page=source['pages'][0];page.pop('motion_not_applicable');page.update(native_scenes={'manim':{'source':'scene.py'}},motion_reviewed=True,motion_description='Current and field change together.')
            l,p=compile_lesson(d,source);r=audit(d,l,p);self.assertEqual(r['motion_scenes'],1);self.assertEqual(r['coverage'][0]['motion'],'checked')
    def test_unchecked_legacy_course_is_not_called_pass(self):
        with tempfile.TemporaryDirectory() as d:
            source=self.fixture();source.pop('kind');source['pages'][0]['derivation_steps']=[]
            l,p=compile_lesson(d,source);self.assertEqual(audit(d,l,p)['status'],'not_applicable')
    def test_formula_steps_links_resolve_to_expanded_actions(self):
        with tempfile.TemporaryDirectory() as d:
            source=self.fixture();p=source['pages'][0];p['layout']='full-derivation'
            p['cues'][0]['actions']=[{'type':'formula_steps','id':'chain','steps':['x=x']},p['cues'][0]['actions'][1]]
            p['derivation_steps'][0]['action_id']='chain-step-1'
            l,pages=compile_lesson(d,source);self.assertEqual(audit(d,l,pages)['status'],'pass')

    def test_silent_preview_preserves_final_assets_and_records_pending_review(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        import course
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=self.fixture();source['pages'][0].pop('motion_not_applicable')
            (p/'lesson.json').write_text(json.dumps(source))
            names=('narration.wav','timeline.json','video.mp4')
            for name in names:(p/name).write_bytes(b'keep existing final asset')
            with patch.object(sys,'argv',['course.py','preview',d]),patch('voice.synth',side_effect=AssertionError('Preview called TTS')),patch('engine_render.render',return_value={}) as render,redirect_stdout(io.StringIO()):
                course.main()
            for name in names:self.assertEqual((p/name).read_bytes(),b'keep existing final asset')
            self.assertTrue(render.call_args.kwargs['preview'])
            self.assertTrue(render.call_args.args[1]['pages'][0]['draft_preview'])
            self.assertEqual(json.loads((p/'draft-preview-teaching-report.json').read_text())['status'],'attention')

class HandwrittenMathTests(unittest.TestCase):
    def fixture(self, formula):
        action = {'type':'math','latex':formula,'x':200,'y':180,'size':32,'write_seconds':3}
        return {'title':'math','pages':[{'id':'p','cues':[{
            'id':'c','tts':'Watch the denominator as the formula is written.', 'actions':[action],
        }]}]}

    def test_legacy_tex_settings_compile_to_sequential_pen_strokes(self):
        source = self.fixture(r'\Psi_1=\frac{\kappa\sqrt{L_1L_2}}{\ell}')
        source['math_renderer'] = 'tex'
        source['pages'][0]['cues'][0]['actions'][0]['renderer'] = 'tex'
        args = SimpleNamespace(backend=None,voice=None,fps=24,draft=True)
        with tempfile.TemporaryDirectory() as d:
            lesson,pages = compile_lesson(d,source)
            data,_,_ = prepare(Path(d),lesson,pages,args)
            strokes = data['pages'][0]['strokes']
            self.assertGreater(len(strokes),10)
            self.assertTrue(all(len(stroke['points'])>=2 and 'data' not in stroke for stroke in strokes))
            self.assertTrue(all(a['end']<b['start'] for a,b in zip(strokes,strokes[1:])))
            self.assertGreater(strokes[-1]['end']-strokes[0]['start'],2.8)

    def test_unsupported_command_reports_missing_handwriting_support(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'Unsupported LaTeX command'):
                compile_lesson(d,self.fixture(r'\begin{pmatrix}1&0\end{pmatrix}'))

if __name__=='__main__':unittest.main()
