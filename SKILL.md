---
name: physics-notebook-video
description: 将物理题或教材制作为电子笔记本式逐笔板书视频。习题课从题面、情景动画和配图推导讲到结果；新授课从现象和对照讲到完整定义、定律与应用。支持中文配音、可编辑 LaTeX 和 TikZ、Manim、Motion Canvas 及本地批量导出。
metadata:
  author: xingxidong
  version: "0.11.0"
  standard: agentskills.io
  icon: assets/icon.png
  requirements: Python 3.11+, FFmpeg, Chinese font; XeLaTeX/xeCJK and PyMuPDF for problem text; Node.js 20+/Chrome for Motion Canvas; TeX/dvisvgm for Manim
---

# 物理逐笔板书课

## 习题课

用户给出待解的题目、题图或题解，围绕所求组织一条完整解题路线。课程源使用 `kind:"problem"`。先读[习题课工作流](references/problem-workflow.md)，登记原题与解答，转写 LaTeX，核对条件、图和公式。已有资料直接用，仅有题目时可独立求解。

题面实际进入视频。主图保留在同页，按推导补画辅助线、受力、投影、分段和结果图，配套提供可编辑 TikZ。用 Manim 或 Motion Canvas 展示物理模型的运动。在对应图旁说明建模依据和必要的代数、求导、积分或初末条件，用 `derivation_steps` 关联真实落笔与口播。首选[一页一题布局](references/layout.md)，长题在完整的中间关系之后续页。

## 新授课

用户要求教一个知识点、定律或教材章节，围绕学生学完应能说明或应用的知识组织课程。课程源使用 `kind:"concept"`。先读[新授课工作流](references/concept-lesson.md)，确定各段要观察的对象、保留的条件、图上的变化和要写进笔记的结论。用观察、对照、解释、正式板书和应用衔接课程；按内容选择所需环节。

先排图、条件和板书位置，再让口播随实际对象、状态和公式推进。用 `knowledge_points` 关联定义、定律或结论的名称、完整文字、条件和公式。全部写完后留出读写时间。用 `scene_events` 让实际物理状态随口播变化。新授课包含例题时，保留新授课的知识主线，例题段沿用习题课的图文推导。

## 共用的制作流程

按[课程格式](references/lesson-format.md)编辑 `lesson.json`、`speech-plan.json` 和讲义。两条入口各带一份可改写的完整示例。安装和依赖见 [README](README.md) 与[跨平台安装](references/platform-install.md)。

```sh
python3 SKILL/scripts/course.py init PROJECT --kind problem
python3 SKILL/scripts/course.py init PROJECT --kind concept
python3 SKILL/scripts/course.py teaching-check PROJECT
python3 SKILL/scripts/course.py build PROJECT --draft
```

前两条命令按课型选用其中一条。已有项目继续使用原课程源。讲义、例题和练习按[物理内容与板书组织](references/teaching.md)制作。每题提供题设图与解题过程图，保留可编辑 TikZ。检查图、题干、推导使用相同符号、方向和几何关系。讲义用自然课堂语言正面说明适用条件，保留必要的计算步骤。练习题保持题目，集中解答另列。

本系列采用方格笔记本、笔尖光标、固定镜头和逐笔笔迹。设 `camera:"static"`、`show_titles:false`，直接从教学图和内容开始。定律名称照常写在板书上。公式以 LaTeX 保存，汉字、公式与图中标注用笔画写出；公式行间省去连接箭头，保留表示受力、速度和位移的物理箭头。按[参数化组件](references/components.md)设置接触和附着点，按[语义场景](references/semantic-scenes.md)同步状态、落笔与口播。

先看 `contact-sheet.png` 和页面 PNG，再按需要用 `course.py preview PROJECT --renderer manim` 查看无配音运动稿。核对动作、文字和图的显示顺序，检查标注与公式的间距。已有可用模型优先复用。题型和场景设置见[情景动画](references/scenario-animation.md)。

## 课堂表达与配音

参照[课堂表达与节奏](references/classroom-delivery.md)改写口播。先让每句承接眼前的图、前一步结果或当前运算，再按实际语速通读。长式分句说清物理量、运算和原因。新项目采用 `speech.delivery_profile:"classroom"`，按观察、思考、读式或转场安排有用途的停顿。批量课可参考[成片案例](references/reference-cases.md)。

正式配音前运行 `scripts/delivery.py PROJECT` 查看原句和术语提示。文字保留正常术语，读音在语音层按词覆盖。沿用用户已选的音色和供应商，配置从本地读取。支持的后端、语调、个人音色和缓存见[教师口播与配音](references/voice.md)。配音后结合画面回听关键术语及相邻语句。可用 `course.py voice-check PROJECT --listen CUE_ID` 截取试听。改稿或修读音后复用其余段的配音缓存。

## 渲染与交付

```sh
python3 SKILL/scripts/course.py build PROJECT --video --renderer motion-canvas --width 1920
python3 SKILL/scripts/captions.py PROJECT --burn
```

二维动态场景可用 Motion Canvas，原生数学或三维场景可用 Manim。已有时间轴和声音时，可用 `course.py render PROJECT --renderer manim` 复用配音。设置和示例见[引擎接入](references/renderers.md)。一课一个目录，批量使用 `course.py batch BATCH.json --video --jobs 2`。长课若需要按章节并行制作，读[多 Agent 工作流](references/multi-agent.md)。

交付成片、字幕、课程源、讲义、TikZ、板书 PDF 与预览。按实际成片复查物理状态、公式书写与显示时间。习题课看题干是否入屏和推导是否连贯；新授课看定义与定律能否从画面完整抄录。反馈给出实际时长、配音后端和检查结果。
