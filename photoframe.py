"""
photoframe.py  -  DarahBot memory photo frame
Puts a visitor's camera photo inside a DarahBot frame (1080 x 1350, Instagram portrait size).
"""
import datetime as dt
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONTS = Path(__file__).parent / "assets" / "fonts"
RED, RED2, WINE, INK, MUTED, PINK = (176, 18, 42), (216, 31, 59), (92, 7, 20), (43, 15, 19), (141, 116, 118), (255, 194, 202)


def font(size, weight="regular"):
    file = {"regular": "Inter-Regular.otf", "semi": "Inter-SemiBold.otf", "black": "InterDisplay-ExtraBold.otf"}[weight]
    try:
        return ImageFont.truetype(str(FONTS / file), size)
    except Exception:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def _gradient(w, h):
    import numpy as np
    y, x = np.mgrid[0:h, 0:w]
    t = np.clip((x / w) * 0.45 + (y / h) * 0.75, 0, 1)[..., None]
    arr = (np.array(RED2) * (1 - t) + np.array(WINE) * t).astype("uint8")
    return Image.fromarray(arr, "RGB")


def make_frame(photo_bytes, name="", score=None, total=None, qr_png=None, mirror=False):
    W, H = 1080, 1350
    base = _gradient(W, H).convert("RGBA")
    d = ImageDraw.Draw(base)
    # soft dot pattern
    for y in range(190, H, 36):
        for x in range(20, W, 36):
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, 22))

    # header
    cx, cy = 92, 92
    d.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill="white")
    d.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=RED2)
    d.text((140, 56), "DarahBot", fill="white", font=font(54, "black"))
    d.text((142, 118), "CSC649 Data Science Exhibition · UiTM Kampus Jasin", fill=PINK, font=font(24, "semi"))

    # photo (rounded, white border)
    photo = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    photo = ImageOps.exif_transpose(photo)
    if mirror:
        photo = ImageOps.mirror(photo)
    pw, ph = 960, 860
    photo = ImageOps.fit(photo, (pw, ph), Image.LANCZOS, centering=(0.5, 0.45))
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=40, fill=255)
    shadow = Image.new("RGBA", (pw + 80, ph + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([40, 52, pw + 40, ph + 52], radius=48, fill=(30, 0, 6, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    base.alpha_composite(shadow, (60 - 40, 180 - 40))
    border = Image.new("RGBA", (pw + 16, ph + 16), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle([0, 0, pw + 15, ph + 15], radius=46, fill="white")
    base.alpha_composite(border, (52, 172))
    base.paste(photo, (60, 180), mask)

    # bottom card
    d = ImageDraw.Draw(base)
    y0 = 1075
    d.rounded_rectangle([60, y0, W - 60, H - 50], radius=34, fill="white")
    title = (name.strip()[:26] or "Blood hero") if name else "Blood hero"
    d.text((100, y0 + 30), title, fill=INK, font=font(46, "black"))
    if score is not None:
        badge = f"Quiz {score}/{total}" + ("  ·  Winner!" if score >= 8 else "")
        bw = d.textlength(badge, font=font(28, "semi")) + 44
        d.rounded_rectangle([100, y0 + 98, 100 + bw, y0 + 146], radius=24, fill=RED if score >= 8 else (255, 240, 241))
        d.text((122, y0 + 106), badge, fill="white" if score >= 8 else RED, font=font(28, "semi"))
        ytxt = y0 + 165
    else:
        ytxt = y0 + 100
    d.text((100, ytxt), "Every drop counts · Setiap titis bermakna", fill=MUTED, font=font(24, "regular"))
    d.text((100, ytxt + 34), dt.date.today().strftime("%d %B %Y") + "  ·  darahbot.streamlit.app", fill=MUTED, font=font(22, "regular"))
    if qr_png:
        q = Image.open(io.BytesIO(qr_png)).convert("RGB").resize((180, 180), Image.NEAREST)
        base.paste(q, (W - 60 - 40 - 180, y0 + 25))

    out = io.BytesIO()
    base.convert("RGB").save(out, format="JPEG", quality=92)
    return out.getvalue()
