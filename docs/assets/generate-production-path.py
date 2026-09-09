"""Render Orpheus's live production-path GIF and editable Draw.io source. Requires Pillow."""
from __future__ import annotations

from base64 import b64encode
from math import atan2, cos, hypot, pi, sin
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUT = ROOT / "orpheus-live-production-path.gif"
DRAWIO = ROOT / "orpheus-live-production-path.drawio"
ICONS = ROOT / "gcp-icons"
W, H, FPS, FRAMES = 1600, 980, 8, 28
INK = "#203247"
MUTED = "#50667D"
RULE = "#C9D7E5"
PAPER = "#FFFFFF"
PANEL = "#F5F8FB"
CLOUD = "#EAF3FF"
ORANGE = "#FF5A36"
BLUE = "#1689D4"
MEDIA = "#2F80ED"
EVIDENCE = "#64748B"
GOLD = "#EAC17C"
SAGE = "#5FAE7B"
RED = "#E7645F"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold
        else ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


H1 = font(29, True)
H2 = font(17, True)
H3 = font(14, True)
BODY = font(13)
SMALL = font(11)
TINY = font(10, True)


class Card:
    def __init__(self, key: str, x: int, y: int, w: int, h: int, title: str, body: tuple[str, ...], icon: str | None = None, tone: str = BLUE, dashed: bool = False):
        self.key, self.x, self.y, self.w, self.h = key, x, y, w, h
        self.title, self.body, self.icon, self.tone, self.dashed = title, body, icon, tone, dashed


CARDS = (
    Card("browser", 54, 244, 214, 164, "ORPHEUS WORKSPACE", ("React / Vite", "Picture, sound, review"), None, BLUE),
    Card("hosting", 370, 170, 174, 132, "FIREBASE HOSTING", ("Static landing", "and workspace"), None, "#F9A825"),
    Card("api", 610, 170, 220, 132, "ORPHEUS API", ("Cloud Run", "Runs + signed URLs"), "cloud-run", BLUE),
    Card("agent", 916, 142, 262, 190, "AGENT BOUNDARY", ("Vertex AI / Agent Engine", "Part-scoped fitting", "Explicit paid turn"), "vertex-ai", ORANGE, True),
    Card("worker", 484, 478, 238, 154, "ORPHEUS WORKER", ("Cloud Run Job", "FFmpeg + NumPy", "Deterministic render"), "cloud-run", MEDIA),
    Card("storage", 790, 478, 252, 154, "MEDIA / ARTIFACTS", ("Cloud Storage", "Source · takes · exports", "Private bucket"), "cloud-storage", SAGE),
    Card("mcp", 1074, 478, 150, 154, "GRAFANA MCP", ("Cloud Run", "Read-only", "Scoped"), None, EVIDENCE),
    Card("secret", 610, 720, 220, 128, "SECRET MANAGER", ("Server-side identities", "Provider + MCP tokens"), None, RED),
    Card("sql", 900, 720, 198, 128, "METADATA PROFILE", ("Cloud SQL", "Configured backend"), "cloud-sql", MUTED, True),
    Card("grafana", 1294, 390, 246, 246, "GRAFANA CLOUD", ("Loki · Prometheus", "Tempo", "Evidence, not media"), None, "#F46800"),
    Card("provider", 1294, 160, 246, 150, "MODEL PROFILE", ("Vertex / Gemini hosted", "OpenRouter local test"), "vertex-ai", "#7B61FF", True),
)
CARD_BY_KEY = {card.key: card for card in CARDS}


PATHS = (
    ("product", [(268, 250), (370, 250)], "START / REVIEW"),
    ("product", [(544, 236), (610, 236)], "HOSTED REQUEST"),
    ("product", [(830, 236), (916, 236)], "CONFIRMED PART"),
    ("media", [(268, 350), (330, 350), (330, 555), (790, 555)], "SIGNED UPLOAD"),
    ("media", [(720, 302), (720, 478)], "ASYNC JOB"),
    ("media", [(1042, 555), (1074, 555)], ""),
    ("media", [(1042, 555), (1058, 555), (1058, 420), (1294, 420)], "REDACTED TELEMETRY"),
    ("evidence", [(830, 260), (868, 260), (868, 362), (1074, 362), (1074, 478)], "READ-ONLY EVIDENCE"),
    ("evidence", [(1224, 555), (1294, 555)], "MCP QUERY"),
    ("evidence", [(1178, 236), (1294, 236)], "MODEL CALL"),
    ("secret", [(720, 720), (720, 632)], "SERVER-ONLY"),
    ("secret", [(830, 784), (900, 784)], "METADATA"),
)
LABEL_POSITIONS = {
    "CONFIRMED PART": (846, 208),
    "READ-ONLY EVIDENCE": (876, 340),
}


def text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, fill: str, face: ImageFont.ImageFont) -> None:
    draw.text((round(xy[0]), round(xy[1])), value, font=face, fill=fill)


def line_text(draw: ImageDraw.ImageDraw, x: int, y: int, values: tuple[str, ...], face: ImageFont.ImageFont = BODY, fill: str = MUTED, step: int = 18) -> None:
    for index, value in enumerate(values):
        text(draw, (x, y + index * step), value, fill, face)


def dashed_segment(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, offset: int, width: int = 3, dash: int = 14, gap: int = 9) -> None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    if not length:
        return
    ux, uy = dx / length, dy / length
    period = dash + gap
    position = -(offset % period)
    while position < length:
        a, b = max(0, position), min(length, position + dash)
        if b > a:
            draw.line((start[0] + ux * a, start[1] + uy * a, start[0] + ux * b, start[1] + uy * b), fill=color, width=width)
        position += period


def path(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str, offset: int = 0, marching: bool = False, width: int = 3) -> None:
    for first, second in zip(points, points[1:]):
        if marching:
            dashed_segment(draw, first, second, color, offset, width)
        else:
            draw.line((first, second), fill=color, width=width)
    before, final = points[-2], points[-1]
    angle = atan2(final[1] - before[1], final[0] - before[0])
    size = 10
    points_arrow = [
        final,
        (final[0] - size * cos(angle - .48), final[1] - size * sin(angle - .48)),
        (final[0] - size * cos(angle + .48), final[1] - size * sin(angle + .48)),
    ]
    draw.polygon(points_arrow, fill=color)


def dashed_rectangle(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: str, offset: int = 0, width: int = 2) -> None:
    x1, y1, x2, y2 = box
    dashed_segment(draw, (x1, y1), (x2, y1), color, offset, width, 13, 9)
    dashed_segment(draw, (x2, y1), (x2, y2), color, offset, width, 13, 9)
    dashed_segment(draw, (x2, y2), (x1, y2), color, offset, width, 13, 9)
    dashed_segment(draw, (x1, y2), (x1, y1), color, offset, width, 13, 9)


def icon(name: str, size: int) -> Image.Image:
    image = Image.open(ICONS / f"{name}.png").convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    return image


def draw_browser(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.rounded_rectangle((x, y, x + 56, y + 45), radius=7, fill="#E7F2FD", outline=BLUE, width=2)
    draw.rectangle((x + 7, y + 10, x + 49, y + 34), fill=PAPER, outline=RULE)
    draw.line((x + 23, y + 45, x + 33, y + 45), fill=BLUE, width=2)
    draw.line((x + 28, y + 45, x + 28, y + 54), fill=BLUE, width=2)
    draw.line((x + 18, y + 54, x + 38, y + 54), fill=BLUE, width=2)


def draw_firebase(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.polygon([(x + 7, y + 48), (x + 30, y + 4), (x + 46, y + 25), (x + 56, y + 48)], fill="#FFA000")
    draw.polygon([(x + 7, y + 48), (x + 28, y + 28), (x + 46, y + 25), (x + 56, y + 48)], fill="#FFCA28")
    draw.polygon([(x + 28, y + 28), (x + 33, y + 10), (x + 46, y + 25)], fill="#F57C00")


def draw_lock(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.rounded_rectangle((x + 6, y + 26, x + 52, y + 63), radius=5, outline=RED, width=4)
    draw.arc((x + 16, y + 4, x + 42, y + 39), start=180, end=360, fill=RED, width=4)
    draw.ellipse((x + 26, y + 40, x + 32, y + 46), fill=RED)
    draw.line((x + 29, y + 46, x + 29, y + 55), fill=RED, width=3)


def draw_grafana(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    for i in range(10):
        angle = i * (2 * pi / 10)
        cx, cy = x + 30 + cos(angle) * 24, y + 30 + sin(angle) * 24
        draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill="#F46800")
    draw.ellipse((x + 15, y + 15, x + 45, y + 45), fill="#F46800")
    draw.ellipse((x + 23, y + 23, x + 37, y + 37), fill=PAPER)


def draw_card(base: Image.Image, card: Card) -> None:
    draw = ImageDraw.Draw(base)
    box = (card.x, card.y, card.x + card.w, card.y + card.h)
    draw.rounded_rectangle(box, radius=10, fill=PAPER, outline=RULE if card.dashed else card.tone, width=2)
    if card.dashed:
        dashed_rectangle(draw, box, card.tone, width=2)
    draw.rectangle((card.x + 15, card.y + 16, card.x + 21, card.y + card.h - 16), fill=card.tone)
    icon_x, icon_y = card.x + 36, card.y + 22
    if card.icon:
        logo = icon(card.icon, 48)
        base.alpha_composite(logo, (icon_x, icon_y))
        title_x = icon_x + 61
    elif card.key == "browser":
        draw_browser(draw, icon_x, icon_y)
        title_x = icon_x
        icon_y += 66
    elif card.key == "hosting":
        draw_firebase(draw, icon_x, icon_y)
        title_x = icon_x + 65
    elif card.key == "secret":
        draw_lock(draw, icon_x, icon_y)
        title_x = icon_x + 72
    elif card.key == "grafana":
        draw_grafana(draw, icon_x, icon_y)
        title_x = icon_x + 72
    else:
        title_x = icon_x
    text(draw, (title_x, card.y + 27), card.title, INK, H3)
    body_y = card.y + 87 if card.key not in {"browser", "hosting", "secret", "grafana"} else card.y + 91
    line_text(draw, card.x + 36, body_y, card.body, BODY, MUTED, 18)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, tone: str) -> None:
    x, y = xy
    bounds = draw.textbbox((x, y), value, font=TINY)
    draw.rounded_rectangle((x - 7, y - 4, bounds[2] + 7, y + 15), radius=3, fill=PAPER, outline="#E0E8F0")
    text(draw, (x, y), value, tone, TINY)


def frame(index: int) -> Image.Image:
    image = Image.new("RGBA", (W, H), PAPER)
    draw = ImageDraw.Draw(image)
    offset = index * 7
    # Header and legend.
    text(draw, (24, 20), "ORPHEUS / LIVE PRODUCTION PATH", INK, H1)
    text(draw, (24, 56), "Creator input → bounded Part fit → deterministic media work → evidence-backed review", MUTED, BODY)
    draw.rounded_rectangle((735, 18, 1576, 68), radius=6, fill="#F5F8FB", outline=RULE)
    text(draw, (754, 34), "Orange = product request · blue dashes = media/job flow · gray dashes = read-only evidence", MUTED, SMALL)

    # Trust boundaries.
    dashed_rectangle(draw, (24, 92, 298, 886), "#5B7591", offset, 2)
    dashed_rectangle(draw, (322, 92, 1240, 886), "#5B7591", offset, 2)
    dashed_rectangle(draw, (1262, 92, 1576, 886), "#64748B", offset, 2)
    text(draw, (38, 111), "CREATOR DEVICE", INK, H2)
    text(draw, (340, 111), "GOOGLE CLOUD / orpheus-agentic", INK, H2)
    text(draw, (1280, 111), "EXTERNAL EVIDENCE / PROVIDERS", INK, H2)

    # Region labels.
    draw.rounded_rectangle((358, 130, 1198, 150), radius=3, fill=CLOUD)
    text(draw, (370, 134), "EDGE + ORCHESTRATION", MUTED, TINY)
    draw.rounded_rectangle((450, 438, 1058, 458), radius=3, fill="#EEF6FF")
    text(draw, (462, 442), "DETERMINISTIC MEDIA LANE", MUTED, TINY)
    draw.rounded_rectangle((1082, 438, 1224, 458), radius=3, fill="#F5F8FB")
    text(draw, (1094, 442), "MCP", MUTED, TINY)

    # Static cards first, then paths above backgrounds but below labels.
    for card in CARDS:
        draw_card(image, card)

    for kind, points, caption in PATHS:
        if kind == "product":
            path(draw, points, ORANGE, width=4)
        elif kind == "media":
            path(draw, points, MEDIA, offset=offset, marching=True, width=3)
        elif kind == "evidence":
            path(draw, points, EVIDENCE, offset=offset * 2, marching=True, width=3)
        else:
            path(draw, points, RED, offset=offset, marching=True, width=2)
        if caption:
            mid = points[len(points) // 2]
            position = LABEL_POSITIONS.get(caption, (mid[0] + 8, mid[1] - 20))
            label(draw, position, caption, ORANGE if kind == "product" else (MEDIA if kind == "media" else (EVIDENCE if kind == "evidence" else RED)))

    # Callout markers, intentionally few and ordered by the reading path.
    markers = [(50, 150, "1"), (370, 140, "2"), (610, 140, "3"), (916, 112, "4"), (484, 448, "5"), (1074, 448, "6"), (1294, 360, "7"), (790, 448, "8"), (610, 690, "9")]
    for x, y, n in markers:
        draw.rounded_rectangle((x, y, x + 34, y + 34), radius=6, fill=BLUE)
        bbox = draw.textbbox((0, 0), n, font=H3)
        draw.text((x + 17 - (bbox[2] - bbox[0]) / 2, y + 7), n, font=H3, fill=PAPER)

    # Boundary facts are more useful than decorative coverage.
    draw.rounded_rectangle((49, 690, 272, 828), radius=8, fill="#F5F8FB", outline=RULE)
    text(draw, (64, 710), "CREATOR CONTROL", INK, H3)
    line_text(draw, 64, 742, ("Marks the Part", "supplies the take", "approves the artifact"), BODY, MUTED, 19)
    draw.rounded_rectangle((1282, 688, 1556, 828), radius=8, fill="#F5F8FB", outline=RULE)
    text(draw, (1298, 708), "EVIDENCE BOUNDARY", INK, H3)
    line_text(draw, 1298, 740, ("No raw media", "No prompts", "No credentials"), BODY, MUTED, 19)

    draw.rounded_rectangle((24, 910, 1576, 956), radius=6, fill="#F5F8FB", outline=RULE)
    text(draw, (44, 925), "Verified deployed services: Firebase Hosting · orpheus-api · grafana-mcp · orpheus-worker · GCS media buckets. Dashed cards are configured boundaries; no raw media crosses into Grafana.", MUTED, SMALL)
    return image.convert("P", palette=Image.Palette.ADAPTIVE, colors=160)


def cell(root: Element, ident: str, value: str, style: str, x: int, y: int, width: int, height: int, vertex: bool = True, source: str | None = None, target: str | None = None) -> None:
    attrs = {"id": ident, "value": value, "style": style, "parent": "1"}
    if vertex:
        attrs["vertex"] = "1"
    else:
        attrs["edge"] = "1"
        if source:
            attrs["source"] = source
        if target:
            attrs["target"] = target
    node = SubElement(root, "mxCell", attrs)
    geometry = SubElement(node, "mxGeometry", {"x": str(x), "y": str(y), "width": str(width), "height": str(height), "as": "geometry"})
    if not vertex:
        geometry.set("relative", "1")


def image_style(name: str) -> str:
    data = b64encode((ICONS / f"{name}.png").read_bytes()).decode()
    return f"shape=image;html=1;aspect=fixed;imageAspect=0;image=data:image/png;base64,{data};"


def write_drawio() -> None:
    graph = Element("mxGraphModel", {"dx": "1600", "dy": "980", "grid": "1", "gridSize": "10", "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1", "pageScale": "1", "pageWidth": "1600", "pageHeight": "980", "math": "0", "shadow": "0"})
    root = SubElement(graph, "root")
    SubElement(root, "mxCell", {"id": "0"})
    SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    label_style = "shape=label;html=1;align=left;verticalAlign=middle;fontColor=#203247;fontStyle=1;fontSize=17;"
    boundary = "rounded=0;html=1;fillColor=none;dashed=1;dashPattern=10 8;strokeWidth=2;strokeColor=#5B7591;"
    card_style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeWidth=2;strokeColor=#1689D4;fontColor=#203247;fontStyle=1;fontSize=14;align=left;verticalAlign=top;spacingLeft=18;spacingTop=16;"
    dashed_card = "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;dashed=1;dashPattern=10 8;strokeWidth=2;strokeColor=#FF5A36;fontColor=#203247;fontStyle=1;fontSize=14;align=left;verticalAlign=top;spacingLeft=18;spacingTop=16;"
    cell(root, "creator-boundary", "", boundary, 24, 92, 274, 794)
    cell(root, "cloud-boundary", "", boundary, 322, 92, 918, 794)
    cell(root, "external-boundary", "", boundary, 1262, 92, 314, 794)
    cell(root, "title", "ORPHEUS / LIVE PRODUCTION PATH", "shape=label;html=1;fontSize=29;fontStyle=1;fontColor=#203247;align=left;verticalAlign=middle;", 24, 20, 560, 34)
    cell(root, "sub", "Creator input → bounded Part fit → deterministic media work → evidence-backed review", "shape=label;html=1;fontSize=13;fontColor=#50667D;align=left;verticalAlign=middle;", 24, 56, 690, 22)
    cell(root, "creator-label", "CREATOR DEVICE", label_style, 38, 110, 210, 25)
    cell(root, "cloud-label", "GOOGLE CLOUD / orpheus-agentic", label_style, 340, 110, 350, 25)
    cell(root, "external-label", "EXTERNAL EVIDENCE / PROVIDERS", label_style, 1280, 110, 260, 25)
    card_ids: dict[str, str] = {}
    for index, card in enumerate(CARDS, start=20):
        ident = f"card-{card.key}"
        card_ids[card.key] = ident
        body = "<br>".join((f"<b>{card.title}</b>", *card.body))
        cell(root, ident, body, dashed_card if card.dashed else card_style, card.x, card.y, card.w, card.h)
        if card.icon:
            cell(root, f"icon-{card.key}", "", image_style(card.icon), card.x + 18, card.y + 22, 46, 46)
    # The Firebase card uses the official service label; core GCP product icons are embedded for the service cards.
    edge_styles = {
        "product": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;strokeColor=#FF5A36;",
        "media": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=12 8;strokeColor=#2F80ED;",
        "evidence": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=12 8;strokeColor=#64748B;",
        "secret": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=2;dashed=1;dashPattern=8 7;strokeColor=#E7645F;",
    }
    links = (
        ("edge-1", "browser", "hosting", "product"), ("edge-2", "hosting", "api", "product"),
        ("edge-3", "api", "agent", "product"), ("edge-4", "browser", "storage", "media"),
        ("edge-5", "api", "worker", "media"), ("edge-6", "worker", "storage", "media"),
        ("edge-7", "api", "mcp", "evidence"), ("edge-8", "mcp", "grafana", "evidence"),
        ("edge-9", "agent", "provider", "evidence"), ("edge-10", "secret", "api", "secret"),
        ("edge-11", "secret", "sql", "secret"),
    )
    for ident, source, target, tone in links:
        cell(root, ident, "", edge_styles[tone], 0, 0, 0, 0, False, card_ids[source], card_ids[target])
    xml = tostring(graph, encoding="unicode")
    DRAWIO.write_text(f'<mxfile host="app.diagrams.net" version="26.0.14"><diagram id="orpheus-live-production" name="Live production path">{xml}</diagram></mxfile>\n')


if __name__ == "__main__":
    frames = [frame(index) for index in range(FRAMES)]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, disposal=2, optimize=True)
    write_drawio()
    print(OUT)
    print(DRAWIO)
