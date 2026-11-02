"""
photoframe.py  -  DarahBot memory photos
=========================================
make_single(): one photo inside the DarahBot frame, on a LANDSCAPE page. The photo is never cropped:
               landscape or portrait, the whole picture is shown.
make_strip():  classic photo-booth strip (4 photos stacked) in the DarahBot red theme.
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


W_, H_ = 2400, 1700          # every memory photo is landscape, like the reference design


def _canvas(present=False):
    """Cream page, soft pink circle and the DarahBot header."""
    W, H, s = W_, H_, 1.0
    base = Image.new("RGBA", (W, H), PAPER + (255,))
    d = ImageDraw.Draw(base)
    R = int(H * 0.42)
    cx, cy = int(W * 0.80), int(H * 0.42)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=BLUSH)
    lr = int(58 * s)
    hx, hy = int(W * .06) + lr, int(H * .07) + lr
    draw_logo(base, hx, hy, lr)
    d = ImageDraw.Draw(base)
    d.text((hx + lr + int(26 * s), hy - int(62 * s)), "DarahBot", fill=INK, font=font(92 * s, "black"))
    d.text((hx + lr + int(30 * s), hy + int(40 * s)), "CSC649 Data Science Exhibition  ·  UiTM Kampus Jasin",
           fill=MUTED, font=font(30 * s, "semi"))
    return base, s


# area where the red photo panel may go (left part of the page)
BOX = (int(W_ * .075), int(H_ * .20), int(W_ * .70), int(H_ * .91))


def _place_panel(base, pw, ph, s):
    """Draw the red panel of size pw x ph centred in BOX; return its box."""
    bx0, by0, bx1, by1 = BOX
    px0 = bx0 + (bx1 - bx0 - pw) // 2
    py0 = by0 + (by1 - by0 - ph) // 2
    px1, py1 = px0 + pw, py0 + ph
    _shadow(base, (px0, py0, px1, py1), int(60 * s), int(30 * s), (0, int(30 * s)), 90)
    base.alpha_composite(_gradient_panel(pw, ph, int(60 * s)), (px0, py0))
    return px0, py0, px1, py1


def _decorate(base, s, panel, name, score, total, winner, present):
    """Name in a dashed box, the tool-grid of stats, floating cards and the footer (like the reference)."""
    W, H = base.size
    px0, py0, px1, py1 = panel
    pw, ph = px1 - px0, py1 - py0
    date = dt.date.today().strftime("%d %b %Y")
    sc = f"{score}/{total}" if score is not None else "–"
    cw = ch = int(230 * s)

    # card under the middle of the panel ("Thank you" / "Winner")
    tx = int(px0 + pw * 0.62 - cw / 2)
    ty = min(py1 - int(ch * 0.42), H - ch - int(30 * s))

    # name, bottom-left on the photo, shrunk until it fits
    who = (name or "Blood hero").strip()[:30]
    d = ImageDraw.Draw(base)
    fsize = 150 * s
    while fsize > 60 * s and d.textlength(who, font=font(fsize, "black")) > pw * 0.84:
        fsize -= 6 * s
    f = font(fsize, "black")
    tw = d.textlength(who, font=f)
    nx = px0 + int(60 * s)
    ny = py1 - int(70 * s) - int(fsize * 1.05)
    if nx + tw + 26 * s > tx - 10 * s:            # would touch the bottom card: lift the name above it
        ny = min(ny, ty - int(40 * s) - int(fsize * 1.18))
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow_layer).text((nx + 4 * s, ny + 6 * s), who, fill=(40, 0, 8, 150), font=f)
    base.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(6 * s)))
    d = ImageDraw.Draw(base)
    d.text((nx, ny), who, fill=(255, 226, 130), font=f)
    _dashed_box(d, (nx - 26 * s, ny - 4 * s, nx + tw + 26 * s, ny + fsize * 1.18), s)

    # tool grid with the stats, overlapping the right edge of the panel
    tiles = [("drop", "DarahBot", ""), ("trophy", sc, "Quiz"), ("star", "Winner" if winner else "Player", ""),
             ("bars", "KKM", "data"), ("pin", "UiTM", "Jasin"), ("calendar", date.split()[0] + " " + date.split()[1], date.split()[2])]
    if present:
        tiles[2] = ("heart", "Prize!", "Hadiah")
    tw_ = th_ = int(150 * s)
    gap, cols = int(16 * s), 3
    gw = cols * tw_ + (cols - 1) * gap + 2 * gap
    gh = 2 * th_ + gap + 2 * gap
    gx = min(px1 - int(gw * 0.30), W - gw - int(W * .03))
    gy = py0 + int(ph * 0.10)
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

    # floating cards: score on the left edge, thanks at the bottom, Jasin on the right with a dashed line
    _card(base, max(int(W * .015), px0 - int(cw * 0.55)), py0 + int(ph * 0.30), cw, ch, s, sc, "Quiz score", "trophy")
    _card(base, tx, ty, cw, ch, s, "Winner" if present else "Thank you", "Terima kasih", "heart")
    jx = max(int(W * .83), gx + gw - cw)
    jy = min(max(int(H * .64), gy + gh + int(50 * s)), H - ch - int(H * .09))
    if jx < px1 + int(20 * s) and jy < py1:      # keep it off the photo
        jx = min(px1 + int(40 * s), W - cw - int(W * .02))
    _card(base, jx, jy, cw, ch, s, "Jasin", "UiTM Melaka", "pin")
    d = ImageDraw.Draw(base)
    for y in range(jy + ch, H - int(70 * s), int(26 * s)):
        d.line([(jx + cw // 2, y), (jx + cw // 2, y + int(12 * s))], fill=INK, width=max(2, int(3 * s)))

    foot = f"Every drop counts · Setiap titis bermakna   ·   {date}   ·   darahbot.streamlit.app"
    ff = font(26 * s)
    fw = d.textlength(foot, font=ff)
    d.text((W - fw - int(W * .03), H - int(52 * s)), foot, fill=MUTED, font=ff)
    out = io.BytesIO()
    base.convert("RGB").save(out, format="JPEG", quality=93)
    return out.getvalue()


def make_single(photo_bytes, name="", score=None, total=6, winner=False, present=False):
    """One photo in the DarahBot frame. The page is always landscape and the photo is NEVER cropped:
    a landscape photo gets a wide panel, a portrait photo a tall one, both on the same landscape page."""
    photo = load_photo(photo_bytes)
    base, s = _canvas(present)
    inset = int(22 * s)
    bw, bh = BOX[2] - BOX[0] - 2 * inset, BOX[3] - BOX[1] - 2 * inset
    k = min(bw / photo.width, bh / photo.height)
    ph = photo.resize((max(1, int(photo.width * k)), max(1, int(photo.height * k))), Image.LANCZOS)
    panel = _place_panel(base, ph.width + 2 * inset, ph.height + 2 * inset, s)
    base.alpha_composite(_rounded(ph, int(44 * s)), (panel[0] + inset, panel[1] + inset))
    return _decorate(base, s, panel, name, score, total, winner, present)


def make_strip(photos, name="", score=None, total=6, winner=False):
    """Classic photo-booth STRIP in the DarahBot red theme: 4 photos stacked, film holes on the sides,
    logo on top, name + score at the bottom. Photos are never cropped."""
    ims = [load_photo(p, 1600) for p in photos][:4]
    W, m, pw, gap = 1200, 110, 980, 46
    sizes = []
    for im in ims:
        h = int(pw * im.height / im.width)
        sizes.append((pw, min(h, int(pw * 1.45))))
    head, foot = 300, 470
    H = head + sum(h for _, h in sizes) + gap * (len(ims) - 1) + foot
    # red gradient background with a soft dot pattern
    yy, xx = np.mgrid[0:H, 0:W]
    t = np.clip(yy / H * 0.85 + xx / W * 0.15, 0, 1)[..., None]
    bg = (np.array(RED2) * (1 - t) + np.array(WINE) * t).astype("uint8")
    base = Image.fromarray(bg, "RGB").convert("RGBA")
    dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for y in range(20, H, 40):
        for x in range(20 + (y // 40 % 2) * 20, W, 40):
            dd.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, 22))
    base.alpha_composite(dots)
    d = ImageDraw.Draw(base)
    # film holes down both sides
    for y in range(40, H - 30, 70):
        for x in (26, W - 26 - 30):
            d.rounded_rectangle([x, y, x + 30, y + 40], radius=8, fill=(40, 2, 8, 255))
    # header
    draw_logo(base, W / 2 - 230, 150, 62)
    d = ImageDraw.Draw(base)
    d.text((W / 2 - 150, 92), "DarahBot", fill="white", font=font(104, "black"))
    sub = "PHOTO BOOTH  ·  CSC649 DATA SCIENCE EXHIBITION"
    f = font(26, "semi")
    d.text(((W - d.textlength(sub, font=f)) / 2, 222), sub, fill=(255, 194, 202), font=f)
    # photos (whole picture, white border, shadow)
    y = head
    for im, (w, h) in zip(ims, sizes):
        k = min(w / im.width, h / im.height)
        p = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
        x = (W - p.width) // 2
        yy0 = y + (h - p.height) // 2
        _shadow(base, (x - 12, yy0 - 12, x + p.width + 12, yy0 + p.height + 12), 30, 18, (0, 14), 120)
        d = ImageDraw.Draw(base)
        d.rounded_rectangle([x - 12, yy0 - 12, x + p.width + 12, yy0 + p.height + 12], radius=30, fill="white")
        base.alpha_composite(_rounded(p, 22), (x, yy0))
        y += h + gap
    # footer: name in a dashed box, score pill, place and date
    y = H - foot + 60
    who = (name or "Blood hero").strip()[:30]
    d = ImageDraw.Draw(base)
    fs = 120
    while fs > 56 and d.textlength(who, font=font(fs, "black")) > W - 2 * m - 60:
        fs -= 6
    f = font(fs, "black")
    tw = d.textlength(who, font=f)
    nx = (W - tw) / 2
    d.text((nx, y), who, fill=(255, 226, 130), font=f)
    _dashed_box(d, (nx - 26, y - 6, nx + tw + 26, y + fs * 1.2), 1.0)
    pill = (f"Quiz {score}/{total}" if score is not None else "DarahBot") + ("  ·  Winner 🏆".replace(" 🏆", "") if winner else "  ·  Thank you!")
    fp = font(40, "semi")
    pwid = d.textlength(pill, font=fp) + 70
    py = y + fs * 1.2 + 46
    d.rounded_rectangle([(W - pwid) / 2, py, (W + pwid) / 2, py + 76], radius=38, fill="white")
    d.text(((W - pwid) / 2 + 35, py + 14), pill, fill=RED, font=fp)
    line = "UiTM Kampus Jasin  ·  " + dt.date.today().strftime("%d %b %Y") + "  ·  darahbot.streamlit.app"
    fl = font(28)
    d.text(((W - d.textlength(line, font=fl)) / 2, py + 112), line, fill=(255, 220, 225), font=fl)
    out = io.BytesIO()
    base.convert("RGB").save(out, format="JPEG", quality=93)
    return out.getvalue()
