# 从教案审阅到交付

出教案前和成片后分别运行 `quality-check --stage plan` 与 `quality-check --stage final`，用[制作检查清单](quality-workflow.md)逐项修复和回听。预览或出教案期间若源文件改变，当前输出会提示重新生成，以便整套审阅材料对应同一个版本。

正式新课和习题课先走[八步制作流程](production-workflow.md)。教案写教学目标、实际重点、讲解依据、每段时间。板书优先在一页内讲完一组完整物理关系。习题课呈现完整题面、图、推导和结果。讲义以 LaTeX 排版、TikZ 配图，逐页读实际 PDF。

1. 看本课模型的开场、接触前后、极值、转折和结束。核对接触点、轨迹、运动方向和标注位置。
2. 用[内置文案技能](classroom-language-editing.md)改教案、板书、学生讲义和完整讲稿，以 `review-language` 登记对应文件。按正常语速录制本课试音，使用计划用于成片的音色。
3. 用 `review-packet` 列出 `教案.md`、`完整讲稿.md`、板书 PDF、动画 MP4、学生讲义 PDF 和本课实录试音。把能直接阅读、观看和试听的材料发给用户。收到对整套的确认后运行 `approve-plan`，照录用户原话。修改材料就重新提交确认。
4. 用 `build --video` 开始正式配音和合成。候选片经实音和画面逐处检查才交付，操作见[最终交付](production-workflow.md#最终交付)。

送审批次绑定课程、稿件、动画、讲义和录音。草稿使用独立预览目录与估算时间，正式渲染沿用已审动画的引擎。

## 片头

新课片头约三秒，显示课名和作者信息。可在课程源配置 `opening.title`、`opening.author`、`opening.school`、`opening.contact`。有本地作者资料时从技能目录的 `author-profile.local.json` 读取，课程显式的 `opening` 优先。公开模板使用通用字段，本地姓名和联系方式在构建该课时进入作者片头。
