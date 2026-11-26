# 从教案审阅到交付

出教案前和成片后分别运行 `quality-check --stage plan` 与 `quality-check --stage final`，用[制作检查清单](quality-workflow.md)逐项修复和回听。预览或出教案期间若源文件改变，当前输出会提示重新生成，以便整套审阅材料对应同一个版本。

新项目的 `review_required:true` 在正式配音与渲染前启用人审。课程先规划一课主问题、可观察的目标、先修知识、重点、难点、讲法和每段时间。板书按每页要让学生理解的一条关系安排。习题课把完整题面、图、推导和结果写进同一套教案。

1. 写好课程源、完整口播和学生讲义。新授课与习题课按[讲义编写与排版](handouts.md)分别组织内容，统一使用 LaTeX 排版、TikZ 配图。编译并逐页查看实际 PDF，保持题面、板书、讲义和图的符号一致。显式设置 `handout:"学生讲义.pdf"`，把实际参与编译的 LaTeX、TikZ、样式和插图逐个加入 `review_assets`。初始化示例的 `讲义.md` 作为草稿继续整理。
2. 有原生 Manim 或 Motion Canvas 动画时先生成无配音预览。开场、接触前后、运动峰值、转折及结束均查看画面，对照接触点、轨迹、速度方向、文字位置。抽样边界检查见[板书排版](board-layout.md)。把正常接触与确实穿模的情况区分清楚，按图里的物理条件调整。
3. 按[课堂文案改稿](classroom-language-editing.md)复读完整讲稿和学生讲义。用 `review-plan` 输出 `教案.md` 和 `review-preview/`，根据口播句编号和讲义行号修改后再生成。给人看完整口播、重难点、板书关键帧、片头和学生讲义。收到修改意见先改教案源、讲稿或动画，再出新的教案。审阅者明确同意当前版本后，用 `approve-plan` 登记实际确认文字。
4. 正式构建后先得到 `delivery-candidate.json` 待审清单。对实际要交付的 MP4 运行 `quality-check --stage final --video-file 文件名`，逐处完成术语、字母、句间衔接及口播落笔检查。制作者把实际观看、试听结果登记到对应检查项；修订后重新检查受影响内容。
5. 所有检查完成后运行 `finalize --video-file 文件名`，生成 `delivery-files.json`。交付视频、学生讲义 PDF、完整 LaTeX/TikZ 源码及依赖素材、板书 PDF，确认每个文件可打开。具体登记命令见 [制作流程](production-workflow.md)。

```sh
python3 SKILL/scripts/course.py preview PROJECT --renderer manim
python3 SKILL/scripts/course.py review-plan PROJECT
python3 SKILL/scripts/course.py approve-plan PROJECT --feedback '审阅者确认当前版本，可以制作'
python3 SKILL/scripts/course.py build PROJECT --video
```

确认绑定当时的课程、口播、教案、片头与所列图文资料。改动后重新确认。只有特定引擎才能显示的动画使用对应引擎预览。草稿使用独立预览目录与估算时间。

## 片头

新课片头约三秒，显示课名和作者信息。可在课程源配置 `opening.title`、`opening.author`、`opening.school`、`opening.contact`。有本地作者资料时从技能目录的 `author-profile.local.json` 读取，课程显式的 `opening` 优先。公开模板使用通用字段，本地姓名和联系方式在构建该课时进入作者片头。
