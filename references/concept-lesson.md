# 新授课

使用 `kind:"concept"`。从教材、章节目标或用户点名的物理概念出发，先确定学生学完后应能复述什么、能解释哪种现象、能在哪些条件下使用结论。将教材中的关键定义、定律、量的方向和适用条件提取到知识点列表。

## 按教学目的安排画面

先安排每段要完成的教学任务和学生此时能看见的内容，再写口播。一个知识点的图、关系和正式表述尽量留在同一页。跨页时在下一页保留需要继续使用的图或公式。

| 教学任务 | 画面与讲解 |
|---|---|
| 引出概念 | 从实验、运动或具体图景提出一个能判断的问题。先画研究对象，标出需要观察的量 |
| 对照条件 | 固定其他条件，只改变正在讨论的量。并排保留两个状态，或用物理模型播放变化 |
| 建立关系 | 指出图中哪条线、哪个方向或哪个测量值进入关系式。按次序写出必要的中间关系 |
| 写正式结论 | 逐笔写出名称、完整文字、适用条件与公式。配合口播写完，学生可暂停查看 |
| 应用 | 用一个短情景让学生预测方向、大小或成立条件。给出思考时间，再用图和结论解释结果 |

按概念选择顺序和详略。定律先从可观察的现象或事实引出，数学推导写明已使用的前提。概念之间的联系在用到前一条关系时讲清。讲到章末综合题时，可按[习题课](problem-workflow.md)组织解答，课型仍记为 `concept`。

## 让口播跟着图和板书走

先确定本段实际显示的图、公式和条件，口播用它们的量名和方向说话。在 `lesson.json` 中用稳定的动作 ID 关联正式结论和推导，在 `speech-plan.json` 中用同一 cue 的 ID 保存自然口语。用动作的 `at` 将落笔对齐到口播关键词。对需播放、暂停或比较的真实物理状态，用 `scene_events` 和现有的物理场景。静态的几何、定义或代数关系可用分步配图，说明本页为何采用静态对照。见[语义场景](semantic-scenes.md)。

思考题先让条件和图形可见，在答案出现前留出停顿。用 `pause_reason:"think"` 说明思考时间，答案放入下一 cue。把完整定义、定律和公式安排在讲解中写完，学生可自行暂停抄录。用 `knowledge-board-report.json` 确认这些笔迹在换页前全部写出。见[知识点结论板书](knowledge-board.md)。

## 从完整示例开始

```sh
python3 SKILL/scripts/course.py init PROJECT --kind concept
python3 SKILL/scripts/course.py teaching-check PROJECT
python3 SKILL/scripts/course.py build PROJECT --draft
```

示例比较同一位置两次使用正试探电荷时的受力。电荷量加倍，电场力的大小也加倍，力与电荷量的比值保持相同。先用箭头和公式显示对照，再逐笔写出电场强度的完整定义。最后换成负试探电荷，请学生先判断力的方向，然后在同一页画出电场与电场力。改成用户的章节时，同步替换示例中的文字、图、知识点和口播。

场景规划、按实际画面组织讲解以及观察后逐步揭示信息的做法参考 OpenMAIC。脚本使用本技能的板书动作、物理场景和语音时间轴。[课程规划](https://github.com/THU-MAIC/OpenMAIC/blob/main/packages/@openmaic/generation/templates/requirements-to-outlines/system.md) · [讲解动作](https://github.com/THU-MAIC/OpenMAIC/blob/main/packages/@openmaic/generation/templates/slide-actions/system.md) · [交互场景动作](https://github.com/THU-MAIC/OpenMAIC/blob/main/packages/@openmaic/generation/templates/interactive-actions/system.md)
