from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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


def main():
    font = _font(900)
    probe = ImageDraw.Draw(Image.new("L", (SIZE, SIZE)))
    bounds = probe.textbbox((0, 0), "P", font=font, stroke_width=10)
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    scale = min(1.0, (SIZE - 112) / width, (SIZE - 112) / height)
    if scale < 1:
        font = _font(int(900 * scale))
        bounds = probe.textbbox((0, 0), "P", font=font, stroke_width=10)
        width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]

    position = ((SIZE - width) / 2 - bounds[0], (SIZE - height) / 2 - bounds[1])
    glyph = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(glyph).text(position, "P", font=font, fill=255, stroke_width=10, stroke_fill=255)

    shadow_mask = Image.new("L", (SIZE, SIZE), 0)
    shadow_mask.paste(glyph, (0, 18))
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(18))
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 64, 34, 0))
    shadow.putalpha(shadow_mask.point(lambda value: value * 96 // 255))

    gradient = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = (
            round(124 * (1 - t)),
            round(255 * (1 - t) + 122 * t),
            round(50 * (1 - t) + 61 * t),
            255,
        )
        draw.line((0, y, SIZE, y), fill=color)
    gradient.putalpha(glyph)

    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.alpha_composite(shadow)
    icon.alpha_composite(gradient)
    icon.save(PNG, "PNG", optimize=True)
    icon.save(
        OUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Created transparent green P icon: {OUT} and {PNG}")


if __name__ == "__main__":
    main()
