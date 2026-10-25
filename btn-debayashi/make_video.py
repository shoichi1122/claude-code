#!/usr/bin/env python3
"""BREAK THE NORMS 出囃子動画ジェネレーター

使い方:
  python3 make_video.py                       # イベント用（ダンサー名なし）
  python3 make_video.py --name "SHOICHI"      # ダンサー個別の出囃子
  python3 make_video.py --name "KAITO" --sub "POPPING" --out kaito.mp4
  python3 make_video.py --name "KAITO" --bg higgsfield_clip.mp4   # AI映像を背景に敷く
"""
import argparse, math, random, subprocess, wave, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1920, 1080, 30, 15.0
BPM = 120
BEAT = 60 / BPM
SR = 44100
RED = (225, 29, 72)
WHITE = (245, 245, 245)
BG = (8, 8, 10)
FONT_EN = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_JA = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

_font_cache = {}
def font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]

def text_layer(txt, size, color=WHITE, path=FONT_EN, spacing=0):
    f = font(path, size)
    chars = list(txt)
    widths = [f.getbbox(c)[2] - f.getbbox(c)[0] if c != " " else size * 0.35 for c in chars]
    tw = int(sum(widths) + spacing * (len(chars) - 1)) + 20
    asc, desc = f.getmetrics()
    img = Image.new("RGBA", (tw, asc + desc + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 10
    for c, w in zip(chars, widths):
        if c != " ":
            d.text((x - f.getbbox(c)[0], 10), c, font=f, fill=color)
        x += w + spacing
    return img

def paste_center(canvas, layer, cx, cy, scale=1.0, alpha=1.0):
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BICUBIC)
    if alpha < 1.0:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer = layer.copy(); layer.putalpha(a)
    canvas.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))

def ease_out(t): return 1 - (1 - min(max(t, 0), 1)) ** 3

# ---------- 映像エフェクト ----------
rng = np.random.default_rng(7)
scan = np.ones((H, W, 1), np.float32)
scan[::3] = 0.82

def glitch(arr, amount, seed):
    r = np.random.default_rng(seed)
    out = arr.copy()
    if amount <= 0: return out
    shift = int(6 + 30 * amount)
    out[..., 0] = np.roll(arr[..., 0], shift, axis=1)
    out[..., 2] = np.roll(arr[..., 2], -shift, axis=1)
    for _ in range(int(3 + 10 * amount)):
        y = r.integers(0, H - 40); h = r.integers(4, 60)
        out[y:y + h] = np.roll(out[y:y + h], r.integers(-120, 120) * amount, axis=1)
    return out

def finish(img, t, glitch_amt=0.0, flash=0.0, shake=0.0, seed=0):
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    if shake > 0:
        r = np.random.default_rng(seed + 999)
        arr = np.roll(arr, (int(r.integers(-1, 2) * shake * 18), int(r.integers(-1, 2) * shake * 18)), axis=(0, 1))
    arr = glitch(arr, glitch_amt, seed)
    if flash > 0:
        arr = arr * (1 - flash) + 255 * flash
    grain = np.random.default_rng(seed + 5).normal(0, 7, (H // 4, W // 4, 1)).astype(np.float32)
    grain = np.repeat(np.repeat(grain, 4, 0), 4, 1)
    arr = arr * scan + grain
    # ビネット
    return np.clip(arr * VIGNETTE, 0, 255).astype(np.uint8)

yy, xx = np.mgrid[0:H, 0:W]
VIGNETTE = (1 - 0.55 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 2)[..., None].astype(np.float32)

# ---------- タイムライン ----------
HITS = [2.0, 2.5, 3.0]          # BREAK / THE / NORMS
def since(t, t0): return t - t0

def render_frame(i, layers, name, sub, bg=None):
    t = i / FPS
    if bg is not None:
        # 背景映像は文字が読めるよう暗く沈め、ヒットの瞬間だけ少し明るくする
        dim = 0.45 if 4.0 <= t < 13.0 else 0.3
        img = Image.fromarray((bg * dim).astype(np.uint8)).convert("RGBA")
    else:
        img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    g = 0.0; flash = 0.0; shake = 0.0

    # 背景の斜めストライプ（ビートで点滅）
    beat_phase = (t % BEAT) / BEAT
    if t >= 4.0:
        off = int(t * 240) % 240
        a = int(26 + 30 * (1 - beat_phase))
        stripe = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stripe)
        for x in range(-H, W + 240, 240):
            sd.polygon([(x + off, H), (x + off + 60, H), (x + off + 60 + H, 0), (x + off + H, 0)], fill=RED + (a,))
        img.alpha_composite(stripe)

    if t < 2.0:
        # イントロ：ノイズの中にちらつく文字
        if random.Random(i).random() < 0.35 + t * 0.2:
            frag = random.Random(i * 3).choice(["BREAK", "NORMS", "THE", "BTN", "B_T_N"])
            paste_center(img, layers["frag_" + frag], W / 2 + random.Random(i).randint(-500, 500),
                         H / 2 + random.Random(i + 1).randint(-300, 300), alpha=0.5)
        d.rectangle([0, H // 2 - 2, int(W * t / 2.0), H // 2 + 2], fill=RED)
        g = 0.4 + 0.5 * t / 2
    elif t < 4.0:
        words = [("BREAK", -230), ("THE", 0), ("NORMS", 230)]
        for k, (w, dy) in enumerate(words):
            st = since(t, HITS[k])
            if st >= 0:
                s = 1.0 + 0.8 * (1 - ease_out(st / 0.15))
                paste_center(img, layers[w], W / 2, H / 2 + dy, scale=s)
        for h0 in HITS:
            st = since(t, h0)
            if 0 <= st < 0.15:
                flash = max(flash, 0.7 * (1 - st / 0.15)); shake = max(shake, 1 - st / 0.15); g = max(g, 0.8 * (1 - st / 0.15))
    elif t < 8.0:
        st = since(t, 4.0)
        paste_center(img, layers["TITLE"], W / 2, H / 2 - 40, scale=1.0 + 0.03 * math.sin(t * math.pi * 2 / BEAT) ** 8)
        # 赤いスラッシュ
        bw = int(W * ease_out(st / 0.3))
        d.polygon([(0, H / 2 + 120), (bw, H / 2 + 80), (bw, H / 2 + 100), (0, H / 2 + 140)], fill=RED)
        paste_center(img, layers["MOTTO_SMALL"], W / 2, H / 2 + 200, alpha=ease_out((st - 0.5) / 0.5))
        g = 0.6 * (1 - beat_phase) ** 6 if int(t / BEAT) % 2 == 0 else 0.05
        if st < 0.12: flash = 0.8 * (1 - st / 0.12); shake = 1 - st / 0.12
    elif t < 11.0 or (not name and t < 13.0):
        st = since(t, 8.0)
        paste_center(img, layers["DANCER"], W / 2, H / 2 - 110, scale=1 + 0.5 * (1 - ease_out(st / 0.2)))
        st2 = since(t, 8.5)
        if st2 >= 0:
            paste_center(img, layers["FIRST"], W / 2, H / 2 + 90, scale=1 + 0.5 * (1 - ease_out(st2 / 0.2)))
        jp = "ダンサーファースト"
        n = int(max(0, since(t, 9.2)) / 0.08)
        if n > 0:
            paste_center(img, text_layer(jp[:min(n, len(jp))], 64, RED, FONT_JA, spacing=14), W / 2, H / 2 + 260)
        for h0 in (8.0, 8.5):
            st = since(t, h0)
            if 0 <= st < 0.12: flash = 0.6 * (1 - st / 0.12); shake = 1 - st / 0.12; g = 0.7
    elif t < 13.0:
        st = since(t, 11.0)
        paste_center(img, layers["NEXT"], W / 2, H / 2 - 210, alpha=ease_out(st / 0.3))
        nl = layers["NAME"]
        paste_center(img, nl, W / 2, H / 2, scale=1 + 0.6 * (1 - ease_out(st / 0.18)))
        if sub:
            paste_center(img, layers["SUB"], W / 2, H / 2 + 190, alpha=ease_out((st - 0.4) / 0.3))
        if st < 0.15: flash = 0.9 * (1 - st / 0.15); shake = 1 - st / 0.15; g = 0.9
        else: g = 0.15 if i % 9 == 0 else 0
    else:
        st = since(t, 13.0)
        paste_center(img, layers["TITLE"], W / 2, H / 2 - 30, scale=0.85)
        paste_center(img, layers["MOTTO_SMALL"], W / 2, H / 2 + 130)
        if st < 0.15: flash = 1.0 * (1 - st / 0.15); shake = 1 - st / 0.15; g = 1.0
        fade = max(0, (t - 14.2) / 0.8)
        arr = finish(img, t, g, flash, shake, i)
        return (arr * (1 - fade)).astype(np.uint8)

    return finish(img, t, g, flash, shake, i)

# ---------- 音声合成 ----------
def synth_audio(path, name):
    n = int(SR * DUR); out = np.zeros(n, np.float32)
    def add(sig, t0, gain=1.0):
        s = int(t0 * SR); e = min(n, s + len(sig))
        if s < n: out[s:e] += sig[:e - s] * gain
    tt = lambda d: np.arange(int(d * SR)) / SR
    def kick():
        t = tt(0.4); f = 50 + 120 * np.exp(-t * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)
    def snare():
        t = tt(0.25)
        return (np.random.default_rng(1).normal(0, 0.6, len(t)) * np.exp(-t * 18) + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.5)
    def hat():
        t = tt(0.05); nz = np.random.default_rng(2).normal(0, 1, len(t))
        return np.diff(nz, prepend=0) * np.exp(-t * 80) * 0.3
    def impact(d=1.5):
        t = tt(d); f = 40 + 200 * np.exp(-t * 12)
        boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.5)
        nz = np.random.default_rng(3).normal(0, 1, len(t)) * np.exp(-t * 6) * 0.4
        return boom + nz
    def bass(freq, d):
        t = tt(d)
        saw = 2 * ((t * freq) % 1) - 1
        return np.tanh(saw * 2) * np.exp(-t * 3) * 0.35
    # イントロ：ライザー
    t = tt(2.0); nz = np.random.default_rng(4).normal(0, 1, len(t))
    riser = nz * (t / 2) ** 2 * 0.35 + np.sin(2 * np.pi * np.cumsum(200 + 1200 * (t / 2) ** 2) / SR) * (t / 2) * 0.15
    add(riser, 0)
    for h in HITS: add(impact(0.5), h, 0.9); add(kick(), h)
    # 4.0〜13.0：ブレイクビーツ
    pattern_k = [0, 0.75, 1.5, 2.5, 2.75]   # 拍単位（2小節=8拍の内の前半）
    pattern_s = [1, 3]
    notes = [55, 55, 65.4, 49]
    end_beat = 13.0 if name else 13.0
    bar = 0
    t0 = 4.0
    while t0 < end_beat - 0.01:
        for b in pattern_k: add(kick(), t0 + b * BEAT, 0.9)
        for b in pattern_s: add(snare(), t0 + b * BEAT, 0.6)
        for k in range(8): add(hat(), t0 + k * BEAT / 2, 0.8 if k % 2 else 0.4)
        add(bass(notes[bar % 4], BEAT * 2), t0, 1.0)
        add(bass(notes[bar % 4] * 1.5, BEAT), t0 + 2.5 * BEAT, 0.7)
        bar += 1; t0 += 4 * BEAT
    for h in (4.0, 8.0, 8.5, 11.0): add(impact(1.0), h, 0.7)
    add(impact(2.0), 13.0, 1.1)
    # マスター
    fade = np.ones(n, np.float32); fs = int(14.2 * SR); fade[fs:] = np.linspace(1, 0, n - fs)
    out = np.tanh(out * 0.9) * fade * 0.9
    pcm = (np.stack([out, out], 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="", help="ダンサー名（入れると11〜13秒に名前が出る）")
    ap.add_argument("--sub", default="", help="名前の下に出すサブテキスト（ジャンル・チーム名など）")
    ap.add_argument("--out", default="btn_debayashi.mp4")
    ap.add_argument("--bg", default="", help="背景に敷く映像（Higgsfieldで生成したクリップなど）。15秒に満たない場合はループ")
    a = ap.parse_args()
    layers = {
        "BREAK": text_layer("BREAK", 230, WHITE, spacing=12),
        "THE": text_layer("THE", 230, RED, spacing=12),
        "NORMS": text_layer("NORMS", 230, WHITE, spacing=12),
        "TITLE": text_layer("BREAK THE NORMS", 140, WHITE, spacing=6),
        "MOTTO_SMALL": text_layer("DANCER FIRST", 54, RED, spacing=24),
        "DANCER": text_layer("DANCER", 240, WHITE, spacing=14),
        "FIRST": text_layer("FIRST", 240, RED, spacing=14),
        "NEXT": text_layer("NEXT DANCER", 56, RED, spacing=22),
    }
    for f in ["BREAK", "NORMS", "THE", "BTN", "B_T_N"]:
        layers["frag_" + f] = text_layer(f, 140, WHITE)
    if a.name:
        nl = text_layer(a.name.upper(), 260, WHITE, FONT_JA if any(ord(c) > 0x2FFF for c in a.name) else FONT_EN, spacing=10)
        if nl.width > W - 160: nl = nl.resize((W - 160, int(nl.height * (W - 160) / nl.width)), Image.BICUBIC)
        layers["NAME"] = nl
        layers["SUB"] = text_layer(a.sub.upper(), 64, RED, FONT_JA if any(ord(c) > 0x2FFF for c in a.sub) else FONT_EN, spacing=18)

    wav = a.out.rsplit(".", 1)[0] + ".wav"
    synth_audio(wav, a.name)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
                           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", a.out],
                          stdin=subprocess.PIPE)
    bgp = None
    if a.bg:
        bgp = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-stream_loop", "-1", "-i", a.bg, "-t", str(DUR),
                                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}",
                                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    for i in range(int(DUR * FPS)):
        bg = None
        if bgp:
            raw = bgp.stdout.read(W * H * 3)
            if len(raw) == W * H * 3:
                bg = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(np.float32)
        ff.stdin.write(render_frame(i, layers, a.name, a.sub, bg).tobytes())
    if bgp: bgp.kill()
    ff.stdin.close(); ff.wait()
    os.remove(wav)
    print("done:", a.out)

if __name__ == "__main__":
    main()
