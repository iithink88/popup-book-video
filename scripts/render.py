# -*- coding: utf-8 -*-
"""立体书动画通用渲染引擎：物体从平铺底板逐个立起 -> 展示 -> 逐个倒下。

用法：
  python render.py <story.json> <workdir> [--still <秒数>] [--outdir <目录>]

<workdir> 需含 layers/s1..sN/ 目录（bg.png + 各物体 <key>.png 抠好的透明图）
        以及 music.wav。素材由 generate_images 流程 + process_layers.py 产出。
"""
import os
import sys
import json
import math
import argparse
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------- 固定画布参数 ----------
W, H = 1280, 720
SRC_W, SRC_H = 1536, 1024
FPS = 30
TRANS = 18                 # 场景交叉淡化帧数
OBJ_SCALE = 1.18           # 物体整体放大系数（源坐标系下）
SRC_ZOOM = 1.14            # 底板放大裁切，切掉底部水印带

# 立起时间轴（场景内 0~1 进度）
RISE_START = 0.06
RISE_SPAN = 0.52
OBJ_RISE_DUR = 0.16
FALL_START = 0.80
FALL_DUR = 0.09

FONT_CANDIDATES = {
    "simkai": "C:/Windows/Fonts/simkai.ttf",
    "simfang": "C:/Windows/Fonts/simfang.ttf",
    "simhei": "C:/Windows/Fonts/simhei.ttf",
    "msyh": "C:/Windows/Fonts/msyh.ttc",
}
if sys.platform != "win32":
    FONT_CANDIDATES = {
        "simkai": "/usr/share/fonts/truetype/arphic/UKai.ttc",
        "simfang": "/usr/share/fonts/truetype/arphic/UGing.ttc",
        "simhei": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "msyh": "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    }


def get_font(key, size):
    path = FONT_CANDIDATES.get(key) or FONT_CANDIDATES["simkai"]
    if not os.path.exists(path):
        path = next((p for p in FONT_CANDIDATES.values() if os.path.exists(p)), None)
    return ImageFont.truetype(path, size)


def ease_out_back(p):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


class Engine:
    def __init__(self, story, workdir):
        self.story = story
        self.workdir = workdir
        self.duration = float(story.get("duration", 47.0))
        self.total = int(FPS * self.duration)
        self.scenes = story["scenes"]
        self.ns = len(self.scenes)
        self.df = self.total / self.ns
        self.style = story.get("style", {})
        self.font_key = self.style.get("font", "simkai")
        self.title = story.get("title", "")
        self.subtitle = story.get("subtitle", "")
        self.seal_char = story.get("seal", self.title[:1] if self.title else "印")

        # 最终画布裁切区（统一去水印）
        self.cw, self.ch = int(SRC_W / SRC_ZOOM), int(SRC_H / SRC_ZOOM)
        self.crop_left = (SRC_W - self.cw) // 2
        self.crop_top = max(0, min(int(SRC_H * 0.90) - self.ch, SRC_H - self.ch))

        self.scene_data = self._load_layers()
        self._build_overlays()

    def _load_layers(self):
        print("Loading layers...", flush=True)
        data = []
        for si, sc in enumerate(self.scenes):
            sd = os.path.join(self.workdir, "layers", f"s{si+1}")
            bgp = os.path.join(sd, "bg.png")
            if not os.path.exists(bgp):
                raise FileNotFoundError(f"missing base plate: {bgp}")
            bg = Image.open(bgp).convert("RGBA")
            if bg.size != (SRC_W, SRC_H):
                bg = bg.resize((SRC_W, SRC_H), Image.LANCZOS)
            objs = []
            for o in sc["objects"]:
                path = os.path.join(sd, f"{o['key']}.png")
                if not os.path.exists(path):
                    print(f"  WARNING missing object: {path}", flush=True)
                    continue
                im = Image.open(path).convert("RGBA")
                objs.append({
                    "im": im, "x": o["cx"], "y": o["cy"],
                    "h": o["h"] * OBJ_SCALE, "delay": float(o["delay"]),
                })
            data.append({"bg": bg, "objs": objs})
            print(f"  scene {si+1}: {len(objs)} objects", flush=True)
        return data

    def _build_overlays(self):
        # 字幕面板
        self.panels = []
        self.panel_pos = []
        for sc in self.scenes:
            lines = sc.get("text", [])
            self.panels.append(self._build_panel(lines) if lines else None)
            p = self.panels[-1]
            self.panel_pos.append(
                (W - 30 - p.width, max(40, (H - p.height) // 2)) if p else (0, 0)
            )
        # 印章
        self.seal = Image.new("RGBA", (44, 44), (0, 0, 0, 0))
        sd = ImageDraw.Draw(self.seal)
        sd.rounded_rectangle([0, 0, 43, 43], radius=6, fill=(158, 40, 36, 235))
        sd.text((22, 22), self.seal_char, font=get_font(self.font_key, 26),
                fill=(250, 244, 230, 255), anchor="mm")
        self.seal_pos = (W - 74, H - 78)
        # 片头标题
        self.title_img = None
        if self.title:
            self.title_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            td = ImageDraw.Draw(self.title_img)
            spaced = " ".join(self.title)
            tsize = 100 if len(self.title) <= 4 else 76
            td.text((W // 2, 235), spaced, font=get_font(self.font_key, tsize),
                    fill=(52, 44, 34, 255), anchor="mm")
            tw = min(300, 40 * len(spaced))
            td.line([(W // 2 - tw, 310), (W // 2 + tw, 310)],
                    fill=(150, 120, 74, 200), width=2)
            if self.subtitle:
                td.text((W // 2, 350), self.subtitle, font=get_font(self.font_key, 32),
                        fill=(90, 74, 56, 255), anchor="mm")
        # 暗角
        yy, xx = np.mgrid[0:H, 0:W]
        nx = (xx - W / 2) / (W / 2)
        ny = (yy - H / 2) / (H / 2)
        r = np.sqrt(nx * nx + ny * ny)
        va = np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * 115
        self.vig = Image.new("RGBA", (W, H), (18, 14, 10, 0))
        self.vig.putalpha(Image.fromarray(va.astype(np.uint8), "L"))

    def _build_panel(self, lines):
        cell, colw, fs = 38, 44, 30
        fnt = get_font(self.font_key, fs)
        maxlen = max(len(x) for x in lines)
        ncols = len(lines)
        pw, ph = ncols * colw + 26, maxlen * cell + 26
        panel = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        d = ImageDraw.Draw(panel)
        d.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=10,
                            fill=(240, 229, 206, 200), outline=(150, 120, 74, 150), width=2)
        for ci, line in enumerate(lines):
            cx = pw - 14 - ci * colw - fs // 2
            for ri, ch in enumerate(line):
                d.text((cx, 13 + ri * cell + cell // 2), ch, font=fnt,
                       fill=(40, 34, 28, 255), anchor="mm")
        return panel

    @staticmethod
    def _with_alpha(img, a):
        a = max(0.0, min(1.0, a))
        if a >= 0.999:
            return img
        out = img.copy()
        out.putalpha(out.getchannel("A").point(lambda v: int(v * a)))
        return out

    @staticmethod
    def _obj_progress(p, delay, max_delay):
        norm = delay / max_delay if max_delay > 0 else 0.0
        rise_t = RISE_START + norm * RISE_SPAN
        if p < rise_t:
            return 0.0
        if p < rise_t + OBJ_RISE_DUR:
            return ease_out_back((p - rise_t) / OBJ_RISE_DUR)
        fall_t = FALL_START + (1 - norm) * 0.02
        if p < fall_t:
            return 1.0
        if p < fall_t + FALL_DUR:
            return 1.0 - ease_out_cubic((p - fall_t) / FALL_DUR)
        return 0.0

    @staticmethod
    def _place_object(canvas, obj, e):
        if e <= 0.01:
            return
        im = obj["im"]
        e = min(e, 1.10)
        w = int(im.width * obj["h"] / im.height)
        cur_h = max(2, int(obj["h"] * e))
        cur_w = max(2, int(w * (0.90 + 0.10 * min(e, 1.0))))
        rs = im.resize((cur_w, cur_h), Image.LANCZOS)
        if e > 0.1:
            sw, sh = int(cur_w * 0.7), max(4, int(12 * min(e, 1.0)))
            shimg = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            ImageDraw.Draw(shimg).ellipse(
                [0, 0, sw - 1, sh - 1], fill=(28, 22, 16, int(65 * min(e, 1.0)))
            )
            shimg = shimg.filter(ImageFilter.GaussianBlur(3))
            canvas.alpha_composite(shimg, (int(obj["x"] - sw / 2), int(obj["y"] - sh / 2 + 4)))
        canvas.alpha_composite(rs, (int(obj["x"] - cur_w / 2), int(obj["y"] - cur_h)))

    def render_scene(self, si, local):
        p = local / self.df
        sd = self.scene_data[si]
        canvas = sd["bg"].copy()
        max_delay = max((o["delay"] for o in sd["objs"]), default=1.0)
        for obj in sd["objs"]:
            e = self._obj_progress(p, obj["delay"], max_delay)
            self._place_object(canvas, obj, e)

        z = 1.0 + 0.03 * p
        cw, ch = int(self.cw / z), int(self.ch / z)
        lx = self.crop_left + (self.cw - cw) // 2
        ty = self.crop_top + (self.ch - ch) // 2
        frame = canvas.crop((lx, ty, lx + cw, ty + ch)).resize((W, H), Image.LANCZOS)
        frame = frame.convert("RGBA")
        frame.alpha_composite(self.vig)

        fade = 16
        a = min(local / fade, (self.df - 1 - local) / fade, 1.0)
        if a > 0.01:
            if self.panels[si]:
                frame.alpha_composite(self._with_alpha(self.panels[si], a), self.panel_pos[si])
            frame.alpha_composite(self._with_alpha(self.seal, a), self.seal_pos)

        if si == 0 and self.title_img and local < 64:
            ta = min(local / 12, 1.0, (64 - local) / 22)
            if ta > 0.01:
                frame.alpha_composite(self._with_alpha(self.title_img, ta))

        return frame.convert("RGB")

    def frame_at(self, f):
        si = min(int(f // self.df), self.ns - 1)
        local = min(int(f - si * self.df), int(self.df) - 1)
        if si > 0 and local < TRANS:
            prev_local = min(int(self.df) - TRANS + local, int(self.df) - 1)
            a = self.render_scene(si - 1, prev_local)
            b = self.render_scene(si, local)
            return Image.blend(a, b, ease_out_cubic(local / TRANS))
        return self.render_scene(si, local)

    def render_all(self, outpath):
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-i", os.path.join(self.workdir, "music.wav"),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest", outpath,
        ]
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        try:
            for f in range(self.total):
                proc.stdin.write(self.frame_at(f).tobytes())
                if f % 150 == 0:
                    print(f"frame {f}/{self.total} ({f / self.total * 100:.0f}%)", flush=True)
            proc.stdin.close()
            err = proc.stderr.read().decode("utf-8", "ignore")
            if proc.wait() != 0:
                print("FFMPEG ERROR:\n", err[-2000:], flush=True)
                raise SystemExit(1)
            print("DONE ->", outpath, flush=True)
        except Exception:
            try:
                proc.stdin.close()
            except Exception:
                pass
            proc.kill()
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("workdir")
    ap.add_argument("--still", type=float, default=None, help="仅渲染该秒数的静帧")
    ap.add_argument("--outdir", default=None, help="静帧输出目录")
    args = ap.parse_args()

    with open(args.story, "r", encoding="utf-8") as f:
        story = json.load(f)
    eng = Engine(story, args.workdir)

    if args.still is not None:
        out = args.outdir or args.workdir
        os.makedirs(out, exist_ok=True)
        f = min(int(args.still * FPS), eng.total - 1)
        path = os.path.join(out, f"still_{args.still:.2f}s.jpg")
        eng.frame_at(f).save(path, quality=92)
        print("STILL ->", path)
    else:
        name = story.get("output_name") or (story.get("title", "video") + "_立体书.mp4")
        outpath = os.path.join(args.workdir, name)
        eng.render_all(outpath)


if __name__ == "__main__":
    main()
