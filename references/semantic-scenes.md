# 讲述、物理状态与公式同步（0.10）

新概念课使用 `kind:"concept"`。先完成物理推导，再声明要观察的状态、对应口播和必要的显示时间。固定镜头与无逐页标题继续沿用。

## 按关键词控制物理状态

在页面设置有限数值的初始状态和事件：

```json
{
  "scene_initial":{"phase":0},
  "scene_events":[{
    "id":"flux-peak","track":"phase","cue_id":"observe",
    "at":{"word":"看曲线"},
    "until":{"at":{"word":"最大"}},
    "to":1.5707963267948966
  }]
}
```

`at` 支持 `"start"`、`"end"` 或 `{word,occurrence?,offset?}`。`until` 可指定另一个 `cue_id`；也可以用 `duration`（秒）替代 `until`，两者选一。每条轨道按事件发生时间连接；事件开始前保持上一状态，结束后保持目标值，直到下一事件开始。同一轨道的事件时间不可重叠。默认线性插值；展示性的平滑变化可写 `easing:"smooth"`，真实运动规律应由物理模型计算。

构建时根据处理后的实际配音绑定时间，生成 `timeline.json` 中的 `scene_tracks`。供应商词时间戳可用时标为 `provider-word`；缺少时标为 `estimated-word`。关键词不存在、事件越出页面、同轨事件重叠均报错。

原生 Manim 场景读取状态：

```python
from scene_events import value
phase = value(page, "phase", self.time)
flux = math.sin(phase)
emf = -math.cos(phase)
```

此例的 `phase` 控制演示进度，实际物理时间与慢放展示时间分开。电动势来自原物理模型的磁通变化率。暂停展示时保留该物理瞬间的场、电压和电流，不对展示时间求导。

场景配置声明 `uses_scene_tracks:true`，并记录 `motion_reviewed:true`、具体的 `motion_description`。声明只是实现约定，仍要观看关键帧、检查实际代码是否调用 `value`，以及对应物理关系是否正确。原生场景的 HTML 预览仍以普通板书为主，实际原生运动以 MP4 为准。

## 逐笔公式

使用 `type:"math"` 与可编辑的 `latex` 源。`x,y` 使用手写布局的笔迹坐标，`size` 控制字幅。`write_seconds` 给书写动作留出时间；时间轴会按笔画长度分配这段时间。公式从空白开始写，笔尖沿笔画移动，已经写出的笔画保留在画面上。

```json
{"id":"coupling","type":"math",
 "latex":"M=\\kappa\\sqrt{L_1L_2}","x":650,"y":300,"size":30,
 "at":{"word":"耦合系数"},"write_seconds":3.5}
```

通用 Notebook、Manim、Motion Canvas 和离线 HTML 共用笔迹。原生场景把 `page['strokes']` 中的公式笔迹交给与文字相同的逐笔图层。静帧优化应将所有笔迹的起止时间纳入活动区间。使用 `preview` 查看笔尖移动、完整写出后的停留以及公式与图之间的间距。

旧项目的 `math_renderer` 和公式动作的 `renderer` 字段可删除。已有 v0.10.0 图像公式时间轴时，重新运行 `course.py build PROJECT --video --renderer manim` 生成逐笔时间轴并复用缓存配音。原先用于淡入的短 `write_seconds` 也应换成实际书写时间。

原生图中随讲解补出的汉字，作为 `type:"text"` 放进笔迹时间轴。比如在画面到达磁通峰值时开始写“磁通最大”。同一个标注的笔迹从通用时间轴读取一次，图稿和成片共用位置与内容。

## 概念课与检查覆盖

概念课每个推导公式有稳定的动作 `id`，并关联 `derivation_steps` 中的依据、口播、先前步骤和结果。纯粹带入前页上下文的公式可标 `teaching_role:"context"`。`formula_steps` 支持步骤显式 ID；有组 ID 时自动生成 `组ID-step-1` 等动作 ID。

```json
{"id":"mutual","depends_on":[],"reason":"完全耦合时比较两线圈自感，再引入耦合系数",
 "cue_id":"derive","action_id":"coupling","result":"M=\\kappa\\sqrt{L_1L_2}"}
```

上面的依据应替换为该结果实际使用的物理关系与运算；`result` 与屏幕动作的 LaTeX 完全一致。检查器只检查关联与结构，物理证明由作者完成。

每页记录经过查看的实际情景动画。仅做代数整理的页面可以写 `motion_not_applicable`，说明本页保留的图与公式为什么足以完成该步骤。它是明确的教学选择，不应用来跳过本来需要展示的物理过程。

```sh
python3 SKILL/scripts/course.py teaching-check PROJECT
python3 SKILL/scripts/course.py preview PROJECT --renderer manim
python3 SKILL/scripts/course.py build PROJECT --draft
python3 SKILL/scripts/course.py build PROJECT --video --renderer manim
```

第一次查看原生运动用 `preview`：它生成带“草稿 · 无配音 · 估算时间”标记的 `draft-preview-manim.mp4`（或 Motion Canvas 对应文件），报告保留尚未完成的教学记录。该命令不调用 TTS，也不覆盖正式 `narration.wav`、`timeline.json`、`video.mp4`；查看关键状态后再填写 `motion_reviewed`。正式构建继续要求教学检查通过。

报告区分 `checked`、`not_checked` 与 `not_applicable`，并单独写明 `physics_correctness:not_evaluated_by_this_checker`。未采用新课程种类的旧项目继续兼容；没有检查内容时显示 `not_applicable`，不再空报通过。概念课缺少推导关联或运动记录时，正式配音前停止构建。
