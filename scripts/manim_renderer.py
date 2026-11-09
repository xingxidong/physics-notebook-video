"""Render course stroke paths with Manim VMobjects, plus optional project-native scenes."""
import argparse,importlib.util,json,math,shutil,sys
from pathlib import Path
import numpy as np
from manim import Scene,MovingCameraScene,ImageMobject,VMobject,VGroup,Dot,tempconfig
from course import portion
from layout import focus_state

def render(payload,output):
    data=json.loads(Path(payload).read_text());page=data['page'];native=data.get('native_scene')
    settings={'pixel_width':data['width'],'pixel_height':data['height'],'frame_rate':data['fps'],'media_dir':str(Path(payload).parent/'manim-media'),'output_file':'page','format':'mp4','disable_caching':True,'write_to_movie':True,'save_last_frame':False,'preview':False,'progress_bar':'none','verbosity':'WARNING'}
    if native:
        sys.path.insert(0,str(Path(native['source']).parent))
        spec=importlib.util.spec_from_file_location('physics_native_scene',native['source']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        SceneClass=getattr(module,native.get('class','PhysicsScene'))
    else:
        settings.update(frame_width=1280,frame_height=720)
        class NotebookScene(MovingCameraScene):
            def construct(self):
                self.add(ImageMobject(data['background']).set(width=1280,height=720))
                multiplier=self.camera.cairo_line_width_multiple
                def points(path):return np.array([[x-640,360-y,0] for x,y in path])
                def make(e):return VMobject(stroke_color=e['color'],stroke_width=e['width']/multiplier,fill_opacity=0).set_points_as_corners(points(e['points']))
                dynamic=data.get('dynamic_frames',[]);max_count=max((len(f) for f in dynamic),default=0)
                dynamic_nodes=VGroup(*[make(next(f[i] for f in dynamic if i<len(f))) for i in range(max_count)])
                events=page['strokes'];nodes=VGroup(*[make(e).set_stroke(opacity=0) for e in events]);states=[None]*len(events)
                cursor=Dot(radius=5,color='#355c49').set_stroke('#fffef9',width=2/multiplier).set_opacity(0)
                layer=VGroup(dynamic_nodes,nodes,cursor);self.add(layer)
                def update(group,dt=0):
                    t=self.time
                    focus=focus_state(page,t);zoom=focus['zoom'];cx,cy=focus['center'];point=np.array([cx-640,360-cy,0])
                    self.camera.frame.set(width=1280/zoom).move_to(point*(1-1/zoom))
                    if dynamic:
                        frame=dynamic[min(len(dynamic)-1,int((t+1e-8)*data['fps']))]
                        for i,mob in enumerate(dynamic_nodes):
                            if i<len(frame):
                                e=frame[i];mob.set_points_as_corners(points(e['points']));mob.set_stroke(color=e['color'],width=e['width']/multiplier,opacity=1)
                            else:mob.set_stroke(opacity=0)
                    cursor.set_opacity(0)
                    for i,(mob,e) in enumerate(zip(nodes,events)):
                        f=max(0,min(1,(t-e['start'])/(e['end']-e['start'])))
                        state=0 if t<e['start'] else 2 if f>=1 else 1
                        if state!=states[i] or state==1:
                            pts=portion(e['points'],f) if state==1 else e['points']
                            if len(pts)<2:pts=[pts[0],[pts[0][0]+.001,pts[0][1]]]
                            mob.set_points_as_corners(points(pts));mob.set_stroke(opacity=0 if state==0 else 1);states[i]=state
                            if state==1:cursor.move_to(points([pts[-1]])[0]).set_opacity(1)
                # Manim samples both ends of the interval; a half-frame offset
                # produces the exact shared-timeline frame count.
                layer.add_updater(update);update(layer);self.wait((page['frames']-.5)/data['fps'],frozen_frame=False)
        SceneClass=NotebookScene
    with tempconfig(settings):
        SceneClass.course_payload=data
        scene=SceneClass();scene.render();movie=Path(scene.renderer.file_writer.movie_file_path)
        shutil.copy2(movie,output)
    print(json.dumps({'renderer':'manim','frames':page['frames'],'native_scene':bool(native)}))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();render(a.input,a.output)
