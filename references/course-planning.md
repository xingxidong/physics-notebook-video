# 整节新授课的编排

先确定这节课围绕什么问题展开，学生已经会什么，课末能独立做什么。按先修关系安排各段，再为每段确定主图、关键推理和最后要写下的结论。教学顺序随内容调整，时间优先分给学生第一次需要理解的推导和观察。

## 写稿前生成课程编排表

```sh
python3 SKILL/scripts/course_outline.py check PROJECT/outline.json
python3 SKILL/scripts/course_outline.py table PROJECT/outline.json --output PROJECT/课程编排表.md
```

编排表可以直接写入 `lesson.json` 的 `course_outline`，也可以在该字段引用项目内的 `outline.json`。电场强度示例带有完整编排、实际板书、引入问题与课末检查。

| 字段 | 怎样填写 |
| --- | --- |
| `title`、`main_question`、`audience`、`target_minutes` | 课程名称、整课围绕的问题、学生基础和目标时长。 |
| `prior_knowledge` | 写出学生本来就会什么。每条有 `id` 和 `description`，以便教学段明确引用。 |
| `objectives` | 每项有 `id` 和 `outcome`。把目标写成学生能够做出的判断、作图、解释或计算。 |
| `units` | 按实际教学顺序排列。每段有 `id`、`focus`、`objective_ids`、`needs`、`minutes`。先修 ID 可以是 `prior_knowledge` 或已经讲过的教学段。 |
| 单段设计 | 写 `opening`、`reasoning`、`board_statement`、`application`、`handoff`。实际提问时把原问句写在 `intro_question`。应用检查填写 `question` 和 `expected_answer`。有物理情景时用 `diagram` 的 `scene` 和 `labels` 写明画什么、标什么，纯代数段可填 `no_diagram`。 |
| `exit_checks` | 每道题填 `objective_ids`、`question` 和 `expected_answer`。最后一个教学段的应用阶段写出这些问题，再讲依据。最后一段的应用题也可以同时承担课末检查。 |
| `deferred` | 记录推后讲的内容和放在哪一课更合适，每项填写 `topic` 和 `reason`。 |

编排阶段按下面三步自行检查。先读各段的开场和最终板书，确认整节课在回答同一个问题。再比相邻两段，确认后段用得上前段的图、量或结论。最后做课末题，确认作答所需的知识都已建立，图和已知条件足以让学生独立开始。

## 从计划排到板书

先检查一段是否有清楚的学习结果：学生应当能沿图说清什么关系、写出什么式子或作出什么判断。决定重点以后，把较多时间留给建立这条关系的理由。旧知识讲到能支撑当前推导，用一次改变条件的应用检查回看学生是否会用。每段结束时，画面保留完整结论和必要条件，并用这条结论接下一段。具体例子见[重难点与制作复查](quality-workflow.md)。

新授课采用 `planning_version:2` 时保留传统的四阶段预算。需要按知识逻辑重新编排时使用 `planning_version:3`，由 `lesson_arc` 和 `concept_units.stages` 记录真实教学拍。两种格式都要写清学生第一次会卡在哪一步，哪张图或哪一行推导解决它，以及学生怎样用新结论作出判断。

- `key_point` 写本段值得学生记的一句话。`difficulty.obstacle` 写具体难点，`difficulty.treatment` 写明讲法。正式板书至少突出一条结论或核心公式。
- 使用 `planning_version:2` 时，`stage_minutes` 用 `introduce`、`explain`、`emphasize`、`apply` 分配时间。使用 `planning_version:3` 时，按 `lesson_arc` 的实际教学拍分配时间。一次需要学生观察或演算的新关系，给足相应的观察或推导时间。正式配音后，`course-timing-report.json` 显示各段和阶段的实测时间。
- `board_pages` 按顺序列 `id` 与 `goal`，每页说明它完成的物理关系。续页填 `from_page` 并在实际页面的 `layout.carry` 带入图和前提。关键问题、图、推导与完整结论的位置可用 [板书排版](board-layout.md) 预览。
- 应用检查换一个具体条件或提供一个新图，让学生说明怎样从图和条件得到结果。避免换几个数字反复讲同一个运算。课末用实际题目核对各目标是否可独立完成。

`course.py review-plan PROJECT` 将计划、逐页板书和完整口播合成教案，交给人审。见[审阅流程](review-workflow.md)。

## 从课纲到课堂推进

课程编排表解决“该教哪些内容”，`lesson_arc` 解决“学生在视频里怎样一步步跟上”。每个教学拍对应连续的一组口播，而不是一张页面或一个漂亮标题。它固定五件事：

- `student_question`：学生此刻究竟在解决什么。
- `visual_ids`：回答这个问题时看哪张图、哪个标注或哪一行式子。
- `scene_change`：本拍中图、物体状态、辅助线或板书怎样变化。
- `takeaway`：讲完这拍，学生笔记上留下什么判断。
- `cue_ids`：这一拍实际覆盖哪些连续口播。
- `purpose`：`orient`、`model`、`reason`、`derive`、`anchor`、`apply` 或 `recap`。

习题课从题目情景进入，先让研究对象、过程和所求清楚，再建立关系、完成推导、把结果放回图中解释，最后总结。新授课从一个具体可观察的问题进入，先让学生发现需要解释的现象，再建立定义或规律，写好可抄的结论，用新情境检验，最后总结。每拍只推动一个理解上的变化。图、口播和落笔同时服务这一个变化。

`review_required:true` 的课程会检查教学拍是否覆盖全课、顺序是否连续、每拍是否有明确的学生问题和板书依据，以及总结拍是否与 `closure` 相连。教案中的“课堂推进”区在正式配音前给人审看，先改这条线，再改每一句话。

## 写稿、分工与合并

- 课程源中的 `concept_units` 使用编排表的教学段 ID、重点和顺序。正式结论写入该段关联的 `knowledge_points`。完整问题在相应的引入或应用阶段写在板书上，并关联回答段。图上的符号、位置与方向仍需用板书预览核对。
- 新授长课在团队计划中填 `course_outline`，每个章节用 `unit_ids` 领取连续的教学段。主 Agent 先检查全课顺序和时长，再发任务。分工时沿用既定的课末目标、正负方向与段间承接。章节合并会验证分到的教学段和最终顺序。
- `course.py teaching-check` 会比较编排与课程源。先修错序、时长预算不一致、目标没有检查题、写稿偏离重点或漏掉计划中的正式板书和问句，都会报告位置。复查学生听完是否理解时，看课末题能否只靠课堂上刚教的内容来做。

时长不足时，回到课末目标，找出尚未讲明白的观察、条件、推导或练习，补上实际讲解。时间过长时，整理用途重复的例子，把依赖以后知识的内容安排到相应课程。
