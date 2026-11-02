"""
photoframe.py  -  DarahBot memory photos
=========================================
make_single(): one photo inside the DarahBot frame. The frame follows the photo:
               landscape photo -> landscape frame, portrait photo -> portrait frame.
make_strip():  four photos stacked like a classic photo booth strip.
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


def make_single(photo_bytes, name="", score=None, total=10, winner=False, present=False):
    """One photo in the DarahBot frame. Landscape or portrait follows the photo itself."""
    photo = load_photo(photo_bytes)
    land = photo.width >= photo.height
    W, H = (2400, 1700) if land else (1600, 2160)
    s = W / 2400 if land else W / 1600
    base = Image.new("RGBA", (W, H), PAPER + (255,))
    d = ImageDraw.Draw(base)

    # big soft circle behind (like the yellow circle in the reference, in our pink)
    R = int((H if land else W) * 0.42)
    cx, cy = (int(W * 0.80), int(H * 0.42)) if land else (int(W * 0.78), int(H * 0.30))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=BLUSH)

    # red panel + photo
    if land:
        px0, py0, px1, py1 = int(W * .09), int(H * .22), int(W * .72), int(H * .86)
    else:
        px0, py0, px1, py1 = int(W * .07), int(H * .17), int(W * .93), int(H * .76)
    _shadow(base, (px0, py0, px1, py1), int(60 * s), int(30 * s), (0, int(30 * s)), 90)
    panel = _gradient_panel(px1 - px0, py1 - py0, int(60 * s))
    base.alpha_composite(panel, (px0, py0))
    inset = int(22 * s)
    ph = ImageOps.fit(photo, (px1 - px0 - 2 * inset, py1 - py0 - 2 * inset), Image.LANCZOS, centering=(0.5, 0.4))
    base.alpha_composite(_rounded(ph, int(44 * s)), (px0 + inset, py0 + inset))

    # header: logo + title
    lr = int(58 * s)
    hx, hy = int(W * .07) + lr, int(H * .075) + lr
    draw_logo(base, hx, hy, lr)
    d = ImageDraw.Draw(base)
    d.text((hx + lr + int(26 * s), hy - int(62 * s)), "DarahBot", fill=INK, font=font(92 * s, "black"))
    d.text((hx + lr + int(30 * s), hy + int(40 * s)), "CSC649 Data Science Exhibition  ·  UiTM Kampus Jasin",
           fill=MUTED, font=font(30 * s, "semi"))

    # name on the photo, inside a dashed "selected" box (like the reference 'Edit' text)
    who = (name or "Blood hero").strip()[:18]
    fsize = 150 * s if len(who) <= 8 else (118 * s if len(who) <= 12 else 92 * s)
    f = font(fsize, "black")
    tw = d.textlength(who, font=f)
    nx, ny = px0 + int(70 * s), py1 - int(70 * s) - int(fsize * 1.05)
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow_layer).text((nx + 4 * s, ny + 6 * s), who, fill=(40, 0, 8, 150), font=f)
    base.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(6 * s)))
    d = ImageDraw.Draw(base)
    d.text((nx, ny), who, fill=(255, 226, 130), font=f)
    _dashed_box(d, (nx - 26 * s, ny - 4 * s, nx + tw + 26 * s, ny + fsize * 1.18), s)

    # floating "tool panel" with stats (like the reference's tool grid)
    date = dt.date.today().strftime("%d %b %Y")
    sc = f"{score}/{total}" if score is not None else "–"
    tiles = [("drop", "DarahBot", ""), ("trophy", sc, "Quiz"), ("star", "Winner" if winner else "Player", ""),
             ("bars", "KKM", "data"), ("pin", "UiTM", "Jasin"), ("calendar", date.split()[0] + " " + date.split()[1], date.split()[2])]
    if present:
        tiles[2] = ("heart", "Prize!", "Hadiah")
    tw_, th_ = int(150 * s), int(150 * s)
    gap = int(16 * s)
    cols = 3
    gw = cols * tw_ + (cols - 1) * gap + 2 * gap
    gh = 2 * th_ + gap + 2 * gap
    if land:
        gx, gy = int(W * .66), int(H * .33)
    else:
        gx, gy = W - gw - int(W * .05), int(H * .13) - gh // 2 + int(30 * s)
        gy = max(int(H * .02), gy)
        gx, gy = W - gw - int(W * .04), int(H * .655)
    _shadow(base, (gx, gy, gx + gw, gy + gh), int(34 * s), int(22 * s), (0, int(14 * s)), 70)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([gx, gy, gx + gw, gy + gh], radius=int(34 * s), fill=(255, 255, 255))
    for i, (ic, t1, t2) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = gx + gap + c * (tw_ + gap)
        y = gy + gap + r * (th_ + gap)
        hi = (i == 1)
        d.rounded_rectangle([x, y, x + tw_, y + th_], radius=int(22 * s), fill=(255, 240, 241) if hi else "white",
                            outline=(231, 168, 176) if hi else LINE, width=max(2, int(3 * s)))
        _icon(base, ic, x + tw_ / 2, y + th_ * .36, th_ * .16)
        d = ImageDraw.Draw(base)
        f1 = font(th_ * (.17 if len(t1) <= 7 else .14), "semi")
        w1 = d.textlength(t1, font=f1)
        d.text((x + tw_ / 2 - w1 / 2, y + th_ * .58), t1, fill=INK, font=f1)
        if t2:
            f2 = font(th_ * .11)
            w2 = d.textlength(t2, font=f2)
            d.text((x + tw_ / 2 - w2 / 2, y + th_ * .79), t2, fill=MUTED, font=f2)

    # floating cards at the edges (like 'Text', 'Filter', 'Corners')
    cw, ch = int(230 * s), int(230 * s)
    if land:
        _card(base, int(W * .025), int(H * .30), cw, ch, s, sc, "Quiz score", "trophy")
        _card(base, int(W * .40), H - ch - int(H * .03), cw, ch, s, "Thank you" if not present else "Winner", "Terima kasih", "heart")
        _card(base, int(W * .84), int(H * .70), cw, ch, s, "Jasin", "UiTM Melaka", "pin")
        d = ImageDraw.Draw(base)
        for y in range(int(H * .70) + ch, H, int(26 * s)):
            d.line([(int(W * .84) + cw // 2, y), (int(W * .84) + cw // 2, y + int(12 * s))], fill=INK, width=max(2, int(3 * s)))
    else:
        _card(base, int(W * .04), int(H * .79), cw, ch, s, sc, "Quiz score", "trophy")
        _card(base, int(W * .36), int(H * .86), cw, ch, s, "Thank you" if not present else "Winner", "Terima kasih", "heart")

    # footer line
    d = ImageDraw.Draw(base)
    foot = f"Every drop counts · Setiap titis bermakna   ·   {date}   ·   darahbot.streamlit.app"
    ff = font(26 * s)
    fw = d.textlength(foot, font=ff)
    d.text(((W - fw) / 2 if not land else W - fw - int(W * .04), H - int(52 * s)), foot, fill=MUTED, font=ff)

    out = io.BytesIO()
    base.convert("RGB").save(out, format="JPEG", quality=93)
    return out.getvalue()


def make_strip(photos, name="", score=None, total=10, winner=False):
    """Classic photo-booth strip: up to 4 photos stacked, DarahBot footer at the bottom."""
    W = 1200
    pw, ph, m, gap, foot = 1080, 810, 60, 34, 300
    n = len(photos)
    H = m + n * ph + (n - 1) * gap + foot
    base = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    for i, pb in enumerate(photos):
        p = ImageOps.fit(load_photo(pb), (pw, ph), Image.LANCZOS, centering=(0.5, 0.4))
        base.paste(p, (m, m + i * (ph + gap)))
    d = ImageDraw.Draw(base)
    y = H - foot + 40
    draw_logo(base, W / 2 - 250, y + 55, 50)
    d = ImageDraw.Draw(base)
    d.text((W / 2 - 185, y + 10), "DarahBot", fill=INK, font=font(78, "black"))
    who = (name or "Blood hero").strip()[:22]
    sc = f"  ·  Quiz {score}/{total}" if score is not None else ""
    line = who + sc + ("  ·  Winner" if winner else "")
    f = font(34, "semi")
    lw = d.textlength(line, font=f)
    d.text(((W - lw) / 2, y + 128), line, fill=RED, font=f)
    sub = "CSC649 Data Science Exhibition · UiTM Kampus Jasin · " + dt.date.today().strftime("%d %b %Y")
    f2 = font(24)
    sw = d.textlength(sub, font=f2)
    d.text(((W - sw) / 2, y + 182), sub, fill=MUTED, font=f2)
    out = io.BytesIO()
    base.convert("RGB").save(out, format="JPEG", quality=93)
    return out.getvalue()
