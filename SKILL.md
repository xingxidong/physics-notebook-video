---
name: physics-notebook-video
description: 将物理题、物理竞赛讲义或概念课制作为电子笔记本式逐笔板书视频，含图文推导、自然中文口播、TikZ 源码、本地批量渲染与长课多 Agent 协作。适用于 Codex、Claude 及其他兼容 Agent Skills 的终端中的手写讲课、Goodnotes 录屏式课程、讲义转视频和系列课程制作。
metadata:
  author: xingxidong
  version: "0.8.0"
  standard: agentskills.io
  icon: assets/icon.png
  requirements: Python 3.11+, FFmpeg, Chinese font; XeLaTeX/xeCJK and PyMuPDF for problem text; Node.js 20+/Chrome for Motion Canvas; TeX/dvisvgm for Manim
---

# 物理逐笔板书课

把物理讲解变成可编辑的课程源包，再用固定程序生成逐笔笔迹、音频、预览和视频。内容与制作分开：模型负责新内容和教学安排，程序负责重复渲染。技能根目录遵循开放 Agent Skills 格式，不把课程逻辑绑定到单一模型供应商。默认采用本用户已选定的方格笔记本、笔尖光标、中文教师口播。

分享版安装、运行依赖与首次试用见 [README](README.md)。跨平台安装、打包与能力边界见 [平台安装](references/platform-install.md)。下文的样式、写法和音色是本模板默认设置，使用者的明确要求优先。

本用户的新偏好：视频每页不显示标题。新课设置 `show_titles:false`，内部页面名称只用于编辑与章节定位。画面直接从图、变量和推导开始。口播用自然的课堂句子，靠指图和物理关系推进，删去模板式开场、流程预告和重复总结；保持必要的推导步骤。

## 自然课堂口播

文稿直接讲眼前的对象和正在算的量。例如“势能只含位置，对速度求导就是零”“两边都有质量，约掉”。删去“整道推导都围绕这张图展开”“图、受力和结论连成了一条线”这类介绍讲解结构的句子。每句话落实到一个物理关系、一个运算或一个确有作用的问题；技术名词照常使用，并在出现时讲清它指什么。

公式写在板书上，口播说明各项从哪里来、为什么这样算、这一步得到什么。长公式分成有意义的部分讲，避免连续逐字念符号。正文保留正常变量记号，朗读优先说“位移”“倾角”等物理名称；读音修正放在语音层。成稿按课堂速度通读，删掉没有新增物理信息的概括句，保留推导所需的中间步骤。具体写法与对照见 [教师口播](references/voice.md#写法)。

本系列采用固定画面：设置 `camera:"static"`，整页尺寸与位置保持一致。公式链逐行出现，默认省去行间连接箭头；受力、位移、速度等物理方向保留。斜面滑块按底边接触放置；后续受力线与标签用 `attach_to` 引用滑块中心，改图时一起移动。重要结果用 `write_seconds` 提前写完，给学生保留看图和读式时间。

## 先确定这一课教什么

讲题时先提醒用户：“请同时提供题目和参考解答，图片、PDF 或文字均可；只有题目时也可先独立求解。”已有资料直接使用，缺少解答时仍具备自主解题能力。先独立梳理物理关系，再核对参考解答；参考中的省略步骤补全，有错误时按正确推导修正并在制作记录中说明。按 [题目与解答工作流](references/problem-workflow.md) 登记原始资料、识别题干与解答，保留原件和可编辑转写。关键数值、上下标或图形条件辨认不清时再向用户确认。

识别后的题目要真正出现在视频画面中，逐项呈现已知、所求与变量；题目正文属于教学内容，沿用每页不加装饰标题的设置。题图优先重画并保留 TikZ；原图本身有教学价值时可截取，记录来源和像素裁切范围，检查文字和关键图形完整。题干、解答和图中的符号、方向与几何关系保持一致。

题目与参考解答中的数学表达式统一转写为 LaTeX。逐式对照原图，保留分式、根号、上下标、向量、点导数、积分上下限、括号层次和分段条件，确认变量字母、正负号、数值与单位。正文中的变量也写成 `$v_F$`、`$\theta$` 等行内公式。辨认不清的部分留为待确认项，明确后再制作。完整转写保存为 Markdown＋LaTeX，题面通过 XeLaTeX 实际排版进入视频，保留可编辑 `.tex`；解答中的板书动作沿用同一份 LaTeX 源。逐式确认与题面预览在正式配音之前完成，排版失败先修复，再生成成片。依赖与写法见 [题目与解答工作流](references/problem-workflow.md#公式识别与-latex-排版)。

讲题成片使用 Motion Canvas 或 Manim，让物理情景实际运动：物体位置、轨迹、速度方向、场、光线或状态随模型变化，重要时刻可以暂停、回看和对照。固定的是镜头，物理对象照常运动。逐笔写字、淡入公式和镜头缩放仅作为呈现手段。已有模型优先复用，其他题型实现本课模型或原生引擎场景；运动由物理参数决定。配置见 [情景动画](references/scenario-animation.md)。

推导按“依据—运算—结果”连续展开。取方向、作投影、两边乘系数、相加消项、常量移入导数、积分和初末条件均展示必要中间式，并在对应位置讲清原因。尤其当多条关系合成新关系时，先写各条关系怎样变形，再写合成结果。每个关键步骤关联实际口播与板书，写入 `derivation_steps`；完整讲义保留更细的计算。

新讲题课程设置 `kind:"problem"`。正式构建先运行 `teaching-check`，检查输入资料、已复核转写、屏幕题目、真实情景运动和推导链的显示关联。它检查材料与结构；物理结论、数学等价和步骤是否充分仍由独立推导、必要计算及实际画面审阅确定。

复用用户已有讲义、题目、符号和已接受的视觉样式。已有完整题解时，把主要精力放在图文衔接、口播和落笔顺序。新题先完成物理推导，再安排页面；过程分段与所用规律按物理对象确定。按需读 [物理教学](references/teaching.md)。

本用户将 edulab 的四棱锥与球心、激光测曲率两条成片作为质量参照。新系列或调整风格时读 [成片参照](references/reference-cases.md)。先突出题目条件，让图中的辅助线、光路、投影和方向承担推导，再在对应位置记公式；保留完整必要步骤。批量制作复用已经确定的这套讲解规格。

每道例题、练习和综合题都配图，保留可编辑 TikZ；解题过程继续补图、引用图中的点、方向、路径与区域。一个完整问题尽量在同一页讲完：保留主图，逐步补充关系、计算和结论，问题结束后再换页。内容确实放不下时，在明确的中间关系之后换页，下一页第一步直接承接。练习题后保持题目本身，集中解答另列。保留求导、积分、微分方程和必要中间步骤。讲义语言按本用户偏好直接、自然地解释物理；用一条完整推导贯穿。

新课优先使用 `one-page-problem` 语义布局：主图固定在 `diagram`，连续推导写入 `derivation`，物理解释和最终关系分别落在 `explanation`、`result`。公式链用 `formula_steps` 对齐向下展开。运行 `layout-check` 检查遮挡、信息密度和同题跨页。可选聚焦需显式设置 `camera:"focus"`；本系列沿用固定画面。格式见 [一页一题布局](references/layout.md)。

v0.6 新题先从参数化物理组件中选择主图：受力图、斜面、抛体、电偶极、高斯面、直流回路、薄透镜和机械波已经内置。组件保存物理参数，编译时展开为逐笔路径，同步进入 TikZ、PDF、HTML 与三套视频渲染路径；题目特有的点、路径和辅助线继续用普通动作补充。运行 `component-check` 检查参数、区域占用和组件 id。字段与示例见 [物理图形组件](references/components.md)。

v0.7 增加固定镜头默认值、组件几何附着点、滑块接触报告与动作书写时长。`component-check` 现在同时检查滑块底边是否贴合斜面；该检查依据实际生成的路径。相关测试覆盖多组倾角、缩放以及改图后受力线的跟随关系。

## 长课的多 Agent 协作

45 分钟以上、约 18 页以上或批量系列课采用混合工作流：一个主 Agent 先固定课程合同，再让最多三个章节 Agent 并行制作连贯教学段，最后由主 Agent 顺序合并、检查、配音和交付。短课由一个 Agent 完成，减少重复读取。

按章节分工，每个章节 Agent 同时负责本段的物理推导、自然口播、板书动作和 TikZ。不要把同一页拆给物理、文案、板书三个 Agent。章节 Agent 只写自己的目录，不直接修改最终 `lesson.json`，也不调用正式付费 TTS。

先读 [多 Agent 工作流](references/multi-agent.md)，再创建任务包：

```sh
python3 SKILL/scripts/team.py init PROJECT --plan PROJECT/team-plan.json
python3 SKILL/scripts/team.py status PROJECT --fail-on-error
python3 SKILL/scripts/team.py validate PROJECT
python3 SKILL/scripts/team.py merge PROJECT
```

课程合同包含学生基础、时长、符号表、页面政策、音色和章节连接。任务包会写入项目、技能和原文的解析路径，以及可直接复制的校验命令。只把对应原文与任务包交给章节 Agent，以减少重复 token。`team.py validate` 同时执行板书动作、字形、参数、时间锚点、几何范围与语义布局检查。

无配音草稿仍用 `course.py build PROJECT --draft`。定稿后使用下列入口；它会先执行严格时长门、合并课程，然后才调用正式 TTS 和视频渲染：

```sh
python3 SKILL/scripts/team.py build-final PROJECT --renderer motion-canvas --width 1920
```

## 内容文件与程序

`SKILL` 指本文件所在目录，`PROJECT` 是用户工作区内本课文件夹。新课主要写 `lesson.json` 与 `讲义.md`。格式与动作见 [课程格式](references/lesson-format.md)；通用引擎在 `scripts/`，每次制作直接运行，按新课需要扩展一次并验证后复用。

```sh
python3 SKILL/scripts/course.py doctor
python3 SKILL/scripts/course.py init PROJECT --title "课程名" --backend glm
python3 SKILL/scripts/course.py check PROJECT
python3 SKILL/scripts/course.py build PROJECT --draft
python3 SKILL/scripts/course.py build PROJECT --video
```

创建后将完整课程内容填入 `lesson.json`。`--example gauss` 可复制已完成的高斯定理课程作为完整实例；平时只读格式说明和相关片段，避免每次加载整个实例。

先生成布局预览，打开 `contact-sheet.png` 与必要的 `pages/*.png`，处理标签、图形、公式和单位的遮挡及出框。正式视频采用实际音频时长；`--draft` 只供排版，带明确标记，并与正式导出分开。用户已经要求视频时，直接完成 MP4。

可嵌入原题图片并逐笔标出条件；已有两等半径圆水平分离的解析运动组件。正式视频生成后可运行 `python3 SKILL/scripts/captions.py PROJECT --burn` 添加同步字幕，保留独立 SRT 便于修改。具体配置见课程格式。

## 动画引擎

已接入 `motion-canvas` 与 `manim`，共用课程 JSON、中文与公式笔画、解析物理坐标和实测配音时间。二维动态课程优先使用 Motion Canvas，三维或原生数学场景使用 Manim。环境与配置见 [引擎接入](references/renderers.md)。

```sh
python3 SKILL/scripts/course.py build PROJECT --video --renderer motion-canvas --width 1920
python3 SKILL/scripts/course.py build PROJECT --video --renderer manim --width 1920
python3 SKILL/scripts/course.py render PROJECT --renderer motion-canvas
```

已有时间轴与音频时使用 `render`，直接复用配音。机器路径记录在安装时生成的 `runtime-local.json`，发布包排除这个文件。每个引擎独立缓存页面并输出 `video-引擎名.mp4`；`video.mp4` 指向最近完成的导出，随后添加字幕。原生 Manim 场景通过页面的 `native_scenes` 配置，三维动画配套保留二维 TikZ 图稿。

## 口播与配音

主参考是 edulab 的物理教学流程与共享 TTS 设计。v0.4 将板书源、实际口语和语调计划分开：`lesson.json` 保存板书及动作，`speech-plan.json` 保存教师口语、教学角色、重音词、语速与停顿，构建后生成已解析的 `prosody.json`。旧课继续兼容 cue 内的 `tts`。

`tts` 使用自然、能直接念出的口语，数学式另存为 LaTeX。先说物理量及其图中关系，按公式结构断句；一个连贯教学句群一起合成，句内动作可锚定关键词。读题、观察、建模、关键转折、推导、结论和物理意义分别安排速度与停顿。需要在口语中嵌入公式时使用 `tts_parts`，本地公式口语化程序负责常见分式、向量、上下标、导数和单位读法；重要句子仍按上下文人工调整。

配置支持 `glm`、`doubao`、`minimax`、`edge`、`user`。新项目默认 GLM 候选音色 `chuichui`，来自 edulab 配置；实际音色按账户可用项和用户试听结果确定。已接受的音色沿用。Edge 是已跑通的轻量路线；系统 `say` 不在本版正式配音后端中。读 [配音](references/voice.md) 获取配置、读音和缓存说明。

本用户已接受 MiniMax 的 `speech-2.8-hd`、音色 `Chinese (Mandarin)_Gentleman`（温润男声）。后续本系列优先沿用这套配置，逐段安排速度和停顿；已经完成真实调用与试听。

用户提供本人或已获授权的原始 MP3、M4A、WAV 时，可用 `scripts/voice_clone.py` 创建专属 MiniMax `voice_id`。先生成短试听，用户确认后再用 `--apply-voice-id` 写入课程，复用已经创建的 ID；不要从粘贴为文本或已经损坏的音频构建音色。具体要求见 [配音](references/voice.md#minimax-本人音色复刻)。

正式构建默认执行本地高通、轻压缩和响度统一，保持音频总时长不变；随后生成 `voice-report.json`，检查峰值、削波、长静音、口语密度、未口语化公式和模板式表达。需要把警告作为失败处理时运行 `python3 SKILL/scripts/course.py voice-check PROJECT --strict`。配音配置与质量门见 [配音](references/voice.md)。

用户已选的后端与音色保持一致。缺密钥时继续完成推导、课程源与布局预览，配置问题只影响实际合成。凭据从当前进程或本课 `.env` 读取；对外汇报只给出是否配置。付费后端按用户选择使用，失败保留已生成资源并报告原因。

## 批量与修改

一课一个文件夹。批量文件为 `{"projects":["lesson-01","lesson-02"]}`，路径相对批量文件。

```sh
python3 SKILL/scripts/course.py batch BATCH.json --video --jobs 2
```

复用讲义中的符号、公式与图形参数。每段音频按文本、后端、音色、模型与语速缓存；每页视频按页面内容、局部时间轴、音频、引擎、字体、分辨率和帧率缓存。修改单页后重新 build，缓存自动复用其余页。批量任务分开运行，有失败项时其余课程继续，结果写入 `batch-report.json`。

## 完成与交付

保留 `lesson.json`、完整文字讲义、`narration.md`、`timeline.json`、TikZ、板书 PDF、自包含 HTML 和 MP4。正式交付说明实际时长、配音后端与已经执行的检查；运行失败的项目标出具体原因。程序负责格式、几何范围、时间与文件一致性；物理结论靠完整推导及必要计算确定。

技能中的公开 API 适配已按源码和文档实现；配音质量、账号音色与供应商可用性以实际合成为准。需要具体公众号范例时，先读取范例再归纳其文稿与声音特点；访问受限时清楚记录可见内容。上游研究、版本和采纳理由见 [研究记录](references/upstream-study.md)。
