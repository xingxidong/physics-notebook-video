# 看课反馈

读[跨课复试与课堂实例](classroom-transfer.md)，查看怎样把一个旧问题落实到新课的每一处，以及怎样把新发现带去下节课。

用户看课后说“这个字念错了”“这里穿模了”时，先保存具体反馈。一次指出几个独立问题，就分别登记。课程、页或秒数能从上下文确定时直接补上。用 `feedback_bank.py list` 找相同问题的 key。分不清错音时照实登记听感，确定后再补读法。

| 库 | 随技能安装的案例 | 新反馈如何用于下一课 |
|---|---|---|
| 视频问题 | [issues.json](../assets/feedback/issues.json) | 按习题课、新授课或全部课程选择检查项。有明确原句时可指定 --match，定位本课讲稿。 |
| 多音字错读 | [polyphones.json](../assets/feedback/polyphones.json) | 以完整词匹配口播，保留标准书面词。确认的拼音进入发音词典，有同音提示时用于本地配音输入。 |
| 字母错读 | [letters.json](../assets/feedback/letters.json) | 从实际口播定位变量，依据字母名记录目标音；保留板书、字幕中的字母。 |

以下命令由正在制课的助手执行。课名和位置填写实际反馈；用户仅提出偏好时，在记录中如实表述。

```sh
python3 SKILL/scripts/feedback_bank.py record issues --key intersection --observed '接触时物块陷进了斜面' --expected '看接触前后轮廓和斜面的相对位置' --lesson '斜面运动' --at '第 2 页'
python3 SKILL/scripts/feedback_bank.py record polyphones --key 长度 --observed '长读成了 zhǎng' --expected 'chang2 du4' --hint 常度
python3 SKILL/scripts/feedback_bank.py record letters --key x --observed '公式里的 x 听起来含混' --at '读下标前'
python3 SKILL/scripts/feedback_bank.py history
python3 SKILL/scripts/course.py feedback-check PROJECT
```

一般问题可加 `--scope concept` 或 `--scope problem` 指定课型，默认两类通用。匹配口播里的具体措辞可加 `--match '实际原句'`。多音词的 `--expected` 每字用一个带调号的拼音；新词只确定有问题时可以先留空。反馈具体指出词中哪个字时，在 record 命令加 `--focus 字`。以后该字出现在未收录词中也会进入课堂复听清单。单个汉字可记为待听；自动读音绑定完整词，如“相位”和“相干”各自有对应读法。课程对本地同音提示有改写时，检查会列出差异供复听。字母的标准读法从现有字母表取，x 和 X 共用记录。课程、位置和内容完全相同的重复提交只计一次，另一节课再次发生会保留为新记录。

学习记录在技能目录的 `assets/learning/feedback.sqlite3`，用于比较和确认的短样放在同目录的 `samples/`，按内容去重。读音卡在 `assets/classroom-cards.json`，课堂笔记在 `references/`。安装包一起带走这些内容。使用原有安装器的 --update 会合并学习记录。要从 0.25 或更早版本迁入，可运行 `python3 scripts/feedback_bank.py import-learning "$HOME/.local/share/physics-notebook-video/feedback.sqlite3"`。设置过 PHYSICS_NOTEBOOK_FEEDBACK_DB 的用户传入自己使用的旧库路径。这个环境变量也可用于隔离测试。

## 每节课怎样查

1. 备课时从 `feedback-check.json` 读取适用检查项、命中句段及预期读法。把本课容易重犯的点落实到实际教案、板书或分镜。习题课拿原题逐小问对照，新授课逐条看规律落笔。完整题面和接触动画需与原件、画面比对。
2. 教案、预览、构建和单独渲染都会重新读库。正式制作中，已知词的读音配置与标准冲突、已选配音带有原片降速记录时，命令指出页和句并在合成前退出。镜头或页标题设置作为定位线索。其余适用项目在报告中列为待看、待听。使用独立制作脚本时也先执行 feedback-check。
3. 用 `course.py voice-check PROJECT --term-reel` 从本课正式音轨取样。用户反馈过的字母和词按命中句段进入试听合辑；用 `--listen CUE_ID --context` 听前后句。把实际试听或观看的结论及位置记进本课制作记录。出现旧问题时只修受影响段落，重新导出并复听。交付时如实说明仍待查看的项目。

## 作者意见怎样影响后来的一课

反馈写成“原话、适用范围、下一课可观察的动作”。作者要求同类文章课至少三十分钟时，按下例保存个人偏好。所有用户共用的案例保留教学方法；同类文章课的时长要求随学习库保存；新课依照本次明确要求和文章课设定安排内容。

```sh
python3 SKILL/scripts/feedback_bank.py record issues --key article-minimum --source-type article --minimum-minutes 30 --observed '文章课至少讲30分钟，不要通过拖慢语速拉长时间' --expected '按原速增加前置知识、连贯推导、读图及应用；用实际交付视频复测。'
```

在本课的制作记录里关联对应的记录键、页、句和实录时间，写清做过的修改、验证方式、作者反馈。新一条相同意见表明这项仍需处理。软件听写、换了提示词和发音检查清单都属于过程证据；确认个人听感时记录作者听过的具体样句。反馈后的同音提示只用于合成输入，字幕和板书照用标准字。

物理术语“分量”指矢量的分量时读 fēn liàng，两个音节分别一声和四声。日常轻重、份量的说法另按原句处理。“两个分量”这类短语要结合前一句确定义项。字母 k 读 /keɪ/，m 读 /ɛm/，后者单音节闭唇收鼻音。先让当前音色分别读变量、变量和相邻汉字连读、m 与 g 连读三种句子。记录听感不佳的替写（如“开”“艾姆”），比较原字母、英文名称或引擎支持的音素输入。长度单位 m 照单位读。可请作者在少量完整样句中选音。

## 从一次反馈到下一节课

收到纠正，先查 `feedback_bank.py list` 找已有的词或问题编号。把“原句和发生位置”记入 `record`。已确认的完整词读音、长期时长要求沿用前面的登记方式。某一版的口播写法、某一音色的试读和单课改动，记入 `decide`。同一问题随后的选择继续用原编号。相同决定的重试只保存一次；改变主意时追加判断，`reviews` 可回看原先的选择与证据。

1. **从反馈里留下下次能用的做法。** 课名和位置说明错误发生在哪里。术语错音、吞字、接句和落笔不同步会在别课重现，默认按同类内容检查。登记时用 `--takeaway` 写清下次怎么听、看哪一步。遇到某题特有的图号、数值或正方向，原处的修订用 `record --only-this-lesson --lesson '课程标题'`，后续选择用 `--scope lesson --lesson '课程标题'`，与课程源的 `title` 对应。长期适用于新授课或习题课的要求分别用 `concept`、`problem`，两类都适用才用 `all`。文章课时长仍按原有 `--source-type article` 登记。
2. **在短样上比较。** 语言和配音选同一句完整课堂话，保留字母两侧汉字。画面问题取口播开始的那一帧，运动问题连看关键动作前后。两段原始音频可用 `feedback_bank.py compare-audio 原句.wav 改后.wav --output AB.wav` 原速拼成同一条试听，顺序为 A、B。记录原来怎样、改后怎样、作者实际听过或看过什么。有明确的长期要求可直接采用。由单次问题推测出的通用办法先记 `trial`，另取一段新课材料试用，确认适用范围后记 `adopted`。改法失效或作者收回选择时记 `withdrawn`，保留缘由。
3. **换课再试。** `course.py feedback-check PROJECT` 生成的 `replay` 按本课命中的页和句给出待办。图像类经验也可适用于整课，逐帧查看相应板书。`compare` 表示仍在试用，`apply_and_check` 表示已有依据、要在本次成品复查。用 `course.py voice-check PROJECT --listen CUE_ID --context` 定位试听。原课一条样句通过后，下一课仍要听新句中和前后汉字的衔接。将新的试听结果写进依据；自动匹配和转写仅用于定位。

例如，学生听到“看这条虚线”时，要能在此刻的画面上找到对应的线。以下命令展示怎样保存一次已经实际做过的对照，使用时填入本课真实的前后效果和依据。

```sh
python3 SKILL/scripts/feedback_bank.py decide issues --key visible-referent --state trial --scope all --before '看这条虚线' --action '先画好虚线，再点明它连接的两个点' --example '看连接 O、P 两点的虚线' --evidence '首次提及的那一帧还只有实线'
python3 SKILL/scripts/feedback_bank.py reviews
```

**教师选中的音色样本**。在原句中比较 A、B，将选中的本地音频文件作为 `--sample`，用 `--before` 记另一种读法或被否决的版本。记录实际模型 ID 与参考录音的 SHA256。模型、参考录音和样本内容三者均能对应时，制作前报告才给出可试听的本地文件。个人录音和修订历史留在制作者电脑上。

```sh
python3 SKILL/scripts/feedback_bank.py decide letters --key W --state adopted --scope all --model "$TTS_MODEL" --reference-sha256 "$VOICE_SHA256" --sample "$ACCEPTED_WAV" --before 'B 的末尾被拆开' --action 'W 使用选定的 A 版读法' --example '记作 W' --evidence '作者带前后句试听后选 A'
```

制课时根据本次实际配音配置，在 `lesson.json` 或 `speech-plan.json` 的 `speech.feedback_voice` 写入 `model` 和 `reference_sha256`。更换模型、参考音色，或制作时尚未选音，命中这个字母的课程会提示 `audition_voice`。如果已选样本丢失或内容改变，报告标记 `restore_or_audition`。这两种情况都需短句重听。录音文件可移到新的本地位置，重新登记已确认的文件即可。

设计参考了三个开源实现。合并相近纠正、保留修订历史和用真实样例比较前后输出分别借鉴了 [AutoSkill](https://github.com/ECNU-ICALK/AutoSkill)、[self-improving-agent](https://github.com/pskoett/self-improving-agent) 和 [Anthropic skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)。
# 学习包的更新与迁移（0.27）

0.27.2 将试音结果也放进同一随行包：`voice_trial_reviews` 保存每句的逐处读音和连读判断、模型配置指纹、词卡与录音指纹，`samples/` 保存所听的实际短音段。`voice_trials.py review` 只接收有审听者和依据的人工听音记录，错处同步进入原有反馈库。下一轮试音读取这些完整课堂错例。安装合并按记录指纹去重，包检查同时核对短音段，原课程删除后仍能使用。

学习包包含 `assets/classroom-cards.json`、`references/` 中的课堂笔记和词表、`assets/learning/` 中的反馈数据库及已登记片段。安装时合并，打包时收回已安装技能中新增的内容。音色选择带着具体模型和参考音色的依据，换音色后重新试音。

课堂笔记按版本指纹合并：只有一处改动就保留改动；两边独立修改时保留两份，并写入 `assets/learning/reference-conflicts.json`。制作者对照原条目与 incoming_file，合并正确内容后填写该记录的 status 为 resolved、reviewer 和 resolution，再编译读音卡。待合并记录会阻止正式配音。打包时旧安装版本不会覆盖较新的已发布笔记。

0.27 将旧库中 13 条只记录原课、缺少通用经验的反馈，另提炼为适用于后续课程的记录，保留原始依据。迁移对应表位于 `assets/learning/history-migrations.json`。后续反馈同样保存原话与下一课怎样检查；原题数值和时间点用于定位，读音、连读、教学和同步经验按场景复用。

