# 课程格式与运行

## 入口与产物

`course.py init PROJECT --title "课程" --backend glm` 创建一课，同时生成 `lesson.json` 和 `speech-plan.json`；示例是完整的点电荷概念课，可按新课改写。`--example gauss` 是完整高斯定理课程。`check` 检查源文件与笔画范围；`build --draft` 生成无配音排版预览；`build --video` 配音并导出正式视频。

依赖：Python 3、Pillow、FFmpeg；Edge 路线另装 edge-tts。推荐在工作区虚拟环境安装。`doctor` 列出当前环境已有依赖。页面标题需要中文 TTF/TTC，自动查找 macOS Songti 或 Linux Noto CJK，也可通过 `font` 或 `PHYSICS_NOTEBOOK_FONT` 指定。笔迹由向量路径绘制。

`--width 1920` 输出 1080p；默认 720p。`--fps 24` 为默认，12 用于快速试片，30 用于较细的动态书写。`--backend`、`--voice` 可临时覆盖项目配音配置。

## lesson.json

```json
{
  "title":"点电荷的电场",
  "speech":{"backend":"glm","voice":"chuichui","speed":1.0,"audio_mastering":true},
  "speech_plan":"speech-plan.json",
  "parameters":{"cx":330,"cy":400,"r":180},
  "pages":[{"id":"p01","title":"电场与距离","cues":[{
    "id":"field","text":"场强与距离的平方成反比。",
    "actions":[
      {"type":"charge","center":["=cx","=cy"],"label":"Q","color":"red"},
      {"type":"math","latex":"E(r)=\\frac{Q}{4\\pi\\varepsilon_0r^2}",
       "x":755,"y":345,"size":36,"color":"blue","at":{"word":"场强"}}
    ]
  }]}]
}
```

页面与 cue 的 id 在一门课程内唯一，并在修改时保持稳定。`text` 是正常书面表达；实际朗读文本和语调参数按相同 cue id 写入 `speech-plan.json`。旧课程继续支持 cue 内的 `tts`、`speed` 和 `pause`。新格式及角色表见 [教师口播与配音](voice.md)。

本用户的新课在 lesson 顶层设置 `"show_titles":false`：保留内部页面名称，视频、板书 PNG 与 HTML 画布不绘制页标题。个别页面可用 `show_title` 覆盖；未配置时兼容已有课程。

## 一页一题布局

页面设置 `"layout":"one-page-problem"` 和稳定的 `problem_id`。动作可写入 `diagram`、`derivation`、`explanation`、`result` 四个区域；公式链使用 `formula_steps`，cue 使用 `focus` 做轻微页内聚焦。完整字段、相对坐标和示例见 [一页一题语义布局](layout.md)。

```sh
python3 SKILL/scripts/course.py layout-check PROJECT --strict
```

构建产生 `layout-report.json`。相同 `problem_id` 出现在多页、文字与公式明显重叠、区域内容过密时写入警告。

## 图形与公式动作

坐标以 1280×720 为基准，内容区为 x=120..1200、y=95..655；输出 1080p 时整体放大。颜色支持 `ink/blue/red/green/muted` 或六位十六进制值。文字默认32像素，公式分母、上标与下标会伸出基线，给上下方留位置。

| type | 字段 |
|---|---|
| text | text,x,y,size,color |
| math | latex 或 value,x,y,size,color |
| line / arrow / dashed_line | from:[x,y],to:[x,y],width,color |
| ellipse | center:[x,y],rx,ry(可省),width,color |
| dashed_circle | center:[x,y],radius,color |
| rect | x,y,w,h,width,color |
| charge | center:[x,y],label,size,color |
| stroke | points:[[x,y],...],curved,width,color |
| plot | origin:[x,y],scale:[sx,sy],domain:[xmin,xmax],expr,samples,width,color |

数字可写为参数表达式，例如 `"=cx+r"`、`"=R*cos(pi/6)"`。表达式支持基本算术和 sin/cos/tan/sqrt/exp/log/asin/acos/atan。plot 的 expr 使用数学变量 x；横向为正，图像纵轴向上，screen_y = origin_y - scale_y*f(x)。分段曲线用多条 plot，共享同一原点与比例。

LaTeX 子集：分式、上下标、向量、单位法线、时间导数点号、绝对值、根式、积分、常用希腊字母、sin/cos/tan/ln/exp。示例：`\\frac{Q}{4\\pi\\varepsilon_0r^2}`、`\\vec E`、`\\dot d`、`v_0^2`、`\\sqrt{2gh}`、`R|v_0|`。根式可用于分式内部。复杂矩阵、伸缩定界符和多行对齐需扩展布局后再使用；遇到未支持命令或字形会具体报出位置。

也可直接写公式树：`["row","E(r)=",["frac","Q",["row","4π",["sub","ε","0"],["sup","r","2"]]]]`。支持 row、frac、sup、sub、vec、hat、sqrt。

## 落笔时机

动作默认按顺序在本段配音中书写。`at:0.4` 表示该段实际时长的40%；`at:{"word":"场强","occurrence":1,"offset":0}` 表示对齐该关键词。关键词应出现在本段 tts 内，各动作的落点按书写顺序递增。

语音服务有词级时间戳时优先使用实际数据；缺少时按文本位置估算，并将 `anchor_quality` 标记为 estimated-word。GLM 当前适配提供真实段长；Edge、豆包及 MiniMax 依可用返回值提供词级信息。长推导拆成有教学意义的句群，在关键步骤后留出看图时间。

## 批量与恢复

```json
{"projects":["chapter-01/lesson-01","chapter-01/lesson-02"]}
```

`course.py batch batch.json --video --jobs 2` 从批量文件所在目录解析路径，各课独立处理。`batch-report.json` 给出逐课结果。修改后再次运行，音频与每页视频按内容缓存，已完成资源直接复用。

输出：preview.html、video.mp4、boards.pdf、pages/*.png、contact-sheet.png、tikz/*.tikz、tikz/boards.tex、timeline.json、narration.md、prosody.json、voice-report.json、layout-report.json、build-report.json。完整文字讲义由制作课程时另写 `讲义.md`，与题设、推导和图文解答相配合。

## 原题图片与两圆运动组件

课程顶层可设置 `"renderer":"motion-canvas"` 或 `"renderer":"manim"`。`build --video --renderer ...` 编译并导出；已有实测音频和时间轴时，用 `render PROJECT --renderer ...` 切换引擎并复用声音。批量命令支持相同参数。配置、依赖和原生三维场景见 [引擎接入](renderers.md)。

页面可附 `image:{"file":"problem.png","x":168,"y":108,"w":952,"h":526}`。预览中嵌入图片数据，TikZ 导出同时保留原图；可叠加逐笔条件框选。

两圆分离演示采用解析坐标，配置在页面的 `demonstration`：

```json
{"kind":"equal-circles","cx":350,"cy":392,"radius":155,
 "d0":0.45,"d1":1.75,"start_cue":"observe","end_cue":"components",
 "vectors_cue":"components"}
```

`d0,d1` 是圆心距与半径的比值，本组件用于 `0<d0<d1<2` 的水平右移；开始、结束与速度箭头按 cue 定时。左圆固定，右圆匀速移动，交点由两圆几何关系计算。当前组件是具体二维模型，其他模型需要各自实现。

## 字幕

正式视频生成后运行 `python3 SKILL/scripts/captions.py PROJECT --burn`，输出 `subtitles.srt`、`subtitles.ass` 与 `video-captioned.mp4`。字幕优先使用词级时间，保留口播中的原始标点。含 libass 的 FFmpeg 直接排版；精简版 FFmpeg 使用 Pillow 字幕图层。目前 Pillow 路线沿用 macOS Songti 字体路径。字幕独立于原视频生成，调整字幕时复用全部板书与音频。
