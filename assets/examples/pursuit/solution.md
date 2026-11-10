# 图文推导

图中蓝点 $F$ 向右匀速运动，绿点 $D$ 的速度始终沿着红色视线。沿视线投影，目标点使距离增加的速率为 $v_F\cos\theta$，追逐点使距离减少的速率为 $v_D$，因此

$$\dot r=v_F\cos\theta-v_D.$$

沿水平方向取相对速度，得到

$$\dot x=v_F-v_D\cos\theta.$$

为了使两个余弦项具有相同的系数，第一式乘 $v_D$，第二式乘 $v_F$：

$$v_D\dot r=v_Dv_F\cos\theta-v_D^2,$$

$$v_F\dot x=v_F^2-v_Dv_F\cos\theta.$$

相加后，余弦项一正一负相消：

$$v_D\dot r+v_F\dot x=v_F^2-v_D^2.$$

两速率为常量，所以

$$v_D\dot r=\frac{d}{dt}(v_Dr),\qquad v_F\dot x=\frac{d}{dt}(v_Fx).$$

导数相加得到和的导数，最终有

$$\boxed{\frac{d}{dt}(v_Dr+v_Fx)=v_F^2-v_D^2.}$$

随包动画采用纯追逐的极坐标解析解取样，物体位移由物理时间和速率决定；播放速度单独安排。静态 TikZ 和板书 PDF 保留追逐中段，便于看到 $r$、$x$ 与 $\theta$ 的关系。
