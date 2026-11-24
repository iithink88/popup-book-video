# -*- coding: utf-8 -*-
"""校验 story.json 并输出素材生成清单（供逐张调用图片生成工具）。

用法：
  python validate_story.py <story.json> [--list] [--json]

输出：
  - 结构校验（场景数、物体数、坐标范围、delay 单调性、水印禁令）
  - --list: 逐张列出需要生成的图片（底板 + 物体）及提示词
  - --json: 以 JSON 输出清单，便于程序化处理
"""
import os
import sys
import json
import argparse

STYLE_TAIL = "，手绘水彩与纸艺立体质感，中国风卡通绘本，等距俯视45度，独立物体居中，纯绿色背景便于抠图，无地面无阴影无文字水印"


def validate(story):
    errs, warns = [], []
    if "scenes" not in story or not isinstance(story["scenes"], list):
        errs.append("缺少 scenes 数组")
        return errs, warns
    scenes = story["scenes"]
    if not (3 <= len(scenes) <= 10):
        warns.append(f"场景数 {len(scenes)}，推荐 6（3~10）")
    total_objs = 0
    for si, sc in enumerate(scenes, 1):
        if not sc.get("bg"):
            errs.append(f"s{si}: 缺少 bg 底板提示词")
        if "text" not in sc:
            warns.append(f"s{si}: 无字幕")
        objs = sc.get("objects", [])
        total_objs += len(objs)
        if not (3 <= len(objs) <= 8):
            warns.append(f"s{si}: 物体数 {len(objs)}，推荐 5~6")
        keys = set()
        delays = []
        for o in objs:
            k = o.get("key")
            if not k:
                errs.append(f"s{si}: 物体缺 key")
                continue
            if k in keys:
                errs.append(f"s{si}: key 重复 {k}")
            keys.add(k)
            if not (0 <= o.get("cx", -1) <= 1536 and 0 <= o.get("cy", -1) <= 1024):
                warns.append(f"s{si}/{k}: 坐标 cx/cy 超出 1536x1024 范围")
            if not (60 <= o.get("h", 0) <= 500):
                warns.append(f"s{si}/{k}: h={o.get('h')} 超出推荐 60~500")
            delays.append(o.get("delay", 0))
        if delays != sorted(delays):
            warns.append(f"s{si}: delay 非递增，物体弹出顺序按 delay 数值")
    est = (len(scenes) + total_objs)
    warns.append(f"预计需生成 {est} 张图，约消耗 {est * 5}~{est * 10} 积分（ImageGen 每张 5~10 积分）")
    return errs, warns


def build_manifest(story):
    items = []
    for si, sc in enumerate(story["scenes"], 1):
        items.append({
            "scene": si, "type": "bg", "key": "bg",
            "path": f"layers/s{si}/bg.png",
            "size": "1536x1024",
            "prompt": sc["bg"],
        })
        for o in sc["objects"]:
            items.append({
                "scene": si, "type": "object", "key": o["key"],
                "path": f"layers/s{si}/{o['key']}/{o['key']}.png",
                "size": "1024x1024",
                "prompt": o["prompt"] + STYLE_TAIL,
            })
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    with open(args.story, "r", encoding="utf-8") as f:
        story = json.load(f)

    errs, warns = validate(story)
    if not args.json:
        print("=== 校验 ===")
        for e in errs:
            print("  [ERROR]", e)
        for w in warns:
            print("  [WARN ]", w)
        if not errs:
            print("  OK: story.json 结构有效")

    manifest = build_manifest(story)
    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    elif args.list:
        print(f"\n=== 素材清单（{len(manifest)} 张）===")
        for it in manifest:
            print(f"\n[{it['scene']}] {it['type']:6s} {it['key']:10s} {it['size']}")
            print(f"    -> {it['path']}")
            print(f"    {it['prompt']}")

    if errs:
        sys.exit(1)


if __name__ == "__main__":
    main()
