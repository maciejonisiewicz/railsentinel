import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import binary_closing, binary_dilation, binary_erosion, binary_opening, gaussian_filter, label
from scipy.signal import fftconvolve

FF = imageio_ffmpeg.get_ffmpeg_exe()
HERE = Path(__file__).resolve().parent
REF = HERE / "wywiady" / "ref_kalendarz.png"
W, H, FPS = 478, 850, 30
PLATE = (3, 24, 35, 44)
FLAP = (50, 213, 118, 242)
PAD = 3
MARGIN = 40
SCALES = [round(0.8 + 0.025 * k, 3) for k in range(21)]
BLUR = 7


def gray(im):
    return np.asarray(im.convert("L"), dtype=np.float32)


def ncc(img, tpl):
    t = tpl - tpl.mean()
    tn = float(np.sqrt((t * t).sum())) + 1e-6
    k = np.ones_like(tpl)
    n = tpl.size
    num = fftconvolve(img, t[::-1, ::-1], mode="valid")
    s1 = fftconvolve(img, k, mode="valid")
    s2 = fftconvolve(img * img, k, mode="valid")
    var = np.maximum(s2 - s1 * s1 / n, 1e-3)
    return num / (np.sqrt(var) * tn)


def templates():
    ref = Image.open(REF)
    out = {}
    for s in SCALES:
        w, h = round(ref.width * s), round(ref.height * s)
        out[s] = gray(ref.resize((w, h), Image.LANCZOS))
    return out


def locate(g, tpls, prev):
    best = (-1.0, None)
    for s, tp in tpls.items():
        if prev and abs(s - prev[2]) > 0.08:
            continue
        if prev:
            x0, y0 = max(0, int(prev[0]) - 30), max(0, int(prev[1]) - 30)
            x1, y1 = min(W, int(prev[0]) + 30 + tp.shape[1]), min(H, int(prev[1]) + 30 + tp.shape[0])
        else:
            x0, y0, x1, y1 = 0, 0, W, 400
        win = g[y0:y1, x0:x1]
        if win.shape[0] < tp.shape[0] or win.shape[1] < tp.shape[1]:
            continue
        r = ncc(win, tp)
        i = np.unravel_index(int(np.argmax(r)), r.shape)
        if r[i] > best[0]:
            best = (float(r[i]), (x0 + i[1], y0 + i[0], s))
    return best


def skin_mask(rgb):
    f = rgb.astype(np.float32) / 255.0
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    mx, mn = f.max(-1), f.min(-1)
    d = mx - mn
    s = d / np.maximum(mx, 1e-6)
    h = np.zeros_like(mx)
    m = d > 1e-6
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    h[rm] = (60 * ((g - b)[rm] / d[rm])) % 360
    h[gm] = 60 * ((b - r)[gm] / d[gm]) + 120
    warm = ((h < 30) | (h > 340)) & (s >= 0.16) & (s <= 0.62) & (mx >= 0.3) & ((r - b) >= 0.1)
    warm = binary_closing(binary_opening(warm, iterations=1), iterations=2)
    lab, n = label(warm)
    if n == 0:
        return warm
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    return lab == int(np.argmax(sizes))


def blur_allowed(skin):
    h, w = skin.shape
    skin = binary_erosion(binary_opening(skin, iterations=2), iterations=1)
    edge = np.full(h, -1, dtype=int)
    for r in range(h):
        xs = np.flatnonzero(skin[r])
        if xs.size:
            edge[r] = xs[-1]
    pad = np.pad(edge, 1, mode="edge")
    edge = np.median(np.stack([pad[k:k + h] for k in range(3)]), axis=0).astype(int)
    cols = np.arange(w)[None, :]
    return cols > edge[:, None]


def ramp(h, w, k=4):
    yy = np.minimum(np.arange(h), np.arange(h)[::-1])[:, None]
    xx = np.minimum(np.arange(w), np.arange(w)[::-1])[None, :]
    return np.clip(np.minimum(yy, xx) / k, 0, 1).astype(np.float32)


def rect(box, pos, pad=0):
    x, y, s = pos
    dx0, dy0, dx1, dy1 = box
    return (max(0, round(x + dx0 * s) - pad), max(0, round(y + dy0 * s) - pad),
            min(W, round(x + dx1 * s) + pad), min(H, round(y + dy1 * s) + pad))


def hsv_v(f):
    return f.max(-1)


def fill_plate(frame, pos):
    x0, y0, x1, y1 = rect(PLATE, pos, PAD)
    if x1 <= x0 or y1 <= y0:
        return frame
    crop = frame[y0:y1, x0:x1].astype(np.float32) / 255.0
    v = hsv_v(crop)
    local = gaussian_filter(v, 3)
    red = (crop[..., 0] > 0.5) & (crop[..., 1] < 0.4) & (crop[..., 2] < 0.4)
    text = binary_dilation(((v - local > 0.13) & (v > 0.55)) | red, iterations=1)
    keep = (~text).astype(np.float32)
    num = np.stack([gaussian_filter(crop[..., c] * keep, 2.5) for c in range(3)], -1)
    den = gaussian_filter(keep, 2.5)[..., None]
    fill = num / np.maximum(den, 1e-3)
    alpha = (text.astype(np.float32) * ramp(y1 - y0, x1 - x0, 2))[..., None]
    out = frame.copy()
    out[y0:y1, x0:x1] = ((alpha * fill + (1 - alpha) * crop) * 255).astype(np.uint8)
    return out


def clean_flap(frame, pos):
    x0, y0, x1, y1 = rect(FLAP, pos)
    if x1 <= x0 or y1 <= y0:
        return frame
    X0, Y0, Y1 = max(0, x0 - MARGIN), max(0, y0 - MARGIN), min(H, y1 + MARGIN)
    allowed = blur_allowed(skin_mask(frame[Y0:Y1, X0:x1]))[y0 - Y0:y1 - Y0, x0 - X0:]
    crop = frame[y0:y1, x0:x1].astype(np.float32) / 255.0
    cool = (crop[..., 2] > crop[..., 0] + 0.03) & (crop.max(-1) - crop.min(-1) > 0.08)
    cool = binary_dilation(cool, iterations=2)
    sx0, sx1 = min(W - 2, x1 + 10), min(W, x1 + 22)
    side = frame[y0:y1, sx0:sx1].astype(np.float32) / 255.0
    wall = np.median(side, axis=1)
    k = 5
    padded = np.pad(wall, ((k, k), (0, 0)), mode="edge")
    wall = np.median(np.stack([padded[i:i + len(wall)] for i in range(2 * k + 1)]), axis=0)
    alpha = (allowed & ~cool).astype(np.float32) * ramp(y1 - y0, x1 - x0, 3)
    alpha = gaussian_filter(alpha, 0.8)[..., None]
    out = frame.copy()
    out[y0:y1, x0:x1] = ((alpha * wall[:, None, :] + (1 - alpha) * crop) * 255).astype(np.uint8)
    return out


def blur_frame(frame, pos):
    return clean_flap(fill_plate(frame, pos), pos)


def redact(src, t0, dur, out, report=None):
    tpls = templates()
    rd = subprocess.Popen([FF, "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-vf", f"fps={FPS}",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    wr = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    prev, scores, n = None, [], 0
    while True:
        buf = rd.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        sc, pos = locate(gray(Image.fromarray(frame)), tpls, prev)
        if pos is not None and (sc >= 0.45 or prev is None):
            prev = pos
        scores.append(sc)
        wr.stdin.write(blur_frame(frame, prev if prev else (194, 44, 1.0)).tobytes())
        n += 1
    wr.stdin.close()
    wr.wait()
    rd.wait()
    if report is not None:
        report.update({"klatek": n, "ncc_min": round(min(scores), 2), "ncc_srednia": round(float(np.mean(scores)), 2)})
    return n


if __name__ == "__main__":
    rep = {}
    n = redact(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], rep)
    print(n, rep)
