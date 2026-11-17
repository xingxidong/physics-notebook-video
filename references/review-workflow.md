# 从教案审阅到交付

出教案前和成片后分别运行 `quality-check --stage plan` 与 `quality-check --stage final`，用[制作检查清单](quality-workflow.md)逐项修复和回听。预览或出教案期间若源文件改变，当前输出会提示重新生成，以便整套审阅材料对应同一个版本。

新项目的 `review_required:true` 在正式配音与渲染前启用人审。课程先规划一课主问题、可观察的目标、先修知识、重点、难点、讲法和每段时间。板书按每页要让学生理解的一条关系安排。习题课把完整题面、图、推导和结果写进同一套教案。

1. 写好课程源、完整口播和学生讲义。讲义按实际授课顺序解释定义、条件和必要推导，例题给题图，解答在对应步骤旁给过程图。保持题面、板书、讲义和可编辑 TikZ 的符号一致。默认讲义文件 `讲义.md`，也可在 `handout` 指定已经准备好的学生版 PDF 等文件。把需要随教案确认的讲义附图或相关源文件加入 `review_assets`。
2. 有原生 Manim 或 Motion Canvas 动画时先生成无配音预览。开场、接触前后、运动峰值、转折及结束均查看画面，对照接触点、轨迹、速度方向、文字位置。抽样边界检查见[板书排版](board-layout.md)。把正常接触与确实穿模的情况区分清楚，按图里的物理条件调整。
3. 用 `review-plan` 输出 `教案.md` 和 `review-preview/`。给人看完整口播、重难点、板书关键帧、片头和学生讲义。收到修改意见先改教案源、讲稿或动画，再出新的教案。审阅者明确同意当前版本后，才用 `approve-plan` 登记实际确认文字。用户的修改意见用于更新教案。
4. 正式构建。配音、动画和板书按实测时间复查。交付视频、学生讲义、板书 PDF 和可编辑 TikZ。字幕可另外导出。查看 `delivery-files.json` 确认学生可打开每个文件。

```sh
python3 SKILL/scripts/course.py preview PROJECT --renderer manim
python3 SKILL/scripts/course.py review-plan PROJECT
python3 SKILL/scripts/course.py approve-plan PROJECT --feedback '审阅者确认当前版本，可以制作'
python3 SKILL/scripts/course.py build PROJECT --video
```

确认绑定当时的课程、口播、教案、片头与所列图文资料。改动后重新确认。只有特定引擎才能显示的动画使用对应引擎预览。草稿使用独立预览目录与估算时间。

## 片头

新课片头约三秒，显示课名和作者信息。可在课程源配置 `opening.title`、`opening.author`、`opening.school`、`opening.contact`。有本地作者资料时从技能目录的 `author-profile.local.json` 读取，课程显式的 `opening` 优先。公开模板使用通用字段，本地姓名和联系方式在构建该课时进入作者片头。
