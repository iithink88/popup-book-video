# -*- coding: utf-8 -*-
"""批量处理分层素材：底板归一化命名 + 物体绿幕抠图 + 去水印 + 裁到内容边界。

用法：
  python process_layers.py <workdir> [--nscenes N]

<workdir>/layers/s1..sN/ 结构：
  - 底板图（文件名含「底板」或 bg.png） -> 统一为 bg.png
  - 每个物体一个同名子目录，内含一张绿幕图 -> 抠图为 <key>.png（透明）
"""
import os
import glob
import argparse
import numpy as np
from PIL import Image, ImageFilter


def chroma(im):
    """绿幕抠图 + 清除右下角 AI 水印"""
    a = np.array(im.convert("RGBA")).astype(np.int16)
    rgb = a[:, :, :3].copy()
    h, w = rgb.shape[:2]
    corners = np.concatenate([
        rgb[:10, :10].reshape(-1, 3), rgb[:10, -10:].reshape(-1, 3),
        rgb[-10:, :10].reshape(-1, 3), rgb[-10:, -10:].reshape(-1, 3),
    ])
    ref = np.median(corners, axis=0)
    # 把右下角水印区涂成绿幕色（水印固定在右下角）
    wx0, wy0 = int(w * 0.76), int(h * 0.84)
    rgb[wy0:, wx0:] = ref.astype(np.int16)
    key = ((rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2]) > 15) &
           (np.linalg.norm(rgb - ref, axis=2) < 95))
    alpha = np.where(key, 0, 255).astype(np.uint8)
    img = Image.fromarray(alpha, "L").filter(ImageFilter.GaussianBlur(1.5))
    out = im.convert("RGBA")
    out.putalpha(img)
    return out


def crop_content(im, pad=6):
    a = np.array(im.getchannel("A"))
    ys, xs = np.where(a > 40)
    if not len(xs):
        return im
    x0, x1 = max(0, xs.min() - pad), min(im.width, xs.max() + pad)
    y0, y1 = max(0, ys.min() - pad), min(im.height, ys.max() + pad)
    return im.crop((x0, y0, x1, y1))


def process(workdir, nscenes):
    root = os.path.join(workdir, "layers")
    for si in range(1, nscenes + 1):
        sd = os.path.join(root, f"s{si}")
        if not os.path.isdir(sd):
            print(f"  s{si}: MISSING DIR")
            continue
        # 底板归一化
        bgs = [f for f in glob.glob(os.path.join(sd, "*.png"))
               if "底板" in os.path.basename(f) or os.path.basename(f) == "bg.png"]
        bg_dst = os.path.join(sd, "bg.png")
        if bgs and os.path.abspath(bgs[0]) != os.path.abspath(bg_dst):
            if os.path.exists(bg_dst):
                os.remove(bg_dst)
            os.rename(bgs[0], bg_dst)
        # 物体子目录
        for sub in sorted(glob.glob(os.path.join(sd, "*") + os.sep)):
            key = os.path.basename(os.path.normpath(sub))
            imgs = glob.glob(os.path.join(sub, "*.png"))
            if not imgs:
                print(f"  s{si}/{key}: NO IMAGE")
                continue
            im = Image.open(imgs[0])
            cut = crop_content(chroma(im))
            cut.save(os.path.join(sd, f"{key}.png"))
            print(f"  s{si}/{key}: {cut.width}x{cut.height}")
    print("DONE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir")
    ap.add_argument("--nscenes", type=int, default=None)
    args = ap.parse_args()
    n = args.nscenes
    if n is None:
        story_path = os.path.join(args.workdir, "story.json")
        if os.path.exists(story_path):
            import json
            with open(story_path, "r", encoding="utf-8") as f:
                n = len(json.load(f)["scenes"])
        else:
            n = len(glob.glob(os.path.join(args.workdir, "layers", "s*")))
    process(args.workdir, n)


if __name__ == "__main__":
    main()
