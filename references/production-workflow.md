# 从备课到局部修订

## 正式课的八步

| 步骤 | 运行或提交 |
|---|---|
| 1. 自我强化 | 用 `start-workflow PROJECT --kind problem` 或 `--kind concept` 扫描自我成长包。开工先读《备课提醒》。文章课另加 `--source-type article`。初始化课程范例时自动扫一次。 |
| 2. 备课 | 按课型写课程源、逐笔板书、教案、学生讲义主 TeX 和每句最终要讲的完整讲稿。填写分段用时和动画。准备普通讲解与关键读式的试音，从本课真实句子选材。 |
| 3. 降低 AI 味 | 使用[随包的文案技能](classroom-language-editing.md)改四份材料。用 `review-plan` 生成完整讲稿、板书文字草稿和讲义 PDF。再用 `review-language PROJECT --lesson-plan … --board … --handout … --script …` 分别登记编辑观察。 |
| 4. 审教案 | 用 `preview PROJECT --renderer manim` 或 `motion-canvas` 导出动画。按[试音说明](../assets/starter-kit/voice-trial/README.md)在项目的 `voice-trial` 目录录制并登记制作端审听。如试音在改稿后更新，先重跑 `review-plan` 和 `review-language`，把实际试音语速反映在送审预计时长里。用 `review-packet` 打包整套材料给用户。等待用户确认，再以 `approve-plan --feedback` 登记实际确认原话。 |
| 5. 正式配音 | `build PROJECT --video` 读[读音卡包](../assets/pronunciation-cards/README.md)和[目标音色包](../assets/target-voice/README.md)。逐次看词义、拼音与连读，对应字母、希腊字母、公式、函数和分组。读音计划保存于 `classroom-pronunciation-plan.json`。支持指定读法的配音后端使用逐句匹配，其他后端也要从实音确认全部要求。 |
| 6. 合成 | 用通过本课试音的教师音色完整录制。用 `speech_group` 把因落笔拆成多条 cue 的连续语段合起来录。用实录时间定位落笔和动画。 |
| 7. 审成片 | 逐处检查最终 MP4，不遗漏任何一句口播。听术语、公式中具体的运算和字母、上下标、字母实际出现次数和语流，看片中相应落笔。发现错音，扩到讲清同一意思的整段重录，再从新 MP4 检查。 |
| 8. 核查流程并交付 | `finalize` 检查前七步和选定 MP4 是否对应。发现漏步时提示用 `start-workflow` 从头重做。完成后交付 MP4、讲义 PDF、可编辑的 LaTeX 和 TikZ 源码。 |

`init --kind` 新建项目自动启用 `classroom_workflow_version:1`。手工建立的新课和习题课也设置这个字段，并设置 `review_required:true`、`speech_review_version:1` 和 `term_inventory_version:2`。复查已有历史 MP4 时，可沿用该课的审查入口。

## 五组材料在哪一步用

首次安装或换电脑时，可在正式备课前用斜面样例跑一遍。第 2 步按需拿长课模板编排、用参数动画搭模型、选配音配置和试音材料。第 4 步提交本课的实录试音和改好的动画。第 5 步沿用确认的配音配置，第 6 步按实录时间把动画和板书排进成片。各组材料的用法见[随包材料表](../assets/starter-kit/README.md)。

试音先由制作者审听，再交用户确认整套材料。稿件修改后，以新版完整讲稿录制和送审。正式录音逐句使用批准的讲稿，排版或音素提示服务于原句的完整朗读。教案给出全课预计值。终审比较选定 MP4 的实测时长与送审预计值，差距超过预计值的 8% 或 15 秒中的较大者时，调整课的内容或编排并再次送审。需要延长时补先修、推导或变式，保持正常语速与落笔速度。

第 7 步查到错音属于成片修订。用 `revise --cue` 圈定完整语段，同一个 `speech_group` 整组重录。改了已批准的讲稿、板书、动画或讲义时重新提交整套材料。发现实际漏过一个阶段时，用 `start-workflow` 开新一轮。旧的批准、试音记录、动画预览和正式时间轴不能通过新一轮的流程审查。

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
| 准备一节课 | 先 `start-workflow`，按课型填写课程源，再走整套送审 | 教案、完整讲稿、静音预览、学生讲义、预计时长 |
| 继续制作 | `status PROJECT` | 课程源、教案签名、实际时间轴、导出记录、最终检查报告 |
| 正式制作 | 作者确认整套材料及试听后用 `approve-plan`，再 `build PROJECT --video` | 使用当前已确认讲稿和实际配音时长落笔 |
| 只做审查 | `quality-check PROJECT --stage final` | 当前 MP4、术语逐处清单、字母与上下标、画面、讲义 |
| 修某几句 | `revise PROJECT --cue 页/句`，可重复指定 | 该句及前后接缝、同步落笔、对应讲义位置 |
| 改符号或方向 | `revise PROJECT --convention 约定名` | 引用这一约定的步骤和后续推导；重审对应图和教案 |
| 只听改动处 | 本次导出后 `repair-reel PROJECT` | 最终 MP4 中的完整句子与相邻接缝，见 revision-review |
| 整片连听 | 成片检查自动生成 `final-speech-continuity.json` | [连贯性复核](speech-continuity.md)，按实音确认词内停顿、公式接续和邻句 |
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

配音修订先扩到讲完同一个意思的相邻句，在相应语段的全部 cue 上登记改动，再用同一音色一次重录整段。原有制作命令复用能命中的音频缓存，并按实际时长重排笔迹、字幕和后续页面。repair-reel 从这次导出的 MP4 截取改动范围及相邻发言，保留句间实际停顿；相邻片段重叠时合并。index.json 保存视频时间、文件摘要和后续起点发生移动的句子。听过的成片换版以后，以新成片取样。只有旧 MP4 的作品先恢复课程源和准确时间轴；旧版缺少导出凭据时，status 会给出需要补做的步骤。

## 可编辑的学生讲义

handout 填供教案审阅的学生文件；handout_source 指向主 TeX 文件。题图和推导中的图使用 TikZ，按题干和推导顺序放入讲义。打包同时沿 LaTeX 引用收集文件，并由 XeLaTeX 记录这份讲义实际打开的本地输入，包括宏选中的图和数据文件。希望学生拿到的其他可编辑素材可以用 handout_assets 显式列出。课程私有文件使用相对路径。源码包在空目录中使用 XeLaTeX，依赖系统 TeX 发行版和字体；引用缺失、标签未解析或使用包外的私有源文件时会报错。此流程适用于两次 XeLaTeX 即可生成的讲义。handout-delivery 目录保存 PDF、源码 ZIP 和两者对应的输入摘要。

## 验证一次升级

运行 `python3 scripts/workflow_eval.py --output 本次.json`。下次加 `--baseline 本次.json` 查看退步的检查项。受控用例会故意让图画晚、让两行公式同时写、或把口播换成另一句话。重读“电压差”时先统计每一次出现，再走原有实音审查。第 43 届第二题原版是作者认可的课堂节奏参照。是否自然连读、音色是否合适，只能由相应版本的真实声音支持。
