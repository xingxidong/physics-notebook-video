"""Optional native Manim page: a rotating spherical dipole layer, no page title."""
from manim import *
import numpy as np

class PhysicsScene(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=65*DEGREES,theta=-40*DEGREES)
        self.camera.background_color='#fffef9'
        shell=Sphere(radius=1.5,resolution=(8,16)).set_fill(BLUE,opacity=.08).set_stroke(BLUE_D,width=.7)
        vectors=VGroup()
        for theta in np.linspace(0,TAU,8,endpoint=False):
            direction=np.array([np.cos(theta),np.sin(theta),.3]);direction/=np.linalg.norm(direction)
            tangent=np.cross(direction,[0,0,1]);tangent/=np.linalg.norm(tangent);tip=1.95*direction
            vectors.add(Line(1.35*direction,tip,color=GREEN,stroke_width=2),Line(tip,tip-.14*direction+.06*tangent,color=GREEN,stroke_width=2),Line(tip,tip-.14*direction-.06*tangent,color=GREEN,stroke_width=2))
        formula=MathTex(r'\phi_{\mathrm{out}}-\phi_{\mathrm{in}}=\frac{D}{\varepsilon_0}',font_size=34,color='#29333c').to_edge(DOWN)
        self.add(shell,vectors);self.add_fixed_in_frame_mobjects(formula)
        self.begin_ambient_camera_rotation(rate=.22)
        self.wait(self.course_payload['page']['frames']/self.course_payload['fps'],frozen_frame=False)
