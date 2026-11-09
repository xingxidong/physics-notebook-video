"""Regressions for camera motion, surface contact and attached drawing geometry."""
import copy,math,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from components import incline_geometry,audit_components
from course import compile_lesson,schedule
from layout import expand_actions,page_spec,focus_state


class StableBoardTests(unittest.TestCase):
    def test_block_base_contacts_slope_at_multiple_angles_and_scales(self):
        for angle in (8,15,30,60,70):
            for scale in (.35,1,2.2):
                g=incline_geometry({'angle':angle,'scale':scale})
                distances=[sum((p[i]-g['origin'][i])*g['normal'][i] for i in (0,1)) for p in g['corners']]
                self.assertGreaterEqual(min(distances),-1e-8)
                for d in distances[:2]:self.assertAlmostEqual(d,0,places=7)
                self.assertAlmostEqual(max(distances),39*scale,places=7)

    def test_contact_report_detects_actual_penetration(self):
        with tempfile.TemporaryDirectory() as folder:
            _,pages=compile_lesson(folder,{'title':'contact','pages':[{'id':'p1','layout':'one-page-problem','cues':[{'tts':'物体放在斜面上。','actions':[{'type':'component','name':'inclined-plane','id':'ramp','zone':'diagram'}]}]}]})
            self.assertEqual(audit_components(pages)['status'],'pass')
            block=next(b for b in pages[0]['cues'][0]['blocks'] if b['component_part']==5)
            for stroke in block['strokes']:
                for p in stroke['points']:p[1]+=12
            self.assertIn('block-contact',[x['code'] for x in audit_components(pages)['warnings']])

    def test_attached_vectors_follow_block_after_geometry_changes(self):
        lesson={'title':'anchors','pages':[{'id':'p1','layout':'one-page-problem','cues':[{'tts':'重力从研究对象出发。','actions':[
            {'type':'component','name':'inclined-plane','id':'ramp','zone':'diagram'},
            {'type':'arrow','attach_to':'ramp.block_center','from':[0,0],'to':[0,75],'color':'red'},
        ]}]}]}
        with tempfile.TemporaryDirectory() as folder:
            origins=[]
            for angle in (20,35):
                edited=copy.deepcopy(lesson);edited['pages'][0]['cues'][0]['actions'][0]['angle']=angle
                _,pages=compile_lesson(folder,edited);page=pages[0]
                arrow=page['cues'][0]['blocks'][-1]['strokes'][0]['points']
                self.assertEqual(arrow[0],page['anchors']['ramp.block_center'])
                self.assertEqual(arrow[1],[arrow[0][0],arrow[0][1]+75]);origins.append(arrow[0])
            self.assertNotEqual(origins[0],origins[1])

    def test_static_camera_suppresses_legacy_focus_and_connectors_are_optional(self):
        lesson={'title':'static','pages':[{'id':'p1','layout':'one-page-problem','cues':[{'tts':'固定画面写下关系。','focus':'diagram','actions':[{'type':'formula_steps','steps':['F=ma','a=F/m']}]}]}]}
        with tempfile.TemporaryDirectory() as folder:
            _,pages=compile_lesson(folder,lesson);self.assertEqual(pages[0]['camera'],'static')
            self.assertNotIn('focus',pages[0]['cues'][0])
            self.assertTrue(all(b['kind']=='math' for b in pages[0]['cues'][0]['blocks']))
            lesson['camera']='focus';_,pages=compile_lesson(folder,lesson);self.assertIn('focus',pages[0]['cues'][0])
        page={'camera':'static','focus':[{'start':1,'end':3,'transition':.35,'rect':[145,110,465,365],'zoom':1.15}]}
        for t in (0,1,2,3,4):self.assertEqual(focus_state(page,t)['zoom'],1)
        explicit=expand_actions([{'type':'formula_steps','connect':True,'steps':['F=ma','a=F/m']}],page_spec('one-page-problem'))
        self.assertTrue(any(a['type']=='arrow' for a in explicit))

    def test_short_writing_leaves_result_visible_during_narration(self):
        block={'strokes':[{'points':[[650,540],[850,540]],'width':3,'color':'#29333c'}],'at':.15,'write_seconds':2}
        events=schedule({'id':'result','tts':'速度关系','pause':1,'blocks':[block]},{'duration':12,'words':[]})
        self.assertGreaterEqual(events[0]['start'],1.8-1e-7)
        self.assertLess(events[-1]['end'],3.8)


if __name__=='__main__':unittest.main()
