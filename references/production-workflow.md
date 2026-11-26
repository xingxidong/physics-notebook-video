# 从备课到局部修订

## 最终交付

正式渲染先输出候选视频和 `delivery-candidate.json`。先 `handout-pack PROJECT` 固定本版讲义，再运行：

```sh
python3 SKILL/scripts/course.py quality-check PROJECT --stage final --video-file video.mp4
# 实际观看和试听后，按 quality-report.json 的 manual_review.items 逐项登记。
python3 SKILL/scripts/course.py review-final PROJECT --task ITEM_ID --token ITEM_TOKEN --reviewer 制作者 --evidence '具体句子、画面或时间位置以及实际观察'
python3 SKILL/scripts/course.py finalize PROJECT --video-file video.mp4
```

`review-final` 记录制作者已进行的观察，不能用自动填“通过”代替试听。术语读音、声调和上下文仍用对应的逐处审听入口登记，硬错误由修改源文件解决。当前版本的检查完成后，`finalize` 才产生状态为 reviewed 的 `delivery-files.json`。

记录绑定课程源、选定 MP4、时间轴和讲义回执。换音、改板书或讲义会使旧记录失效。交付带字幕文件时，两条命令指定同一个文件名。

公式按完整表达式比较，布局空白会归一化；增加了项的式子不会因子串命中而通过。讲义使用等价写法时明确登记 `handout_result`，保留实际板书 result，并检查两式等价。全部笔迹都检查同时书写，包括未登记为推导的笔迹。

修订追踪整课参数、音频和动画依赖、页面设置、删句后形成的新接缝，以及依赖已改口播的后续推导。多段课程组装保留审阅、讲义、流程版本和编排设置。

| 现在要做什么 | 入口 | 审阅依据 |
|---|---|---|
| 准备一节课 | 按课型填写课程源，运行 `review-plan PROJECT` | 教案、完整讲稿、静音预览、学生讲义、预计时长 |
| 继续制作 | `status PROJECT` | 课程源、教案签名、实际时间轴、导出记录、最终检查报告 |
| 正式制作 | 作者确认教案后用 `approve-plan`，再 `build PROJECT --video` | 使用当前已确认讲稿和实际配音时长落笔 |
| 只做审查 | `quality-check PROJECT --stage final` | 当前 MP4、术语逐处清单、字母与上下标、画面、讲义 |
| 修某几句 | `revise PROJECT --cue 页/句`，可重复指定 | 该句及前后接缝、同步落笔、对应讲义位置 |
| 改符号或方向 | `revise PROJECT --convention 约定名` | 引用这一约定的步骤和后续推导；重审对应图和教案 |
| 只听改动处 | 本次导出后 `repair-reel PROJECT` | 最终 MP4 中的完整句子与相邻接缝，见 revision-review |
| 交付讲义 | `handout-pack PROJECT` | 打包的 LaTeX、TikZ 及依赖，在空目录解压编译两遍所得 PDF |

以上入口均由 `python3 scripts/course.py` 调用。内容编排仍由教学目标决定。新授课要给学生一条可抄下的完整定义或定律，习题课要让图上的量进入每一步推导。多个字母在同一行出现时，口播也要说清运算顺序。

## 教案里的一个推导步骤

正式新课或习题课在 lesson.json 设置 `workflow_version: 1`，指定 `handout_source` 为主 TeX 文件，在已有的 `pages[].derivation_steps` 补下面的字段。旧课迁移可以从一个步骤开始，直接补上 spoken_anchor 与 handout_label 即对该步生效。

```json
{
  "id": "zero-moment",
  "cue_id": "radial-push",
  "action_id": "moment-zero",
  "result": "\\tau_O=Fd=0",
  "reason": "作用线过 O，从 O 到作用线的垂距为零。",
  "question": "沿着半径推，对 O 的力矩有多大？",
  "requires_visible": ["origin-O", "force-line"],
  "spoken_anchor": "力臂等于零，所以对这点的力矩也是零",
  "handout_label": "eq:zero-moment",
  "uses_conventions": ["origin"],
  "depends_on": ["moment-arm"]
}
```

把 question 真正写到提问的板书上。requires_visible 使用同页板书的对象或组合编号。handout_label 放在对应公式的 LaTeX 环境内。spoken_anchor 应当逐字出现在该句口播中且只出现一次。全课物理约定放在 `conventions` 对象里，比如 `{"origin":"取门轴 O 为取矩点"}`。同页先修步骤用 depends_on；跨页引用用 upstream_steps，例如 `["p01/moment-arm"]`。做教案时查问题、图和公式之间的物理含义。时间轴审查核实先后顺序、发言时间内的实际笔迹和两行公式的重叠。缺少能对齐的逐词时间时只记整句证据，制作者需听看该句原片。

## 改过的地方怎样复查

先改课程源，再运行 revise 写入 revision-plan.json，然后按 status 给出的入口继续。已导出的新课保存上一版的内容、音色、时间轴和视频摘要。制作端会找出内容变化的句子；只换录音且讲稿相同时显式指定 --cue。音色配置改变时覆盖全课。约定改变而步骤尚未标注时，整课进入复查。改物理量、图或推导后，重新生成教案交作者确认。

同一句的整句声音用同一音色重配。原有制作命令复用能命中的音频缓存，并按实际时长重排笔迹、字幕和后续页面。repair-reel 从这次导出的 MP4 截取每句及前后半秒左右的相邻发言，保留句间实际停顿；相邻片段重叠时合并。index.json 保存视频时间、文件摘要和后续起点发生移动的句子。听过的成片换版以后，以新成片取样。只有旧 MP4 的作品先恢复课程源和准确时间轴；旧版缺少导出凭据时，status 会给出需要补做的步骤。

## 可编辑的学生讲义

handout 填供教案审阅的学生文件；handout_source 指向主 TeX 文件。题图和推导中的图使用 TikZ，按题干和推导顺序放入讲义。打包同时沿 LaTeX 引用收集文件，并由 XeLaTeX 记录这份讲义实际打开的本地输入，包括宏选中的图和数据文件。希望学生拿到的其他可编辑素材可以用 handout_assets 显式列出。课程私有文件使用相对路径。源码包在空目录中使用 XeLaTeX，依赖系统 TeX 发行版和字体；引用缺失、标签未解析或使用包外的私有源文件时会报错。此流程适用于两次 XeLaTeX 即可生成的讲义。handout-delivery 目录保存 PDF、源码 ZIP 和两者对应的输入摘要。

## 验证一次升级

运行 `python3 scripts/workflow_eval.py --output 本次.json`。下次加 `--baseline 本次.json` 查看退步的检查项。受控用例会故意让图画晚、让两行公式同时写、或把口播换成另一句话。重读“电压差”时先统计每一次出现，再走原有实音审查。第 43 届第二题原版是作者认可的课堂节奏参照。是否自然连读、音色是否合适，只能由相应版本的真实声音支持。
