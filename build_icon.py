from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SIZE = 1024
OUT = Path("AHU_Match.ico")
PNG = Path("AHU_Match.png")


def _font(size: int):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _gradient(size, top, bottom):
    img = Image.new("RGBA", (size, size), top)
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        a = int(top[3] * (1 - t) + bottom[3] * t)
        for x in range(size):
            px[x, y] = (r, g, b, a)
    return img


def main():
    s = SIZE
    im = Image.new("RGBA", (s, s), (255, 255, 255, 255))

    # Green document frame.
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((88, 78, 888, 942), radius=92, fill=(0, 70, 35, 85))
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    im.alpha_composite(shadow)

    frame = _gradient(s, (56, 245, 24, 255), (0, 120, 65, 255))
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((82, 68, 900, 936), radius=92, fill=255)
    im.alpha_composite(Image.composite(frame, Image.new("RGBA", (s, s)), mask))

    # White paper area with folded corner.
    paper = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pd = ImageDraw.Draw(paper)
    pd.rounded_rectangle((138, 124, 850, 884), radius=62, fill=(250, 252, 253, 255))
    pd.polygon([(650, 124), (850, 324), (650, 324)], fill=(30, 188, 76, 255))
    im.alpha_composite(paper)

    # Large green P.
    pfont = _font(590)
    pd = ImageDraw.Draw(im)
    pbox = pd.textbbox((0, 0), "P", font=pfont)
    px = 205 - pbox[0]
    py = 172 - pbox[1]
    pd.text((px + 12, py + 16), "P", font=pfont, fill=(0, 70, 35, 85))
    pd.text((px, py), "P", font=pfont, fill=(8, 188, 45, 255), stroke_width=5, stroke_fill=(0, 120, 55, 255))

    # Subtle document lines.
    line_y = [690, 765, 840]
    widths = [390, 500, 330]
    for y, w in zip(line_y, widths):
        pd.rounded_rectangle((194, y, 194 + w, y + 26), radius=13, fill=(180, 197, 207, 255))

    # Green approval badge.
    badge = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.ellipse((535, 565, 925, 955), fill=(0, 85, 45, 90))
    badge = badge.filter(ImageFilter.GaussianBlur(12))
    im.alpha_composite(badge)

    badge = _gradient(s, (90, 245, 40, 255), (0, 135, 68, 255))
    bmask = Image.new("L", (s, s), 0)
    bmd = ImageDraw.Draw(bmask)
    bmd.ellipse((520, 550, 910, 940), fill=255)
    im.alpha_composite(Image.composite(badge, Image.new("RGBA", (s, s)), bmask))

    # White check mark.
    d = ImageDraw.Draw(im)
    d.line([(615, 744), (690, 815), (820, 670)], fill="white", width=48, joint="curve")
    d.ellipse((591, 720, 639, 768), fill="white")
    d.ellipse((796, 646, 844, 694), fill="white")

    im.save(PNG, "PNG", optimize=True)
    icon = im.convert("RGB")
    icon.save(
        OUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Created {OUT} and {PNG}")


if __name__ == "__main__":
    main()
