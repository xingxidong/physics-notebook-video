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
| mg | 先解释为重力；读式时读 m 乘 g |
| mg sinθ | 先解释为重力沿斜面的分量；读式时读 m 乘 g，乘 θ 的正弦 |
| ε₀ | 真空介电常数 ε 下标零 |
| Q_in | 高斯面包住的净电荷，记作 Q 下标 in |
| dS | 面积微元 d S；两个字母连续读出 |
| v₀²/(2a) | v 下标零的平方，除以二倍 a；结合上下文解释初速度与加速度 |
| 10 m/s | 十米每秒 |
| 2 m/s² | 二米每二次方秒 |

量名解释与符号朗读各有作用。关键推导在板书出现时读出实际变量、运算及上下标，随后解释这一步的物理意义。对照每条关键式检查口播中的字母，不能整课只用中文量名代替板书符号。字母使用英语字母名，与两侧汉语一起合成完整句；单位按单位名称读。修改读音后同时查整词与整句连续性，配音头尾的碰声、残音和内部断裂分别定位。用户实听指出的错误保留为待修，自动识音的支持结果不能将其覆盖为通过。

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

### 变量、字母和单位

板书写“横坐标记作 x”，声音里的 x 读英语字母名 /ɛks/。大小写保留在课文和字幕中。变量、由多个点命名的几何对象、下标和单位先分清，再用带上下文的真实课文试听。

`delivery-report.json` 的 `pronunciation.cues` 列出待试听的字母和术语。成片的 `voice-report.json` 按句给出对应时间。重点回听字母首次出现、推导中连续出现的变量和曾经读错的字母。单个字母或中文词听着正常后，再听整句的连读与停顿。

## 读音卡、目标音色与成片复核

**常见词汇读音卡。** 在 `assets/pronunciation-cards/classroom-cards.json` 查术语义项、拼音、连读和同字异读。用 `term-inventory.json` 把读法落到本课每一个出现位置，包括题目、读图、公式讲解和总结。

**目标音色包的课堂读法。** 从 `assets/target-voice/reading-practice.json` 选本课用得上的字母、函数、数学表达式和物理公式例句。每条保留课名、板书式、整句口播和停连提示。参考课学习只登记文字读法，按原声或板书等实际依据说明来源。正式制作新课时，用本课讲稿确定每个符号和整个公式怎么读。

新课 `speech_review_version:1` 使用 `voice_trials.py run --project PROJECT --config VOICE.json --output PROJECT/voice-trial`，按需用 `--ids` 选句，至少录一段本课原句。用 `review` 登记实际听过的判断，试音通过后开始整课合成。构建逐段比对实际使用的音色和模型。Qwen 另比对真实参考录音的指纹。课内的读音卡与公式读法同时进入配音和复查清单。

终审使用交付版 MP4。对着板书逐条听公式，查实际字母、下标、函数、负号、幂、分子分母及运算顺序，检查落笔时间。按本句应出现的位置核对字母次数，有意在两个位置写出的同一字母分别核对。读音和重复都登记；读法或次数有疑点时，用同一音色连续复录整段，再从新版 MP4 复听前后句。自动识音保留其依据，尚未实际审听的项目继续待审。

### 物理术语和多音字

配音前用同一份物理术语词表检查整词读法。例如“相位”读 `xiang4 wei4`，“相长干涉”读 `xiang1 zhang3 gan1 she4`。检查报告按句提供原稿、朗读文本和命中的带调拼音。

选用 MiniMax 时，适配器把词级读音写入 [`pronunciation_dict.tone`](https://platform.minimax.io/docs/api-reference/speech-t2a-http)。本地模型从 `tts_inputs` 取朗读文本和读音目标，纯文本模型可使用已确认的同音提示。GLM、豆包和 Edge 的现有适配会发送口播文本，带调拼音可用于审稿和试听核对。自定义接口可从同一份报告读取 `script` 和 `pinyin`，按所选引擎的输入格式处理。

课程级读音配置放在 `lesson.json` 或 `speech-plan.json` 的 `speech` 下。

```json
{"speech":{"backend":"minimax","minimax_pronunciation":{"载荷":"zai4 he4"}}}
```

单段读音配置可写在 `speech-plan.json` 对应 cue 的 `minimax_pronunciation`。优先级依次为内置、课程、单段，后者覆盖前者。每个汉字对应一个带声调数字的拼音，以空格分开，轻声用 `5`。词条值为 `null` 时交由合成器按原句处理，整份设置为 `false` 时清空该层继承的词表。遇到同一个词在两处读法不同时，把两处放在不同口播段，分别指定读音。

配音前运行 `python3 SKILL/scripts/delivery.py PROJECT`。在 `delivery-report.json` 的 `pronunciation.cues` 中可查看每段命中的拼音与建议试听的词。已配音项目可用 `timeline.json` 定位到具体段落，试听关键术语。改读音时按所选模型的输入能力调整音节、同音提示或口语句子的上下文。

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

审查成片时，按报告定位“长度”“伸长”“相位”“相乘”“感应电动势”等词，听实际声调和术语是否读完整。按词和上下文分别核对“长度”的 cháng、“相位”的 xiàng 和“相乘”的 xiāng。词表之外出现的新术语，也要回听首次出现与关键结论，确认稳定后才加入共用词表。`pending_listening` 表示待试听。运行 `python3 SKILL/scripts/course.py voice-check PROJECT --listen CUE_ID --context` 可裁取本段和相邻句。修正词表或口播后，重合成并回听这些片段。光学术语“散射”的参考读音可查[《重编国语辞典修订本》](https://dict.revised.moe.edu.tw/dictView.jsp?ID=144947&la=0&powerMode=0)。

## 时间戳与成本

真实段长来自音频。Edge 保存 WordBoundary；豆包保存返回的 word 时间；MiniMax 在字幕返回可用时保存时间。没有词级时间时明确记录估算落点，避免把字符比例称作精确字级对齐。

本版程序没有语言模型调用。生成和改写物理内容仍使用模型 token；语音服务费用、本地渲染时间分别统计。缓存能减少重复合成，逐页缓存能减少修改后的重渲。

实现状态：Edge、MiniMax 已在本机实际跑通。GLM、豆包适配按公开源码和接口结构编写，仍需用用户选定账户实际试听和验证。v0.4 已接入确定性的音频和文稿检查；ASR 回听仍作为后续可选质量门。

2026-11-09 更新：MiniMax 已通过用户账户实际调用，25 秒温润男声试听已被用户接受。后续本系列采用 `speech-2.8-hd`、`Chinese (Mandarin)_Gentleman`；本课 `.env` 使用 `MINIMAX_API_HOST=https://api.minimax.cn`。电偶极层课程已取得全部 18 段音频和 1342 条词级时间数据。GLM、豆包仍保持未实测状态。

参考：[edulab共享TTS](https://github.com/wy51ai/edulab/blob/805fdc5dd6bdf942290a7791924bf0ee08f26632/skills/edu-math-video/shared/tts.py)、[GLM-TTS技术报告](https://arxiv.org/abs/2512.14291)、[MiniMax官方API控制台](https://solutions.minimax.cn/debug/speech)、[火山引擎官方示例](https://github.com/bytedance/agentkit-samples/blob/main/skills/byted-text-to-speech/scripts/text_to_speech.py)。

## 变量和物理术语怎样发音

“用 x 表示压缩量”有两件事要讲给学生。先读出字母 x，再告诉学生它对应哪段长度。公式里的 x、y、F、m 都按字母名念；下标和平方另读。课文中写“力”“半径”“质量”就照原文念。“线段 AB”“三角形 ABC”会按点名逐个读出字母。组合单位宜在口播中写全，例如“米每秒”。函数名与英文单词保留完整。

技能在中英文混合口播里用英文 `ex` 提示 x 的字母音 /ɛks/。y 的目标音为 /waɪ/。英文字母保留英语字母名，X 的元音与 /ks/ 连续发出。旧版中用量名替代字母的配置在重新编译时自动恢复为字母名。字幕和板书保留源字符。

中文按完整术语选音。例如“长度”的长读 cháng，“增长”的长读 zhǎng，“相位”的相读 xiàng，“相乘”的相读 xiāng。MiniMax 按词接收带声调的拼音。本地音色走 `user` 后端时，先运行 `python3 SKILL/scripts/delivery.py PROJECT`，从 `delivery-report.json` 的 `tts_inputs` 取每句。内含可直接用于合成的 `text`，以及字母目标音 `letters` 和词级拼音 `pinyin`。只接受纯文本的本地引擎会在输入中看到“常度”“向位”等同音提示。支持原文与发音标注分离的后端可取 `script` 和对应标注。配音专用写法留在音频输入层，教案、字幕与板书显示原文。若某个本地音色还会错读其他词，在 `speech.plain_pronunciation` 保存试听过的同音提示，例如 `{"重合":"崇合"}`。该音色的跨课默认词表可保存在本机 `runtime-local.json` 的 `speech_defaults.user.plain_pronunciation`，新建本地配音课时会自动载入。句段同名字段可覆盖词条，值设为 `null` 可在该句恢复原词。

试听时连听“令 x 表示弹簧的压缩量”“把 x 的平方代进去”“长度增长了多少”“两列波的相位相同”。用 `course.py voice-check PROJECT --term-reel` 从当前音轨截取实测片段，按索引复听对应原句。发现字母混读或声调读错，修正输入后重新合成并回听该句所在的配音组。

拼接独立录音先测前段末尾和下段开头各自已有的安静时间。句子需要换气时只补实际欠缺的间隔；词内连续发音。接点采用短渐变，对夹在两段安静区之间的孤立响声单独处理。以最终导出的音轨连听接点两侧的原句。

字母与汉语衔接断裂时，往前后找到共同讲完一个意思的几句，用同一音色一次重录完整语段。把字母及其前后汉字放在这个语段里连续读，听起音、韵尾和语气。选中后只在语段的外侧合入。遇到新的个人读法偏好，才请作者在一组短样中选择。将选定的原声存入个人音色目录，记录音色模型、参考音频校验值和片段校验值，下次从 feedback-check.json 读取。

## 续做已经试听过的本地音色

先从作者认可的成片或其配音记录找回模型版本、参考录音、参考文字和合成参数。用本课实际推导录一段连续口播，保留前后句，听整段的说话节奏，再听字母和多音词。作者要求先听样片时，把样片作为续做依据，并记录对应的模型和实际音轨。

作者反馈卡顿、重复或回音时，对照成片、未拼接录音和接点两侧。重复出现在一条原始录音里，就重录这一完整意思，并检查讲稿本身的重复表述。问题集中于接点时，按实际换气和原始词尾重做接合。转写能定位漏读、念重和错词，安静区与波形对比能提供接点证据。音色和自然度以完整句试听为准。把实际反馈与候选版本存入问题库。

试听音色时记下对应的音频。检查最终成片时，从报题开始连续听到第一段推导，把片头切换和第一处章节接句一起听完。作者指出结巴或复读时，保留成片问题位置，用同一音色按语段重录开头。把试听确认的完整语段合回整课后，从实际 MP4 提取开头核对，再校正字幕和笔迹。

试听通过后，把本地权重版本、参考音频指纹和克隆方式一起写入本课的配音记录。仅提取说话人音色与同时使用参考录音及其转写，是两套输入。独立缓存每套音频。切换到批量合成前，检查每条输入确实带有试听时的说话人向量，再用课程原句复查实际成片。音色通过后可以直接复用试听句的原音。软件比对可发现混入别的录音或音轨时间中断，语句是否流畅、英文字母是否连读仍以实际试听为准。

边合成边播放时听到断续，记下视频、时间点和当时运行的任务。等合成与渲染结束后，在同一时间点比较成片和由这段成片提取的 PCM 音频。结合音轨时间戳和系统资源记录定位问题，再决定是否需要复录。同样的情况只在播放器复现时，继续比较播放器的解码和系统负载。

## 常用词读音审查

课前可以检查一整课，也可以在写讲稿时查一句。

```sh
python3 SKILL/scripts/course.py pronunciation-check --project PROJECT
python3 SKILL/scripts/course.py pronunciation-check --text '应该先处理数据，再看此处的响应。'
```

每条记录给出词在本句的起点、词里的多音字和带调拼音。“处理／此处”的处读 chǔ／chù，“还原／还有”的还读 huán／hái，“奇数／奇特”的奇读 jī／qí。词典暂时无法确定的字标为“按句意定音”。课程和句子配置里的较长短语也按其中的固定词检查，发现冲突时根据提示修正本句配置。

备课报告 `tone_targets[].characters` 保存每个字的原句位置和目标音。复听实际 MP4 后，`final-tone-review.json` 的 `character_results` 记录听到的拼音、目标音及二者是否一致。目标音来自讲稿和词表，实听结果来自此份成片的审听登记。

## 成片声调复听

“测量速度”读 cè liáng，“这个物理量”读 wù lǐ liàng。“测量的量”在同一句内从二声变为四声。以本课物理意思确定长词和短语。遇到单独的“量”，先看它在句子里做什么。未确定的用法会列入待听清单。数学词同样按词义处理，例如“数清”读 shǔ qīng，“数值”读 shù zhí，“行列式”读 háng liè shì。

本地纯文本模型取 `local_tts_text(text, matched_pronunciations(text))` 的结果。初录和整段补录共用这一步。在配音输入中用“测梁”“从地心梁起”提示二声，“测梁的亮”区分相邻的两个读法。字幕与笔迹仍以原稿为准。缓存同时核对本次要送入的文字和录音时的实际输入；重新生成录音时，重新做转写和时间对齐。能指定音素的引擎优先用标准词和带调拼音。

1. 运行 `course.py feedback-check PROJECT`，看 `tone_targets` 中的原句、位置、预期读法。学科词、个人反馈词，以及已知易错字在陌生语境中的每次出现分别定位。“倒数”这样的词结合本句是求倒数还是倒着数来判断。用 `pronunciation_trial` 先试录本课至多六句，其余位置在成片继续听。
2. 渲染后运行 `course.py quality-check PROJECT --stage final`。从 `final-tone-review.json` 取一处 `id`，用下面的命令导出该处连前后文的原速声音。自定义工程可用 `--timeline FILE` 指定含 pages/cues 或逐笔板书 pages/beats 的实际时间轴。
   同一句有多个目标时，以其中任一位置运行 `--id ID --cue-clip`，一次听完整句；报告的 `cue_items` 按原文顺序列出全部位置。
3. 制作者实际听音后登记听到的逐字带调拼音。读音随语境而定的词另填 `--intended`。听不清时保持待听，确认读错则重录包含该处的完整语段。独立脚本可以复用 `tone_review.inspect`，按 `remaining` 检查。登记以成片指纹、时间窗、原句和目标词为依据。换音轨或重导成片后重新听。

```sh
python3 SKILL/scripts/tone_review.py PROJECT --video-file video.mp4
python3 SKILL/scripts/tone_review.py PROJECT --video-file video.mp4 --id ID --clip
python3 SKILL/scripts/tone_review.py PROJECT --video-file video.mp4 --id ID --heard 'ce4 liang2'
```

同句多项可用 `--id ID --hearings-file 逐处实听.json` 一次登记已听的部分。JSON 以该句的实际位置编号为键，值含 `heard`；词义待定的项同时填 `intended`。听到的字音与目标不符会进入重录，未填的继续待听。

制作者从 `producer_queue` 取段。已经听出有错的段排在前面；每组用 `listen_id` 和 `--cue-clip` 取原速整段，按 `items` 记录各处结果。转写漏掉字母或把字母旁的音节带进来时，核对该词起止，再看整句转写与邻字，另与同音色已认可的原句比较。公式段同时在画面上定位正在念的符号。自动结果与实听记录分别保留。交付反馈只向作者报告结果；尚有技术疑点由制作者跟进，只有新的偏好需要作者选择。

转写出的“测量”无法区分 liáng 和 liàng。当时间轴有逐字时间时，用同一条命令的 `--id ID --pitch` 读取所选成片中的音节基频。该可选检查使用 librosa 与 NumPy；字级时间不足时会注明，音高数据单独保存在报告中。问句语调、相邻音节和变调也影响音高，听感不明确时可换成等义的课堂说法，再录完相邻语段一起听。
# 本地 Qwen 配音

`--backend qwen` 调用本机 MLX Qwen 环境。[安装器](platform-install.md#随技能安装本地配音)为支持的 Apple Silicon Mac 下载运行环境和固定版本的模型。也可用自己的现有环境，在技能目录的 `runtime-local.json` 设置 `qwen.python`、`qwen.model`。新装可直接用随包合成样音试讲。

换成自己的音色时，同时填 `qwen.reference_audio` 和 `qwen.reference_text`。参考录音为 24 kHz 单声道 PCM16 WAV，文字和录音逐字对应。模板见 [local-qwen.json](../assets/starter-kit/voice-trial/local-qwen.json)。已有自选环境和音色会覆盖默认值，参考材料在本机读取。

接口使用原速 1，按当前读音卡构造配音文字。缓存记录运行库版本、模型文件信息、工作脚本、参考音频指纹和实际输入，并核对返回音频哈希。改变音色参考或配音输入后生成新音频。依赖缺失时说明原因，不切换云端。

当前适配器没有可信的逐字时间戳，words 返回空值；自动词锚点是估计位置，须对着实际录音逐步审看推导，或接入真实对齐结果。成功返回 WAV 与课堂读音已正确是两项不同检查。

[固定试音句与三份配置](../assets/starter-kit/voice-trial/README.md)可用于本地 Qwen、MiniMax 和已有录音。外部请求示例标注为离线模板，只有明确选择外部接口才调用。

