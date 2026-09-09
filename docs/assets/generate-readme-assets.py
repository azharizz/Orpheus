"""Generate Orpheus's repository-owned README animation. Requires Pillow."""
from __future__ import annotations

from math import sin, pi
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, FRAMES = 960, 540, 12, 48
OUT = Path(__file__).with_name("orpheus-decision-loop.gif")
BANNER = Path(__file__).with_name("orpheus-readme-banner.png")
BG = "#0C0E10"
SURFACE = "#171A1D"
RULE = "#343B42"
WHITE = "#EFEFE8"
MUTED = "#ABB2B7"
ORANGE = "#FF5A36"
GOLD = "#EAC17C"
SAGE = "#9DCFAD"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]
        if bold else ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
    ) + ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()

TITLE = font(48, True)
LABEL = font(17, True)
DATA = font(14, False)
SMALL = font(12, True)


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def alpha_paste(base: Image.Image, layer: Image.Image, opacity: float) -> None:
    if opacity <= 0:
        return
    layer.putalpha(int(255 * min(1, opacity)))
    base.alpha_composite(layer)


def text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, fill: str, which: ImageFont.ImageFont) -> None:
    draw.text((int(xy[0]), int(xy[1])), value, fill=fill, font=which)


def frame(index: int) -> Image.Image:
    t = index / (FRAMES - 1)
    image = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(image)
    # Quiet grain, deliberately deterministic.
    for y in range(14, H, 31):
        for x in range(12 + (y % 11), W, 43):
            shade = 18 + ((x * 7 + y * 3) % 14)
            draw.point((x, y), fill=(shade + 12, shade + 14, shade + 16, 120))

    draw.line((42, 52, W - 42, 52), fill=RULE, width=1)
    text(draw, (42, 23), "ORPHEUS / FAMILY WORKFLOW", WHITE, SMALL)
    text(draw, (W - 203, 23), "HUMAN IN CONTROL", MUTED, SMALL)

    phase = t * 4
    if phase < 1:
        title, subtitle = "MARK A PART", "One confirmed sound becomes the anchor."
    elif phase < 2:
        title, subtitle = "FIND RELATED MOMENTS", "Local matching ranks the same sound across the film."
    elif phase < 3:
        title, subtitle = "REVIEW THE FAMILY", "Keep only the moments that belong together."
    else:
        title, subtitle = "RENDER THE ACCEPTED", "Everything else remains original."

    text(draw, (42, 88), title, WHITE, TITLE)
    text(draw, (45, 147), subtitle, MUTED, DATA)

    x0, x1, y = 72, W - 72, 270
    draw.rounded_rectangle((48, 208, W - 48, 362), radius=5, outline=RULE, width=2, fill=SURFACE)
    draw.line((x0, y, x1, y), fill=RULE, width=3)
    text(draw, (72, 228), "PICTURE CLOCK", MUTED, SMALL)

    nodes = [0.16, 0.32, 0.51, 0.73, 0.88]
    seed_alpha = ease((phase - 0.15) / 0.45)
    cascade = ease((phase - 1.05) / 0.75)
    review = ease((phase - 2.02) / 0.65)
    render = ease((phase - 3.0) / 0.7)
    for n, node in enumerate(nodes):
        x = lerp(x0, x1, node)
        visible = seed_alpha if n == 0 else cascade
        if visible > 0:
            color = ORANGE if n == 0 else GOLD
            if n in (0, 2, 4):
                color = tuple(int(lerp(a, b, review)) for a, b in zip((234, 193, 124), (157, 207, 173)))
            r = int(4 + 7 * visible)
            draw.rectangle((x-r, y-r, x+r, y+r), fill=color)
            draw.line((x, y - 34, x, y + 34), fill=color, width=2)
            if n > 0:
                origin_x = lerp(x0, x1, nodes[0])
                draw.line((origin_x, y + 49, x, y + 49), fill=(255, 90, 54, int(180 * cascade)), width=2)

    # Accepted replacement envelope only appears after review.
    if render:
        start, end = x0 + 14, x1 - 14
        amplitude = 22
        points = []
        for px in range(int(start), int(end), 7):
            wave = sin((px - start) * 0.105) * amplitude * (0.5 + 0.5 * sin((px - start) * 0.021) ** 2)
            points.append((px, int(326 + wave)))
        draw.line(points, fill=ORANGE, width=3)
        draw.rounded_rectangle((W - 248, 303, W - 73, 339), radius=4, fill="#12221A", outline=SAGE, width=1)
        text(draw, (W - 232, 314), "ACCEPTED ONLY", SAGE, SMALL)

    # Bounded decision cues.
    cards = [
        ("ORIGINAL", MUTED),
        ("MATCHED", GOLD),
        ("APPROVED", SAGE),
    ]
    progress = (seed_alpha, cascade, review)
    for i, ((label, color), opacity) in enumerate(zip(cards, progress)):
        cx = 72 + i * 285
        alpha = max(0.16, opacity)
        outline = tuple(int(v * alpha) for v in (255, 255, 255))
        draw.rounded_rectangle((cx, 405, cx + 247, 470), radius=4, outline=outline, width=1)
        draw.rectangle((cx + 14, 421, cx + 19, 454), fill=color)
        text(draw, (cx + 33, 418), label, color, LABEL)
        if i == 0:
            copy = "unchanged source"
        elif i == 1:
            copy = "ranking evidence"
        else:
            copy = "creator decision"
        text(draw, (cx + 33, 444), copy, MUTED, DATA)

    # Long analog-style fade avoids an abrupt GIF loop.
    if t > 0.9:
        overlay = Image.new("RGBA", (W, H), BG)
        alpha_paste(image, overlay, ease((t - .9) / .1))
    return image.convert("P", palette=Image.Palette.ADAPTIVE, colors=96)


def banner() -> Image.Image:
    image = Image.new("RGB", (1600, 560), BG)
    draw = ImageDraw.Draw(image)
    for y in range(8, 560, 19):
        for x in range(11 + y % 17, 1600, 29):
            shade = 18 + ((x * 5 + y * 3) % 11)
            draw.point((x, y), fill=(shade, shade + 2, shade + 4))
    # Fine framing rules instead of a generic UI card.
    for left, top, right, bottom in [(54, 82, 214, 136), (1386, 82, 1546, 136), (54, 424, 214, 478), (1386, 424, 1546, 478)]:
        draw.line((left, top, right, top), fill="#718089", width=2)
        draw.line((left, top, left, bottom), fill="#718089", width=2)
    text(draw, (86, 99), "PICTURE · SOUND · EVIDENCE", WHITE, font(19, True))
    text(draw, (86, 194), "ORPHEUS", WHITE, font(152, True))
    draw.rectangle((92, 362, 184, 368), fill=ORANGE)
    text(draw, (86, 390), "AN AGENTIC FOLEY WORKBENCH", MUTED, font(25, False))
    text(draw, (995, 132), "ONE EVENT / WHOLE FILM", GOLD, font(16, True))
    timeline_y = 192
    draw.line((995, timeline_y, 1495, timeline_y), fill=RULE, width=3)
    draw.line((995, timeline_y, 1150, timeline_y), fill=ORANGE, width=5)
    for i, (position, color) in enumerate([(1035, GOLD), (1110, SAGE), (1247, GOLD), (1384, SAGE), (1457, GOLD)]):
        h = 28 + (i % 2) * 8
        draw.rectangle((position, timeline_y - h // 2, position + 8, timeline_y + h // 2), fill=color)
    points = []
    for x in range(995, 1495, 6):
        wave = sin((x - 995) * .095) * (18 + 12 * sin((x - 995) * .022) ** 2)
        points.append((x, int(294 + wave)))
    draw.line(points, fill=ORANGE, width=5)
    draw.line((995, 389, 1495, 389), fill=RULE, width=1)
    text(draw, (995, 423), "MARK · FIND · FIT · REVIEW", WHITE, font(21, True))
    text(draw, (86, 492), "LOCAL MATCHING · BOUNDED AGENT FITTING · HUMAN APPROVAL", "#718089", font(15, False))
    return image


if __name__ == "__main__":
    frames = [frame(i) for i in range(FRAMES)]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, disposal=2, optimize=True)
    banner().save(BANNER, optimize=True)
    print(OUT)
    print(BANNER)
