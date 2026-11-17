# 按实际笔迹排板书

新课优先把主问题、题图、关键推导和完整结论安排在同一页。新授课先在课程编排中选出重点与难点，再决定各页学生可以独立看懂的关系。习题课给完整题面、示意图、推导和结果留出位置。一条关系需要续页时，下一页原位保留后面实际要用的图、符号和上一步式子。

## 可复用的布局

设页面 `"layout":"lesson-board"`。从上到下使用 `question`、左右并排的 `diagram` 与 `derivation`、底部的 `conclusion`。区域顺序由物理内容决定，各区可用 `zones` 覆盖。长式推导也可选 `full-derivation` 加 `"flow":"measured"`。旧的 `one-page-problem` 仍可使用。

给汉字或 LaTeX 动作指定 `zone`，由程序按笔迹宽高堆叠。使用 `formula_steps` 对齐同列的等号。长式在顶层等号等边界换行，分式、根式及下标一起保留。式子整块过宽时调整区域或按物理逻辑安排续页。关键一句和核心式设置 `emphasis:true`，程序用同色下划线收束。图形用 `relative_to` 定位，显式坐标可用于图内局部标签。发布版保持固定镜头。

用 `id` 或 `board_group` 给图和关系命名。多条笔迹同属一个图时共享组名。续页设置 `"layout":{"preset":"lesson-board","carry":["cart","initial-equation"]}`，把前页这些已写好的笔迹作为本页初始状态。需要延续原生动画时，教案另写新页从哪个物理状态接起。

在首次介绍物理模型的页面，把主图各部分和必要标注编入同一个 `board_group`。设置 `"layout":{"preset":"one-page-problem","prewritten":["circuit"]}`，用已完成的笔迹显示整张图。选中的本页动作从首帧可见，后续仍可被 `carry` 引用。它们使用统一的初始时刻，省去 `at` 和 `write_seconds`。公式与推导中新引入的辅助图继续按讲解顺序逐笔写。对首句口播登记 `{"cue":"read-entry","at":"start","visible":["circuit"]}`，确保学生听到“看 A 点”前能看到整个模型和 A 点标注。

## 检查学生实际看到的画面

```sh
python3 SKILL/scripts/course.py board-check PROJECT --strict
```

横屏比例的 `review-preview/contact-sheet.png`、板书、PDF 和 TikZ 都来自同一份笔迹。检查小字、上下标、图上单位和字幕区域。普通布局报告仍给出出界、文字重叠和区域密度。新布局的 `board-review-report.json` 按页、口播段和时间列出问题、首次使用的图上标注、应同时出现的式子和完整结论。

`layout.checkpoints` 可给自定时刻指定同屏笔迹。例 `{"cue":"derive","at":{"word":"代入"},"visible":["cart","known-acceleration"]}`。时点可选 `start`、`end` 或语音关键词。图上量的 `scene_labels.first_use_at` 可登记首次实际引用的词。用半透明、颜色和笔迹表示含义时，确保还可以从文字或公式辨认状态。

内置物理模型的轨迹会和当时已经显示的板书比较。原生动画可以从实际场景导出抽样边界到 `layout.motion_boxes`，例如

```json
{
  "cue": "slide",
  "fraction": 0.5,
  "objects": {"block": [220,300,275,346], "track": [145,346,430,356]},
  "disjoint": [["block","track"]]
}
```

这里的框格式是 `[x1,y1,x2,y2]`，对象刚好接触时允许边界相同。只给体积确实应分开的对象登记 `disjoint`。曲面、相互遮挡的三维投影及合法接触优先逐帧看原生预览，必要时登记多组更贴合物体的边界。图中设计为标注物体的标签可用 `label_allow` 记录允许覆盖的板书 ID。

参考 `course.py init PROJECT --example dimension-board`。第二页沿用同一小车图与量纲关系，继续写修正式和结论。
