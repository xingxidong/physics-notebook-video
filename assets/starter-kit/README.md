# 下载后先跑这份样例

安装后可先重放斜面示例，再按需要打开试音句、备课模板和动画。五组材料均可编辑，随技能一起安装和打包。

| 材料 | 入口 | 可以做什么 |
|---|---|---|
| 一页 PDF 到成片 | [斜面样例](incline/README.md) | 对照原题、转写、TikZ、讲稿与成片；复用随包音频重新渲染 |
| 固定试音句 | [试音说明](voice-trial/README.md) | 用同一组完整课堂句比较模型与音色，逐处查读音和连贯性 |
| 三种配音配置 | voice-trial/local-qwen.json、external-minimax.json、recordings.json | 本地合成、外部接口、已有录音；保留实际输入与返回音频记录 |
| 两份长课模板 | [90/180 分钟备课](long-lessons/README.md) | 改讲义位置、重点、练习和时间分配，先提交教案 |
| 三组参数动画 | [碰撞、磁场、薄膜](animations/README.md) | 改参数后重算图、箭头、公式与 TikZ，并在浏览器中演示 |

```sh
# PHYSICS_SKILL 指向安装目录，Python 环境已安装 assets/requirements.txt，FFmpeg 已在 PATH。
python3 "$PHYSICS_SKILL/scripts/sample_kit.py" render /ABS/EMPTY/demo
# 已配置相应引擎时，也可以加 --renderer motion-canvas 或 --renderer manim。
```

重放示例时，直接用安装包里的音频，无需配音服务或文本模型。运行后会得到 video.mp4、方格笔记本板书、时间轴和 HTML 预览。换成自己的题目后，先审教案、查术语读音，再查看成片。

授权与音频来源见 [LICENSE.md](LICENSE.md)。这些材料中没有附教师真人参考录音。
