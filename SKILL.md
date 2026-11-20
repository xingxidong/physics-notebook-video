---
name: physics-notebook-video
description: 将物理题或教材制作为电子笔记本式逐笔板书视频。习题课从题面、情景动画和配图推导讲到结果；新授课从现象和对照讲到完整定义、定律与应用。支持中文配音、可编辑 LaTeX 和 TikZ、Manim、Motion Canvas 及本地批量导出。
metadata:
  author: xingxidong
  version: "0.20.0"
  standard: agentskills.io
  icon: assets/icon.png
  requirements: Python 3.11+, FFmpeg, Chinese font; XeLaTeX/xeCJK and PyMuPDF for problem text; Node.js 20+/Chrome for Motion Canvas; TeX/dvisvgm for Manim
---

# 物理逐笔板书课

## 看课反馈与下次备课

用户指出成片有错时，当次调用 `scripts/feedback_bank.py record` 登记到对应库。综合问题、多音词和字母分别登记，能定位时记下课名、页或时间点。沿用相同的词或问题编号，保留再次发生的位置。听不清的实音照实描述，读法待确认时先登记；完成修复后将成片对应片段实际复看、复听。

每次制作两种课型、续做旧课或批量出片，都先看适用的历史问题。已有课程源就运行 `course.py feedback-check PROJECT`，读本课的 `feedback-check.json`，在教案和预览里逐项核实相应画面，按命中的句段试听。自定义渲染或本地配音也走这一步。收到新反馈后重新运行。正式音轨生成后再听同一批句子；按页、句、时间点记下所见所闻。操作与三个库见[看课反馈](references/viewer-feedback.md)。

作者的长期要求也进入反馈循环。把“以后”“至少”“同类课也这样做”连同适用课型和来源写入个人库；下一课编排时读取，完课后按实际 MP4 复查。审阅记录区分作者报告、已复录、自动识别结果和作者确认。相同反馈再次出现时追加本次实例。字母用所选音色在完整课堂句中比较；ASR 转写正确仍需关注听感，见[作者反馈的闭环](references/viewer-feedback.md)。

收到纠正时先找已有的 key，将本次原话留在对应库里。一次性的要求标记具体课名。试听或对照画面后用 `feedback_bank.py decide` 记录候选办法、作者选取或撤回的版本、适用范围和依据。选中的实音绑定合成模型、参考音色指纹和本地样本。下一课读取 `feedback-check.json` 的 `replay`，在命中的新句子或实际画面上复查；音色变更重新短句试听。具体操作见[从一次反馈到下一节课](references/viewer-feedback.md#从一次反馈到下一节课)。

文章完整讲解设置 `source_type: article` 和 `article_coverage`，逐项把原文公式、图的各子图、推理和作者建议的学生活动落到讲稿、板书。时长下限用正常语速的实录估计并用交付文件实测。内容短时展开学生需要的推导、读图、先修和变式，重新送审。[文章改课与时长](references/article-lesson.md)

## 习题课

用户给出待解的题目、题图或题解，围绕所求组织一条完整解题路线。课程源使用 `kind:"problem"`。先读[习题课工作流](references/problem-workflow.md)，登记原题与解答，转写 LaTeX，核对条件、图和公式。已有资料直接用，仅有题目时可独立求解。

题面实际进入视频。主图保留在同页，按推导补画辅助线、受力、投影、分段和结果图，配套提供可编辑 TikZ。用 Manim 或 Motion Canvas 展示物理模型的运动。在对应图旁说明建模依据和必要的代数、求导、积分或初末条件，用 `derivation_steps` 关联真实落笔与口播。首选[一页一题布局](references/layout.md)，长题在完整的中间关系之后续页。

习题课的重点按[重难点与制作复查](references/quality-workflow.md)落实到讲稿、实际板书和应用判断，用 `review_notes.focus_actions` 关联关键落笔。

## 新授课

用户要求教一个知识点、定律或教材章节，围绕学生学完应能说明或应用的知识组织课程。课程源使用 `kind:"concept"`。先按[整课编排](references/course-planning.md)生成并检查课程编排表，再读[新授课工作流](references/concept-lesson.md)。根据先修知识和本课难点，决定从现象、对照、定义、模型或推导进入，确定图上的变化和需要写进笔记的结论。用 `concept_units.stages` 记录实际讲述顺序。应用检查可以是一道简短判断题，写出问题并说明答案和依据。

写口播前为两种课型建立 `lesson_arc`。每个教学拍写学生此刻要解决的问题、眼前的图或式、这一拍留给学生的判断，并绑定连续的 cue。习题课至少走模型、关键推导、结果落笔、总结；新授课至少走问题引入、结论落笔、应用、总结。它避免视频变成按页念稿，教案会先展示这条课堂推进线。

提问时在板书上写出完整问题，随后再解释。物理图在开讲前规划好对象、已知值与单位、方向和变量，参与推导的量在图上逐一标清。用 `knowledge_points` 关联定义、定律或结论的名称、完整文字、条件和公式。在对应讲解中把板书写完，随后继续讲课。学生可自行暂停记笔记。用 `scene_events` 让实际物理状态随口播变化。新授课包含例题时，保留新授课的知识主线，例题段沿用习题课的图文推导。

## 人审教案与学生讲义

新授课与习题课的学生讲义均按[讲义编写与排版](references/handouts.md)制作：使用 LaTeX 排版、TikZ 配图。交付编译后的 PDF、LaTeX 主文件及所引用的 TikZ 源码。两类讲义在提交审阅和交付前都做最后一轮语言复读，尤其重读最后一节和末段。去掉“本题的主线”等编排用语，用具体物理结论、图中关系或结果的实际含义收尾。检查实际 PDF 的图文衔接、重点层次和分页。

备课先按[课堂时长编排](references/duration-planning.md)判断讲多久，适用于习题课和新授课。用学生基础、解题或知识主线、难点、落笔与必要观察分配时间，先报告建议范围和各段理由。用户要求长讲时，在教案上列出要加的先修知识、应展开的推导、读图或模型对照，以及相应的教学目的。全课保持自然语速和正常书写速度，禁止用整体降速、延长落笔或增加空白凑时长。新增内容仍不足以支撑目标时，给出按当前内容估算的实际时长。成片记录实测时长。加长版在对应教学段填写 `extension.outcome` 和 `extension.used_in`，教案分别列出原有内容和新增内容的预计用时。有原版正式时间轴时，用 `duration_plan.reference_timeline` 对比两版相同句子和相同笔迹的用时。

新项目设置 `review_required:true`。先用[人审与交付流程](references/review-workflow.md)给用户看完整教案、逐页板书和动画预览。教案写出重点、难点及讲法、应用检查、完整口播与片头。收到对当前版本的明确确认后记录反馈，再合成正式配音和视频。改动讲稿、板书、动画源、片头或已提交的讲义时重新出教案。交付包含视频和学生讲义。

## 共用的制作流程

按[课程格式](references/lesson-format.md)编辑 `lesson.json`、`speech-plan.json` 和讲义。两条入口各带一份可改写的完整示例。安装和依赖见 [README](README.md) 与[跨平台安装](references/platform-install.md)。

```sh
python3 SKILL/scripts/course.py init PROJECT --kind problem
python3 SKILL/scripts/course.py init PROJECT --kind concept
python3 SKILL/scripts/course.py teaching-check PROJECT
python3 SKILL/scripts/course.py build PROJECT --draft
```

前两条命令按课型选用其中一条。已有项目继续使用原课程源。讲义、例题和练习按[物理内容与板书组织](references/teaching.md)制作。每题提供题设图与解题过程图，保留可编辑 TikZ。检查图、题干、推导使用相同符号、方向和几何关系。讲义用自然课堂语言正面说明适用条件，保留必要的计算步骤。练习题保持题目，集中解答另列。

本系列采用方格笔记本、笔尖光标、固定镜头和逐笔笔迹。设 `camera:"static"`、`show_titles:false`，以片头课名和作者信息开场，正课页从教学图和内容开始。定律名称照常写在板书上。公式以 LaTeX 保存，汉字、公式与图中标注用笔画写出；公式行间省去连接箭头，保留表示受力、速度和位移的物理箭头。按[参数化组件](references/components.md)设置接触和附着点，按[语义场景](references/semantic-scenes.md)同步状态、落笔与口播。

片头结束后先呈现完整的主模型和首段会用到的标注，再开始指图讲解。主图用 `layout.prewritten` 在正课页首帧呈现，续页用 `carry` 原位保留。推导中新增的辅助线和变量可逐笔写，在口播用到它们之前画完。用 `layout.checkpoints` 检查第一句和每个首次引用的画面。

先按[实际笔迹排版](references/board-layout.md)设置题图、推导、结论和续页，再用 `course.py board-check PROJECT --strict` 核对关键时刻的画面。原生动画用 `course.py preview PROJECT --renderer manim` 查看无配音运动稿。核对动作、文字和图的显示顺序，检查标注与公式的间距。已有可用模型优先复用。题型和场景设置见[情景动画](references/scenario-animation.md)。

## 课堂表达与配音

学生口播直接点出画面里的对象。“看右边的速度箭头，它缩短了多少？”让学生有具体动作。资料出处留在备课记录。字幕逐句核对；听字母时保留两侧汉字。26 个拉丁字母均按英语字母名整体发音，TTS 输入优先使用英文或引擎支持的英语音素，旧讲稿的汉字谐音改回英语字母名，特别留意 W 的最后一个音、S 和 X 的韵尾、Q 的起音，以及 P、T、V 在句中的自然收音。独立句的交界用正式音轨连听，发现急接或碰声时回到原始分句修复。

出教案前运行 `course.py quality-check PROJECT --stage plan`，按页面和句段处理教学、口播、时长和画面问题。报告中的 `coverage` 说明检查范围；原生动画需实际观看开始、接触前后、极值、转折和结束。见[制作复查](references/quality-workflow.md)。

参照[课堂表达与节奏](references/classroom-delivery.md)做两轮口播：第一轮对着画面讲清物理对象、原因和步骤，第二轮连读相邻段，改掉念稿、空泛指代、长串符号和空转过渡。每段用眼前的图、前一步结果或当前运算承接。新项目采用 `speech.delivery_profile:"classroom"`，平常句群连着说，重难点减速并把重音给决定结果的词，抄录由学生自行暂停。

同一个思路拆成多条 cue 仅为同步笔迹时，在 `speech-plan.json` 用同一个 `speech_group` 连续合成，避免每个 cue 都重新起句。问题、观察、关键转折和总结保持独立组，使语气变化来自真实教学动作。先试听开场、一段连续推导和收束，再决定局部语速、重音或读音。

在教案里设计独立的总结段，不把最后一个推导句当成结尾。课程源填写 `closure`，列出总结时仍可见的题图、关键式或结论板书，以及实际的总结 cue。习题课回扣模型、关键一步和最终所求；新授课回到开场问题、完整结论和可用的情境。总结 cue 排在整课末尾，沿用正课图和结论板书，等最后一句自然收住再结束。格式见[课程收束](references/lesson-format.md#课程收束)。

教案包含口播检查原句。正式配音前运行 `scripts/delivery.py PROJECT`，核对变量、单位、字母与多音字的预期读法。文字保留正常术语，读音在语音层按词覆盖，先试听本课音色下的代表句。配音后按 `voice-report.json` 的试听清单连听开场、难点、结论、字母和中文多音字，核实实际声音与自然书写节奏。用 `course.py voice-check PROJECT --listen CUE_ID --context` 带前后句定位。读音、连读或断句需要调整时，只重配并复听受影响的段落。讲稿中的字母按字母名朗读。拉丁字母 x、X 都读 /ɛks/，板书、字幕、教案保留原符号。量名写入另外的解释，例如“用 x 表示压缩量”。首次出现、连读多个符号及含下标的公式都要用最终音色试听。中文多音字按完整词匹配读音并检查冲突。正式检查从本课实际音轨截取字母和多音词的试听合辑。读音修正方法见[教师口播与配音](references/voice.md)。

## 渲染与交付

成片后运行 `course.py quality-check PROJECT --stage final`，交付烧录字幕版时用 `--video-file video-captioned.mp4` 指向交付件。以报告中的原尺寸公式帧、落笔帧和动画时间点复看小字、细线和运动轮廓，分别记录画面码率与音频码率。修复并回听相关片段。自动报告保留尚需观看与试听的事项，交付时说明实际完成的检查及待处理项。

```sh
python3 SKILL/scripts/course.py build PROJECT --video --renderer motion-canvas --width 1920
python3 SKILL/scripts/captions.py PROJECT --burn
```

二维动态场景可用 Motion Canvas，原生数学或三维场景可用 Manim。已有时间轴和声音时，可用 `course.py render PROJECT --renderer manim` 复用配音。设置和示例见[引擎接入](references/renderers.md)。一课一个目录，批量使用 `course.py batch BATCH.json --video --jobs 2`。长课若需要按章节并行制作，读[多 Agent 工作流](references/multi-agent.md)。

交付成片、字幕、课程源、讲义、TikZ、板书 PDF 与预览。按实际成片复查物理状态、公式书写与显示时间。习题课看题干是否入屏和推导是否连贯；新授课逐段检查引入的问题、图上的量、讲解依据和完整结论。核对提问、作图和推导与口播同步。反馈给出实际时长、配音后端和检查结果。
