"""Render Orpheus's production-path GIF and editable Draw.io source. Requires Pillow."""
from __future__ import annotations

from base64 import b64encode
from math import atan2, cos, hypot, sin
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUT = ROOT / "orpheus-live-production-path.gif"
DRAWIO = ROOT / "orpheus-live-production-path.drawio"
ICONS = ROOT / "gcp-icons"
W, H, FPS, FRAMES = 1600, 940, 8, 28

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
GOLD = "#D3912A"
SAGE = "#5FAE7B"


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
H2 = font(16, True)
H3 = font(14, True)
BODY = font(13)
SMALL = font(11)
TINY = font(10, True)


class Domain:
    def __init__(self, key: str, box: tuple[int, int, int, int], title: str, note: str, tone: str = RULE):
        self.key, self.box, self.title, self.note, self.tone = key, box, title, note, tone


class Card:
    def __init__(
        self,
        key: str,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        body: tuple[str, ...],
        icon: str | None = None,
        tone: str = BLUE,
        state: str = "DEPLOYED",
    ):
        self.key, self.x, self.y, self.w, self.h = key, x, y, w, h
        self.title, self.body, self.icon, self.tone, self.state = title, body, icon, tone, state


GOOGLE_CLOUD_BOUNDARY = (262, 92, 1190, 842)


DOMAINS = (
    Domain("creator", (24, 104, 250, 842), "CREATOR", "browser control", "#8095AA"),
    Domain("delivery", (278, 104, 742, 386), "DELIVERY", "entry and API", "#76A6D7"),
    Domain("coordination", (764, 104, 1178, 386), "AGENT COORDINATION", "Part-scoped fit", "#E4A263"),
    Domain("media", (278, 410, 742, 730), "MEDIA PIPELINE", "deterministic work", "#76A6D7"),
    Domain("evidence", (764, 410, 1178, 730), "EVIDENCE PLANE", "read-only history", "#96A3B4"),
    Domain("external", (1202, 104, 1576, 842), "EXTERNAL ENDPOINTS", "no raw media", "#8A98A9"),
)

CARDS = (
    Card("browser", 48, 400, 178, 142, "ORPHEUS WORKSPACE", ("Creator marks a Part", "and reviews results"), None, BLUE),
    Card("hosting", 310, 220, 178, 130, "FIREBASE HOSTING", ("Static web delivery", "Landing + workspace"), None, "#F9A825"),
    Card("api", 526, 220, 180, 130, "ORPHEUS API", ("Cloud Run service", "Runs + signed URLs"), "cloud-run", BLUE),
    Card("agent", 800, 220, 342, 130, "AGENT COORDINATOR", ("Vertex AI / Agent Engine", "Bounded Part fit"), "vertex-ai", ORANGE, "CONFIGURED"),
    Card("worker", 310, 510, 178, 140, "ORPHEUS WORKER", ("Cloud Run Job", "FFmpeg + NumPy"), "cloud-run", MEDIA),
    Card("storage", 526, 510, 180, 140, "MEDIA ARTIFACTS", ("Cloud Storage", "Source · takes · exports"), "cloud-storage", SAGE),
    Card("mcp", 800, 510, 210, 140, "GRAFANA MCP", ("Cloud Run service", "Scoped read-only tools"), "cloud-run", EVIDENCE),
    Card("provider", 1236, 220, 300, 130, "MODEL PROVIDER", ("Gemini hosted profile", "OpenRouter local test"), "vertex-ai", ORANGE, "CONFIGURED"),
    Card("grafana", 1236, 510, 300, 140, "GRAFANA CLOUD", ("Loki · Prometheus · Tempo", "Evidence, not media"), None, "#F46800"),
)
CARD = {card.key: card for card in CARDS}

# Each animated path terminates at a service. Domains, cards, and dividers never march.
PATHS = (
    ("product", [(226, 471), (268, 471), (268, 285), (310, 285)], "OPEN WORKSPACE"),
    ("product", [(488, 285), (526, 285)], ""),
    ("product", [(706, 285), (800, 285)], "PART REQUEST"),
    ("agent", [(1142, 285), (1236, 285)], "MODEL TURN"),
    ("media", [(616, 350), (616, 450), (399, 450), (399, 510)], "START JOB"),
    ("media", [(488, 580), (526, 580)], "WRITE ARTIFACT"),
    ("evidence", [(971, 350), (971, 510)], "HISTORY QUERY"),
    ("evidence", [(1010, 580), (1236, 580)], "READ-ONLY EVIDENCE"),
)


# The visible caption positions keep labels clear of every service card.
LABEL_POSITIONS = {
    "OPEN WORKSPACE": (237, 435),
    "PART REQUEST": (714, 259),
    "MODEL TURN": (1153, 259),
    "START JOB": (497, 421),
    "WRITE ARTIFACT": (491, 555),
    "HISTORY QUERY": (978, 420),
    "READ-ONLY EVIDENCE": (1045, 555),
}


def text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, fill: str, face: ImageFont.ImageFont) -> None:
    draw.text((round(xy[0]), round(xy[1])), value, font=face, fill=fill)


def line_text(draw: ImageDraw.ImageDraw, x: int, y: int, values: tuple[str, ...], face: ImageFont.ImageFont = BODY, fill: str = MUTED, step: int = 18) -> None:
    for index, value in enumerate(values):
        text(draw, (x, y + index * step), value, fill, face)


def dashed_segment(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, offset: int, width: int = 3, dash: int = 13, gap: int = 9) -> None:
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


def marching_path(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str, offset: int) -> None:
    for first, second in zip(points, points[1:]):
        dashed_segment(draw, first, second, color, offset)
    before, final = points[-2], points[-1]
    angle = atan2(final[1] - before[1], final[0] - before[0])
    arrow = [
        final,
        (final[0] - 10 * cos(angle - .48), final[1] - 10 * sin(angle - .48)),
        (final[0] - 10 * cos(angle + .48), final[1] - 10 * sin(angle + .48)),
    ]
    draw.polygon(arrow, fill=color)


def icon(name: str, size: int) -> Image.Image:
    image = Image.open(ICONS / f"{name}.png").convert("RGBA")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    return image


def draw_browser(base: Image.Image, x: int, y: int) -> None:
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((x, y, x + 50, y + 39), radius=6, fill="#E7F2FD", outline=BLUE, width=2)
    draw.rectangle((x + 7, y + 9, x + 43, y + 30), fill=PAPER, outline=RULE)
    draw.line((x + 20, y + 39, x + 30, y + 39), fill=BLUE, width=2)
    draw.line((x + 25, y + 39, x + 25, y + 48), fill=BLUE, width=2)
    draw.line((x + 16, y + 48, x + 34, y + 48), fill=BLUE, width=2)


def draw_grafana(base: Image.Image, x: int, y: int) -> None:
    draw = ImageDraw.Draw(base)
    for i in range(10):
        angle = i * (6.28318530718 / 10)
        cx, cy = x + 26 + cos(angle) * 21, y + 26 + sin(angle) * 21
        draw.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill="#F46800")
    draw.ellipse((x + 13, y + 13, x + 39, y + 39), fill="#F46800")
    draw.ellipse((x + 20, y + 20, x + 32, y + 32), fill=PAPER)


def status_badge(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, tone: str) -> None:
    width = 72 if value == "DEPLOYED" else 84
    draw.rounded_rectangle((x, y, x + width, y + 20), radius=3, fill="#F2F6FA", outline=RULE)
    draw.ellipse((x + 7, y + 7, x + 13, y + 13), fill=tone)
    text(draw, (x + 19, y + 5), value, tone, TINY)


def draw_card(base: Image.Image, card: Card) -> None:
    draw = ImageDraw.Draw(base)
    box = (card.x, card.y, card.x + card.w, card.y + card.h)
    draw.rounded_rectangle(box, radius=8, fill=PAPER, outline=card.tone, width=2)
    icon_x, title_x = card.x + 16, card.x + 16
    if card.icon:
        base.alpha_composite(icon(card.icon, 43), (icon_x, card.y + 18))
        title_x = icon_x + 54
    elif card.key == "browser":
        draw_browser(base, icon_x, card.y + 18)
        title_x = icon_x + 62
    elif card.key == "grafana":
        draw_grafana(base, icon_x, card.y + 18)
        title_x = icon_x + 62
    text(draw, (title_x, card.y + 23), card.title, INK, H3)
    status_badge(draw, card.x + 16, card.y + 73, card.state, card.tone)
    line_text(draw, card.x + 16, card.y + 101, card.body, BODY, MUTED, 17)


def draw_google_cloud_boundary(draw: ImageDraw.ImageDraw) -> None:
    x1, y1, x2, y2 = GOOGLE_CLOUD_BOUNDARY
    draw.rounded_rectangle(GOOGLE_CLOUD_BOUNDARY, radius=12, fill="#FFFFFF", outline="#5B7591", width=2)
    draw.rounded_rectangle((x1 + 16, y1 - 12, x1 + 288, y1 + 12), radius=3, fill=PAPER)
    text(draw, (x1 + 28, y1 - 7), "GOOGLE CLOUD / ORPHEUS-AGENTIC", INK, TINY)


def draw_domain(draw: ImageDraw.ImageDraw, domain: Domain) -> None:
    x1, y1, x2, y2 = domain.box
    draw.rounded_rectangle(domain.box, radius=10, fill="#FBFCFD", outline=domain.tone, width=2)
    draw.rectangle((x1 + 16, y1 + 16, x1 + 22, y1 + 48), fill=domain.tone)
    text(draw, (x1 + 32, y1 + 17), domain.title, INK, H2)
    text(draw, (x1 + 32, y1 + 37), domain.note, MUTED, SMALL)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, tone: str) -> None:
    x, y = xy
    bounds = draw.textbbox((x, y), value, font=TINY)
    draw.rounded_rectangle((x - 6, y - 4, bounds[2] + 6, y + 14), radius=3, fill=PAPER, outline="#E0E8F0")
    text(draw, (x, y), value, tone, TINY)


def frame(index: int) -> Image.Image:
    image = Image.new("RGBA", (W, H), PAPER)
    draw = ImageDraw.Draw(image)
    offset = index * 7

    text(draw, (24, 20), "ORPHEUS / LIVE PRODUCTION PATH", INK, H1)
    text(draw, (24, 56), "One bounded Part becomes a reviewed, deterministic full-film decision.", MUTED, BODY)
    draw.rounded_rectangle((910, 18, 1576, 70), radius=6, fill=PANEL, outline=RULE)
    text(draw, (928, 31), "MARCHING DASHES = SERVICE-TO-SERVICE CALLS", INK, TINY)
    text(draw, (928, 47), "Orange product · blue media · gold model · gray evidence · fixed domain borders", MUTED, SMALL)

    # Fixed domains are deliberately solid and identical on every frame.
    draw_google_cloud_boundary(draw)
    for domain in DOMAINS:
        draw_domain(draw, domain)

    # All actual links animate, but only the links between service cards.
    colors = {"product": ORANGE, "agent": GOLD, "media": MEDIA, "evidence": EVIDENCE}
    for kind, points, caption in PATHS:
        marching_path(draw, points, colors[kind], offset)
        if caption:
            label(draw, LABEL_POSITIONS[caption], caption, colors[kind])

    # Cards are rendered above service lines so routes terminate cleanly at their owner.
    for card in CARDS:
        draw_card(image, card)

    draw.rounded_rectangle((304, 760, 1150, 824), radius=8, fill=PANEL, outline=RULE)
    text(draw, (324, 775), "CONFIGURED SUPPORTS", INK, H3)
    text(draw, (324, 798), "Secret Manager keeps provider and Grafana tokens server-side. Cloud SQL is the configured run-record backend.", MUTED, BODY)

    draw.rounded_rectangle((24, 862, 1576, 912), radius=6, fill=PANEL, outline=RULE)
    text(draw, (44, 876), "Verified deployed: Firebase Hosting · orpheus-api · grafana-mcp · orpheus-worker · GCS media buckets. Configured: Vertex/Agent Engine · model provider · Cloud SQL.", MUTED, SMALL)
    text(draw, (44, 894), "Media remains in the private storage lane; Grafana receives only redacted evidence.", MUTED, SMALL)
    return image


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
    graph = Element("mxGraphModel", {"dx": str(W), "dy": str(H), "grid": "1", "gridSize": "10", "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1", "pageScale": "1", "pageWidth": str(W), "pageHeight": str(H), "math": "0", "shadow": "0"})
    root = SubElement(graph, "root")
    SubElement(root, "mxCell", {"id": "0"})
    SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    cloud_style = "rounded=1;html=1;fillColor=#FFFFFF;strokeWidth=2;strokeColor=#5B7591;"
    domain_style = "rounded=1;html=1;fillColor=#FBFCFD;strokeWidth=2;strokeColor=#8095AA;"
    label_style = "shape=label;html=1;align=left;verticalAlign=middle;fontColor=#203247;fontStyle=1;fontSize=16;"
    note_style = "shape=label;html=1;align=left;verticalAlign=middle;fontColor=#50667D;fontSize=11;"
    card_style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeWidth=2;strokeColor=#1689D4;fontColor=#203247;fontStyle=1;fontSize=14;align=left;verticalAlign=top;spacingLeft=16;spacingTop=20;"
    configured_card = "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeWidth=2;strokeColor=#FF5A36;fontColor=#203247;fontStyle=1;fontSize=14;align=left;verticalAlign=top;spacingLeft=16;spacingTop=20;"
    cell(root, "title", "ORPHEUS / LIVE PRODUCTION PATH", "shape=label;html=1;fontSize=29;fontStyle=1;fontColor=#203247;align=left;verticalAlign=middle;", 24, 20, 600, 34)
    cell(root, "sub", "One bounded Part becomes a reviewed, deterministic full-film decision.", "shape=label;html=1;fontSize=13;fontColor=#50667D;align=left;verticalAlign=middle;", 24, 56, 700, 22)
    x1, y1, x2, y2 = GOOGLE_CLOUD_BOUNDARY
    cell(root, "google-cloud-boundary", "", cloud_style, x1, y1, x2 - x1, y2 - y1)
    cell(root, "google-cloud-label", "GOOGLE CLOUD / ORPHEUS-AGENTIC", label_style, x1 + 28, y1 + 4, 320, 20)
    domain_ids: dict[str, str] = {}
    for index, domain in enumerate(DOMAINS, start=2):
        ident = f"domain-{domain.key}"
        domain_ids[domain.key] = ident
        x1, y1, x2, y2 = domain.box
        cell(root, ident, "", domain_style, x1, y1, x2 - x1, y2 - y1)
        cell(root, f"domain-label-{domain.key}", domain.title, label_style, x1 + 32, y1 + 16, x2 - x1 - 48, 20)
        cell(root, f"domain-note-{domain.key}", domain.note, note_style, x1 + 32, y1 + 36, x2 - x1 - 48, 18)

    card_ids: dict[str, str] = {}
    for card in CARDS:
        ident = f"card-{card.key}"
        card_ids[card.key] = ident
        body = "<br>".join((f"<b>{card.title}</b>", *card.body, f"<font color='#50667D'>{card.state.lower()}</font>"))
        cell(root, ident, body, configured_card if card.state == "CONFIGURED" else card_style, card.x, card.y, card.w, card.h)
        if card.icon:
            cell(root, f"icon-{card.key}", "", image_style(card.icon), card.x + 14, card.y + 14, 43, 43)

    styles = {
        "product": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=13 9;strokeColor=#FF5A36;",
        "agent": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=13 9;strokeColor=#D3912A;",
        "media": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=13 9;strokeColor=#2F80ED;",
        "evidence": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=13 9;strokeColor=#64748B;",
    }
    links = (
        ("edge-1", "browser", "hosting", "product"),
        ("edge-2", "hosting", "api", "product"),
        ("edge-3", "api", "agent", "product"),
        ("edge-4", "agent", "provider", "agent"),
        ("edge-5", "api", "worker", "media"),
        ("edge-6", "worker", "storage", "media"),
        ("edge-7", "agent", "mcp", "evidence"),
        ("edge-8", "mcp", "grafana", "evidence"),
    )
    for ident, source, target, tone in links:
        cell(root, ident, "", styles[tone], 0, 0, 0, 0, False, card_ids[source], card_ids[target])
    xml = tostring(graph, encoding="unicode")
    DRAWIO.write_text(f'<mxfile host="app.diagrams.net" version="26.0.14"><diagram id="orpheus-live-production" name="Live production path">{xml}</diagram></mxfile>\n')


def verify_motion() -> None:
    first, later = frame(0).convert("RGB"), frame(8).convert("RGB")
    # Every domain border is outside every service route and must stay byte-identical.
    for border in ((24, 104, 250, 108), (262, 92, 1190, 96), (1202, 104, 1576, 108)):
        assert ImageChops.difference(first.crop(border), later.crop(border)).getbbox() is None
    # The service paths must carry the only frame-to-frame animation.
    assert ImageChops.difference(first, later).getbbox() is not None


if __name__ == "__main__":
    verify_motion()
    frames = [frame(index).convert("P", palette=Image.Palette.ADAPTIVE, colors=160) for index in range(FRAMES)]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, disposal=2, optimize=True)
    write_drawio()
    print(OUT)
    print(DRAWIO)
