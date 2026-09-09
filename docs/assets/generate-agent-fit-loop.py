"""Render the bounded Orpheus agent-fit loop and editable Draw.io source. Requires Pillow."""
from __future__ import annotations

from math import atan2, cos, hypot, sin
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUT = ROOT / "orpheus-agent-fit-loop.gif"
DRAWIO = ROOT / "orpheus-agent-fit-loop.drawio"
W, H, FPS, FRAMES = 1600, 940, 8, 28

INK = "#203247"
MUTED = "#50667D"
RULE = "#C9D7E5"
PAPER = "#FFFFFF"
PANEL = "#F5F8FB"
ORANGE = "#FF5A36"
BLUE = "#2F80ED"
GOLD = "#D3912A"
EVIDENCE = "#64748B"
SAGE = "#5FAE7B"
ROSE = "#E7645F"


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
    def __init__(self, box: tuple[int, int, int, int], title: str, note: str, tone: str):
        self.box, self.title, self.note, self.tone = box, title, note, tone


class Step:
    def __init__(self, key: str, box: tuple[int, int, int, int], title: str, body: tuple[str, ...], tone: str, tag: str):
        self.key, self.box, self.title, self.body, self.tone, self.tag = key, box, title, body, tone, tag


AGENT_BOUNDARY = (270, 92, 1046, 842)
DOMAINS = (
    Domain((24, 104, 246, 842), "CREATOR INPUT", "explicit consent", "#8095AA"),
    Domain((296, 138, 526, 470), "PART + BASELINE", "fixed starting point", "#76A6D7"),
    Domain((546, 138, 774, 470), "AGENT SESSION", "bounded paid turn", "#E4A263"),
    Domain((296, 494, 774, 738), "LOCAL FIT TOOLS", "inside accepted windows", "#76A6D7"),
    Domain((794, 424, 1022, 738), "SELECTION GATE", "measured only", "#96A3B4"),
    Domain((1072, 104, 1346, 842), "READ-ONLY EVIDENCE", "Grafana MCP", "#96A3B4"),
    Domain((1370, 104, 1576, 842), "CREATOR VERDICT", "human only", "#8095AA"),
)
STEPS = (
    Step("input", (48, 356, 222, 502), "AUTHORIZE FIT", ("Select one Part", "Assign one family take"), ORANGE, "HUMAN"),
    Step("boundary", (320, 220, 502, 348), "VALIDATE BOUNDARY", ("Confirmed ranges only", "No full-film paid turn"), BLUE, "LOCAL"),
    Step("baseline", (320, 330, 502, 440), "DETERMINISTIC BASELINE", ("Same take · same Part", "Measured starting point"), SAGE, "LOCAL"),
    Step("agent", (570, 220, 750, 370), "ADK COORDINATOR", ("Inspect · reason · call tools", "Crop · timing · gain"), GOLD, "OPTIONAL PAID"),
    Step("inspect", (320, 550, 502, 678), "PART INSPECTION", ("Frames + source audio", "Local Part clock"), BLUE, "TOOL"),
    Step("fit", (570, 550, 750, 678), "FIT CANDIDATE", ("Use accepted windows", "Render one revision"), ORANGE, "TOOL"),
    Step("measure", (818, 490, 998, 558), "MEASURE", ("Loudness · peak · timing",), BLUE, "TOOL"),
    Step("selection", (818, 590, 998, 700), "SELECT OR STOP", ("Needs human review", "or unsuitable"), EVIDENCE, "AGENT RESULT"),
    Step("mcp", (1096, 260, 1322, 410), "GRAFANA MCP", ("History · failures · runtime", "Scoped read-only evidence"), EVIDENCE, "REQUIRED"),
    Step("receipt", (1096, 530, 1322, 658), "EXACT CANDIDATE", ("Clipping · timing · export", "Evidence must be nonempty"), EVIDENCE, "REQUIRED"),
    Step("verdict", (1394, 680, 1552, 824), "AUDITION + VERDICT", ("Compare against picture", "Approve or reject"), ORANGE, "HUMAN"),
)
STEP = {step.key: step for step in STEPS}

# Every animated dash goes from one actual actor, tool, or evidence service to another.
PATHS = (
    ("product", [(222, 429), (270, 429), (270, 284), (320, 284)], "EXPLICIT CONSENT"),
    ("product", [(502, 284), (570, 284)], "PART + TAKE"),
    ("baseline", [(411, 348), (411, 330)], "BASELINE"),
    ("baseline", [(502, 385), (536, 385), (536, 300), (570, 300)], ""),
    ("tool", [(660, 370), (660, 510), (411, 510), (411, 550)], "INSPECT"),
    ("evidence", [(750, 294), (1096, 294)], "HISTORY"),
    ("tool", [(660, 370), (660, 550)], "FIT"),
    ("tool", [(750, 614), (784, 614), (784, 524), (818, 524)], "CANDIDATE"),
    ("evidence", [(998, 524), (1048, 524), (1048, 594), (1096, 594)], "CANDIDATE EVIDENCE"),
    ("evidence", [(1096, 634), (998, 634)], "EVIDENCE OK"),
    ("product", [(998, 645), (1346, 645), (1346, 752), (1394, 752)], "REVIEWABLE CANDIDATE"),
)
LABELS = {
    "EXPLICIT CONSENT": (234, 398),
    "PART + TAKE": (510, 258),
    "BASELINE": (421, 353),
    "INSPECT": (508, 491),
    "HISTORY": (890, 267),
    "FIT": (670, 510),
    "CANDIDATE": (758, 590),
    "CANDIDATE EVIDENCE": (884, 500),
    "EVIDENCE OK": (1005, 610),
    "REVIEWABLE CANDIDATE": (1085, 668),
}


def text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, fill: str, face: ImageFont.ImageFont) -> None:
    draw.text((round(xy[0]), round(xy[1])), value, font=face, fill=fill)


def lines(draw: ImageDraw.ImageDraw, x: int, y: int, values: tuple[str, ...], face: ImageFont.ImageFont = BODY, color: str = MUTED, step: int = 17) -> None:
    for index, value in enumerate(values):
        text(draw, (x, y + index * step), value, color, face)


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


def draw_domain(draw: ImageDraw.ImageDraw, domain: Domain) -> None:
    x1, y1, x2, y2 = domain.box
    draw.rounded_rectangle(domain.box, radius=10, fill="#FBFCFD", outline=domain.tone, width=2)
    draw.rectangle((x1 + 16, y1 + 16, x1 + 22, y1 + 48), fill=domain.tone)
    text(draw, (x1 + 32, y1 + 17), domain.title, INK, H2)
    text(draw, (x1 + 32, y1 + 37), domain.note, MUTED, SMALL)


def draw_agent_boundary(draw: ImageDraw.ImageDraw) -> None:
    x1, y1, x2, y2 = AGENT_BOUNDARY
    draw.rounded_rectangle(AGENT_BOUNDARY, radius=12, fill=PAPER, outline="#5B7591", width=2)
    draw.rounded_rectangle((x1 + 16, y1 - 12, x1 + 298, y1 + 12), radius=3, fill=PAPER)
    text(draw, (x1 + 28, y1 - 7), "ORPHEUS / ONE SELECTED PART", INK, TINY)


def tag(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, tone: str) -> None:
    width = max(56, len(value) * 6 + 18)
    draw.rounded_rectangle((x, y, x + width, y + 20), radius=3, fill="#F2F6FA", outline=RULE)
    draw.ellipse((x + 7, y + 7, x + 13, y + 13), fill=tone)
    text(draw, (x + 19, y + 5), value, tone, TINY)


def draw_step(draw: ImageDraw.ImageDraw, step: Step) -> None:
    x1, y1, x2, y2 = step.box
    draw.rounded_rectangle(step.box, radius=8, fill=PAPER, outline=step.tone, width=2)
    text(draw, (x1 + 16, y1 + 19), step.title, INK, H3)
    tag(draw, x1 + 16, y1 + 53, step.tag, step.tone)
    lines(draw, x1 + 16, y1 + 83, step.body)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, tone: str) -> None:
    x, y = xy
    bounds = draw.textbbox((x, y), value, font=TINY)
    draw.rounded_rectangle((x - 6, y - 4, bounds[2] + 6, y + 14), radius=3, fill=PAPER, outline="#E0E8F0")
    text(draw, (x, y), value, tone, TINY)


def frame(index: int) -> Image.Image:
    image = Image.new("RGBA", (W, H), PAPER)
    draw = ImageDraw.Draw(image)
    offset = index * 7

    text(draw, (24, 20), "ORPHEUS / HOW THE AGENT FITS ONE PART", INK, H1)
    text(draw, (24, 56), "A bounded agent improves a real Foley take; it never becomes the editor of the whole film.", MUTED, BODY)
    draw.rounded_rectangle((908, 18, 1576, 70), radius=6, fill=PANEL, outline=RULE)
    text(draw, (928, 31), "MARCHING DASHES = AGENT TOOL CALL / RESULT", INK, TINY)
    text(draw, (928, 47), "Orange creator · blue local tool · gold paid model · gray read-only evidence · fixed domain borders", MUTED, SMALL)

    # Solid domains are a stable map, never an animation target.
    draw_agent_boundary(draw)
    for domain in DOMAINS:
        draw_domain(draw, domain)

    colors = {"product": ORANGE, "baseline": SAGE, "tool": BLUE, "evidence": EVIDENCE}
    for kind, points, caption in PATHS:
        marching_path(draw, points, colors[kind], offset)
        if caption:
            label(draw, LABELS[caption], caption, colors[kind])

    for step in STEPS:
        draw_step(draw, step)

    draw.rounded_rectangle((48, 760, 998, 824), radius=8, fill=PANEL, outline=RULE)
    text(draw, (68, 775), "HARD BOUNDARY", INK, H3)
    text(draw, (68, 798), "The agent cannot add family events, extend an accepted range, render the full movie as a paid turn, or approve its own candidate.", MUTED, BODY)

    draw.rounded_rectangle((24, 862, 1576, 912), radius=6, fill=PANEL, outline=RULE)
    text(draw, (44, 876), "A missing or empty Grafana receipt stops selection. A passing measurement makes a candidate reviewable; it is never an approval.", MUTED, SMALL)
    text(draw, (44, 894), "After a human approval, the separate local matcher may search the full movie. That later step is deterministic, reviewable, and not a paid-agent run.", MUTED, SMALL)
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


def write_drawio() -> None:
    graph = Element("mxGraphModel", {"dx": str(W), "dy": str(H), "grid": "1", "gridSize": "10", "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1", "pageScale": "1", "pageWidth": str(W), "pageHeight": str(H), "math": "0", "shadow": "0"})
    root = SubElement(graph, "root")
    SubElement(root, "mxCell", {"id": "0"})
    SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    boundary_style = "rounded=1;html=1;fillColor=#FFFFFF;strokeWidth=2;strokeColor=#5B7591;"
    domain_style = "rounded=1;html=1;fillColor=#FBFCFD;strokeWidth=2;strokeColor=#8095AA;"
    label_style = "shape=label;html=1;align=left;verticalAlign=middle;fontColor=#203247;fontStyle=1;fontSize=16;"
    note_style = "shape=label;html=1;align=left;verticalAlign=middle;fontColor=#50667D;fontSize=11;"
    card_style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeWidth=2;strokeColor=#2F80ED;fontColor=#203247;fontStyle=1;fontSize=14;align=left;verticalAlign=top;spacingLeft=16;spacingTop=18;"
    cell(root, "title", "ORPHEUS / HOW THE AGENT FITS ONE PART", "shape=label;html=1;fontSize=29;fontStyle=1;fontColor=#203247;align=left;verticalAlign=middle;", 24, 20, 700, 34)
    cell(root, "sub", "A bounded agent improves a real Foley take; it never becomes the editor of the whole film.", "shape=label;html=1;fontSize=13;fontColor=#50667D;align=left;verticalAlign=middle;", 24, 56, 800, 22)
    x1, y1, x2, y2 = AGENT_BOUNDARY
    cell(root, "agent-boundary", "", boundary_style, x1, y1, x2 - x1, y2 - y1)
    cell(root, "agent-boundary-label", "ORPHEUS / ONE SELECTED PART", label_style, x1 + 28, y1 + 4, 320, 20)
    for index, domain in enumerate(DOMAINS, start=10):
        x1, y1, x2, y2 = domain.box
        cell(root, f"domain-{index}", "", domain_style, x1, y1, x2 - x1, y2 - y1)
        cell(root, f"domain-label-{index}", domain.title, label_style, x1 + 32, y1 + 16, x2 - x1 - 48, 20)
        cell(root, f"domain-note-{index}", domain.note, note_style, x1 + 32, y1 + 36, x2 - x1 - 48, 18)

    step_ids: dict[str, str] = {}
    for index, step in enumerate(STEPS, start=30):
        ident = f"step-{step.key}"
        step_ids[step.key] = ident
        x1, y1, x2, y2 = step.box
        body = "<br>".join((f"<b>{step.title}</b>", *step.body, f"<font color='#50667D'>{step.tag.lower()}</font>"))
        cell(root, ident, body, card_style.replace("#2F80ED", step.tone), x1, y1, x2 - x1, y2 - y1)

    styles = {
        "product": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=13 9;strokeColor=#FF5A36;",
        "baseline": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=13 9;strokeColor=#5FAE7B;",
        "tool": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=13 9;strokeColor=#2F80ED;",
        "evidence": "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=13 9;strokeColor=#64748B;",
    }
    links = (
        ("edge-1", "input", "boundary", "product"),
        ("edge-2", "boundary", "agent", "product"),
        ("edge-3", "boundary", "baseline", "baseline"),
        ("edge-4", "agent", "inspect", "tool"),
        ("edge-5", "agent", "mcp", "evidence"),
        ("edge-6", "agent", "fit", "tool"),
        ("edge-7", "fit", "measure", "tool"),
        ("edge-8", "measure", "receipt", "evidence"),
        ("edge-9", "receipt", "selection", "evidence"),
        ("edge-10", "selection", "verdict", "product"),
    )
    for ident, source, target, tone in links:
        cell(root, ident, "", styles[tone], 0, 0, 0, 0, False, step_ids[source], step_ids[target])
    xml = tostring(graph, encoding="unicode")
    DRAWIO.write_text(f'<mxfile host="app.diagrams.net" version="26.0.14"><diagram id="orpheus-agent-fit-loop" name="Agent fit loop">{xml}</diagram></mxfile>\n')


def verify_motion() -> None:
    first, later = frame(0).convert("RGB"), frame(8).convert("RGB")
    borders = ((24, 104, 246, 108), (270, 92, 1046, 96), (1370, 104, 1576, 108))
    assert all(ImageChops.difference(first.crop(border), later.crop(border)).getbbox() is None for border in borders)
    assert ImageChops.difference(first, later).getbbox() is not None


if __name__ == "__main__":
    verify_motion()
    frames = [frame(index).convert("P", palette=Image.Palette.ADAPTIVE, colors=160) for index in range(FRAMES)]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, disposal=2, optimize=True)
    write_drawio()
    print(OUT)
    print(DRAWIO)
