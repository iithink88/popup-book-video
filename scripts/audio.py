# -*- coding: utf-8 -*-
"""立体书动画通用配乐：五声音阶 古筝拨弦 + 竹笛长音 + 低频垫 + 卷积混响。

用法：
  python audio.py <story.json> <workdir>

按 story.style 的 mood/scale 选择调式与音色，按 duration 自动铺排旋律。
"""
import os
import sys
import json
import argparse
import numpy as np
from scipy.signal import fftconvolve
from scipy.io import wavfile

SR = 44100

# 各调式五声音阶的半音偏移（相对 D=62）
MOODS = {
    "elegant": {"root": 62, "scale": [0, 2, 4, 7, 9], "flute_vel": 0.26, "arp_vel": 0.18, "bright": 1.0},
    "serene":  {"root": 57, "scale": [0, 2, 5, 7, 9], "flute_vel": 0.22, "arp_vel": 0.15, "bright": 0.85},
    "joyful":  {"root": 64, "scale": [0, 2, 4, 7, 9], "flute_vel": 0.28, "arp_vel": 0.20, "bright": 1.15},
    "mystic":  {"root": 55, "scale": [0, 3, 5, 7, 10], "flute_vel": 0.22, "arp_vel": 0.14, "bright": 0.75},
    "epic":    {"root": 60, "scale": [0, 2, 4, 7, 9], "flute_vel": 0.30, "arp_vel": 0.22, "bright": 1.1},
}
ROOT_OFFSETS = {"C": -2, "D": 0, "E": 2, "F": 3, "G": 5, "A": 7, "B": 9}


def make_music(story, seed=2026):
    dur = float(story.get("duration", 47.0))
    style = story.get("style", {})
    mood = style.get("mood", "elegant")
    cfg = MOODS.get(mood, MOODS["elegant"])
    root = cfg["root"] + ROOT_OFFSETS.get(style.get("scale", "D"), 0)
    scale = [root + s for s in cfg["scale"]]
    scale_hi = [s + 12 for s in scale]
    scale_lo = [s - 12 for s in scale]

    rng = np.random.default_rng(seed)
    N = int(SR * dur)

    def hz(m):
        return 440.0 * 2 ** ((m - 69) / 12.0)

    def pluck(midi, length, vel=0.5):
        n = int(length * SR)
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        t = np.arange(n) / SR
        f = hz(midi)
        out = np.zeros(n, dtype=np.float64)
        for k, amp in ((1, 1.0), (2, 0.42), (3, 0.20), (4, 0.10), (5, 0.05)):
            if f * k > 12000:
                break
            out += amp * np.sin(2 * np.pi * f * k * t + rng.uniform(0, 6.28))
        out += 0.22 * np.sin(2 * np.pi * f * 1.0018 * t)
        out *= np.exp(-t * (2.1 + f / 900))
        out *= (1 - np.exp(-t * 400))
        return (out * vel).astype(np.float32)

    def flute(midi, length, vel=0.28, vib=4.6):
        n = int(length * SR)
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        t = np.arange(n) / SR
        f = hz(midi)
        phase = 2 * np.pi * f * t + 0.28 * np.sin(2 * np.pi * vib * t)
        out = np.sin(phase) + 0.16 * np.sin(2 * phase) + 0.06 * np.sin(3 * phase)
        out = out + rng.normal(0, 1, n) * 0.03
        a = int(min(length * 0.22, 0.32) * SR)
        env = np.ones(n)
        env[:a] = np.linspace(0, 1, a) ** 1.6
        r = int(min(length * 0.30, 0.5) * SR)
        env[-r:] *= np.linspace(1, 0, r) ** 1.2
        return (out * env * vel).astype(np.float32)

    def pad(midi, length, vel=0.10):
        n = int(length * SR)
        if n <= 0:
            return np.zeros(0, dtype=np.float32)
        t = np.arange(n) / SR
        f = hz(midi)
        out = np.zeros(n, dtype=np.float64)
        for det in (-0.004, 0.0, 0.0045):
            out += np.sin(2 * np.pi * f * (1 + det) * t)
        out += 0.12 * np.sin(2 * np.pi * f * 2 * t)
        a = int(length * 0.35 * SR)
        e = np.ones(n)
        e[:a] = np.linspace(0, 1, a) ** 1.5
        e[-a:] *= np.linspace(1, 0, a) ** 1.2
        return (out * e * vel / 3).astype(np.float32)

    music = np.zeros(N, dtype=np.float32)

    def add(buf, snd, start):
        i = int(start * SR)
        j = min(i + len(snd), N)
        if i < N and j > i:
            buf[i:j] += snd[: j - i]

    ns = len(story.get("scenes", [])) or 6
    seg = dur / ns

    # 低频垫：每 2~3 场景一组
    pad_len = seg * 2.4
    t0 = 0.0
    while t0 < dur:
        for m in (root - 24, root - 17, root - 12):
            add(music, pad(m, pad_len, 0.11), t0)
        t0 += pad_len * 0.94

    # 竹笛旋律：每场景一句，音型随场景序号起伏
    Contour = [
        [4, 3, 2, 4, 1], [2, 3, 4, 3, 2], [1, 2, 3, 4, 3],
        [4, 3, 2, 1, 0], [3, 4, 4, 3, 2], [2, 1, 1, 0, 0],
    ]
    for si in range(ns):
        t = si * seg + 0.8
        contour = Contour[si % len(Contour)]
        for deg in contour:
            note = scale_hi[deg % len(scale_hi)]
            d = 0.9 + (deg % 3) * 0.15
            add(music, flute(note, d, cfg["flute_vel"]), t)
            t += d

    # 古筝琶音：贯穿，句尾留白
    arp = [scale[0], scale[2], scale[3], scale[4], scale_hi[0], scale[3], scale[2], scale[1]]
    step = 0.62
    t = 0.35
    while t < dur - 0.5:
        beat = int(t / step)
        if (t % seg) < 0.65:
            t += step
            continue
        m = arp[beat % len(arp)]
        add(music, pluck(m, 1.5, cfg["arp_vel"] if beat % 4 == 0 else cfg["arp_vel"] * 0.65), t)
        if beat % 8 == 0:
            add(music, pluck(scale_lo[0], 2.0, 0.16), t)
        t += step

    # 高音点缀
    for k in range(int(dur / 3.2)):
        t = 3.0 + k * 3.05 + rng.uniform(-0.4, 0.4)
        if t < dur - 1:
            m = scale_hi[rng.integers(0, len(scale_hi))]
            add(music, pluck(m, 0.9, 0.075), t)

    # 卷积混响
    ir_len = int(1.7 * SR)
    ir = rng.normal(0, 1, ir_len).astype(np.float32)
    ir *= np.exp(-np.arange(ir_len) / SR * 3.2)
    ir[:int(0.01 * SR)] = 0
    wet = fftconvolve(music, ir)[:N]
    music = music * 0.82 + wet * 0.30

    # 首尾包络
    fade = int(1.2 * SR)
    env = np.ones(N, dtype=np.float32)
    env[:fade] = np.linspace(0, 1, fade) ** 1.4
    env[-fade:] *= np.linspace(1, 0, fade) ** 1.2
    music *= env

    peak = np.max(np.abs(music))
    if peak > 0:
        music = music / peak * 0.92
    music = np.tanh(music * 1.15) * 0.9
    return music


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("workdir")
    args = ap.parse_args()
    with open(args.story, "r", encoding="utf-8") as f:
        story = json.load(f)
    music = make_music(story)
    out = os.path.join(args.workdir, "music.wav")
    wavfile.write(out, SR, (music * 32767).astype(np.int16))
    print("WROTE", out, "dur", story.get("duration", 47.0), "peak", round(float(np.max(np.abs(music))), 3))


if __name__ == "__main__":
    main()
