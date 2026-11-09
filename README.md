# 物理逐笔板书视频技能

版本：0.2.0。面向可运行本地命令的 Codex，制作带中文配音的物理讲解视频。

已完成并实测：中文与公式逐笔书写、图文推导、MiniMax 与 Edge 配音、同步字幕、Motion Canvas 和 Manim 渲染、页面缓存、批量导出，以及 TikZ 与板书 PDF。0.2.0 新增长课多 Agent 任务包、章节校验与确定性合并。当前完整视频流程在 macOS 上验证；Windows、Linux 的完整安装流程尚未验证。

模板默认采用无逐页标题的笔记本样式、自然课堂口播和 MiniMax 温润男声。使用者可指定其他样式与音色。

项目仓库：[xingxidong/physics-notebook-video](https://github.com/xingxidong/physics-notebook-video)。

下载：[最新版本](https://github.com/xingxidong/physics-notebook-video/releases/latest)。

## 最省事的安装方式

把仓库地址发给 Codex，并发送：

```text
请从 https://github.com/xingxidong/physics-notebook-video 安装技能。
先阅读 README.md 和 SKILL.md，检查本机环境，再配置独立的 Python 环境与所需动画依赖。
先生成自带示例的无配音排版预览，确认安装完成。
MiniMax 使用我自己的 API Key，保存在本地课程 .env 中。
```

也可以下载上面的发布 ZIP，附给 Codex，并发送：

```text
请安装附件中的 physics-notebook-video 技能到当前 Codex 支持的用户级技能目录。
先检查本机环境，再配置独立的 Python 环境和所需动画依赖。
先生成自带示例的无配音排版预览，确认安装完成。
MiniMax 使用我自己的 API Key，保存在本地课程 .env 中。
```

安装完成后开启新会话，使用 `$physics-notebook-video` 调用。

## 手动安装技能

解压 ZIP，复制整个 `physics-notebook-video` 文件夹。按当前 Codex 官方手动安装说明，用户级目录为：

```text
~/.agents/skills/physics-notebook-video/SKILL.md
```

文件夹内应直接有 `SKILL.md`，以及 `scripts`、`references`、`assets` 等目录。通过内置 skill-installer 安装时，使用安装器选定的技能目录，避免重复安装同名副本。

[Codex 官方技能安装目录说明](https://developers.openai.com/api/reference/cli)。

使用 Git 安装时：

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/xingxidong/physics-notebook-video.git "$HOME/.agents/skills/physics-notebook-video"
```

已安装同名技能时，先确认原目录的位置与自己的改动，再进行更新。技能文件安装完成后，继续准备下面的运行环境。

## 准备运行环境

需要 Python 3.11 或更新版本、FFmpeg/ffprobe、中文字体。Motion Canvas 还需要 Node.js 20 或更新版本与 Chrome/Chromium。原生 Manim 的 MathTex 需要 TeX 和 dvisvgm。

让 Codex 检查已有依赖并补齐缺项，或在工作目录中运行以下 macOS 命令。将 `PHYSICS_SKILL` 改成实际安装目录：

```sh
PHYSICS_SKILL="$HOME/.agents/skills/physics-notebook-video"
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

向 Codex 提供题图或讲义，然后发送：

```text
使用 $physics-notebook-video，将这道题制作成物理竞赛讲解视频。
用我已配置的 MiniMax 音色，文案像老师自然讲课。
逐笔书写，每页不加标题；保留必要推导、过程配图和可编辑 TikZ。
导出1080p视频、字幕、讲义与课程源。
```

新题由 Codex 完成物理推导、图形与口播编排；渲染、重新编码和缓存复用由程序执行。图形和笔画组件可随题型继续积累。

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

直接发送发布 ZIP 和这份 README 即可。接收者安装到自己的 Codex，并配置自己的运行环境与配音账户。

分享 [GitHub 仓库](https://github.com/xingxidong/physics-notebook-video) 或 [最新发布页](https://github.com/xingxidong/physics-notebook-video/releases/latest)，接收者即可自行下载。每个版本同时提供 ZIP 与 SHA256 校验文件。

发布包包含代码、模板、依赖锁文件与第三方材料说明。语音服务账户、费用及生成内容所需的模型使用量由各使用者自己的环境承担。第三方材料来源见 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md)。
