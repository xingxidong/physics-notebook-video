from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from course import compile_lesson
from course_outline import markdown, validate
from teaching import audit
from team import init, inspect_team, merge


class CourseOutlineTests(unittest.TestCase):
    def sample(self):
        return json.loads((ROOT / 'assets/electric-field-intro.json').read_text())

    def test_planning_requires_prerequisites_objective_checks_and_time(self):
        base = self.sample()['course_outline']
        self.assertFalse(validate(base))
        self.assertIn('试探电荷量加倍，电场力怎样变？', markdown(base))
        edits = {
            'outline-prerequisite': lambda p: p['units'][0]['needs'].append(p['units'][0]['id']),
            'outline-objective-unassessed': lambda p: p['exit_checks'].clear(),
            'outline-duration': lambda p: p['units'][0].update(minutes=3),
            'outline-scene-labels': lambda p: p['units'][0]['diagram']['labels'].clear(),
        }
        for code, edit in edits.items():
            with self.subTest(code=code):
                outline = deepcopy(base)
                edit(outline)
                self.assertIn(code, {item['code'] for item in validate(outline)})

    def test_script_must_preserve_focus_board_and_final_check(self):
        edits = {
            'outline-source': lambda s: s.pop('course_outline'),
            'outline-unit-order': lambda s: s['concept_units'][0].update(id='another-unit'),
            'outline-unit-focus': lambda s: s['concept_units'][0].update(focus='别的概念。'),
            'outline-board': lambda s: s['course_outline']['units'][0].update(board_statement='另一条结论。'),
            'outline-intro-question': lambda s: s['course_outline']['units'][0].update(intro_question='引入问题改了吗？'),
            'outline-exit-question': lambda s: s['course_outline']['exit_checks'][0].update(question='课末问题改了吗？'),
        }
        with tempfile.TemporaryDirectory() as folder:
            lesson, pages = compile_lesson(folder,self.sample())
            self.assertEqual(audit(folder,lesson,pages)['course_outline']['status'],'pass')
            for code, edit in edits.items():
                with self.subTest(code=code):
                    sample=self.sample()
                    edit(sample)
                    lesson, pages = compile_lesson(folder,sample)
                    errors = audit(folder,lesson,pages)['errors']
                    self.assertIn(code,{error['code'] for error in errors})

    def test_team_keeps_the_assigned_outline_through_merge(self):
        source = self.sample()
        unit_id = source['concept_units'][0]['id']
        outline = source['course_outline']
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = {'course':{'title':'电场强度','kind':'concept','target_minutes':1.25},
                    'sections':[{'id':'field','title':'电场强度','target_minutes':1.25,'unit_ids':[unit_id]}],
                    'course_outline':'outline.json'}
            (root/'outline.json').write_text(json.dumps(outline))
            plan_file = root/'plan.json'
            plan_file.write_text(json.dumps(plan))
            init(root,plan_file)
            work = root/'team/sections/field'
            assignment=json.loads((work/'assignment.json').read_text())
            self.assertEqual(assignment['planned_units'][0]['id'],unit_id)
            self.assertEqual(assignment['exit_checks'],outline['exit_checks'])

            page=source['pages'][0]
            rename={c['id']:'s01-field-'+c['id'] for c in page['cues']}
            rename[page['id']]='s01-field'
            def remap(value):
                if isinstance(value,list):
                    return [remap(item) for item in value]
                if isinstance(value,dict):
                    return {key:remap(item) for key,item in value.items()}
                return rename.get(value,value) if isinstance(value,str) else value
            fragment=remap({key:source[key] for key in ('pages','concept_units','knowledge_points')})
            fragment.update(section_id='field',symbols_used=[])
            fragment['pages'][0].update(board_unit='电场强度',complete_on_page=True)
            path=work/'fragment.json'
            path.write_text(json.dumps(fragment))
            self.assertTrue(inspect_team(root,deep=True)[-1]['ok'])
            merge(root,'lesson.json')
            self.assertEqual(json.loads((root/'lesson.json').read_text())['course_outline'],outline)

            fragment['concept_units'][0]['id']='off-plan'
            path.write_text(json.dumps(fragment))
            report=inspect_team(root,deep=True)[-1]
            self.assertFalse(report['ok'])
            self.assertIn('课程片段须按编排顺序完成分配的教学段',' '.join(report['errors']))


if __name__ == '__main__':
    unittest.main()
