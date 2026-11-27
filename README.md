# 物理逐笔板书视频技能

当前版本 0.27.14。给它一道物理题或一节课的主题，可以制作带中文配音的逐笔板书视频，也能导出学生讲义和可编辑的 TikZ 配图。使用时需要支持 Agent Skills 和本地命令的宿主。

0.27.14 按[八步流程](references/production-workflow.md)制作，附读音卡包、目标音色包、自我成长包和五组可编辑材料。斜面样例共用通用字形，重放时再生成时间轴与检查报告。

0.27.9 内置 Academic Humanizer。备新授课或习题课时，可以按[课堂文案改稿说明](references/classroom-language-editing.md)修改讲稿。重写[两份长课模板](assets/starter-kit/long-lessons/README.md)，各段均附试讲。符合条件的 Apple Silicon Mac 安装技能时会同时下载[本地 Qwen 配音](references/platform-install.md#随技能安装本地配音)。

公开仓库保留读音卡、反馈和复试记录，随包试音使用公开合成音色。个人音色配置、参考录音和私人试听留在本机。

## 教案审阅与交付

先扫自我成长包，再按课型备课。把完整讲稿、教案、板书、动画预览、学生讲义和实录试音一起交给授课人。确认后用 `approve-plan` 记录，再开始正式配音。成片逐句核对口播与落笔，交付视频、学生讲义 PDF 和可编辑的 LaTeX、TikZ 源码。[审阅教案的步骤](references/review-workflow.md)片头可按课程指定作者信息，或从本机作者配置读取。

两个课型都可用 `estimate-duration` [估算课长](references/duration-planning.md)，教案并列显示教学预算与按讲稿推算的时长。配音检查分开提醒句内疑似卡壳和段与段之间的空档，`voice-check --listen CUE_ID --context` 导出相邻语句供连续回听。

## 选择课型

| 课型 | 适用内容 | 课堂推进 |
|---|---|---|
| [习题课](references/problem-workflow.md) | 指定题目、题解或习题集 | 题面入屏，演示题设过程，结合主图和辅助图逐步推导 |
| [新授课](references/concept-lesson.md) | 新概念、定律或教材章节 | 观察与对照，引出关系，逐笔写完整结论，给出思考和应用 |

两种课型共用一个安装包。直接对 Agent 说“使用 $physics-notebook-video，把这道题做成习题课”或“使用 $physics-notebook-video，讲一节关于电场强度的新授课”。也可从两个可编辑示例开始：

~~~sh
python3 scripts/course.py init exercise-demo --kind problem
python3 scripts/course.py init concept-demo --kind concept
~~~

习题课载入追逐运动示例，新授课载入位移式的量纲检查示例。各自用 `build PROJECT --draft` 查看布局与落笔顺序。两种课型共用板书笔迹、动画引擎、配音缓存和导出命令。讲到结论时，视频会在板书上把它写完整，学生可以暂停抄写。

## 制作能力

可以把文字和公式逐笔写到板书上，边画图边讲推导。支持 MiniMax、Edge 配音和同步字幕，用 Motion Canvas 或 Manim 渲染。支持页面缓存和批量导出，也能保存 TikZ 配图和板书 PDF。完整制作流程已在 macOS 上试过。Windows 和 Linux 的完整安装流程还有待试用。

模板默认采用固定画面、无逐页标题的笔记本样式和自然课堂口播。MiniMax 音色优先读取本机已配置的默认值。使用者可指定其他样式与音色。

项目仓库：[xingxidong/physics-notebook-video](https://github.com/xingxidong/physics-notebook-video)。

下载：[最新版本](https://github.com/xingxidong/physics-notebook-video/releases/latest)。

## 平台支持

| 平台 | 安装方式 | 说明 |
|---|---|---|
| Codex | `~/.codex/skills/physics-notebook-video` 或项目 `.codex/skills/` | 原生 Agent Skills |
| Claude Code | `~/.claude/skills/physics-notebook-video` 或项目 `.claude/skills/` | 原生 Agent Skills |
| claude.ai | 上传发布 ZIP | 需支持自定义 Skill 和代码执行的账户方案 |
| 豆包工作 | 在开发者平台上传豆包 ZIP | 公开上架需企业认证和审核 |
| DeepSeek | 在 Codex、Claude Code、OpenCode 等宿主中使用 DeepSeek 模型 | DeepSeek 官方聊天端当前无本地 Skill 商店 |
| 其他宿主 | 安装到宿主的 Agent Skills/capability 目录 | 遵循 `agentskills.io` |

平台是执行文件和脚本的宿主，模型是负责推理与生成的供应商。同一个 Codex/Claude/OpenCode 宿主可以使用 OpenAI、Anthropic、豆包或 DeepSeek 模型，技能源码不变。各平台能运行哪些功能，见[跨平台安装](references/platform-install.md)。

## 统一安装器

克隆仓库后，使用同一个脚本安装：

```sh
git clone https://github.com/xingxidong/physics-notebook-video.git
cd physics-notebook-video
python3 scripts/platform_install.py info
python3 scripts/platform_install.py install --target codex
# 或
python3 scripts/platform_install.py install --target claude
```

安装到项目级目录：

```sh
python3 scripts/platform_install.py install --target codex --scope project --project /path/to/project
python3 scripts/platform_install.py install --target claude --scope project --project /path/to/project
```

生成通用上传包。通过豆包平台上传时，按其独立的容量要求检查。[平台限制](references/platform-install.md#zip-文件数限制)

```sh
python3 scripts/platform_install.py package --target universal --output physics-notebook-video.zip
```

安装完成后开启新会话。Codex 使用 `$physics-notebook-video`，Claude Code 可使用 `/physics-notebook-video`，也可以让宿主按 `description` 自动触发。已安装同名技能时，显式使用 `--update`；更新保留 `.env` 和 `runtime-local.json`。

## 准备运行环境

需要 Python 3.11 或更新版本、FFmpeg/ffprobe、中文字体。题面排版需要 XeLaTeX、xeCJK、amsmath 和 PyMuPDF。Motion Canvas 还需要 Node.js 20 或更新版本与 Chrome/Chromium。原生 Manim 的 MathTex 需要 TeX 和 dvisvgm。

让当前 Agent 检查已有依赖并补齐缺项，或在工作目录中运行以下 macOS 命令。将 `PHYSICS_SKILL` 改成实际安装目录：

```sh
PHYSICS_SKILL="$HOME/.codex/skills/physics-notebook-video"
python3 -m venv .venv
.venv/bin/python -m pip install -r "$PHYSICS_SKILL/assets/requirements.txt"
.venv/bin/python -m pip install -r "$PHYSICS_SKILL/assets/requirements-manim.txt"
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" setup-renderers --runtime "$PWD/.runtime/motion-canvas"
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" doctor
```

`setup-renderers` 安装锁定版本的 Motion Canvas 依赖，并生成这台机器自己的 `runtime-local.json`，记录运行环境位置。此文件保留在本机，更新或发布技能时沿用本机配置。

具体引擎设置与原生三维场景见 [引擎说明](references/renderers.md)。

## 第一次运行：先看布局

首次使用可以先做一遍[从一页 PDF 到成片的示例](assets/starter-kit/incline/README.md)。

```sh
python3 "$PHYSICS_SKILL/scripts/sample_kit.py" render /ABS/EMPTY/demo
```

它使用随包音频，输出约一分半的完整视频、板书与预览，不调用配音接口。下面的课型示例用于自己备课。

```sh
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" init lesson-demo --title "点电荷的电场" --backend minimax
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" build lesson-demo --draft
```

打开 `lesson-demo/preview.html` 或 `contact-sheet.png`。这一步使用自带示例和估算时长，供安装与版面检查。

教案经人确认后，将技能中的 `.env.example` 复制为 `lesson-demo/.env`，在本地填入自己的 MiniMax API Key：

```dotenv
MINIMAX_API_KEY=自己的密钥
MINIMAX_API_HOST=https://api.minimax.cn
```

然后生成正式视频：

```sh
# 依照教案审阅流程准备全套材料与试音，完成确认后再运行 build。
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" review-plan lesson-demo
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" build lesson-demo --video --renderer motion-canvas --width 1920
.venv/bin/python "$PHYSICS_SKILL/scripts/captions.py" lesson-demo --burn
```

待审成片为 `lesson-demo/video-captioned.mp4`。对该文件运行 `quality-check lesson-demo --stage final --video-file video-captioned.mp4`，按 [制作流程](references/production-workflow.md) 完成实际试听与观看，再用 `finalize lesson-demo --video-file video-captioned.mp4` 生成交付清单。需要先试另一种配音时，可在 `init` 中选择 `--backend edge`；Edge 需要联网。

## 习题课的资料与用法

请同时提供题目和参考解答，图片、PDF、文字均可。只有题目时，Agent 也会独立求解。原件先登记，再将识别后的题干、参考解答和逐步推导转成课程源：

```sh
python3 "$PHYSICS_SKILL/scripts/intake.py" my-problem --problem question.png --solution answer.pdf
```

实际转写、解题与图文编排由当前 Agent 完成，程序保留原件和来源哈希。详细流程见 [题目与解答](references/problem-workflow.md)。

向已安装技能的 Agent 提供题图或讲义，然后发送：

```text
使用 $physics-notebook-video，将这道题制作成物理竞赛讲解视频。
我会同时提供题目和参考解答；公式转写为 LaTeX，逐式对照原图，补全参考解答中的省略步骤。
用我已配置的 MiniMax 音色，文案像老师自然讲课。
逐笔书写，每页不加标题；保留必要推导、过程配图和可编辑 TikZ。
题目要出现在视频里，情景用 Motion Canvas 或 Manim 动起来，镜头保持固定。
导出1080p视频、字幕、讲义与课程源。
```

新题由当前 Agent 完成物理推导、图形与口播编排；渲染、重新编码和缓存复用由程序执行。图形和笔画组件可随题型继续积累。

内置组件涵盖受力图、斜面、抛体、电偶极、高斯面、直流回路、薄透镜和机械波。用完整示例检查组件布局：

```sh
python3 "$PHYSICS_SKILL/scripts/course.py" init components-demo --example components --backend minimax
python3 "$PHYSICS_SKILL/scripts/course.py" build components-demo --draft
python3 "$PHYSICS_SKILL/scripts/course.py" component-check components-demo --strict
```

组件字段与物理参数见 [参数化物理图形组件](references/components.md)。

体验 v0.8 的“题目入屏、情景运动、逐步推导”完整示例：

```sh
python3 "$PHYSICS_SKILL/scripts/course.py" init pursuit-demo --example pursuit --backend minimax
python3 "$PHYSICS_SKILL/scripts/course.py" teaching-check pursuit-demo
python3 "$PHYSICS_SKILL/scripts/course.py" build pursuit-demo --draft
# 先生成教案，等审阅者明确确认后记录 approve-plan。
python3 "$PHYSICS_SKILL/scripts/course.py" review-plan pursuit-demo
python3 "$PHYSICS_SKILL/scripts/course.py" build pursuit-demo --video --renderer motion-canvas --width 1920
```

安装包里有这道题和参考解答。情景中的运动按模型计算，板书逐步写出 8 个中间式。`teaching-report.json` 记录资料和课程结构的检查结果。制作时还要复算并查看画面。模型设置见 [情景动画](references/scenario-animation.md)。

v0.7 的斜面完整示例包含底边接触、受力线附着、逐行推导和结果停留：

```sh
python3 "$PHYSICS_SKILL/scripts/course.py" init incline-demo --example incline --backend minimax
python3 "$PHYSICS_SKILL/scripts/course.py" build incline-demo --draft
python3 "$PHYSICS_SKILL/scripts/course.py" component-check incline-demo --strict
```

## 长课与多 Agent

目标时长超过 45 分钟时，可让主 Agent 先建立课程合同，再把不同教学段交给最多三个章节 Agent 并行制作。每个章节 Agent 同时完成本段的物理、口播、板书和 TikZ；主 Agent 最后统一合并、生成正式配音和视频。

从示例建立计划：

```sh
cp "$PHYSICS_SKILL/assets/team-plan.example.json" long-course/team-plan.json
python3 "$PHYSICS_SKILL/scripts/team.py" init long-course --plan long-course/team-plan.json
python3 "$PHYSICS_SKILL/scripts/team.py" status long-course --fail-on-error
```

各章节完成 `fragment.json` 后：

```sh
python3 "$PHYSICS_SKILL/scripts/team.py" validate long-course
python3 "$PHYSICS_SKILL/scripts/team.py" merge long-course
python3 "$PHYSICS_SKILL/scripts/course.py" build long-course --draft
```

`validate` 已包含动作、字形和几何范围检查。定稿后使用下列命令正式制作；它会先执行严格时长门和合并，通过后才调用 TTS 与视频渲染：

```sh
python3 "$PHYSICS_SKILL/scripts/team.py" build-final long-course --renderer motion-canvas --width 1920
```

成片后用 `team.py verify-video long-course --video long-course/video-captioned.mp4` 检查最低时长。

各段要交哪些文件、合并前要检查什么，见[多 Agent 工作流](references/multi-agent.md)。

## 分享给其他人

直接发送发布 ZIP 和这份 README 即可。接收者安装到自己的 Agent 宿主，并配置自己的运行环境与配音账户。

分享 [GitHub 仓库](https://github.com/xingxidong/physics-notebook-video) 或 [最新发布页](https://github.com/xingxidong/physics-notebook-video/releases/latest)，接收者即可自行下载。每个版本同时提供 ZIP 与 SHA256 校验文件。

发布包包含代码、模板、依赖锁文件与第三方材料说明。语音服务账户、费用及生成内容所需的模型使用量由各使用者自己的环境承担。第三方材料来源见 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)。

## 版本记录

<details>
<summary>查看 0.6 到 0.27.8 的改动</summary>

0.27.8 将[自我成长库的跨课复试](references/classroom-transfer.md)接入备课和成片复查。保留每次试用的完整课堂句、结果及短样，记录故障发生的环节，按当前版改法回看依据。

0.27.7 从真实课稿、赛题和讲义新增[68 张读音卡](references/term-glossaries/扩展-0.27.7/README.md)，整库 3,740 张。订正 23 张旧卡，修复“三相交流电”和“偏转角”的跨词误判。

0.27.6 新增[四组课堂读音卡](references/term-glossaries/扩展-0.27.6/README.md)共 1,000 张，整库 3,672 张。新增词逐卡交叉复读，上一批 72 张补做独立复查。修订涉及“分度值”和“滞止点”。

0.27.5 新增[实验测量、机械波与声学、流体与材料读音卡](references/term-glossaries/扩展-0.27.5/README.md) 72 张，词库共 2,672 张。

0.27.4 新增[三组完整读音卡](references/term-glossaries/扩展-0.27.4/README.md)，共 180 张，现有 2600 张。补充力学与数学方法、电磁学与光学、热学与近代物理中的常用缺项，沿用完整例句和具体连读标准，原有学习记录保留。

0.27.3 完成[全部 2,420 张课堂读音卡的六项内容](references/term-glossaries/全库完善/README.md)：保留 63 张完整卡，逐条补齐其余 2,357 张的词义、课堂例句、连读和易混提示；保留参考课来源，订正发现的旧拼音。全部随技能安装，并接入固定试音、历史反馈和成片逐处检查。

0.27.2 将 [16 句固定试音与读音卡、历史反馈、本课难句接通](assets/starter-kit/voice-trial/README.md)。自动选材，逐处区分读音与连读，实听结果和音段随技能保存；词卡改变后相关句重查，成片仍检查每次出现。

0.27.1 恢复随包斜面视频的浅色方格笔记本背景，同步更新板书预览和样例成片；新课与样例沿用默认网格样式。

0.27.0 增加[完整样例、固定试音材料、长课模板与参数动画](assets/starter-kit/README.md)，接通本地 Qwen；完善逐句术语盘点、学习资料合并、推导同步与最终交付检查。[制作与交付](references/production-workflow.md)

0.26.0 将课堂词卡、制课反馈、改法与试听片段随技能打包。创建课程会先生成《备课提醒》，写完讲稿后逐句对照以往的问题。[随技能带走的学习记录](references/viewer-feedback.md)

0.25.0 增加制课进度、逐步对应的板书和讲义、修订试听，以及可在空目录编译的学生讲义源码包。[制课与修订命令](references/production-workflow.md)

0.24.0 让制作前的术语清单、配音输入和成片检查共用逐处读法。作者指出的断词可以直接进入个人词卡。重复术语中节奏异常的句子会集中列出，26 个字母配有中文课堂例句。[词卡用法与复听](references/term-flow.md#同一句里的不同读音)

0.23.0 加入独立保存的课堂读音卡。学过的课程可以删除原片，今后仍可查整词拼音、易混用法和连读示例。制作端逐句补齐本课新词，在本次导出的音轨上逐次检查。[课堂读音卡和整课逐词检查](references/term-flow.md#课堂读音卡)

0.22.0 新增整句音画复核、本地拼音与字母音素复测和匿名录音盲测。补录后按改变的音轨、接缝及板书重查。[语音纠错操作](references/term-flow.md#听完整句话再决定怎样补录)

0.21.1 将各讲新增的整词读音直接接入备课和成片审查。新词候选附原句，读音有分歧的术语在配音前单列。[新词覆盖](references/term-flow.md)

0.21.0 先识别整课物理术语，再从最终音轨逐处检查发音和连读。[术语检查](references/term-flow.md)

0.20.3 增加常用词逐字读音审查，口播和交付音轨共用词、字与原句位置。[常用词读音审查](references/voice.md#常用词读音审查)

0.20.2 对全课排查学科多音词，从本课选试音句，一次听一整句并逐处记录实音。

0.20.1 增加“测量”和物理量的分词选音，按反馈词在实际交付视频中的每次出现记录声调。[成片声调复听](references/voice.md#成片声调复听)

0.20.0 将作者反馈的修订历史、适用课型和已选音色样本接入下一课的制作前检查。用一条真实课堂句比较修改前后的效果。[反馈与样本复查](references/viewer-feedback.md#从一次反馈到下一节课)

0.19.2 增加学生口播出处提示、字母连读提示、句间急接和短脉冲的定位。

0.19.1 增加文章讲解的原文对照、作者最低时长偏好和成片时长检查。

0.19.0 加入[看课反馈与制作前检查](references/viewer-feedback.md)。两类课和批量制课共用历史问题库、多音字错读库、字母错读库。

0.18.1 让变量按字母名朗读，x、X 的目标音都是 /ɛks/。本地配音输入含字母音标、词级拼音和高频错读词的纯文本提示，正式检查按原音轨定位试听。

0.18.0 在教案中列出加长课程带来的学习收获，支持按句指定字母读法、导出读音试听合辑，并从交付的 MP4 抽取原尺寸画面。

0.17.0 把课堂编排升级为可审阅的“教学拍”：每一拍记录学生问题、画面依据、画面变化和本步结论，支持从观察、反例、对照、模型或推导进入，不套固定四段式。连续的相邻推理可用 `speech_group` 一次配音，减少逐句重新起音的机械感。

0.16.2 将课程收束设为正式教学结构：总结回扣模型或开场问题、关键依据和结果或应用，教案直接展示总结设计。构建前还会检查总结开始时，学生能否看到它指向的模型、关键式和结论。

0.16.1 支持用 `layout.prewritten` 在开讲前呈现完整模型。备课加入总结口播，收尾时沿用图和结论板书。

0.16.0 加入[统一制作检查](references/quality-workflow.md)：习题课重点关联实际板书，按教学段比较时长；所有布局参与可见性检查，配音严格检查包含句内疑似卡壳、段间空档和术语试听。`quality-check` 汇总具体问题与尚需观看试听的范围。本地作者信息随安装保留，通用安装包不携带个人作者配置。

0.10.6 为概念课增加完整结论板书。定义和定律关联实际手写动作，时间轴检查全部写出后的保留时间。见 [知识点结论板书](references/knowledge-board.md)。

0.10.5 加强课堂口播改写。配音前报告引用具体原句，提示套话、重复段首、句中断点和密集报数。配音后报告提供回听位置。见 [课堂表达与节奏](references/classroom-delivery.md)。

0.10.4 将多音字、常用物理术语和已知术语错字加入成片配音审查。报告标出试听位置，`voice-check --listen` 可从现有配音截取指定段落。见 [质量报告](references/voice.md#本地母带与质量报告)。

0.10.3 加入 MiniMax 物理术语读音词表，支持按课程或口播段补充。配音前报告列出匹配项，修改读音时复用其他音频段。见 [物理术语和多音字](references/voice.md#物理术语和多音字)。

0.10.2 的板书公式与图中讲解用的汉字标注采用逐笔手写。视频内字幕使用同一套手写笔迹，LaTeX 作为可编辑公式源。物理状态按配音关键词变化，概念课记录推导关联。见 [语义场景与逐笔公式](references/semantic-scenes.md)。

0.9.0 加入课堂节奏配置、配音前文稿检查、教学停顿用途和本地音频首尾空白处理。词时间戳随裁切同步移动，原始配音缓存继续保留。新课直接按图讲物理，减少绕行符号描述与统一长段；详细写法见 [课堂表达与节奏](references/classroom-delivery.md)。实际语感通过成片试听与观看确定。

0.7.1 将自然课堂文稿要求写入技能：直接解释物理对象与运算，删去介绍讲解结构的套话；重写斜面示例口播，并增加偏导符号的逐笔书写支持。

0.8.0 加入题目与参考解答登记、LaTeX 题面排版、源图片裁切、纯追逐情景动画和逐步推导关联。题干和解答公式逐式对照原件，保留上下标、分式、向量和积分范围；题面经 XeLaTeX 编译，交付可编辑 `.tex`。新讲题课程在正式配音前检查资料与教学结构。固定镜头下，物理对象按模型移动，推导保留乘系数、消项和合成导数等中间步骤。

0.8.1 修复 Manim 中很短的笔画显示：点导数上方的小点、物理点标记等绘制为实际圆点，普通笔画采用圆形端点，保留完整数学记号。

0.7 将固定画面设为默认，去掉公式行间的连接箭头，加入滑块接触检查、组件附着点和书写时长控制。

0.6 新增八类参数化物理图形组件。

</details>
