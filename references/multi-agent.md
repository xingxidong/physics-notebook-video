# 长课的多 Agent 工作流

这一模式用于目标时长超过 45 分钟、页面超过约 18 页，或一批课程需要同时制作的任务。短课继续由一个 Agent 完成，减少重复读取与合并成本。

## 组织方式

使用一个主 Agent 和最多三个并行章节 Agent。主 Agent负责课程合同、原始资料切分、最终合并、正式配音与交付；章节 Agent 各自负责一个连贯教学段，同时完成物理推导、口播、板书动作和 TikZ。不要把同一页面拆成“物理 Agent、文案 Agent、板书 Agent”，这种交接容易使图、公式和讲解脱节。

执行顺序：

1. 主 Agent 阅读完整讲义，确定学生基础、课程目标、时长、符号表、章节连接和页面政策。
2. 用 `team.py init` 固定课程合同与章节任务包。
3. 把不同章节目录交给并行 Agent；每个 Agent 只读所需原文，只写自己的目录。
4. 主 Agent 运行 `team.py validate`，处理符号、新增内容、页面完整性、重复 ID，并提前检查板书动作、字形和几何范围。
5. `team.py merge` 确定性生成最终 `lesson.json`。
6. 顺序运行 `course.py check` 与 `course.py build --draft`，查看页面和过程截图。
7. 文稿与板书定稿后运行 `team.py build-final`；程序先执行严格时长门，再统一调用正式 TTS 并渲染视频。

正式 TTS 只在合并定稿后运行。章节 Agent 不调用付费语音，不直接修改项目根目录的 `lesson.json`，也不修改其他章节目录。

## 建立课程合同

复制 `assets/team-plan.example.json` 到课程工作区并填写。课程目标时长应等于各章节目标时长之和；`minimum_minutes` 是正式成片的最低时长。

```sh
python3 SKILL/scripts/team.py init PROJECT --plan PROJECT/team-plan.json
python3 SKILL/scripts/team.py status PROJECT --fail-on-error
```

生成结构：

```text
PROJECT/
├── team/
│   ├── course-contract.json
│   ├── manifest.json
│   └── sections/
│       ├── section-a/
│       │   ├── assignment.json
│       │   ├── AGENT_PROMPT.md
│       │   └── fragment.json
│       └── section-b/
└── team-plan.json
```

`course-contract.json` 是全课唯一标准。`assignment.json` 同时记录 `project_root`、`skill_root`、原文输入值和解析后路径；`AGENT_PROMPT.md` 含可直接复制的校验命令。需要增加新符号、修改目标或改变共同口播风格时，由主 Agent 更新合同，再通知受影响章节；章节 Agent 不自行建立第二套符号约定。

## 章节交付格式

章节 Agent 读取本目录的 `assignment.json`，写出 `fragment.json`。示例：

```json
{
  "section_id": "model",
  "summary": "从火车过隧道进入质点模型",
  "bridge_in": "从初中速度计算接入研究对象",
  "bridge_out": "保留位置和方向，交给下一段矢量学习",
  "symbols_used": ["x"],
  "pages": [
    {
      "id": "s01-train-model",
      "title": "内部编辑名称",
      "board_unit": "火车完全通过隧道",
      "complete_on_page": true,
      "source_refs": ["chapters/week01/day01-intro.tex"],
      "cues": [
        {
          "id": "s01-train-model-enter",
          "tts": "先把火车完整通过隧道的过程画出来。",
          "text": "先画出火车完整通过隧道的过程。",
          "pause": 0.8,
          "actions": [
            {
              "type": "arrow",
              "from": [220, 300],
              "to": [620, 300],
              "color": "blue"
            }
          ]
        }
      ]
    }
  ]
}
```

页面 ID 使用任务包提供的 `page_prefix`；cue ID 以页面 ID 加连字符开头。实际页面至少有一个绘图动作。`board_unit` 表明本页要完整解决的问题或概念，`complete_on_page:true` 表示图、推导和结论均落在本页。确需跨页时设置 `complete_on_page:false` 并填写具体的 `continuation_reason`，下一页第一段直接承接已得到的物理关系。

每个章节同时保留文字讲义片段和可编辑 TikZ。`fragment.json` 的页面使用现有 [课程格式](lesson-format.md)，合并后由原有编译器处理。

## 校验与合并

```sh
python3 SKILL/scripts/team.py validate PROJECT
python3 SKILL/scripts/team.py merge PROJECT
python3 SKILL/scripts/course.py build PROJECT --draft
```

`team.py validate` 检查章节是否齐全、页面与 cue ID 是否冲突、符号是否属于共同符号表、每页是否完成一个板书单元，同时调用课程编译器检查动作、字形、参数、语音时间锚点和几何范围。估算口播时长只用于发现内容缺口；正式时长以实测配音和最终 MP4 为准。

章节定稿前再运行一次严格时长检查；估算不足最低时长 85% 时停止：

```sh
python3 SKILL/scripts/team.py validate PROJECT --strict-duration
```

`team.py merge` 只会覆盖先前由它自己生成的 `lesson.json`。项目中已有手写 `lesson.json` 时，它会停止并要求另选输出路径，防止覆盖既有课程。

定稿后使用正式入口；它会自动运行严格时长门与合并，通过后才会产生配音费用：

```sh
python3 SKILL/scripts/team.py build-final PROJECT --renderer motion-canvas --width 1920
```

## 给章节 Agent 的上下文

只传四类信息：`assignment.json`、对应原文、上一段的输出关系、下一段需要接收的关系。不要让每个 Agent 读取整本书、完整技能源码或其他章节草稿。这样可以降低重复 token，也能保持各章节边界清楚。

章节 Agent 的任务说明使用生成的 `AGENT_PROMPT.md`。启动时明确告诉它：它与其他 Agent 同时工作，只拥有自己的章节目录，不撤销其他人的修改。主 Agent 等待全部章节完成后再合并。

## 最终质量门

合并后按顺序完成：

1. 物理对象、条件、符号、方向和结论贯穿全课一致。
2. 每个例题和练习在题设与解题过程都有配图和对应 TikZ。
3. 一个问题尽量在一页完成；换页发生在结论或明确中间关系之后。
4. 前一章节的 `bridge_out` 能自然进入后一章节的 `bridge_in`。
5. 预览、板书 PDF、字幕和 MP4 使用同一版口播与课程源。
6. 最终 MP4 的实测时长达到 `minimum_minutes`：

```sh
python3 SKILL/scripts/team.py verify-video PROJECT --video PROJECT/video-captioned.mp4
```

`team/merge-report.json` 中并排保留合同与片段的 `bridge_in` / `bridge_out`，主 Agent 据此读一次章节连接。
