# 物理逐笔板书视频技能

版本：0.8.0。面向支持 Agent Skills 和本地命令的 Agent 宿主，制作带中文配音的物理讲解视频。

已完成并实测：中文与公式逐笔书写、图文推导、MiniMax 与 Edge 配音、同步字幕、Motion Canvas 和 Manim 渲染、页面缓存、批量导出，以及 TikZ 与板书 PDF。0.6 新增八类参数化物理图形组件；0.7 默认固定画面、取消公式行间连接箭头，加入滑块接触检查、组件附着点和书写时长控制。当前完整视频流程在 macOS 上验证；Windows、Linux 的完整安装流程尚未验证。

模板默认采用固定画面、无逐页标题的笔记本样式和自然课堂口播。MiniMax 音色优先读取本机已配置的默认值。使用者可指定其他样式与音色。

0.7.1 将自然课堂文稿要求写入技能：直接解释物理对象与运算，删去介绍讲解结构的套话；重写斜面示例口播，并增加偏导符号的逐笔书写支持。

0.8.0 加入题目与参考解答登记、LaTeX 题面排版、源图片裁切、纯追逐情景动画和逐步推导关联。题干和解答公式逐式对照原件，保留上下标、分式、向量和积分范围；题面经 XeLaTeX 编译，交付可编辑 `.tex`。新讲题课程在正式配音前检查资料与教学结构。固定镜头下，物理对象按模型移动，推导保留乘系数、消项和合成导数等中间步骤。

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

平台是执行文件和脚本的宿主，模型是负责推理与生成的供应商。同一个 Codex/Claude/OpenCode 宿主可以使用 OpenAI、Anthropic、豆包或 DeepSeek 模型，技能源码不变。详细能力边界见 [跨平台安装](references/platform-install.md)。

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

生成通用上传包和豆包专用检查包：

```sh
python3 scripts/platform_install.py package --target universal --output physics-notebook-video.zip
python3 scripts/platform_install.py package --target doubao --output physics-notebook-video-doubao.zip
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

```sh
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" init lesson-demo --title "点电荷的电场" --backend minimax
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" build lesson-demo --draft
```

打开 `lesson-demo/preview.html` 或 `contact-sheet.png`。这一步使用自带示例和估算时长，供安装与版面检查。

正式配音前，将技能中的 `.env.example` 复制为 `lesson-demo/.env`，在本地填入自己的 MiniMax API Key：

```dotenv
MINIMAX_API_KEY=自己的密钥
MINIMAX_API_HOST=https://api.minimax.cn
```

然后生成正式视频：

```sh
.venv/bin/python "$PHYSICS_SKILL/scripts/course.py" build lesson-demo --video --renderer motion-canvas --width 1920
.venv/bin/python "$PHYSICS_SKILL/scripts/captions.py" lesson-demo --burn
```

成片为 `lesson-demo/video-captioned.mp4`。需要先试另一种配音时，可在 `init` 中选择 `--backend edge`；Edge 需要联网。

## 日常使用

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
python3 "$PHYSICS_SKILL/scripts/course.py" build pursuit-demo --video --renderer motion-canvas --width 1920
```

该示例随包提供文字题目和参考解答。物理运动由模型计算，含 8 个有依据的中间式。`teaching-report.json` 检查资料与结构，数学和物理正确性仍由推导、计算和画面审阅共同确定。模型设置见 [情景动画](references/scenario-animation.md)。

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

详细任务边界、片段格式与质量门见 [多 Agent 工作流](references/multi-agent.md)。

## 分享给其他人

直接发送发布 ZIP 和这份 README 即可。接收者安装到自己的 Agent 宿主，并配置自己的运行环境与配音账户。

分享 [GitHub 仓库](https://github.com/xingxidong/physics-notebook-video) 或 [最新发布页](https://github.com/xingxidong/physics-notebook-video/releases/latest)，接收者即可自行下载。每个版本同时提供 ZIP 与 SHA256 校验文件。

发布包包含代码、模板、依赖锁文件与第三方材料说明。语音服务账户、费用及生成内容所需的模型使用量由各使用者自己的环境承担。第三方材料来源见 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)。
