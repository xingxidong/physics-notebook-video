# 跨平台安装与模型接入

本项目以 `SKILL.md + scripts/ + references/ + assets/` 为唯一源码，遵循 Agent Skills 开放格式。平台名称和模型供应商是两个维度：Codex、Claude Code 是能读文件并运行脚本的 Agent 宿主；OpenAI、Anthropic、豆包、DeepSeek 是模型供应商。使用豆包或 DeepSeek 模型时，宿主仍需提供文件系统、Shell 和程序执行能力。

## 统一工具

```sh
python3 scripts/platform_install.py info
python3 scripts/platform_install.py check
python3 scripts/platform_install.py install --target codex
python3 scripts/platform_install.py install --target claude
python3 scripts/platform_install.py package --target universal --output physics-notebook-video.zip
python3 scripts/platform_install.py package --target doubao --output physics-notebook-video-doubao.zip
python3 scripts/platform_install.py verify physics-notebook-video.zip --target universal
```

`install` 在目标目录已存在时停止；显式传入 `--update` 才合并更新。更新保留本机的 `.env` 和 `runtime-local.json`。需要自定义位置时使用 `--dest /absolute/path/physics-notebook-video`。

## Codex

用户级默认安装到 `$CODEX_HOME/skills/physics-notebook-video`；未设置 `CODEX_HOME` 时使用 `~/.codex/skills/physics-notebook-video`。项目级安装使用：

```sh
python3 scripts/platform_install.py install --target codex --scope project --project /path/to/project
```

也可以让 Codex 直接从公开 GitHub 仓库安装。

## Claude Code 与 claude.ai

Claude Code 的用户级目录是 `~/.claude/skills/physics-notebook-video`，项目级目录是 `.claude/skills/physics-notebook-video`。

```sh
python3 scripts/platform_install.py install --target claude
python3 scripts/platform_install.py install --target claude --scope project --project /path/to/project
```

claude.ai 的自定义 Skill 界面直接上传 `package --target claude` 产生的 ZIP。该能力需账户方案支持且开启代码执行。

## 豆包工作

豆包工作支持开发者上传 Skill ZIP。使用 `package --target doubao` 生成符合 16 MB 总量、1024 文件、单文件 2 MB 限制的包。上架需完成豆包开发者平台企业认证、静态检查、评测报告和平台审核。

本技能的本地 Python、Motion Canvas、Manim 与 FFmpeg 需要可执行脚本的环境。若豆包的运行环境只加载 `SKILL.md` 而不提供本地执行，将渲染命令暴露为经过鉴权的远程 MCP/连接器；密钥保存在服务端，不写入 Skill ZIP。

## DeepSeek

DeepSeek 模型 API 支持工具调用，并提供 OpenAI Responses / Anthropic 兼容接口。DeepSeek 官方聊天端当前没有公开的本地 Skill 安装目录或 Skill 商店。实际接入时，在 Codex、Claude Code、OpenCode 或其他 Agent Skills 宿主中配置 DeepSeek 作为模型，再按宿主方式安装本技能。

只有 DeepSeek API 时，应用程序还需负责：把 Skill 的 `name` 和 `description` 加入可发现上下文；命中后读取 `SKILL.md`；提供文件、Shell 和权限受控的工具循环。模型 API 只返回工具调用意图，实际程序仍由宿主执行。

## 通用 Agent Skills 宿主

对兼容 `agentskills.io` 的其他宿主，把整个 `physics-notebook-video` 目录放到宿主的 capability/skills 目录。如果宿主的目录不在预设列表，显式使用：

```sh
python3 scripts/platform_install.py install --target agents --dest /absolute/capability/path/physics-notebook-video
```

## 凭据和包内容

公开包只包含指令、程序、模板与开源资源。以下内容在安装和打包时排除：

- `.env` 和 API Key；
- `runtime-local.json` 和机器绝对路径；
- `cache/`、`node_modules/`、`__pycache__/` 和已生成视频。

各使用者在自己的课程目录或宿主凭据管理中配置 TTS 与模型密钥。

## 官方规范

- [Agent Skills 开放规范](https://agentskills.io/specification)
- [OpenAI Skills](https://developers.openai.com/api/docs/guides/tools-skills)
- [Claude Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Claude Code Skills](https://code.claude.com/docs/en/skills)
- [豆包工作 Skill 接入指南](https://open.doubao.com/document/doubao-developer-guide/skill-integration-guide)
- [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)
- [DeepSeek Responses API](https://api-docs.deepseek.com/guides/responses_api/)
