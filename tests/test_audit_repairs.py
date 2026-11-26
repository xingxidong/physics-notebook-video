import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import final_review
import platform_install
from learning_bundle import sync_references,write_reference_history
from production_workflow import signature,scope
from step_review import source_check,inspect
from lesson_review import export_delivery
from team import init


class AuditRepairs(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.p=Path(temp.name).resolve()
        self.lesson={'workflow_version':1,'handout_source':'lesson.tex','handout':'lesson.tex',
                     'pages':[{'id':'p1','cues':[{'id':'c1','tts':'力等于质量乘加速度。'}],
                        'derivation_steps':[{'id':'s1','cue_id':'c1','action_id':'formula1','question':'力是多少？',
                        'spoken_anchor':'力等于质量乘加速度','handout_label':'eq:force','result':'F=ma'}]}]}
        (self.p/'lesson.tex').write_text(r'\documentclass{article}\begin{document}\begin{equation}F=ma\label{eq:force}\end{equation}\end{document}')

    def test_whole_formula_and_correct_align_row(self):
        p=self.p/'lesson.tex'
        self.assertFalse(source_check(self.p,self.lesson))
        for expression in ('F=ma+1','-F=ma','F=ma-F_0'):
            p.write_text(r'\documentclass{article}\begin{document}\begin{equation}'+expression+r'\label{eq:force}\end{equation}\end{document}')
            self.assertIn('step-handout-equation',[r['code'] for r in source_check(self.p,self.lesson)])
        p.write_text(r'\documentclass{article}\begin{document}\begin{align}F&=ma\label{eq:force}\\Q&=mcT\label{eq:heat}\end{align}\end{document}')
        self.assertFalse(source_check(self.p,self.lesson))
        self.lesson['pages'][0]['derivation_steps'][0]['result']='Q=mcT'
        self.assertIn('step-handout-equation',[r['code'] for r in source_check(self.p,self.lesson)])

    def test_status_uses_the_actually_reviewed_captioned_video(self):
        from production_workflow import effective,checkpoint,status
        from course import digest
        from lesson_review import fingerprint
        from handout_bundle import digest as file_hash
        lesson={'pages':[{'id':'p','cues':[{'id':'c','tts':'沿斜面向下。'}]}]}
        (self.p/'lesson.json').write_text(json.dumps(lesson))
        effective_lesson=effective(self.p)
        timeline={'lesson_sha256':digest(effective_lesson),'pages':[]}
        (self.p/'timeline.json').write_text(json.dumps(timeline))
        (self.p/'video.mp4').write_bytes(b'base video')
        captioned=self.p/'video-captioned.mp4';captioned.write_bytes(b'captioned video')
        checkpoint(self.p,effective_lesson,timeline,self.p/'video.mp4')
        report={'stage':'final','status':'reviewed','source_sha256':fingerprint(self.p,effective_lesson),
                'media_sha256':file_hash(captioned),'coverage':{'media':{'file':str(captioned)}},'findings':[]}
        (self.p/'quality-report.json').write_text(json.dumps(report))
        self.assertEqual(status(self.p)['next'],'finalize --video-file '+str(captioned))
        captioned.write_bytes(b'replaced captioned video')
        self.assertEqual(status(self.p)['next'],'quality-check --stage final')

    def test_all_pen_actions_even_without_derivation_metadata(self):
        t={'pages':[{'id':'p1','start':0,'cues':[],
             'strokes':[{'board_id':'a','start':1,'end':3},{'board_id':'b','start':2,'end':4}]}]}
        self.assertEqual(inspect({'pages':[]},t)[0][0]['code'],'parallel-formulas')
        t['pages'][0]['strokes'][1].update(start=3,end=4)
        self.assertFalse(inspect({'pages':[]},t)[0])
        t['pages'].append({'id':'p2','start':1,'strokes':[{'start':.5,'end':1.5}]})
        self.assertTrue(inspect({'pages':[]},t)[0])

    def test_parameters_assets_and_upstream_changes_reach_dependent_step(self):
        lesson=deepcopy(self.lesson)
        lesson['pages'].append({'id':'p2','cues':[{'id':'c2','tts':'用刚得到的力计算加速度。'}],
                               'derivation_steps':[{'id':'s2','action_id':'a2','cue_id':'c2','upstream_steps':['p1/s1']}]})
        before=signature(lesson,self.p)
        changed=deepcopy(lesson);changed['parameters']={'m':5}
        self.assertEqual(scope(changed,before,project=self.p)['changed'],['p1/c1','p2/c2'])
        changed=deepcopy(lesson);changed['pages'][0]['cues'][0]['tts']='还要加上第二个外力。'
        self.assertEqual(scope(changed,before,project=self.p)['physics_steps'],['p1/s1','p2/s2'])
        (self.p/'lesson.tex').write_text((self.p/'lesson.tex').read_text()+'\n% actual source edit')
        self.assertTrue(scope(lesson,before,project=self.p)['review_entire_course'])

    def test_deletion_checks_the_new_join(self):
        lesson={'pages':[{'id':'p','cues':[{'id':x,'tts':x} for x in 'abc']} ]}
        before=signature(lesson)
        del lesson['pages'][0]['cues'][1]
        changed=scope(lesson,before)
        self.assertEqual(changed['removed_cues'],['p/b'])
        self.assertEqual(changed['changed'],['p/a','p/c'])
        self.assertEqual(changed['adjacent_seams'],[['p/a','p/c']])

    def test_export_does_not_roll_back_published_reference(self):
        old,new=self.p/'old',self.p/'new'
        for p in (old,new):(p/'references').mkdir(parents=True)
        name='references/lesson.md'
        (old/name).write_text('old published')
        write_reference_history(old)
        (new/name).write_text('new published')
        write_reference_history(new)
        sync_references(old,new,prefer_incoming=False)
        self.assertEqual((new/name).read_text(),'new published')

    def test_final_check_errors_cannot_be_waived(self):
        (self.p/'video.mp4').write_bytes(b'fixture')
        (self.p/'timeline.json').write_text('{}')
        data={'stage':'final','status':'attention','source_sha256':'fixture',
              'coverage':{'media':{'file':str(self.p/'video.mp4')}},
              'manual_review':{'tasks':[]},'findings':[{'severity':'error','message':'wrong formula'}]}
        data=final_review.attach(self.p,self.lesson,data)
        (self.p/'quality-report.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'未解决'):final_review.require(self.p,self.lesson,self.p/'video.mp4')

    def test_upgrade_and_export_preserve_new_learning(self):
        source,dest,other=(self.p/n for n in ('source','installed','new-computer'))
        for p in (source,dest,other):(p/'references').mkdir(parents=True)
        note='references/ying-xiaolv-example.md'
        (source/note).write_text('original');(dest/note).write_text('original')
        write_reference_history(source)
        (dest/note).write_text('learned local correction')
        sync_references(source,dest)
        self.assertEqual((dest/note).read_text(),'learned local correction')
        (dest/'references/extra.md').write_text('new independent teaching note')
        sync_references(dest,source)
        self.assertEqual((source/note).read_text(),'learned local correction')
        sync_references(source,other)
        self.assertTrue((other/'references/extra.md').exists())
        self.assertEqual((other/note).read_text(),'learned local correction')
        (dest/note).write_text('second independent local edit')
        (source/note).write_text('independently edited source')
        sync_references(source,dest)
        self.assertEqual((dest/note).read_text(),'second independent local edit')
        conflict=json.loads((dest/'assets/learning/reference-conflicts.json').read_text())[-1]
        self.assertEqual((dest/conflict['incoming_file']).read_text(),'independently edited source')
        count=len(json.loads((dest/'assets/learning/reference-conflicts.json').read_text()))
        sync_references(source,dest)
        self.assertEqual(len(json.loads((dest/'assets/learning/reference-conflicts.json').read_text())),count)

    def test_team_preserves_whole_course_production_settings(self):
        settings={'title':'test','kind':'problem','target_minutes':1,'review_required':True,
                  'workflow_version':1,'handout':'lesson.tex','handout_source':'lesson.tex',
                  'duration_plan':'duration.json','conventions':{'origin':'O'},
                  'lesson_arc':{'entry_question':'怎样建立关系？','beats':[]},'opening':{'author':'测试作者'}}
        (self.p/'plan.json').write_text(json.dumps({'course':settings,'sections':[{'id':'a','title':'a','target_minutes':1}]}))
        init(self.p,self.p/'plan.json')
        lesson=json.loads((self.p/'team/course-contract.json').read_text())['lesson']
        for key in ('review_required','workflow_version','handout','handout_source','duration_plan','conventions','lesson_arc','opening'):
            self.assertEqual(lesson[key],settings[key])

    def test_review_receipt_needs_observations_and_expires_on_media_change(self):
        (self.p/'video.mp4').write_bytes(b'synthetic media identity')
        (self.p/'timeline.json').write_text('{}')
        result={'stage':'final','status':'ready_for_review','source_sha256':'present',
                'coverage':{'media':{'file':'video.mp4'}},'findings':[],
                'manual_review':{'status':'pending','tasks':['核对第一句公式与实际落笔。']}}
        result=final_review.attach(self.p,self.lesson,result)
        final_review.save(self.p/'quality-report.json',result)
        with self.assertRaisesRegex(ValueError,'尚未逐项完成'):final_review.require(self.p,self.lesson,self.p/'video.mp4')
        task=result['manual_review']['items'][0]
        with self.assertRaisesRegex(ValueError,'观察结果'):
            final_review.record(self.p,self.lesson,task['id'],task['token'],'tester','pass')
        final_review.record(self.p,self.lesson,task['id'],task['token'],'test fixture','这是隔离测试中的明确观察记录，不表示实听课程。')
        self.assertEqual(final_review.require(self.p,self.lesson,self.p/'video.mp4')['status'],'reviewed')
        (self.p/'video.mp4').write_bytes(b'changed media')
        with self.assertRaises(ValueError):final_review.require(self.p,self.lesson,self.p/'video.mp4')

    def test_semantic_inventory_requires_reading_the_sentence_and_current_board(self):
        from term_inventory import apply,draft
        lesson={'term_inventory_version':2,'pages':[{'id':'p','cues':[{'id':'c','tts':'研究里德伯阻塞对激发的影响。','actions':[]}]}]}
        result=draft(self.p,lesson)
        data=json.loads(Path(result['file']).read_text())
        path=self.p/'term-inventory.json';path.write_text(json.dumps(data))
        self.assertFalse(apply(self.p,lesson)['_term_inventory'])
        row=data['items'][0]
        row.update(reviewer='fixture reviewer',evidence='识别描述的物理效应并给出整词读法。',
                   terms=[{'term':'里德伯阻塞','offset':2}])
        data['readings']={'里德伯阻塞':'li3 de2 bo2 zu3 se4'}
        path.write_text(json.dumps(data))
        self.assertIn('里德伯阻塞',apply(self.p,lesson)['speech']['physics_terms'])
        lesson['pages'][0]['cues'][0]['actions']=[{'type':'text','text':'换过的模型'}]
        self.assertFalse(apply(self.p,lesson)['_term_inventory'])

    def test_qwen_cache_binds_reference_and_actual_local_input(self):
        import wave
        import qwen_voice
        model=self.p/'model';model.mkdir();(model/'model.safetensors').write_bytes(b'fixture')
        ref=self.p/'reference.wav';ref.write_bytes(b'reference1')
        config={'python':sys.executable,'model':str(model),'reference_audio':str(ref),'reference_text':'参考语音'}
        requests=[]
        def worker(argv,**kwargs):
            if '--describe' in argv:
                return subprocess.CompletedProcess(argv,0,json.dumps({'mlx-audio':'fixture','mlx':'fixture'}),'')
            request=json.loads(Path(argv[-1]).read_text());requests.append(request)
            with wave.open(request['output'],'wb') as out:
                out.setparams((1,2,24000,0,'NONE','not compressed'));out.writeframes(b'\0'*12000)
            Path(request['metadata']).write_text(json.dumps({'actual_input':request['text']}))
            return subprocess.CompletedProcess(argv,0,'','')
        with patch('qwen_voice.config',return_value=config),patch('qwen_voice.subprocess.run',side_effect=worker):
            cue={'id':'c','tts':'切向分量。','_qwen_input':'切向分量。'}
            first=qwen_voice.synth(self.p,{},cue)
            self.assertTrue(qwen_voice.synth(self.p,{},cue)['cache_hit'])
            ref.write_bytes(b'reference2')
            second=qwen_voice.synth(self.p,{},cue)
            self.assertFalse(second['cache_hit'])
            self.assertNotEqual(first['signature']['reference_sha256'],second['signature']['reference_sha256'])
            self.assertEqual(requests[0]['text'],cue['_qwen_input'])

    @unittest.skipUnless(shutil.which('ffmpeg'),'requires FFmpeg')
    def test_unheard_audio_cannot_be_delivered(self):
        p=self.p
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=duration=3','-f','lavfi','-i','color=s=64x64:d=3',
                        '-c:v','libx264','-c:a','aac','-shortest',str(p/'video.mp4')],check=True)
        lesson={'handout':'student.md','pages':[{'id':'p','cues':[{'id':'c','tts':'长度增加。','start':0,'end':2}]}]}
        (p/'student.md').write_text('test')
        (p/'timeline.json').write_text(json.dumps({'pages':[{'id':'p','start':0,'cues':lesson['pages'][0]['cues'],'strokes':[]}]}))
        export_delivery(p,lesson)
        self.assertTrue((p/'delivery-candidate.json').is_file())
        self.assertFalse((p/'delivery-files.json').exists())
        with self.assertRaisesRegex(ValueError,'待审项'):export_delivery(p,lesson,publish=True)
        self.assertFalse((p/'delivery-files.json').exists())


if __name__=='__main__':unittest.main()
