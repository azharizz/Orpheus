"""Render the bounded Orpheus agent-turn diagram and editable Draw.io source. Requires Pillow."""
from __future__ import annotations

from math import atan2, cos, hypot, sin
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).parent
OUT = ROOT / "orpheus-agent-fit-loop.gif"
DRAWIO = ROOT / "orpheus-agent-fit-loop.drawio"
W, H, FPS, FRAMES = 1600, 900, 8, 28

BLACK = "#0C0E10"
RAISED = "#171A1D"
ACTIVE = "#252A2F"
CHALK = "#EFEFE8"
MUTED = "#ABB2B7"
RULE = "#343B42"
EDGE = "#718089"
ORANGE = "#FF5A36"
GOLD = "#EAC17C"
SAGE = "#9DCFAD"
ROSE = "#FF8790"
BLUE = "#8AB4F8"


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


TITLE = font(31, True)
SUBTITLE = font(14)
H2 = font(16, True)
H3 = font(13, True)
BODY = font(12)
SMALL = font(10, True)


class Station:
    def __init__(self, key: str, x: int, title: str, detail: tuple[str, ...], tone: str, tag: str):
        self.key, self.x, self.title, self.detail, self.tone, self.tag = key, x, title, detail, tone, tag


SCOPE = (274, 150, 1272, 730)
STATION_Y = 442
STATION_W, STATION_H = 130, 118
STATIONS = (
    Station("baseline", 310, "BASELINE", ("Deterministic", "same Part"), SAGE, "LOCAL"),
    Station("history", 465, "HISTORY", ("Grafana MCP", "read-only"), GOLD, "EVIDENCE"),
    Station("inspect", 620, "INSPECT", ("Frames +", "source audio"), BLUE, "LOCAL"),
    Station("fit", 775, "FIT", ("Crop · gain", "timing"), ORANGE, "AGENT"),
    Station("measure", 930, "MEASURE", ("Peak · loudness", "timing"), BLUE, "LOCAL"),
    Station("verify", 1085, "VERIFY", ("Exact MCP", "evidence"), GOLD, "EVIDENCE"),
)
STATION = {station.key: station for station in STATIONS}

# The first point is the source and the final point is the arrow target.
PATHS = (
    ("creator", [(238, 500), (286, 500), (286, 501), (310, 501)], "CONSENT"),
    ("baseline", [(440, 501), (465, 501)], ""),
    ("history", [(595, 501), (620, 501)], ""),
    ("inspect", [(750, 501), (775, 501)], ""),
    ("fit", [(905, 501), (930, 501)], ""),
    ("verify", [(1060, 501), (1085, 501)], ""),
    ("creator", [(1215, 501), (1330, 501), (1330, 500), (1350, 500)], "HUMAN REVIEW"),
)
PATH_COLORS = {
    "creator": ORANGE,
    "baseline": SAGE,
    "history": GOLD,
    "inspect": BLUE,
    "fit": ORANGE,
    "verify": GOLD,
}
LABELS = {"CONSENT": (247, 472), "HUMAN REVIEW": (1223, 472)}


def text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, fill: str, face: ImageFont.ImageFont) -> None:
    draw.text((round(xy[0]), round(xy[1])), value, font=face, fill=fill)


def lines(draw: ImageDraw.ImageDraw, x: int, y: int, values: tuple[str, ...], fill: str = MUTED, step: int = 17) -> None:
    for index, value in enumerate(values):
        text(draw, (x, y + index * step), value, fill, BODY)


def dash_start(offset: int, dash: int, gap: int) -> int:
    """Return the dash phase measured forward from a path source."""
    return offset % (dash + gap)


def dashed_segment(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, offset: int, width: int = 3, dash: int = 14, gap: int = 9) -> None:
    """Move dashes from start toward end as the offset increases."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    if not length:
        return
    ux, uy = dx / length, dy / length
    period = dash + gap
    position = dash_start(offset, dash, gap)
    while position < length:
        a, b = max(0, position), min(length, position + dash)
        if b > a:
            draw.line((start[0] + ux * a, start[1] + uy * a, start[0] + ux * b, start[1] + uy * b), fill=color, width=width)
        position += period


def marching_path(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str, offset: int) -> None:
    for first, second in zip(points, points[1:]):
        dashed_segment(draw, first, second, color, offset)
    before, target = points[-2], points[-1]
    angle = atan2(target[1] - before[1], target[0] - before[0])
    arrow = [
        target,
        (target[0] - 10 * cos(angle - .48), target[1] - 10 * sin(angle - .48)),
        (target[0] - 10 * cos(angle + .48), target[1] - 10 * sin(angle + .48)),
    ]
    draw.polygon(arrow, fill=color)


def frame_rule(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: str = RULE, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=8, outline=color, width=width)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, tone: str) -> None:
    width = max(52, 16 + len(value) * 6)
    draw.rounded_rectangle((x, y, x + width, y + 20), radius=3, fill=ACTIVE, outline=RULE)
    draw.ellipse((x + 7, y + 7, x + 13, y + 13), fill=tone)
    text(draw, (x + 19, y + 5), value, tone, SMALL)


def draw_station(draw: ImageDraw.ImageDraw, station: Station) -> None:
    x, y = station.x, STATION_Y
    draw.rounded_rectangle((x, y, x + STATION_W, y + STATION_H), radius=8, fill=RAISED, outline=station.tone, width=2)
    draw.rectangle((x + 14, y + 16, x + 18, y + 44), fill=station.tone)
    text(draw, (x + 29, y + 18), station.title, CHALK, H3)
    pill(draw, x + 14, y + 54, station.tag, station.tone)
    lines(draw, x + 14, y + 84, station.detail)


def draw_actor(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, detail: tuple[str, ...]) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=10, fill=RAISED, outline=ORANGE, width=2)
    text(draw, (x1 + 16, y1 + 20), title, CHALK, H3)
    pill(draw, x1 + 16, y1 + 52, "HUMAN", ORANGE)
    lines(draw, x1 + 16, y1 + 84, detail)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, tone: str) -> None:
    x, y = xy
    bounds = draw.textbbox((x, y), value, font=SMALL)
    draw.rounded_rectangle((x - 6, y - 4, bounds[2] + 6, y + 14), radius=3, fill=BLACK, outline=RULE)
    text(draw, (x, y), value, tone, SMALL)


def frame(index: int) -> Image.Image:
    image = Image.new("RGBA", (W, H), BLACK)
    draw = ImageDraw.Draw(image)
    offset = index * 7

    text(draw, (48, 36), "ORPHEUS / BOUNDED AGENT TURN", CHALK, TITLE)
    text(draw, (48, 78), "One confirmed Part becomes one reviewable candidate. The agent never approves it.", MUTED, SUBTITLE)
    frame_rule(draw, (1075, 30, 1552, 84), RULE)
    text(draw, (1095, 45), "DASHES MOVE WITH THE ARROW", CHALK, SMALL)
    text(draw, (1095, 62), "static lines define the safe Part scope", MUTED, BODY)

    # This is a fixed frame, not an animated border.
    frame_rule(draw, SCOPE, EDGE, 2)
    draw.rectangle((SCOPE[0] + 20, SCOPE[1] - 12, SCOPE[0] + 276, SCOPE[1] + 12), fill=BLACK)
    text(draw, (SCOPE[0] + 34, SCOPE[1] - 7), "ONE CONFIRMED PART / 05–60 S", CHALK, SMALL)

    draw_actor(draw, (48, 420, 238, 580), "CREATOR SETUP", ("Confirm Part", "Assign family take", "Allow paid fit"))
    draw_actor(draw, (1350, 420, 1552, 580), "CREATOR VERDICT", ("Audition candidate", "Approve or reject"))

    draw.rounded_rectangle((470, 226, 1080, 368), radius=12, fill=RAISED, outline=ORANGE, width=2)
    text(draw, (496, 253), "ADK COORDINATOR", ORANGE, H2)
    text(draw, (496, 282), "Directs only the shown tools inside this Part.", CHALK, BODY)
    text(draw, (496, 306), "Its allowed adjustment: crop · gain · timing.", MUTED, BODY)
    pill(draw, 914, 250, "OPTIONAL PAID", GOLD)
    pill(draw, 914, 284, "NO SELF-APPROVAL", ROSE)

    # Static spokes explain agency; they never animate.
    for station in STATIONS[1:5]:
        center = station.x + STATION_W // 2
        draw.line((center, 368, center, STATION_Y - 8), fill=RULE, width=1)
    for station in STATIONS:
        draw_station(draw, station)

    for kind, points, caption in PATHS:
        marching_path(draw, points, PATH_COLORS[kind], offset)
        if caption:
            label(draw, LABELS[caption], caption, PATH_COLORS[kind])

    draw.rounded_rectangle((310, 636, 1215, 684), radius=8, fill=ACTIVE, outline=RULE)
    text(draw, (332, 651), "STOP IF EVIDENCE IS EMPTY OR THE CANDIDATE IS UNSUITABLE.", CHALK, H3)
    text(draw, (332, 669), "A passing measurement is only a handoff to the human reviewer.", MUTED, BODY)

    draw.rounded_rectangle((48, 782, 1552, 846), radius=8, fill=RAISED, outline=RULE)
    text(draw, (70, 797), "HARD LIMIT", CHALK, H3)
    text(draw, (70, 819), "No new family events · no range extension · no paid full-film edit · no automatic approval.", MUTED, BODY)
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
    graph = Element("mxGraphModel", {"dx": str(W), "dy": str(H), "grid": "1", "gridSize": "10", "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1", "pageScale": "1", "pageWidth": str(W), "pageHeight": str(H), "math": "0", "shadow": "0", "background": BLACK})
    root = SubElement(graph, "root")
    SubElement(root, "mxCell", {"id": "0"})
    SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    cell(root, "background", "", f"rounded=0;html=1;fillColor={BLACK};strokeColor=none;", 0, 0, W, H)
    label_style = f"shape=label;html=1;align=left;verticalAlign=middle;fontColor={CHALK};fontStyle=1;fontSize=16;"
    note_style = f"shape=label;html=1;align=left;verticalAlign=middle;fontColor={MUTED};fontSize=12;"
    scope_style = f"rounded=1;html=1;fillColor=none;strokeWidth=2;strokeColor={EDGE};"
    station_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={RAISED};strokeWidth=2;strokeColor={BLUE};fontColor={CHALK};fontStyle=1;fontSize=13;align=left;verticalAlign=top;spacingLeft=14;spacingTop=18;"
    actor_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={RAISED};strokeWidth=2;strokeColor={ORANGE};fontColor={CHALK};fontStyle=1;fontSize=13;align=left;verticalAlign=top;spacingLeft=16;spacingTop=18;"
    agent_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={RAISED};strokeWidth=2;strokeColor={ORANGE};fontColor={CHALK};fontStyle=1;fontSize=16;align=left;verticalAlign=top;spacingLeft=26;spacingTop=24;"
    cell(root, "title", "ORPHEUS / BOUNDED AGENT TURN", f"shape=label;html=1;fontSize=31;fontStyle=1;fontColor={CHALK};align=left;verticalAlign=middle;", 48, 36, 650, 34)
    cell(root, "subtitle", "One confirmed Part becomes one reviewable candidate. The agent never approves it.", note_style, 48, 78, 800, 22)
    x1, y1, x2, y2 = SCOPE
    cell(root, "scope", "", scope_style, x1, y1, x2 - x1, y2 - y1)
    cell(root, "scope-label", "ONE CONFIRMED PART / 05–60 S", label_style, x1 + 34, y1 + 3, 300, 20)
    cell(root, "creator-setup", "<b>CREATOR SETUP</b><br>Confirm Part<br>Assign family take<br>Allow paid fit", actor_style, 48, 420, 190, 160)
    cell(root, "agent", "<b>ADK COORDINATOR</b><br>Directs only the shown tools inside this Part.<br>Crop · gain · timing", agent_style, 470, 226, 610, 142)
    cell(root, "creator-verdict", "<b>CREATOR VERDICT</b><br>Audition candidate<br>Approve or reject", actor_style, 1350, 420, 202, 160)

    ids: dict[str, str] = {}
    for index, station in enumerate(STATIONS, start=20):
        ident = f"station-{station.key}"
        ids[station.key] = ident
        style = station_style.replace(BLUE, station.tone)
        value = "<br>".join((f"<b>{station.title}</b>", *station.detail, f"<font color='{MUTED}'>{station.tag.lower()}</font>"))
        cell(root, ident, value, style, station.x, STATION_Y, STATION_W, STATION_H)

    edge_styles = {
        "creator": f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=14 9;strokeColor={ORANGE};",
        "baseline": f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=14 9;strokeColor={SAGE};",
        "history": f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=14 9;strokeColor={GOLD};",
        "inspect": f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=14 9;strokeColor={BLUE};",
        "fit": f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=14 9;strokeColor={ORANGE};",
        "verify": f"edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;endFill=1;strokeWidth=3;dashed=1;dashPattern=14 9;strokeColor={GOLD};",
    }
    links = (
        ("edge-1", "creator-setup", "baseline", "creator"),
        ("edge-2", "baseline", "history", "baseline"),
        ("edge-3", "history", "inspect", "history"),
        ("edge-4", "inspect", "fit", "inspect"),
        ("edge-5", "fit", "measure", "fit"),
        ("edge-6", "measure", "verify", "verify"),
        ("edge-7", "verify", "creator-verdict", "creator"),
    )
    for ident, source, target, tone in links:
        source_id = ids.get(source, source)
        target_id = ids.get(target, target)
        cell(root, ident, "", edge_styles[tone], 0, 0, 0, 0, False, source_id, target_id)
    xml = tostring(graph, encoding="unicode")
    DRAWIO.write_text(f'<mxfile host="app.diagrams.net" version="26.0.14"><diagram id="orpheus-agent-turn" name="Bounded agent turn">{xml}</diagram></mxfile>\n')


def verify_motion() -> None:
    first, later = frame(0).convert("RGB"), frame(8).convert("RGB")
    static = (SCOPE[0], SCOPE[1], SCOPE[2], SCOPE[1] + 4)
    assert ImageChops.difference(first.crop(static), later.crop(static)).getbbox() is None
    assert ImageChops.difference(first, later).getbbox() is not None
    # A later frame starts each dash farther from the source, toward its arrow target.
    assert dash_start(7, 14, 9) > dash_start(0, 14, 9)


if __name__ == "__main__":
    verify_motion()
    frames = [frame(index).convert("P", palette=Image.Palette.ADAPTIVE, colors=160) for index in range(FRAMES)]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0, disposal=2, optimize=True)
    write_drawio()
    print(OUT)
    print(DRAWIO)
