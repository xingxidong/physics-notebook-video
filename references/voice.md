# 教师口播与配音

## edulab 的可取设计

它把正常板书/字幕与实际朗读文本分开，维护读音词表，用真实音频时长安排画面；共享语音模块接入 GLM、豆包、MiniMax，部分后端返回词级时间。新技能保留这些机制，并沿用用户已选择的逐笔笔记本风格。

真人感的参照分三层：文稿如何带学生思考、选用什么音色、句内和句间怎样停顿。分析具体视频时分别记录。仓库配置只证明代码使用什么后端；具体公众号视频的声音以视频或作者说明为准。

## 写法

一个 cue 对应一个完整思考或连贯句群。短判断可单独成段，较长推导按意思衔接，避免连续相同长度的段落。讲解复杂分式时分清分子、分母；第一次给出物理量名称，再引用图中的符号。单位、乘方和方向读完整。不要添加“嗯”“呃”等伪装思考的填充。文稿、音频空白与落笔节奏的具体安排见 [课堂表达与节奏](classroom-delivery.md)。

从具体对象说起，顺着图和运算讲。可以说“把重力分一下”“两边都有质量，约掉”；采用物理课堂中常用的说法，长短句按意思自然交替。问题用于引出确实需要学生判断的关系，例如“势能只含位置，对速度求导会剩下什么”。避免每段都以提问或“首先、接下来、最后”起头。

| 原来像在汇报教学流程的句子 | 直接讲物理的写法 |
|---|---|
| 整道推导都围绕这张图展开。 | 物块沿光滑斜面往下滑，先把重力和支持力画出来。 |
| 图中的受力方向、加速度和最后的速度关系，现在连成了一条线。 | 倾角固定，加速度就是常量。滑过的距离越长，速度越大。 |
| 再和运动学关系连接，就得到速度平方。 | 加速度恒定，把它代入这个速度和位移的关系。 |

板书保留式子的结构，声音解释这一步为何成立。遇到偏导，讲清固定哪个变量、哪一项留下；遇到负号，讲清它来自势能还是移项。成稿通读时逐句判断：删掉这一句，学生会少理解哪个对象、关系或运算。只保留有具体教学作用的句子。正文中的变量使用正常符号，TTS 的特殊读音单独处理。

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

## 三层课程源

新课由 `course.py init` 生成独立的 `speech-plan.json`。`lesson.json` 保存板书、图形与动作；讲义保存在 `讲义.md`；实际朗读和语调安排保存在语音计划。构建输出的 `prosody.json` 是解析角色默认值后的最终语调表。

```json
{
  "version":1,
  "defaults":{"role":"explain"},
  "cues":{
    "symmetry":{
      "role":"key_turn",
      "tts":"看这里。由对称性，交点的横坐标始终等于圆心距的一半。",
      "emphasis":["对称性","一半"],
      "pause_before":0.25,
      "pause_after":0.9
    }
  }
}
```

内置角色为 `read_problem`、`observe`、`model`、`derive`、`key_turn`、`conclusion`、`physical_meaning`、`transition` 和 `explain`。角色给出适合该教学动作的默认语速与停顿；cue 中的显式参数覆盖默认值。

v0.9 新课使用 `speech.delivery_profile:"classroom"` 与本地 `trim_edges:true`。旧课未选择时继续沿用既有角色参数。显式教学停顿用 `pause_reason` 记录，裁切后的词时间同步用于字幕与落笔。构建会在正式 TTS 前生成 `delivery-report.json`，也可单独运行 `scripts/delivery.py PROJECT`。

口播在语音计划中另存 `tts`，公式用 `latex`，原书面表达放在 lesson cue 的 `text`。试听关注多音字、数字、字母串、希腊字母、单位和分式。

### 物理术语和多音字

MiniMax 配音自动查物理术语词表。读音按整词配置，例如“相位”读 `xiang4 wei4`，“相长干涉”读 `xiang1 zhang3 gan1 she4`。原句仍用汉字。程序把匹配到的读音另传给 MiniMax 的 [`pronunciation_dict.tone`](https://platform.minimax.io/docs/api-reference/speech-t2a-http)，所以字幕、讲义和板书沿用原字。

课程级读音配置放在 `lesson.json` 或 `speech-plan.json` 的 `speech` 下。

```json
{"speech":{"backend":"minimax","minimax_pronunciation":{"载荷":"zai4 he4"}}}
```

单段读音配置可写在 `speech-plan.json` 对应 cue 的 `minimax_pronunciation`。优先级依次为内置、课程、单段，后者覆盖前者。每个汉字对应一个带声调数字的拼音，以空格分开，轻声用 `5`。词条值为 `null` 时交由合成器按原句处理，整份设置为 `false` 时清空该层继承的词表。遇到同一个词在两处读法不同时，把两处放在不同口播段，分别指定读音。

配音前运行 `python3 SKILL/scripts/delivery.py PROJECT`。在 `delivery-report.json` 的 `pronunciation.cues` 中可查看每段命中的拼音与建议试听的词。已配音项目可用 `timeline.json` 定位到具体段落，试听关键术语。GLM、豆包、Edge 或真人录音也可用报告找出试听位置。修正这类配音时按选用后端的读音能力处理，或者调整口语句子的上下文。

读音配置进入命中段落的音频缓存键。改词表后重新构建，读音配置没变的音频段复用缓存。配音返回的词序能对应原句时用词级时间。返回文本与原句不同的段落沿用原句并使用估算时间，画面与字幕仍使用汉字。实际声调以试听为准。

### 本地公式口语化

`tts_parts` 可以混合普通句子和 LaTeX：

```json
{"tts_parts":["因此，",{"latex":"E(r)=\\frac{Q}{4\\pi\\varepsilon_0r^2}"},"。"]}
```

程序支持当前板书 LaTeX 子集中的分式、根式、上下标、向量、时间导数和常用希腊字母。课程可在 `speech-plan.json` 的 `pronunciation` 中覆盖读法。单独试听某个公式：

```sh
python3 SKILL/scripts/oralize.py 'v^2=2gh'
```

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

MiniMax cue 支持 `speed`、`volume`、数值 `pitch`（半音）和该音色可用的 `emotion`；Edge 支持 `speed`、`volume` 与 `+NHz`/`-NHz` 形式的 `pitch`。整课优先靠角色、断句和停顿形成起伏，音高只做小范围调整。

## MiniMax 本人音色复刻

使用本人声音或已取得明确授权的声音。准备 MP3、M4A 或 WAV，时长 10 秒到 5 分钟，文件不超过 20 MB；30—60 秒安静、单人、无音乐和低混响的自然讲课录音通常更适合作为课程音色。先创建试听：

```sh
python3 SKILL/scripts/voice_clone.py teacher.wav \
  --project PROJECT \
  --voice-id PhysicsTeacher01 \
  --preview-text "看图，先把物体受到的力逐个画出来。" \
  --confirm-rights
```

成功后得到 `voice-clone-report.json`、可用时得到 `voice-clone-preview.mp3`。试听通过后直接应用已经创建的 ID，不重复调用复刻接口：

```sh
python3 SKILL/scripts/voice_clone.py --project PROJECT --apply-voice-id PhysicsTeacher01
```

课程的 MiniMax `voice` 会切换到该 `voice_id`，后续 TTS 请求持续复用这个 ID，无需重复上传音频。希望创建后立即写入课程时可在第一次命令加入 `--update-project`。降噪适合有稳定背景噪声的素材，干净录音保持关闭更能保留音色细节。

## 本地母带与质量报告

正式构建默认启用：

```json
{"speech":{"audio_mastering":{"target_lufs":-16,"true_peak_db":-1.5,"lra":7,"highpass_hz":65}}}
```

流程包含高通、轻压缩和响度统一，输出时通过补齐与裁切保持时间轴长度。设置 `"audio_mastering":false` 可保留原始合成声音。处理结果按音频内容和参数缓存。

每次正式构建生成 `voice-report.json`，记录电平、停顿、口语密度、词级时间覆盖率、文稿提示和术语审查。`terminology.items` 列出多音字和常用物理术语出现的段落、上下文、参考读音和视频时间。配音请求记录可用时，也列出实际传给 MiniMax 的拼音。词级时间与原句对齐时定位到词，其他情况提供整段时间。文稿命中明确的术语错字会另列为警告。

```sh
python3 SKILL/scripts/course.py voice-check PROJECT --strict
```

审查成片时，按报告定位“相位”“相乘”“感应电动势”等词，听实际声调和术语是否读完整。`pending_listening` 表示待试听。需要单听一段时运行 `python3 SKILL/scripts/course.py voice-check PROJECT --listen CUE_ID`，从本地配音裁取该段。用 `minimax_pronunciation` 修正读音或改正文稿后，再听新生成的对应段落。光学术语“散射”的参考读音可查[《重编国语辞典修订本》](https://dict.revised.moe.edu.tw/dictView.jsp?ID=144947&la=0&powerMode=0)。

## 时间戳与成本

真实段长来自音频。Edge 保存 WordBoundary；豆包保存返回的 word 时间；MiniMax 在字幕返回可用时保存时间。没有词级时间时明确记录估算落点，避免把字符比例称作精确字级对齐。

本版程序没有语言模型调用。生成和改写物理内容仍使用模型 token；语音服务费用、本地渲染时间分别统计。缓存能减少重复合成，逐页缓存能减少修改后的重渲。

实现状态：Edge、MiniMax 已在本机实际跑通。GLM、豆包适配按公开源码和接口结构编写，仍需用用户选定账户实际试听和验证。v0.4 已接入确定性的音频和文稿检查；ASR 回听仍作为后续可选质量门。

2026-11-09 更新：MiniMax 已通过用户账户实际调用，25 秒温润男声试听已被用户接受。后续本系列采用 `speech-2.8-hd`、`Chinese (Mandarin)_Gentleman`；本课 `.env` 使用 `MINIMAX_API_HOST=https://api.minimax.cn`。电偶极层课程已取得全部 18 段音频和 1342 条词级时间数据。GLM、豆包仍保持未实测状态。

参考：[edulab共享TTS](https://github.com/wy51ai/edulab/blob/805fdc5dd6bdf942290a7791924bf0ee08f26632/skills/edu-math-video/shared/tts.py)、[GLM-TTS技术报告](https://arxiv.org/abs/2512.14291)、[MiniMax官方API控制台](https://solutions.minimax.cn/debug/speech)、[火山引擎官方示例](https://github.com/bytedance/agentkit-samples/blob/main/skills/byted-text-to-speech/scripts/text_to_speech.py)。
