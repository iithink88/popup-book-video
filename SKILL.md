---
name: popup-book-video
description: 生成"立体书"风格动画视频：一张俯视的平面地图上，树木、房屋、人物等物体依次从纸面"立起来"变成 3D 立体场景，停留后再逐个倒下消失。当用户给出名称或一段文字描述并要求制作此类视频时使用，例如"做个陋室铭立体书视频""把这段描写做成物体立起来的立体书动画""用立体书形式呈现春天校园"。也适用于诗词、散文、写景段落、历史事件的可视化。用户提到"立体书""pop-up book""物体立起来""平铺变立体""纸艺动画"时同样触发。
agent_created: true
---

# 立体书动画视频

## Overview

把任意主题（诗词、散文、写景段落、事件）转成一段 40~60 秒的立体书动画：画面是一张摊开的手绘地图，物体逐个从纸面弹出立起、停留、再逐个倒下，配竖排字幕和五声音阶古风配乐。全程纯代码渲染，无需视频素材，只需 AI 生成分层插画。

**典型效果**：山不在高→松树、小屋、瀑布、隐士、小桥依次立起→全立成景→倒下→切下一句。

## 成本提示（必须先告知用户）

生成一套 6 场景需要约 42 张 AI 图片（6 底板 + 36 物体），ImageGen 每张约 5~10 积分，**合计约 210~420 积分**。在开始生成前明确告知用户该消耗。若用户只想看效果，可先做"重点场景分层"或单场景样片。

## 环境依赖

- Python（推荐 WorkBuddy 托管 venv：`~/.workbuddy/binaries/python/envs/default/Scripts/python.exe`），需 `Pillow numpy scipy`
- `ffmpeg`（PATH 中）
- 中文字体：Windows 用 `C:/Windows/Fonts/simkai.ttf` 等（脚本已内置路径表）
- 图片生成工具（ImageGen）与视频编码工具（ffmpeg CLI）

## Workflow

### Step 1 — 解析主题，编写 story.json

把用户输入翻译成剧本配置。阅读 `references/writing-guide.md` 了解拆场景、写字幕、定坐标的方法，按 `references/story-schema.md` 的字段结构写 JSON。可直接复制 `examples/陋室铭.json` 改造。

要点：
- 6 场景，每场景 5~6 个物体；字幕用原文分句或自写的 6~12 字短句
- 底板提示词只写空白地形，**不能出现要立起的物体**
- 物体 `prompt` 只写物体本身（绿幕后缀脚本自动加）
- `delay` 严格递增（0.05 起，每次 +0.3~0.35）
- 优先把 story.json 存到工作目录，例如 `<项目>/story.json`

写完后校验：
```bash
python scripts/validate_story.py <项目>/story.json --list
```
根据输出的素材清单核对提示词（清单已自动附上绿幕后缀）。

### Step 2 — 生成底板与物体插画（AI 图片）

按 `validate_story.py --list` 的清单逐张生成，目录结构严格如下：

```
<项目>/layers/
  s1/bg.png                    <- 底板（文件名含"底板"即可，脚本会归一化为 bg.png）
  s1/<key>/<key>.png           <- 每个物体单独一个子目录，一张绿幕图
  s2/...
```

调用图片生成工具时的 prompt 规则：
- **底板**：用 story.json 的 `bg` 原文，尺寸 `1536x1024`
- **物体**：用清单里已拼好后缀的 prompt（`物体描述 + 绿幕风格后缀`），尺寸 `1024x1024`
- 图片工具若返回中文长文件名，脚本靠目录名识别 key，无需手动重命名

> 提示：可并行批量生成（每批 3~6 张）加快速度。生成前确认用户已知积分消耗。

### Step 3 — 抠图（绿幕转透明 + 去水印）

```bash
python scripts/process_layers.py <项目>
```
脚本会：底板归一化为 `bg.png`；每个物体绿幕抠成透明、清除右下角 AI 水印、裁到内容边界，输出 `sN/<key>.png`。检查打印的每物体尺寸是否正常（过小可能是抠错）。

### Step 4 — 合成配乐

```bash
python scripts/audio.py <项目>/story.json <项目>
```
按 `style.mood`/`style.scale` 自动谱曲，输出 `<项目>/music.wav`。

### Step 5 — 渲染成片

先出静帧确认排版（强烈建议，避免渲完整片才发现坐标问题）：
```bash
python scripts/render.py <项目>/story.json <项目> --still 18 --outdir <项目>
python scripts/render.py <项目>/story.json <项目> --still 40 --outdir <项目>
```
用图片查看工具检查静帧：物体是否贴地、是否被裁切、字幕是否遮挡主体。有问题就改 story.json 的坐标/高度，回到 Step 2 只重生成受影响的图。
确认无误后渲染全片：
```bash
python scripts/render.py <项目>/story.json <项目>
```
输出 `<项目>/<output_name>`（H.264 + AAC，1280×720/30fps）。

### Step 6 — 校验与交付

```bash
# 参数与音量
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height -of default=noprint_wrappers=1 <成片>
ffmpeg -hide_banner -i <成片> -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
# 抽几帧看转场与全立
ffmpeg -y -ss 7 -i <成片> -frames:v 1 -q:v 2 <项目>/check.jpg
```
- 音量参考：均值约 -16dB、峰值约 -3dB 即正常
- 抽帧确认无黑帧/闪烁、物体立起顺序正确、字幕清晰
- 把成片复制到用户桌面或工作区显眼位置，并用交付工具展示
- 生成一张封面：`ffmpeg -y -ss <中间秒> -i <成片> -frames:v 1 -q:v 2 <项目>/cover.jpg`

## 调整速查

| 想改什么 | 改哪里 |
|---|---|
| 字幕文字 | story.json `scenes[i].text` |
| 物体位置/大小 | story.json `scenes[i].objects[j].cx/cy/h` |
| 弹出顺序 | `delay` 数值（小=先立） |
| 音乐风格/调式 | `style.mood` / `style.scale`，重跑 Step 4 |
| 场景数量 | 增删 `scenes`，需同步重生成素材 |
| 立起/倒下节奏 | `scripts/render.py` 顶部 `RISE_START/RISE_SPAN/FALL_START` 常量 |

## Resources

- `scripts/render.py` — 通用渲染引擎（读 story.json，Ken Burns + 逐物体立起/倒下 + 竖排字幕 + 暗角 + ffmpeg 管道）
- `scripts/audio.py` — 五声音阶配乐合成（mood/scale/duration 参数化）
- `scripts/process_layers.py` — 绿幕抠图、去水印、裁切、批量命名
- `scripts/validate_story.py` — story.json 校验 + 素材生成清单
- `references/story-schema.md` — 字段全表、坐标速查、最小示例
- `references/writing-guide.md` — 从名称/描述拆场景、写提示词、定坐标的方法
- `examples/陋室铭.json` — 6 场景完整剧本样例
