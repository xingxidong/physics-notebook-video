import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from components import CATALOG,audit_components,expand_component
from course import compile_lesson


class PhysicsComponentsV06Tests(unittest.TestCase):
    def test_catalog_expands_to_ordinary_actions(self):
        allowed={'text','math','line','arrow','dashed_line','ellipse','dashed_circle','rect','charge','stroke','plot'}
        for name in CATALOG:
            actions,manifest=expand_component({'type':'component','name':name,'id':name,'zone':'diagram','at':.2},'fallback')
            self.assertGreater(len(actions),0,name)
            self.assertTrue(all(a['type'] in allowed for a in actions),name)
            self.assertEqual(sum('at' in a for a in actions),1,name)
            self.assertTrue(all(a['component_id']==name for a in actions),name)
            self.assertEqual(manifest['primitive_count'],len(actions))

    def test_physics_direction_and_geometry_invariants(self):
        dipole,_=expand_component({'type':'component','name':'electric-dipole','id':'d'},'x')
        moment=next(i for i,a in enumerate(dipole) if a.get('latex')==r'\vec p')
        self.assertGreater(dipole[moment-1]['from'][0],dipole[moment-1]['to'][0])
        projectile,_=expand_component({'type':'component','name':'projectile-trajectory','id':'p'},'x')
        trajectory=next(a for a in projectile if a['type']=='stroke')
        self.assertAlmostEqual(trajectory['points'][0][1],trajectory['points'][-1][1],places=6)
        lens,_=expand_component({'type':'component','name':'thin-lens','id':'l'},'x')
        rays=[a for a in lens if a['type']=='line' and a.get('color') in ('red','blue')]
        image=rays[-1]['to']
        self.assertEqual(rays[-2]['to'],image)
        with self.assertRaisesRegex(ValueError,'greater than focal_length'):
            expand_component({'type':'component','name':'thin-lens','id':'bad','object_distance':60,'focal_length':70},'x')

    def test_complete_component_example_compiles_and_audits(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);shutil.copy2(ROOT/'assets/components.json',project/'lesson.json')
            lesson,pages=compile_lesson(project);report=audit_components(pages)
            self.assertEqual(lesson['title'],'物理竞赛图形组件')
            self.assertEqual(len(pages),len(CATALOG))
            self.assertEqual(report['status'],'pass')
            self.assertEqual(sum(report['counts'].values()),len(CATALOG))

    @unittest.skipUnless(Path('/System/Library/Fonts/Supplemental/Songti.ttc').exists(),'draft export needs a Chinese font')
    def test_draft_export_writes_component_report_and_tikz_markers(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);shutil.copy2(ROOT/'assets/components.json',project/'lesson.json')
            run=subprocess.run([sys.executable,str(ROOT/'scripts/course.py'),'build',str(project),'--draft'],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            report=json.loads((project/'component-report.json').read_text())
            self.assertEqual(report['status'],'pass')
            self.assertIn('% component: force-main (force-diagram)',(project/'tikz/p01.tikz').read_text())
            build=json.loads((project/'build-report.json').read_text())
            self.assertEqual(build['components'],len(CATALOG))


if __name__=='__main__':unittest.main()
