# 固定试音、课堂读音卡与反馈库

16 句是每次换模型、换音色都使用的基础材料。扩展材料从随技能携带的课堂读音卡、历史反馈和本课完整讲稿选取。三种来源都有候选时，先各选一句，再按历史错误风险补齐本轮额度。`--rotation` 轮换词卡例句。所有选入句都读取当前词卡的读音、词义和连读提示，同一句重复出现的词分别列位置。

试音负责判断当前配音配置在这些句子上的表现。本课仍需逐句盘点物理术语，并从最终 MP4 检查每个术语和字母的每次出现。16 句全部通过，也只说明听过的这些录音通过。

## 生成材料

备课运行 `course.py feedback-check PROJECT` 时，会同时生成 `PROJECT/voice-trial-plan.json`。也可单独生成：

```sh
python3 SKILL/scripts/voice_trials.py plan --project /ABS/PROJECT --output /ABS/OUT/plan.json --max-extra 16 --rotation 0
python3 SKILL/scripts/voice_trials.py run --plan /ABS/OUT/plan.json --config /ABS/VOICE.json --output /ABS/OUT/trial
```

不传 `--project` 时可用于新安装或换音色。默认保留 16 句固定材料，额外选 16 句；`--max-extra 0` 只录基础材料。`coverage` 列出已选来源、预算内未选入的句子、缺例句的词卡和本课尚未完成人工语义盘点的句子。未选入、缺材料、没听过的项目保持待查。

新课中的生词先写进 `term-inventory.json`，给出完整原句和按词义确定的读法，再生成试音材料。词卡只有拼音、没有例句时，补一句自然课堂用语；材料生成器不虚构已听过的声音。课堂参考课提炼的词卡使用原有 `classroom_terms.py --compile` 编译入口，之后的试音计划自动读取更新。

## 逐处审听与写回

`run` 输出 `listen.html`、`scorecard.csv`、`listening-template.json` 和 `trial-results.json`。每处术语与字母分别检查 `pronunciation`（读音）和 `flow`（连读）；每句另查 `continuity`（重复、卡壳、杂音及衔接）和 `delivery`（语速与讲课口吻）。字母在完整中文句中听，保留实际字母名及公式读法。

制作者实际听完后，复制 `listening-template.json`，填写 `reviewer`、`basis`、`evidence`，把听过位置的 `status` 改为 `ok`、`wrong` 或 `unsure`。没听的留 `pending`；错处在 `note` 记录实际现象。机器转写只能提供线索，不能填作实听依据。

```sh
python3 SKILL/scripts/voice_trials.py review /ABS/OUT/trial --judgments /ABS/OUT/listening.json
python3 SKILL/scripts/voice_trials.py status /ABS/OUT/trial
```

检查结果存入技能 `assets/learning/feedback.sqlite3` 的 `voice_trial_reviews`，实听音段按内容哈希保存在旁边的 `samples/`。错误同时写回多音词、字母或连读反馈库，下一次选材会带上完整原句。成功记录保留当前模型配置、词卡版本、实际输入和音频的指纹，不修改词典读法；要订正词卡，用原有 `record-term` 明确填写确认过的词义和读法。

换模型、音色参考、语速、采样参数或配音输入后重新试录。词卡和反馈变更会让涉及的旧句进入 `stale`，不影响无关句。原文件被替换、讲稿被改动，也会要求重查。可用 `--ids` 只补受影响的整句。更新安装和打包会合并这张审听记录表及音段；删除原课程目录后，随行包仍保留这些材料。

## 配音配置与参考声音

先读 sentences.json 的完整句和逐处目标，再听实际音频。16 句包括同字异读、整词连读、26 个字母中历史高风险项、大小写、上下标和相邻句接点。两句中相同词各有自己的位置。

`audio/` 为 Kokoro 固定公开合成音色的比较样本，没有教师真人录音。它们帮助判断音色和运行流程，**不能把其中读法自动认定为正确答案**；目标以文字读音、词义和实际审听为准。用户确认的教师音色另外在本机配置，不随公开样例发布。

```sh
python3 SKILL/scripts/voice_trials.py run --config local-qwen.json --output /ABS/OUT/qwen
python3 SKILL/scripts/voice_trials.py run --config external-minimax.json --output /ABS/OUT/minimax
python3 SKILL/scripts/voice_trials.py run --config recordings.json --output /ABS/OUT/recordings
python3 SKILL/scripts/voice_trials.py compare /ABS/OUT/qwen /ABS/OUT/recordings --output /ABS/OUT/comparison.html
```

本地试音配置直接使用安装器下载的模型。外部接口从环境变量或输出目录 `.env` 读密钥，明确选它才调用并计费。已有录音按句子 ID 命名 WAV/MP3。其他合成接口也可将完整句录音按这个命名交给 `recordings.json`，再走同一审听流程。可加 `--ids mixed-q subscript` 只试两句，再录全组。新音色第一轮听开头、含字母推导、结尾。正式记录用上面的 review 命令导入。

每次输出保留原稿、实际请求输入、词的位置、带调拼音、模型/音色签名和真实音频哈希。`external-request.example.json` 是离线构造的请求示例；没有虚构云端返回结果，也不会自动花余额跑验证。

已实际运行的两句可打开[本地 Qwen 与已有录音对照](comparison.html)。完整请求与结果分别在 `measured-local/trial-results.json` 和 `measured-recordings/trial-results.json`。这轮 Qwen 用 `public-reference.wav` 的公开合成音色作参照。参考文字和来源见 `public-reference.json`。需用自己的音色时，换掉配置里的参考录音路径和对应文字。相对参考路径由试音工具按配置文件所在目录解析。

`join-a` 和 `join-b` 除了单独听，还应按实际制课接法连续听。只记录本次实际听到的内容。换模型、音色参考、读音策略或采样参数后，用相同句子再比较，旧模型的通过记录不转给新模型。
