# 参数化物理图形组件

v0.6 把高频物理图形写成 `component` 动作。课程源只保存物理参数，编译器再展开为普通的线、箭头、公式和笔画。展开后的路径进入 Notebook、HTML、Motion Canvas、Manim、PNG、PDF 与 TikZ，修改参数后所有产物一起更新。

## 通用格式

```json
{
  "type":"component",
  "name":"force-diagram",
  "id":"block-forces",
  "zone":"diagram",
  "origin":[220,180],
  "scale":1.0,
  "at":{"word":"受力"}
}
```

`zone` 同时作为组件的相对坐标区域；`origin`、`center` 等坐标从该区域左上角量起。`id` 在一页内保持唯一。`scale` 统一缩放长度、字号与线宽。`at` 锚定组件第一笔，其余笔画按组件内部顺序继续出现。

## 组件目录

| name | 用途 | 主要参数 |
|---|---|---|
| `force-diagram` | 单个研究对象的受力图 | `origin`、`body`、`forces[]` |
| `inclined-plane` | 斜面、倾角、滑块和投影线 | `origin`、`length`、`angle`、`block_position` |
| `projectile-trajectory` | 坐标轴、抛物线、初速度和重力 | `origin`、`speed`、`angle`、`gravity`、`space_scale` |
| `electric-dipole` | 正负电荷、场线与电偶极矩 | `center`、`separation`、`moment_label` |
| `gaussian-surface` | 球面、柱面或平面高斯面 | `center`、`shape`、`radius`、`length` |
| `circuit-loop` | 电源、电阻、电流方向与闭合导线 | `origin`、`width`、`height`、各符号标签 |
| `thin-lens` | 主轴、焦点、物像与两条特征光线 | `center`、`focal_length`、`object_distance`、`object_height` |
| `wave-profile` | 正弦波形与波长标记 | `origin`、`length`、`amplitude`、`wavelength`、`phase` |

运行完整组件示例：

```sh
python3 SKILL/scripts/course.py init PROJECT --example components --backend minimax
python3 SKILL/scripts/course.py build PROJECT --draft
```

## 受力图

角度按数学正方向定义：水平向右为 0°，向上为 90°，向左为 180°，向下为 -90°。

```json
{
  "type":"component",
  "name":"force-diagram",
  "id":"incline-forces",
  "zone":"diagram",
  "origin":[250,175],
  "forces":[
    {"label":"F_N","angle":120,"length":90,"color":"blue"},
    {"label":"mg","angle":-90,"length":105,"color":"red"},
    {"label":"f","angle":210,"length":65,"color":"green"}
  ]
}
```

力的方向和标签来自题目建模；组件负责保持箭头、物体与标注的相对关系。

## 电学与光学

球形高斯面：

```json
{"type":"component","name":"gaussian-surface","id":"gauss-sphere",
 "zone":"diagram","shape":"sphere","center":[225,180],"radius":105}
```

薄透镜的实像图由焦距、物距和物高计算，`object_distance` 大于 `focal_length`。图中像距与放大率来自
`1/f=1/u+1/v` 和 `m=-v/u`，两条特征光线落在同一个像点。

## 组件检查

```sh
python3 SKILL/scripts/course.py component-check PROJECT
python3 SKILL/scripts/course.py component-check PROJECT --strict
```

报告写入 `component-report.json`，列出每页组件、展开后的包围框、各类组件数量和区域占用提示。未知组件、非物理参数范围、重复 id 及超出总书写区会在编译时给出具体位置；`--strict` 将组件区域提示作为失败处理。

每个组件生成的 TikZ 路径前带组件 id 注释，便于在 `tikz/页面.tikz` 中定位和继续编辑。新题先选最接近的组件，再根据题设补充辅助线、局部过程图和结果图。
