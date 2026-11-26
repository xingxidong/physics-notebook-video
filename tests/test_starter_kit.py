import json
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from animation_examples import calculate
from incline_motion import setup,state
from course_outline import validate
from classroom_language import review_narration


class StarterKit(unittest.TestCase):
    def test_collision_conserves_momentum_and_energy(self):
        p=json.loads((ROOT/'assets/starter-kit/animations/parameters.json').read_text())
        for m1,m2,u1,u2 in ((1,2,3,0),(3,1,1,-2),(.5,4,2,1)):
            p['collision']=dict(m1=m1,m2=m2,u1=u1,u2=u2)
            d=calculate(p)['collision'];v1,v2=d['v1'],d['v2']
            self.assertAlmostEqual(m1*u1+m2*u2,m1*v1+m2*v2)
            self.assertAlmostEqual(m1*u1*u1+m2*u2*u2,m1*v1*v1+m2*v2*v2)
            self.assertGreaterEqual(v2,v1)

    def test_orbit_and_reflection_phase(self):
        p=json.loads((ROOT/'assets/starter-kit/animations/parameters.json').read_text())
        d=calculate(p)
        self.assertAlmostEqual(d['magnetic']['radius'],2)
        p['magnetic']['q']=-1
        self.assertEqual(calculate(p)['magnetic']['omega'],-1)
        self.assertAlmostEqual(d['film']['reflection_phase'],-math.pi)
        p['film']['n2']=2
        self.assertEqual(calculate(p)['film']['reflection_phase'],0)
        p['magnetic']['B']=0
        with self.assertRaises(ValueError):calculate(p)

    def test_incline_contact_and_acceleration(self):
        m=setup({'kind':'incline'})
        self.assertAlmostEqual(m['acceleration'],5)
        for i in range(101):
            s=state(m,i/100)
            for point in s['corners']:
                above=sum((point[j]-m['origin'][j])*s['n'][j] for j in (0,1))
                self.assertGreaterEqual(above,-1e-10)
            self.assertAlmostEqual(s['distance'],2*(i/100)**2)
        self.assertAlmostEqual(state(m,1)['speed'],math.sqrt(20))

    def test_filled_long_course_outlines(self):
        for name,total in [('high-school-90',90),('competition-180',180)]:
            d=json.loads((ROOT/'assets/starter-kit/long-lessons'/(name+'.json')).read_text())
            self.assertEqual(validate(d),[])
            self.assertEqual(sum(u['minutes'] for u in d['units']),total)
            self.assertTrue(all(u['difficulty']['treatment'] and u['board_pages'] for u in d['units']))
            markdown=(ROOT/'assets/starter-kit/long-lessons'/(name+'.md')).read_text()
            for u in d['units']:
                self.assertIn(u['sample_narration'],markdown)
                self.assertFalse(review_narration([{'id':u['id'],'tts':u['sample_narration']}]))

    def test_trial_targets_are_real_occurrences(self):
        d=json.loads((ROOT/'assets/starter-kit/voice-trial/sentences.json').read_text())['items']
        self.assertEqual(len({x['id'] for x in d}),len(d))
        for row in d:
            self.assertTrue(row['flow'])
            for target in row['targets']:
                self.assertTrue(row['text'].startswith(target['term'],target['offset']))
                self.assertEqual(len(target['term']),len(target['pinyin'].split()))
            self.assertTrue((ROOT/'assets/starter-kit/voice-trial'/row['reference_audio']).is_file())


if __name__=='__main__':unittest.main()
