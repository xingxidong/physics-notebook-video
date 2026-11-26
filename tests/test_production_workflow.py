import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from course import digest
from handout_bundle import build,digest as file_hash,verified
from lesson_review import fingerprint
from production_workflow import audition,checkpoint,dispatch,effective,save,scope,signature,status
from step_review import source_check
from workflow_eval import run


class ProductionTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.project=Path(folder.name).resolve()
        self.lesson={'title':'力矩','pages':[{'id':'p','cues':[{'id':c,'tts':c,'actions':[]} for c in ('a','b','c')]}]}

    def test_classroom_regressions(self):
        first=run()
        self.assertEqual(first['status'],'pass',first)
        self.assertFalse(run(first)['regressions'])

    def test_physics_revision_reaches_dependent_pages(self):
        lesson=deepcopy(self.lesson)
        lesson.update(conventions={'origin':'O','direction':'右'})
        lesson['pages'][0]['derivation_steps']=[dict(id='s',cue_id='b',action_id='line',uses_conventions=['origin'])]
        lesson['pages'].append(dict(id='next',cues=[dict(id='b',tts='later')],
            derivation_steps=[dict(id='s',cue_id='b',action_id='new',upstream_steps=['p/s'])]))
        before=signature(lesson)
        lesson['conventions']['origin']='P'
        report=scope(lesson,before)
        self.assertEqual(report['changed'],['p/b','next/b'])
        self.assertEqual(len(report['adjacent_seams']),3)
        self.assertEqual(report['physics_steps'],['next/s','p/s'])
        with self.assertRaises(ValueError):
            scope(lesson,{},['b'])
        self.assertTrue(scope(lesson,{},conventions=['direction'])['review_entire_course'])

    @unittest.skipUnless(shutil.which('xelatex') or Path('/Library/TeX/texbin/xelatex').exists(),'requires XeLaTeX')
    def test_source_bundle_rebuild_and_stale_nested_tikz(self):
        p=self.project; (p/'part').mkdir()
        (p/'student.tex').write_text(r'\documentclass{article}\usepackage{tikz}\begin{document}\input{part/derivation}\end{document}')
        (p/'part/derivation.tex').write_text(r'\begin{equation}M=Fd\label{eq:moment}\end{equation}\input{part/arm.tikz}')
        fig=p/'part/arm.tikz';fig.write_text(r'\tikz\draw (0,0)--(1,1);')
        lesson={**self.lesson,'handout':'student.tex','handout_source':'student.tex'}
        receipt=build(p,lesson)
        with zipfile.ZipFile(p/receipt['archive']) as z:
            self.assertEqual(set(z.namelist()),{'student.tex','part/derivation.tex','part/arm.tikz'})
        sha=fingerprint(p,lesson)
        self.assertTrue(verified(p,lesson))
        fig.write_text(r'\tikz\draw (0,0)--(1,2);')
        self.assertFalse(verified(p,lesson))
        self.assertNotEqual(sha,fingerprint(p,lesson))
        lesson['pages'][0]['derivation_steps']=[dict(id='s',cue_id='a',question='取矩点在哪？',spoken_anchor='力矩',handout_label='eq:wrong')]
        self.assertIn('step-handout',[r['code'] for r in source_check(p,lesson)])
        step=lesson['pages'][0]['derivation_steps'][0]
        step.update(handout_label='eq:moment',result='M=-Fd')
        self.assertIn('step-handout-equation',[r['code'] for r in source_check(p,lesson)])
        fig.unlink()
        with self.assertRaisesRegex(ValueError,'编译失败'):
            build(p,lesson)
        self.assertEqual(file_hash(p/receipt['archive']),receipt['archive_sha256'])

    @unittest.skipUnless(shutil.which('ffmpeg'),'requires FFmpeg')
    def test_changed_only_from_final_and_refuse_stale_or_unchanged_media(self):
        p=self.project
        save(p/'lesson.json',self.lesson); lesson=effective(p)
        time={'draft':False,'lesson_sha256':digest(lesson),'pages':[{'id':'p','start':.25,'cues':
              [{'id':c,'start':i,'end':i+.7} for i,c in enumerate('abc')]}]}
        save(p/'timeline.json',time)
        media=p/'video.mp4'
        def encode(freq):
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'sine=frequency={freq}:duration=4',
                            '-f','lavfi','-i','color=s=64x64:d=4','-c:v','libx264','-c:a','aac','-shortest',str(media)],check=True)
        encode(440);checkpoint(p,lesson,time,media)
        self.assertEqual(status(p)['stage'],'rendered')
        args=argparse.Namespace(command='revise',project=p,cue=['b'],convention=[])
        self.assertEqual(dispatch(args)['changed'],['p/b'])
        with self.assertRaisesRegex(ValueError,'尚无新的成片'):
            audition(p)
        time['pages'][0]['cues'][2].update(start=2.1,end=2.8)
        save(p/'timeline.json',time)
        encode(550);checkpoint(p,lesson,time,media)
        result=audition(p)
        start,end,keys=result['windows_in_final'][0]
        self.assertAlmostEqual(start,.45)
        self.assertAlmostEqual(end,2.85)
        self.assertEqual(result['shifted_cues'],['p/c'])
        self.assertEqual(keys,['p/b'])
        self.assertTrue((p/result['file']).is_file())
        with media.open('ab') as stream:
            stream.write(b'x')
        self.assertEqual(status(p)['stage'],'timed')
        with self.assertRaisesRegex(ValueError,'已经更换'):
            audition(p)
