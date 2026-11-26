# 一页讲义到一段成片

原题为本项目新编的固定光滑斜面题，配音约 90 秒，整片加上片头与自然句界约 96 秒。

1. `source.pdf`、`source.tex`：一页原题及其可编辑源。
2. `transcription.json`、`statement.md`、`input-manifest.json`：逐项转写、题设条件、来源指纹及建模依据。
3. `incline.tikz`、`forces.tikz`：题设图和推导中使用的受力图。
4. `script.md`、`lesson.json`：完整讲稿与落笔安排，含片头、运动、受力、六步推导和总结。
5. `audio/`、`audio-provenance.json`：固定公开合成音色、实际送入文字、原速时长与文件哈希。
6. `demo.mp4`、`board-preview.png`、`preview.html`：已经渲染的样例、方格笔记本板书和浏览器预览。
7. `student.pdf`、`student.tex`：一页学生讲义；题设图和受力图放在相应的推导位置。

运行 `python3 SKILL/scripts/sample_kit.py render /ABS/EMPTY/demo` 可从随包音频重放一次。脚本只接受指纹相符的固定样例，输出 `demo-replay.json`，不冒充新课的人审记录或正式交付清单。改题后复制工程，用正常 `course.py review-plan` 流程制作。

模型按匀加速关系计算位移，方块底边始终贴在斜面。题面先出现，再指图讲解。声音是 Kokoro 公开合成音色，并非作者个人音色；音频来源有明确记录，听感仍由实际试听判断。示例的词锚点按整句时间安排，制作自己课程时继续检查口播与落笔。

XeLaTeX 编译 source.tex 或 student.tex；优先使用本机 Songti SC，否则使用 FandolSong-Regular.otf。所需中文字体由自己的 TeX/字体环境提供，不附系统商业字体。
