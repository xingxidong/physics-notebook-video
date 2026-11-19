# 看课反馈

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

一般问题可加 `--scope concept` 或 `--scope problem` 指定课型，默认两类通用。匹配口播里的具体措辞可加 `--match '实际原句'`。多音词的 `--expected` 每字用一个带调号的拼音；新词只确定有问题时可以先留空。单个汉字可记为待听；自动读音绑定完整词，如“相位”和“相干”各自有对应读法。课程对本地同音提示有改写时，检查会列出差异供复听。字母的标准读法从现有字母表取，x 和 X 共用记录。课程、位置和内容完全相同的重复提交只计一次，另一节课再次发生会保留为新记录。

个人记录保存在 `~/.local/share/physics-notebook-video/feedback.sqlite3`；设置了 `XDG_DATA_HOME` 时使用该数据目录。同一个系统用户下不同宿主、项目和技能更新共用记录。通过 `PHYSICS_NOTEBOOK_FEEDBACK_DB` 可以指定共享文件或隔离测试库。安装包只带三份整理好的案例。公开分享新案例时，单独整理通用条目。

## 每节课怎样查

1. 备课时从 `feedback-check.json` 读取适用检查项、命中句段及预期读法。把本课容易重犯的点落实到实际教案、板书或分镜。习题课拿原题逐小问对照，新授课逐条看规律落笔。完整题面和接触动画需与原件、画面比对。
2. 教案、预览、构建和单独渲染都会重新读库。正式制作中，已知词的读音配置与标准冲突、已选配音带有原片降速记录时，命令指出页和句并在合成前退出。镜头或页标题设置作为定位线索。其余适用项目在报告中列为待看、待听。使用独立制作脚本时也先执行 feedback-check。
3. 用 `course.py voice-check PROJECT --term-reel` 从本课正式音轨取样。用户反馈过的字母和词按命中句段进入试听合辑；用 `--listen CUE_ID --context` 听前后句。把实际试听或观看的结论及位置记进本课制作记录。出现旧问题时只修受影响段落，重新导出并复听。交付时如实说明仍待查看的项目。
