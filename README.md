# popup-book-video · 立体书动画视频生成器

输入一个名称或一段文字描述，自动生成一段「立体书」风格的动画视频：

> 一张摊开的手绘地图上，树木、房屋、人物等物体**从纸面逐个"立起来"**，变成 3D 立体场景，停留片刻后再**逐个倒下消失**，配竖排字幕与古风配乐。

效果参考：诗词《陋室铭》——山不在高→松树、小屋、瀑布、隐士、小桥依次立起→成景→倒下→切换下一句。

![效果示意](https://img.shields.io/badge/风格-立体书%20%2F%20纸艺%20%2F%20水彩-orange) ![视频规格](https://img.shields.io/badge/输出-1280x720%2030fps-blue) ![许可](https://img.shields.io/badge/license-MIT-green)

## 🎬 DEMO ·《陋室铭》

点击封面图查看/下载完整成片（47 秒，1280×720，约 28 MB）：

[![陋室铭立体书动画 DEMO](demo/cover.jpg)](https://github.com/iithink88/popup-book-video/raw/main/demo/loushiming.mp4)

> 六场景依次呈现：山林茅屋 → 水潭青龙 → 陋室读书 → 青苔白鹤 → 文人谈笑 → 月夜抚琴。每场景中松树、小屋、瀑布、隐士等物体从平面地图逐个立起，停留后逐个倒下，再切换下一场景。配乐为五声音阶古筝 + 竹笛，字幕为《陋室铭》原文竖排。

该 DEMO 由本技能的 `examples/陋室铭.json` 剧本生成，素材脚本与配置均已随仓库提供。

## 它能做什么

| 输入 | 例子 |
|---|---|
| 单一名篇 | 「陋室铭」「赤壁赋」「荷塘月色」 |
| 一段描述 | 「描写春天校园，有花坛、操场、教学楼」 |
| 一个主题 | 「介绍诸葛亮的一生」「校园噪音调查」 |

输出：40~60 秒 MP4（H.264 + AAC），含片头标题、竖排字幕、印章、暗角、五声音阶配乐。

## 安装

### 方式一：作为 WorkBuddy 技能安装（推荐）

把本文件夹整个复制到技能目录：

- Windows：`C:\Users\<你的用户名>\.workbuddy\skills\popup-book-video\`
- macOS / Linux：`~/.workbuddy/skills/popup-book-video/`

复制后在 WorkBuddy 里说一句「把《陋室铭》做成物体立起来的立体书视频」即可触发。技能目录名必须是 `popup-book-video`（与 SKILL.md 的 name 一致）。

### 方式二：手动使用脚本

不装技能也能用脚本，按下方「使用流程」自己写 `story.json` 并依次执行命令。

## 环境依赖

| 依赖 | 说明 |
|---|---|
| Python 3 | 需 `Pillow`、`numpy`、`scipy`。安装：`pip install pillow numpy scipy` |
| ffmpeg | 需在 PATH 中（`ffmpeg -version` 能跑通） |
| 中文字体 | Windows 自带楷体/仿宋；macOS/Linux 需 Noto CJK 等中文字体（脚本内置路径表，可自行改） |
| 图片生成工具 | 生成底板与物体插画（如 WorkBuddy 内置 ImageGen、或任意能出图的 AI 工具） |

## ⚠️ 成本提示

一套 6 场景视频需生成约 **42 张 AI 图片**（6 张底板 + 36 个物体），每张约 5~10 积分，**合计约 210~420 积分**。请确认额度后再开始生成。

## 使用流程（6 步）

完整规则见 `SKILL.md`，字段说明见 `references/`，下面速览：

**1. 写剧本 `story.json`**
按 `references/writing-guide.md` 把主题拆成 6 场景，结构照抄 `examples/陋室铭.json` 改。核心字段：场景底板提示词 `bg`、字幕 `text`、物体列表 `objects`（含名称 `prompt`、坐标 `cx/cy`、高度 `h`、出场顺序 `delay`）。

**2. 校验并生成素材清单**
```bash
python scripts/validate_story.py story.json --list
```
输出逐张图片清单（提示词已自动拼好绿幕后缀）。

**3. 生成插画**
按清单逐张生成，目录结构严格如下：
```
layers/
  s1/bg.png              ← 底板（1536×1024，俯视空白地图）
  s1/house/house.png     ← 每个物体单独子目录（1024×1024，纯绿幕背景）
  s2/...
```

**4. 抠图（绿幕→透明，去水印）**
```bash
python scripts/process_layers.py .
```

**5. 配乐**
```bash
python scripts/audio.py story.json .
```

**6. 渲染**
```bash
# 先出静帧验证排版（强烈建议）
python scripts/render.py story.json . --still 18 --outdir .
# 确认无误后渲全片
python scripts/render.py story.json .
```

## 想调整？

| 想改什么 | 改哪里 |
|---|---|
| 字幕文字 | `story.json` → `scenes[i].text` |
| 物体位置/大小 | `story.json` → `scenes[i].objects[j].cx/cy/h` |
| 弹出顺序 | `delay`（数值小的先立起） |
| 音乐风格 | `style.mood`（elegant/serene/joyful/mystic/epic）、`style.scale` |
| 立起/倒下节奏 | `scripts/render.py` 顶部 `RISE_START` / `RISE_SPAN` / `FALL_START` |

## 文件结构

```
popup-book-video/
├── SKILL.md                      WorkBuddy 技能工作流
├── README.md                     本说明
├── LICENSE                       MIT 许可
├── examples/
│   └── 陋室铭.json                6 场景完整剧本样例
├── references/
│   ├── story-schema.md           字段全表 + 坐标速查
│   └── writing-guide.md          从名称/描述拆场景的方法
└── scripts/
    ├── validate_story.py         剧本校验 + 素材清单
    ├── process_layers.py         绿幕抠图 + 去水印
    ├── audio.py                  五声音阶配乐合成
    └── render.py                 通用渲染引擎
```

## 许可

MIT —— 自由使用、修改、分发，请保留署名。
