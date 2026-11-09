# 教师口播与配音

## edulab 的可取设计

它把正常板书/字幕与实际朗读文本分开，维护读音词表，用真实音频时长安排画面；共享语音模块接入 GLM、豆包、MiniMax，部分后端返回词级时间。新技能保留这些机制，并沿用用户已选择的逐笔笔记本风格。

真人感的参照分三层：文稿如何带学生思考、选用什么音色、句内和句间怎样停顿。分析具体视频时分别记录。仓库配置只证明代码使用什么后端；具体公众号视频的声音以视频或作者说明为准。

## 写法

一个 cue 是一段连贯教学句群，通常40—100汉字，按实际推导调整。讲解复杂分式时分清分子、分母；第一次给出物理量名称，再引用图中的符号。单位、乘方和方向读完整。不要添加“嗯”“呃”等伪装思考的填充。

读题自然稍快，建模与方向放慢，关键转折强调因果，列式后留出看图时间。语速和音高变化服务于物理解释，保持整课音色一致。

| 板书 | 可读口播 |
|---|---|
| mg | 重力；需要符号时再读字母 |
| mg sinθ | 重力沿斜面的分量 |
| ε₀ | 真空介电常数 |
| Q_in | 高斯面包住的净电荷 |
| dS | 这一小块面积 |
| v₀²/(2a) | 初速度的平方，除以两倍加速度 |
| 10 m/s | 十米每秒 |
| 2 m/s² | 二米每二次方秒 |

口播在 JSON 中另存 tts；公式用 latex，原书面字幕可放 text。多音字先通过自然措辞或该后端的发音功能处理。试听关注数字、字母串、希腊字母、单位和分式。

## 配置

本版默认新项目选 `glm`；候选音色来自 edulab，具体声音按账户音色列表和试听确定。用户已接受某个后端、音色时沿用。

| backend | 凭据 | 配置 |
|---|---|---|
| glm | GLM_API_KEY | voice默认chuichui；model固定glm-tts |
| doubao | DOUBAO_API_KEY | voice；resource_id默认seed-tts-2.0 |
| minimax | MINIMAX_API_KEY | voice；model默认speech-2.8-hd；MINIMAX_API_HOST默认https://api.minimaxi.com |
| edge | 无API密钥，需联网及edge-tts | 默认zh-CN-YunxiNeural；支持pitch |
| user | 无API密钥 | 每个cue用audio指定本课目录中的录音 |

凭据从进程环境或本课 `.env` 读取，环境变量优先。项目源文件只放后端、模型、音色等公开配置。任何生成包排除 `.env`。GLM、豆包、MiniMax属于外部语音服务，使用和收费按用户账户与供应商实际情况确定。

合成成功的段落会缓存；失败保留已有段落和课程源。付费请求失败后停止该项，不自动切换服务或音色。Edge 的服务可用性按运行环境确认；与同一合成无关的全局依赖和浏览器设置保持原样。

## 时间戳与成本

真实段长来自音频。Edge 保存 WordBoundary；豆包保存返回的 word 时间；MiniMax 在字幕返回可用时保存时间。没有词级时间时明确记录估算落点，避免把字符比例称作精确字级对齐。

本版程序没有语言模型调用。生成和改写物理内容仍使用模型 token；语音服务费用、本地渲染时间分别统计。缓存能减少重复合成，逐页缓存能减少修改后的重渲。

实现状态：Edge、MiniMax 已在本机实际跑通。GLM、豆包适配按公开源码和接口结构编写，仍需用用户选定账户实际试听和验证。ASR 自动听写尚未接入固定流水线；按课程需要可用本地听写检查片段。

2026-11-09 更新：MiniMax 已通过用户账户实际调用，25 秒温润男声试听已被用户接受。后续本系列采用 `speech-2.8-hd`、`Chinese (Mandarin)_Gentleman`；本课 `.env` 使用 `MINIMAX_API_HOST=https://api.minimax.cn`。电偶极层课程已取得全部 18 段音频和 1342 条词级时间数据。GLM、豆包仍保持未实测状态。

参考：[edulab共享TTS](https://github.com/wy51ai/edulab/blob/805fdc5dd6bdf942290a7791924bf0ee08f26632/skills/edu-math-video/shared/tts.py)、[GLM-TTS技术报告](https://arxiv.org/abs/2512.14291)、[MiniMax官方API控制台](https://solutions.minimax.cn/debug/speech)、[火山引擎官方示例](https://github.com/bytedance/agentkit-samples/blob/main/skills/byted-text-to-speech/scripts/text_to_speech.py)。
