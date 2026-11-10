# 让题目情景动起来

讲题使用 Motion Canvas 或 Manim 显示物理过程：物体沿轨迹移动，速度和加速度方向随状态变化，光线、场或相互作用按题设展开。镜头默认固定。安排看运动、暂停分析、继续运动，配合当前口播。

## 已接入的追逐模型

```json
{
  "demonstration":{
    "kind":"pursuit","vF":1,"vD":1.5,"L":1,
    "origin":[210,305],"scale":210,"board_progress":0.35,
    "vectors_cue":"radial",
    "segments":[
      {"start_cue":"motion","end_cue":"motion","from":0,"to":0.35},
      {"start_cue":"finish","end_cue":"finish","from":0.35,"to":1}
    ]
  }
}
```

本模型用于 `vD>vF>=0` 的有限纯追逐：蓝点沿直线匀速移动，绿点沿追逐轨迹运动，速度方向始终指向蓝点。视线、水平投影、角度和轨迹随同一物理状态变化。

速率和 `L` 使用一致的物理单位。`scale` 是每单位长度的屏幕像素数；物理追及时间由模型计算，视频中的演示用 cue 区间映射。`segments` 使用物理过程的进度 0—1，顺序播放，段间暂停。播放速度和物体的物理解分开。

`board_progress` 选择 PNG、PDF 和 TikZ 保留的过程快照；视频和 HTML 仍完整播放。追逐模型来自极坐标解析解的数值取样，Python 渲染和 HTML 使用同一取样数据。已实现的两圆运动仍采用原格式。

## 完整试用

```sh
python3 SKILL/scripts/course.py init PROJECT --example pursuit --backend minimax
python3 SKILL/scripts/course.py teaching-check PROJECT
python3 SKILL/scripts/course.py build PROJECT --draft
python3 SKILL/scripts/course.py build PROJECT --video --renderer motion-canvas --width 1920
```

示例自带可追溯的文字题目和参考解答，包含 8 个有依据的中间步骤。它展示速度投影与加权相加的讲解过程。

## 其他物理情景

选择题设真正需要的运动和状态变量。现有模型不覆盖时，为本题实现解析模型、数值模型或原生引擎场景，按 [引擎接口](renderers.md) 接入。模型中保留质量、长度、速率、初态及各阶段衔接量。来自参考解答的条件进入同一参数表，静态图也从这些参数生成。

原生场景完成后，实际查看关键时刻和不同时间的帧，在页面写 `motion_description` 与 `motion_reviewed:true`。程序能核对文件与结构；真实运动效果和物理正确性由计算和画面共同确认。特别留意接触、穿透、方向、比例、暂停时刻，以及讲解与状态的对应关系。
