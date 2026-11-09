# 一页一题语义布局

v0.5 在旧坐标格式之外增加语义区域。旧课程继续使用绝对坐标；新题优先让主图、推导、物理解释和结果共享一页，问题结束后再换页。

## 页面布局

```json
{
  "id":"p01",
  "problem_id":"incline-01",
  "layout":"one-page-problem",
  "cues":[]
}
```

`one-page-problem` 提供四个区域：

- `diagram`：左侧主图，整题保留。
- `derivation`：右侧逐行推导。
- `explanation`：左下角物理解释。
- `result`：右下角最终关系。

`full-derivation` 用于推导占主导的概念页，提供 `context`、`derivation` 和 `result`。需要微调时可覆盖区域：

```json
{"layout":{"preset":"one-page-problem","zones":{"diagram":[145,110,500,365]}}}
```

区域仍需落在 x=120..1200、y=95..655 的书写范围内。

## 自动落位与区域相对坐标

文字和公式可按行自动落位：

```json
{"type":"math","latex":"a=g\\sin\\theta",
 "zone":"derivation","place":{"line":1},"size":34,"color":"blue"}
```

图形使用 `relative_to`，坐标相对于区域左上角：

```json
{"type":"arrow","from":[210,180],"to":[110,235],
 "relative_to":"diagram","color":"blue"}
```

这样调整区域时，整张主图会一起移动。

## 连续公式变形

`formula_steps` 在同一列对齐各行，逐步写出，前面的推导始终保留。v0.7 默认直接逐行书写；需要行间连接时显式设置 `connect:true`。

```json
{
  "type":"formula_steps",
  "id":"incline-chain",
  "zone":"derivation",
  "color":"blue",
  "size":34,
  "steps":[
    "mg\\sin\\theta=ma",
    "a=g\\sin\\theta",
    "v^2=2gs\\sin\\theta"
  ]
}
```

每一步也可以写成对象，单独设置 `latex`、`line`、`color`、`size` 或 `at`。前一行保留在页面上，学生能够沿着空间位置追踪推导。

## 固定画面与可选聚焦

v0.7 默认 `camera:"static"`，整页尺寸与位置保持一致。该值可设置在课程或页面；课程值由全部页面继承。固定模式会忽略旧课 cue 中的 `focus`，从同一课程源生成的 Notebook、HTML、Motion Canvas 和普通 Manim 板书都保持固定画面。

其他系列需要聚焦时，在课程或页面显式设置 `camera:"focus"`，再给 cue 指定区域：

```json
{"id":"derive","focus":{"zone":"derivation","zoom":1.06},"actions":[]}
```

`zoom` 范围为 1.00—1.15，默认 1.06；`transition` 默认 0.35 秒。聚焦围绕区域中心轻微放大，页面空间关系保持不变。Notebook、HTML、Motion Canvas 和普通 Manim 板书共用同一时间轴。原生 Manim 场景自行控制相机。

## 布局质量门

```sh
python3 SKILL/scripts/course.py layout-check PROJECT
python3 SKILL/scripts/course.py layout-check PROJECT --strict
```

报告写入 `layout-report.json`，包含文本与公式遮挡、区域密度和同一 `problem_id` 跨页情况。普通构建保留警告，`--strict` 将警告作为失败处理。联系紧密的概念链可以共用一页；每个完整例题和练习使用独立 `problem_id`。
