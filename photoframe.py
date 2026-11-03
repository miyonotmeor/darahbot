"""
photoframe.py  -  DarahBot memory photos
=========================================
make_single(): the "chat" design, drawn ON TOP of the photo (frosted-glass DarahBot header, the visitor's question,
               DarahBot's answer with evidence, the name in yellow). The whole photo is kept, any orientation.
make_strip():  photo booth print: 3 photos per strip, two identical strips side by side, red DarahBot theme.
Both return JPEG bytes. Photos come from the device's own camera (full quality).
"""
import datetime as dt
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONTS = Path(__file__).parent / "assets" / "fonts"
RED, RED2, WINE, INK, MUTED = (176, 18, 42), (216, 31, 59), (92, 7, 20), (43, 15, 19), (141, 116, 118)
PAPER, BLUSH, PINK, LINE = (251, 246, 244), (247, 205, 211), (255, 194, 202), (236, 220, 216)


def font(size, weight="regular"):
    file = {"regular": "Inter-Regular.otf", "semi": "Inter-SemiBold.otf", "black": "InterDisplay-ExtraBold.otf"}[weight]
    try:
        return ImageFont.truetype(str(FONTS / file), int(size))
    except Exception:
        try:
            return ImageFont.load_default(size=int(size))
        except TypeError:
            return ImageFont.load_default()


try:                                   # iPhone photos can be HEIC
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass


def load_photo(photo_bytes, max_side=2400):
    """Open the camera photo the right way up (iPhone/iPad photos store rotation separately)."""
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(photo_bytes))).convert("RGB")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    return im


def drop_points(cx, cy, r):
    """A blood drop pointing UP (the DarahBot logo shape)."""
    pts = []
    for i in range(361):
        t = math.radians(i)
        x = cx + r * 0.95 * math.sin(t) * math.sin(t / 2) ** 1.0 * 1.25
        y = cy - r * 1.15 * math.cos(t) + r * 0.25
        pts.append((x, y))
    return pts


def draw_logo(img, cx, cy, r):
    """DarahBot logo: red circle with a white blood drop (same as the app)."""
    S = int(r * 2 * 4)
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    yy, xx = np.mgrid[0:S, 0:S] / S
    t = np.clip(np.sqrt((xx - .3) ** 2 + (yy - .25) ** 2) * 1.3, 0, 1)[..., None]
    grad = (np.array([255, 93, 112]) * (1 - t) + np.array(RED) * t).astype("uint8")
    g = Image.fromarray(grad, "RGB").convert("RGBA")
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).ellipse([0, 0, S - 1, S - 1], fill=255)
    tile.paste(g, (0, 0), m)
    ImageDraw.Draw(tile).polygon(drop_points(S / 2, S / 2, S * 0.27), fill="white")
    tile = tile.resize((int(r * 2), int(r * 2)), Image.LANCZOS)
    img.alpha_composite(tile, (int(cx - r), int(cy - r)))


def _rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=radius, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def _shadow(base, box, radius, blur, offset=(0, 20), alpha=80):
    x0, y0, x1, y1 = box
    pad = blur * 3
    sh = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad, pad + x1 - x0, pad + y1 - y0], radius=radius, fill=(60, 5, 15, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(sh, (x0 - pad + offset[0], y0 - pad + offset[1]))


def _gradient_panel(w, h, radius):
    yy, xx = np.mgrid[0:h, 0:w]
    t = np.clip(xx / w * 0.5 + yy / h * 0.6, 0, 1)[..., None]
    arr = (np.array(RED2) * (1 - t) + np.array(WINE) * t).astype("uint8")
    return _rounded(Image.fromarray(arr, "RGB"), radius)


def _card(base, x, y, w, h, s, title, sub, icon="drop"):
    """White floating card with an icon and a label (like the 'Text' / 'Filter' cards in the reference)."""
    _shadow(base, (x, y, x + w, y + h), int(28 * s), int(18 * s), (0, int(12 * s)), 70)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([x, y, x + w, y + h], radius=int(28 * s), fill="white", outline=(214, 196, 192), width=max(2, int(3 * s)))
    cx, cy = x + w / 2, y + h * 0.36
    _icon(base, icon, cx, cy, h * 0.17)
    f = font(h * 0.2 if len(title) < 8 else h * 0.16, "semi")
    tw = d.textlength(title, font=f)
    d.text((cx - tw / 2, y + h * 0.58), title, fill=INK, font=f)
    if sub:
        f2 = font(h * 0.105, "regular")
        sw = d.textlength(sub, font=f2)
        d.text((cx - sw / 2, y + h * 0.8), sub, fill=MUTED, font=f2)


def _icon(base, kind, cx, cy, r):
    d = ImageDraw.Draw(base)
    if kind == "drop":
        d.polygon(drop_points(cx, cy, r * 0.75), fill=RED)
    elif kind == "trophy":
        d.rounded_rectangle([cx - r * .7, cy - r, cx + r * .7, cy + r * .1], radius=int(r * .5), fill=RED)
        d.rectangle([cx - r * .12, cy, cx + r * .12, cy + r * .6], fill=RED)
        d.rounded_rectangle([cx - r * .55, cy + r * .55, cx + r * .55, cy + r * .85], radius=int(r * .1), fill=RED)
        d.arc([cx - r * 1.05, cy - r * .9, cx - r * .35, cy - r * .1], 90, 270, fill=RED, width=max(2, int(r * .18)))
        d.arc([cx + r * .35, cy - r * .9, cx + r * 1.05, cy - r * .1], 270, 90, fill=RED, width=max(2, int(r * .18)))
    elif kind == "pin":
        d.ellipse([cx - r * .65, cy - r, cx + r * .65, cy + r * .3], fill=RED)
        d.polygon([(cx - r * .5, cy), (cx + r * .5, cy), (cx, cy + r)], fill=RED)
        d.ellipse([cx - r * .25, cy - r * .6, cx + r * .25, cy - r * .1], fill="white")
    elif kind == "bars":
        for i, hh in enumerate([.5, 1.0, .75]):
            x = cx - r * .9 + i * r * .65
            d.rounded_rectangle([x, cy + r * .8 - r * 1.6 * hh, x + r * .45, cy + r * .8], radius=int(r * .12), fill=RED)
    elif kind == "star":
        pts = []
        for i in range(10):
            a = math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * .45
            pts.append((cx + rr * math.cos(a), cy - rr * math.sin(a)))
        d.polygon(pts, fill=RED)
    elif kind == "heart":
        d.ellipse([cx - r, cy - r * .7, cx, cy + r * .3], fill=RED)
        d.ellipse([cx, cy - r * .7, cx + r, cy + r * .3], fill=RED)
        d.polygon([(cx - r * .97, cy - r * .1), (cx + r * .97, cy - r * .1), (cx, cy + r * .95)], fill=RED)
    elif kind == "calendar":
        d.rounded_rectangle([cx - r * .85, cy - r * .7, cx + r * .85, cy + r * .85], radius=int(r * .2), outline=RED, width=max(2, int(r * .18)))
        d.rectangle([cx - r * .85, cy - r * .7, cx + r * .85, cy - r * .25], fill=RED)


def _dashed_box(d, box, s, color=(255, 255, 255)):
    x0, y0, x1, y1 = box
    dash, gap, w = int(16 * s), int(10 * s), max(2, int(3 * s))
    for x in range(int(x0), int(x1), dash + gap):
        d.line([(x, y0), (min(x + dash, x1), y0)], fill=color, width=w)
        d.line([(x, y1), (min(x + dash, x1), y1)], fill=color, width=w)
    for y in range(int(y0), int(y1), dash + gap):
        d.line([(x0, y), (x0, min(y + dash, y1))], fill=color, width=w)
        d.line([(x1, y), (x1, min(y + dash, y1))], fill=color, width=w)
    hs = int(10 * s)
    for (hx, hy) in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
        d.rectangle([hx - hs, hy - hs, hx + hs, hy + hs], fill="white", outline=color, width=max(1, int(2 * s)))


YELLOW = (255, 226, 130)
MAKERS = "@amirrulmukminin  ·  @ayuni"


def _date():
    return dt.date.today().strftime("%d %b %Y")


def _red_gradient(W, H, diag=True):
    yy, xx = np.mgrid[0:H, 0:W]
    t = np.clip(xx / W * 0.5 + yy / H * 0.6, 0, 1)[..., None] if diag else np.clip(yy / H * 0.85 + xx / W * 0.15, 0, 1)[..., None]
    return Image.fromarray((np.array(RED2) * (1 - t) + np.array(WINE) * t).astype("uint8"), "RGB").convert("RGBA")


def _glass(base, box, r, s, alpha=170, blur=26, shadow=True):
    """Frosted glass panel: the photo behind is blurred and tinted white."""
    x0, y0, x1, y1 = [int(v) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(base.width, x1), min(base.height, y1)
    if shadow:
        _shadow(base, (x0, y0, x1, y1), int(r), int(20 * s), (0, int(12 * s)), 70)
    region = base.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(blur * s))
    region.alpha_composite(Image.new("RGBA", region.size, (255, 255, 255, alpha)))
    m = Image.new("L", region.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, region.width - 1, region.height - 1], radius=int(r), fill=255)
    base.paste(region, (x0, y0), m)
    ImageDraw.Draw(base).rounded_rectangle([x0, y0, x1, y1], radius=int(r), outline=(255, 255, 255, 170), width=max(2, int(2.5 * s)))


def _tshadow(base, xy, text, f, fill, blur, anchor="la"):
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 4, xy[1] + 6), text, font=f, fill=(40, 0, 8, 170), anchor=anchor)
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    ImageDraw.Draw(base).text(xy, text, font=f, fill=fill, anchor=anchor)


def make_single(photo_bytes, name="", score=None, total=6, winner=False, present=False):
    """The chat design on top of the photo. Layout uses s = (short side / 1400), the same numbers as the live
    camera guide in camera.js, so what visitors see on the camera matches the final photo."""
    im = load_photo(photo_bytes)
    k = 2400 / max(im.size)
    im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    base = im.convert("RGBA")
    W, H = base.size
    s = min(W, H) / 1400
    score = 0 if score is None else score
    who = (name or "Blood hero").strip()
    first = who.split()[0]

    # soft shading at the bottom so the text reads on any photo
    yy = np.linspace(0, 1, H)[:, None]
    a = (np.clip((yy - 0.35) / 0.65, 0, 1) ** 1.7 * 150).astype("uint8")
    sh = np.zeros((H, W, 4), "uint8"); sh[..., 0] = 50; sh[..., 3] = np.broadcast_to(a, (H, W))
    base.alpha_composite(Image.fromarray(sh, "RGBA"))

    # thin red border on the photo (rounded inside)
    band = int(18 * s)
    m = Image.new("L", (W, H), 255)
    ImageDraw.Draw(m).rounded_rectangle([band, band, W - band, H - band], radius=int(48 * s), fill=0)
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 0)); fr.paste(_red_gradient(W, H), (0, 0), m); base.alpha_composite(fr)
    pad = band + 60 * s

    # top-left: DarahBot header (logo, title, online line, makers)
    lr = int(46 * s)
    d = ImageDraw.Draw(base)
    f_t, f_o, f_m = font(58 * s, "black"), font(21 * s, "semi"), font(22 * s, "semi")
    l2 = "online · CSC649 Data Science Exhibition"
    hw = 36 * s + lr * 2 + 26 * s + max(d.textlength("DarahBot", font=f_t), d.textlength(l2, font=f_o) + 24 * s,
                                        d.textlength(MAKERS, font=f_m)) + 50 * s
    hh = 180 * s
    hx, hy = pad - 10 * s, pad - 10 * s
    _glass(base, (hx, hy, hx + hw, hy + hh), 44 * s, s, alpha=180)
    draw_logo(base, hx + 36 * s + lr, hy + hh / 2, lr)
    d = ImageDraw.Draw(base)
    tx = hx + 36 * s + lr * 2 + 26 * s
    d.text((tx, hy + 54 * s), "DarahBot", fill=INK, font=f_t, anchor="lm")
    d.ellipse([tx, hy + 100 * s, tx + 15 * s, hy + 115 * s], fill=(29, 138, 90))
    d.text((tx + 24 * s, hy + 108 * s), l2, fill=MUTED, font=f_o, anchor="lm")
    d.text((tx, hy + 146 * s), MAKERS, fill=RED, font=f_m, anchor="lm")

    # top-right: the visitor's question (red bubble) with time and ticks
    fb, fsm = font(36 * s, "semi"), font(18 * s, "semi")
    right = W - pad
    q = "Hi DarahBot, did I win?" if winner else "Hi DarahBot, how did I do?"
    qw = d.textlength(q, font=fb) + 70 * s
    y = pad + 10 * s
    _shadow(base, (int(right - qw), int(y), int(right), int(y + 84 * s)), int(42 * s), int(16 * s), (0, int(10 * s)), 80)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([right - qw, y, right, y + 84 * s], radius=int(42 * s), fill=RED)
    d.text((right - qw + 35 * s, y + 42 * s), q, fill="white", font=fb, anchor="lm")
    d.text((right - 10 * s, y + 104 * s), dt.datetime.now().strftime("%I:%M %p").lstrip("0") + "  ✓✓", fill=(255, 235, 238), font=fsm, anchor="rm")

    # bottom-left: DarahBot's answer (glass) with evidence + typing dots
    y2 = H - pad - 330 * s
    lx = pad + 80 * s
    a1 = (f"Yes, {first}! You scored {score}/{total} and won a prize." if winner
          else f"You scored {score}/{total}, {first}! Thanks for playing. Every drop counts.")
    a2 = f"Evidence · quiz score {score}/{total} · {_date()}"
    f2 = font(22 * s, "semi")
    while d.textlength(a1, font=fb) > W * 0.62 and fb.size > 18 * s:     # long names on narrow photos
        fb = font(fb.size - 2 * s, "semi")
    bw = max(d.textlength(a1, font=fb), d.textlength(a2, font=f2) + 40 * s) + 80 * s
    _glass(base, (lx, y2, lx + bw, y2 + 160 * s), 40 * s, s, alpha=205)
    draw_logo(base, pad + 30 * s, y2 + 130 * s, 30 * s)
    d = ImageDraw.Draw(base)
    d.text((lx + 40 * s, y2 + 52 * s), a1, fill=INK, font=fb, anchor="lm")
    d.rounded_rectangle([lx + 40 * s, y2 + 92 * s, lx + 80 * s + d.textlength(a2, font=f2), y2 + 136 * s], radius=int(12 * s), fill=(255, 240, 241))
    d.text((lx + 60 * s, y2 + 114 * s), a2, fill=RED, font=f2, anchor="lm")
    _glass(base, (lx, y2 + 185 * s, lx + 130 * s, y2 + 245 * s), 30 * s, s, alpha=190, shadow=False)
    d = ImageDraw.Draw(base)
    for i, al in enumerate((255, 180, 110)):
        x = lx + 32 * s + i * 26 * s
        d.ellipse([x, y2 + 207 * s, x + 16 * s, y2 + 223 * s], fill=RED + (al,))

    # bottom-right: the name in yellow
    fN = font(150 * s, "black")
    while ImageDraw.Draw(base).textlength(who, font=fN) > W * 0.46 and fN.size > 60 * s:
        fN = font(fN.size - 6 * s, "black")
    _tshadow(base, (right, H - pad + 10 * s), who, fN, YELLOW, 8 * s, "rs")
    _tshadow(base, (right - 4 * s, H - pad + 40 * s), "Winner · Tahniah!" if winner else "Thank you · Terima kasih",
             font(26 * s, "semi"), "white", 4 * s, "rm")
    out = io.BytesIO()
    base.convert("RGB").save(out, format="JPEG", quality=93)
    return out.getvalue()


def make_strip(photos, name="", score=None, total=6, winner=False):
    """Photo booth print: 3 photos per strip, two identical strips side by side (cut down the middle)."""
    ims = [load_photo(p, 1600) for p in photos][:3]
    score = 0 if score is None else score
    SW, m, g, bd = 600, 46, 22, 9
    pw = SW - 2 * m
    asp = sorted(i.width / i.height for i in ims)[len(ims) // 2]
    ph = int(pw / max(0.6, min(asp, 1.9)))
    head, foot = 380, 110
    H = head + len(ims) * ph + (len(ims) - 1) * g + foot
    strip = _red_gradient(SW, H, diag=False)
    dots = Image.new("RGBA", (SW, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(dots)
    for y in range(16, H, 32):
        for x in range(16 + (y // 32 % 2) * 16, SW, 32):
            dd.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, 22))
    strip.alpha_composite(dots)
    d = ImageDraw.Draw(strip)
    for y in range(26, H - 20, 54):                              # film holes
        for x in (12, SW - 12 - 18):
            d.rounded_rectangle([x, y, x + 18, y + 28], radius=5, fill=(40, 2, 8, 255))
    cx = SW / 2
    fsub = font(15, "semi")
    sub = "CSC649 · DATA SCIENCE EXHIBITION"
    d.text((cx - d.textlength(sub, font=fsub) / 2, 40), sub, fill=(255, 194, 202), font=fsub)
    ft = font(64, "black")
    tw = d.textlength("DarahBot", font=ft)
    x0 = cx - (tw + 70 + 14) / 2
    draw_logo(strip, x0 + 35, 112, 35)
    d = ImageDraw.Draw(strip)
    d.text((x0 + 84, 74), "DarahBot", fill="white", font=ft)
    who = (name or "Blood hero").strip()
    fs = 70
    while fs > 34 and d.textlength(who, font=font(fs, "black")) > SW - 2 * m - 20:
        fs -= 3
    fN = font(fs, "black")
    d.text((cx - d.textlength(who, font=fN) / 2, 172), who, fill=YELLOW, font=fN)
    fd = font(22, "semi")
    d.text((cx - d.textlength(_date(), font=fd) / 2, 172 + fs * 1.12), _date(), fill=(255, 220, 225), font=fd)
    pill = f"Quiz {score}/{total}  ·  " + ("Winner!" if winner else "Thank you!")
    fp = font(24, "semi")
    pwd = d.textlength(pill, font=fp) + 44
    py = 172 + fs * 1.12 + 44
    d.rounded_rectangle([cx - pwd / 2, py, cx + pwd / 2, py + 46], radius=23, fill="white")
    d.text((cx - pwd / 2 + 22, py + 9), pill, fill=RED, font=fp)
    top = H - foot - (len(ims) * ph + (len(ims) - 1) * g)
    for i, im in enumerate(ims):
        y = top + i * (ph + g)
        _shadow(strip, (m - bd, y - bd, m + pw + bd, y + ph + bd), 18, 10, (0, 8), 110)
        d = ImageDraw.Draw(strip)
        d.rounded_rectangle([m - bd, y - bd, m + pw + bd, y + ph + bd], radius=18, fill="white")
        k = min(pw / im.width, ph / im.height)
        p = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
        strip.alpha_composite(_rounded(p, 12), (int(m + (pw - p.width) / 2), int(y + (ph - p.height) / 2)))
    d = ImageDraw.Draw(strip)
    fm = font(22, "semi")
    d.text((cx - d.textlength(MAKERS, font=fm) / 2, H - foot / 2 - 12), MAKERS, fill="white", font=fm)
    sheet = Image.new("RGB", (SW * 2, H), WINE)
    sheet.paste(strip.convert("RGB"), (0, 0)); sheet.paste(strip.convert("RGB"), (SW, 0))
    ImageDraw.Draw(sheet).line([(SW, 0), (SW, H)], fill=(255, 255, 255), width=2)
    out = io.BytesIO()
    sheet.save(out, format="JPEG", quality=93)
    return out.getvalue()
