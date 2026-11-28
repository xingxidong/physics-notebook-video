# Motion Canvas 与 Manim 接入

两个引擎共用现有课程编译器：`lesson.json → 物理组件、笔画路径、物理模型坐标、实测配音时间轴 → 指定引擎 → MP4`。汉字与公式继续使用中心线笔画；页面是否显示标题由 `show_titles` 控制。原有 MiniMax、字幕、TikZ 和讲义流程继续工作。语义区域、连续公式、参数化物理组件和页内聚焦都进入共用时间轴。

v0.8 的题目框与源图裁切进入共用背景。追逐模型的位置、轨迹、方向和投影由物理参数生成，两套引擎绘制同一组逐帧几何；HTML 从同一物理取样数据播放。具体分段、暂停和板书快照见 [情景动画](scenario-animation.md)。

## 安装与选择

平台安装器复制技能后自动配置两套引擎。通过宿主界面导入 ZIP 或手动复制目录后，在已安装的技能目录运行：

```sh
python3 scripts/platform_install.py animation-engines
python3 scripts/course.py doctor
```

配置命令优先复用可用环境，必要时安装 Manim、锁定版本的 Motion Canvas 和浏览器。成功的环境路径写入本机的 `runtime-local.json`。可用 `animation-engines --runtime-dir /path/to/runtime` 指定新环境的存放位置。[安装说明](platform-install.md#安装动画引擎)

Motion Canvas 采用 3.17.2，配套 Vite 5.4.21 与 Playwright Core 1.65.0；依赖由 `scripts/motion_canvas/package-lock.json` 固定。可用环境变量 `PHYSICS_ANIMATION_RUNTIME`、`PHYSICS_MANIM_PYTHON`、`CHROME_PATH` 覆盖对应路径。

```sh
python SKILL/scripts/course.py build PROJECT --video --renderer motion-canvas --width 1920
python SKILL/scripts/course.py build PROJECT --video --renderer manim --width 1920
```

也可在课程顶层写 `"renderer":"motion-canvas"` 或 `"renderer":"manim"`；命令行参数优先。原有 `notebook` 渲染器保持可选。

已经有 `timeline.json` 与 `narration.wav` 时，直接切换引擎渲染，不再合成配音：

```sh
python SKILL/scripts/course.py render PROJECT --renderer motion-canvas --width 1920
python SKILL/scripts/course.py render PROJECT --renderer manim --width 1920
```

每个引擎保存独立的 `video-引擎名.mp4`，同时更新 `video.mp4` 供字幕程序使用。对同一个项目依次运行两个引擎；不同课程可以用 batch 并行生成。

```sh
python SKILL/scripts/course.py batch BATCH.json --video --renderer motion-canvas --jobs 2
python SKILL/scripts/captions.py PROJECT --burn
```

## 渲染方式

Motion Canvas 通过真实的 `Renderer`、`Scene2D`、`Line`、`Circle` 与信号绘制笔迹和动态物体。无头 Chrome 执行引擎，自定义导出器把 PNG 帧流传给本机 FFmpeg。板书纸张使用共用背景，笔迹和动态模型由 Motion Canvas 的矢量组件绘制。

Manim 通过 `MovingCameraScene`、`VMobject` 与更新器绘制同一组笔画，按实测时间逐笔出现。动态模型的解析坐标由同一模块逐帧提供，两个引擎读取相同的数据。普通课程的中心线笔画渲染使用已编译路径，无需每次调用 LaTeX。v0.7 默认 `camera:"static"`，Motion Canvas、Manim、Notebook 和 HTML 都保持画面大小与位置一致。显式使用 `camera:"focus"` 时，才按共用的 `focus` 事件控制镜头。

页面缓存包括引擎源码、引擎版本、页面内容、分辨率、帧率、字体、音频与本地时间轴。不同引擎的缓存目录独立，完整导出且帧数正确后才写入缓存。换引擎、改图和重编码复用已有配音。

## 动画中的手写标注

模型几何可以预绘，物体与轨迹由动画引擎更新。图内变量、上下标、数值及文字说明使用与讲解板书相同的笔迹。普通文本用 `ink.text_strokes`，LaTeX 标注用 `ink.math_strokes`，将笔画路径交给 Manim 的 VMobject 或 Motion Canvas 的路径组件。给每条标注记录对应的口播词和落笔区间，沿用板书的单支笔时序。移动标注使用物理对象的当前坐标加固定偏移，完整写出后持续跟随。同一份笔迹用于静止和运动时的标注。

成片查看每个新标注在落笔前、书写中以及对象移动后的画面。对比同字母在图中和公式中的笔形，并核对箭尾、角度、下标和辅助线的归属。字幕沿实际音轨同步显示。

## 原生 Manim 三维场景

页面可设置：

```json
"native_scenes": {
  "manim": {
    "source":"scenes/sphere.py",
    "class":"PhysicsScene",
    "dependencies":[]
  }
}
```

`source` 是本课目录内的 Python 文件，类继承 Manim 的 Scene 或 ThreeDScene。通过 `self.course_payload` 取得页面数据、时长、帧率等；场景时长使用 `page.frames/fps`，导出后会检查帧数。导入本课辅助代码或素材时，将这些文件列在 `dependencies`，使修改后正确刷新缓存。

可从 `assets/engine-examples/sphere.py` 开始编写。原生场景自行安排相机与物体；课程中的普通动作继续提供配套二维板书、TikZ 与讲义图。原生 `MathTex` 排版需要可用的 TeX 与 dvisvgm；三维几何与共用笔画层可独立使用。

## 参考实现

- [Motion Canvas Renderer](https://github.com/motion-canvas/motion-canvas/blob/main/packages/core/src/app/Renderer.ts)
- [Motion Canvas Curve](https://github.com/motion-canvas/motion-canvas/blob/main/packages/2d/src/lib/components/Curve.ts)
- [Manim VMobject](https://docs.manim.community/en/stable/reference/manim.mobject.types.vectorized_mobject.VMobject.html)

这次新增的是课程格式适配与本地渲染程序；上游引擎由 npm/pip 安装，保留各自许可。
