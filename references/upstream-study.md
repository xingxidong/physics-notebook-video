# 上游研究与采纳记录

研究时间：2026-11-08 至 2026-11-09。优先研究用户点名的项目。以下关注度为对应 GitHub API 快照，后续会变化。

| 项目 | 星标/分支 | 对本项目的价值 |
|---|---|---|
| [wy51ai/edulab](https://github.com/wy51ai/edulab) | 1767 stars、388 forks；最近推送2026-10-23 | 主参考：物理对象、过程分段、规律选择、图解、口播、数学读音、语音后端、真实音频时间轴 |
| [liangdabiao/whiteboard-teacher-video](https://github.com/liangdabiao/whiteboard-teacher-video) | 516 stars、70 forks；最近推送2026-11-08 | 补充参考：按时间纯函数回放、关键词落点、单页缓存、过程截图 |
| [haiderfarooq3/khan-explainer](https://github.com/haiderfarooq3/khan-explainer) | 156 stars、31 forks；读取提交 `326bf9b5332bb30a09e9d11f0ba81e30e7a0e81f` | 补充参考：语句片段驱动画笔、整板累积、逐片段总览图和本地渲染 |

读取固定版本：edulab `805fdc5dd6bdf942290a7791924bf0ee08f26632`；whiteboard-teacher-video `834902a813f9831cb6638aa2d2c5f18b5819cb04`。

## edulab 为主

已读 edu-physics-video 的 SKILL、physics-solving、script-writing、visual-design、pronunciation，以及 phys.js、engine.js、build_audio.py、render.mjs；进一步读 edu-math-video/shared/tts.py 与 tts-setup，了解 GLM、豆包和 MiniMax 的共享实现。

采纳：先完成物理解，再安排图示和口播；正常公式与朗读文本分开；画面按真实音频时间点推进；把读音与物理图示当作课程制作的一部分。保留一个主推导，按本用户偏好在过程内配图与解释。

本次也看到需要结合物理情境判断的地方：旧版说明中把“物体运动反向”和“摩擦力反向”连写，实际应由接触双方的相对运动或趋势确定。新技能按相对运动建模。固定的37度近似只在题目指定近似时采用。

engine.js 中的 txt 使用 `fillText(chars.slice(...))`，是手写字体逐字显现。当前用户要求笔画逐笔写出，因此保留本项目真实中心线笔画与汉字笔顺数据。它的蓝图、配乐和每幕连续运动要求，按具体课程需要选择；本用户默认安静的笔记本板书。

## whiteboard-teacher-video 的补充作用

已读 SKILL、分镜、脚本与页面 API、配音后端、缓存/渲染与检查脚本、setup 和许可归属。

采纳它的时间函数、关键词锚点与分段缓存原则。本版用本地 Python 笔画渲染，缓存键包括影响输出的页面、局部时间、声音、引擎与输出设置。保留当前被用户接受的真实逐笔外观。

该项目的包装代码为MIT，上游 Frametell 引擎为AGPL。此技能没有复制该引擎或安装它；复用的是本对话已完成的本地渲染代码。edulab 的仓库许可为Apache-2.0，本版为独立实现与流程借鉴。

## khan-explainer 的补充作用

已读 README、SKILL、Canvas 绘制层、渲染程序、中文测试和持续集成。采纳“先规划完整画板、同一问题累积呈现、语句片段按实测声音长度驱动画笔、每个片段结束生成检查图”的工作方式。

该项目的中文 `write` 使用 Canvas 字体整体排版后逐步揭示，没有汉字笔顺路径；公式也没有 LaTeX 排版层。当前技能继续使用自身的汉字中心线笔画、公式布局、MiniMax 配音和页面缓存。长课按完整问题分页，并用主 Agent 加章节 Agent 的课程合同保持符号、口播和图形一致。没有复制 khan-explainer 源码。

## 微信范例

用户提供：

- https://mp.weixin.qq.com/s/bpcPqIyND_4nVkj-knhLzA
- https://mp.weixin.qq.com/s/ffDkSg-oQso7_sArvaoU2Q

这次网页请求均返回微信“环境异常，完成验证后即可继续访问”；浏览器工具也未成功取得文章正文。随后用户提供了两份本地视频，已经提取关键帧、分析画面阶段，并用本地 Whisper 转写口播。范例特征记录在 `reference-cases.md`，原始视频与音频未打包进技能。

已确认仓库README中的公众号入口与二维码，并确认物理技能使用GLM-TTS；共享语音模块支持更多后端。公众号某条成片是否采用相同后端、哪个音色，当前资料尚未确定。
