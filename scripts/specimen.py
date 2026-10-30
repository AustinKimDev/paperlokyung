"""Render the README specimen images as self-contained SVGs.

Text is converted to outlines, so the images look the same everywhere, and
each SVG switches palette with prefers-color-scheme.

Usage: python3 scripts/specimen.py [FONTS_DIR] [UPSTREAM_DIR] [OUT_DIR]
"""

import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

WEIGHTS = [
    ("1Thin", "1 Thin"), ("2ExtraLight", "2 ExtraLight"), ("3Light", "3 Light"),
    ("4Regular", "4 Regular"), ("5Medium", "5 Medium"), ("6SemiBold", "6 SemiBold"),
    ("7Bold", "7 Bold"), ("8ExtraBold", "8 ExtraBold"), ("9Black", "9 Black"),
]
KYUNG = "큥"

STYLE = """<style>
.bg{fill:#FAF8F4}.ink{fill:#16140F}.muted{fill:#8C867C}.accent{fill:#FF5A2C}
.line{stroke:#E6E0D6;fill:none}.ghost{fill:#16140F;fill-opacity:.12}
.stroke{fill:none;stroke:#FF5A2C}.dash{fill:none;stroke:#FF5A2C;stroke-dasharray:10 8}
@media (prefers-color-scheme:dark){
.bg{fill:#121110}.ink{fill:#F3EFE8}.muted{fill:#8C867C}.accent{fill:#FF7A4D}
.line{stroke:#2B2825}.ghost{fill:#F3EFE8;fill-opacity:.14}
.stroke{stroke:#FF7A4D}.dash{stroke:#FF7A4D}}
</style>"""


def num(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


class Face:
    def __init__(self, path):
        self.font = TTFont(path)
        self.gs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm
        self.hmtx = self.font["hmtx"]
        self.kern = self.font["kern"].kernTables[0].kernTable if "kern" in self.font else {}

    def glyph(self, ch):
        return self.cmap.get(ord(ch), ".notdef")

    def path(self, name, x, y, size):
        s = size / self.upm
        pen = SVGPathPen(self.gs, ntos=num)
        self.gs[name].draw(TransformPen(pen, (s, 0, 0, -s, x, y)))
        return pen.getCommands()

    def run(self, text, x, y, size, tracking=0.0):
        """Lay out text; yield (char, x, advance, path d)."""
        s = size / self.upm
        prev = None
        for ch in text:
            name = self.glyph(ch)
            if prev is not None:
                x += self.kern.get((prev, name), 0) * s
            adv = self.hmtx[name][0] * s
            yield ch, x, adv, self.path(name, x, y, size)
            x += adv + tracking * size
            prev = name

    def width(self, text, size, tracking=0.0):
        return sum(adv + tracking * size for _, _, adv, _ in self.run(text, 0, 0, size, tracking)) - tracking * size


def text(face, s, x, y, size, cls="ink", accent=None, tracking=0.0, anchor="start"):
    """Outlined text; characters in `accent` get the accent class."""
    if anchor != "start":
        w = face.width(s, size, tracking)
        x -= w if anchor == "end" else w / 2
    out = []
    for ch, _, _, d in face.run(s, x, y, size, tracking):
        if d:
            c = "accent" if accent and ch in accent else cls
            out.append(f'<path class="{c}" d="{d}"/>')
    return "".join(out)


def svg(w, h, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{title}"><title>{title}</title>{STYLE}'
        f'<rect class="bg" width="{w}" height="{h}" rx="24"/>{body}</svg>'
    )


def hero(f):
    w, h = 1280, 600
    black, bold, reg = f["9Black"], f["7Bold"], f["4Regular"]
    body = []
    # Type-specimen guides around the big 큥.
    gx, base, size = 96, 470, 400
    em = size * 792 / black.upm
    top = base - size * 726 / black.upm
    for y in (top, base):
        body.append(f'<line class="line" x1="56" x2="{num(gx + em + 40)}" y1="{num(y)}" y2="{num(y)}" stroke-width="2"/>')
    body.append(f'<rect class="line" x="{gx}" y="{num(top)}" width="{num(em)}" height="{num(base - top)}" stroke-width="2"/>')
    body.append(text(black, KYUNG, gx, base, size, cls="accent"))
    body.append(text(reg, "U+D065", gx, base + 56, 22, cls="muted", tracking=0.05))
    tx = 640
    body.append(text(black, "Paperlokyung", tx, 228, 74, tracking=-0.01))
    body.append(text(bold, "페이퍼로큥", tx, 318, 64))
    body.append(text(reg, "Paperlogy에 비어 있던 ‘큥’을 채운 글꼴", tx, 392, 28, cls="muted", accent=KYUNG))
    body.append(text(bold, "9 weights  ·  SIL OFL 1.1  ·  TTF", tx, 470, 22, cls="ink", tracking=0.02))
    return svg(w, h, "".join(body), "Paperlokyung — 페이퍼로큥")


def before_after(f, up):
    w, h = 1280, 480
    reg_new, reg_old, label = f["7Bold"], up["7Bold"], f["4Regular"]
    sample = "오늘도 큥! 하고 웃는 큥이"
    size, x0 = 76, 64
    body = []
    rows = [(reg_old, "Paperlogy 1.001 (원본)", 168), (reg_new, "Paperlokyung", 392)]
    for face, name, base in rows:
        body.append(text(label, name, x0, base - 100, 24, cls="muted"))
        for ch, x, adv, d in face.run(sample, x0, base, size):
            if face is reg_old and ch == KYUNG:
                s = size / face.upm
                body.append(
                    f'<rect class="dash" x="{num(x + 6)}" y="{num(base - 760 * s)}" '
                    f'width="{num(adv - 12)}" height="{num(810 * s)}" rx="8" stroke-width="2.5"/>'
                )
            elif d:
                cls = "accent" if ch == KYUNG else "ink"
                body.append(f'<path class="{cls}" d="{d}"/>')
        if face is reg_old:
            body.append(text(label, "← 빈 글리프: 폭 1000짜리 공백만 남고 대체 폰트로도 넘어가지 않습니다", x0, base + 48, 22, cls="accent"))
    body.append(f'<line class="line" x1="{x0}" x2="{w - x0}" y1="262" y2="262" stroke-width="2"/>')
    return svg(w, h, "".join(body), "Paperlogy와 Paperlokyung 비교")


def construction(f):
    w, h = 1280, 520
    face, label = f["6SemiBold"], f["4Regular"]
    size, base = 230, 330
    cell = 300
    xs = [70 + i * cell for i in range(4)]
    body = []
    g = lambda ch: face.glyph(ch)
    # 쿵, 튱 as sources, an overlay, and the result.
    body.append(f'<path class="ink" d="{face.path(g("쿵"), xs[0], base, size)}"/>')
    body.append(f'<path class="ink" d="{face.path(g("튱"), xs[1], base, size)}"/>')
    body.append(f'<path class="ghost" d="{face.path(g("쿵"), xs[2], base, size)}"/>')
    body.append(f'<path class="stroke" stroke-width="2.5" d="{face.path(g(KYUNG), xs[2], base, size)}"/>')
    body.append(f'<path class="accent" d="{face.path(g(KYUNG), xs[3], base, size)}"/>')
    ops = ["+", "→", "="]
    adv = 792 * size / face.upm
    for i, op in enumerate(ops):
        cx = xs[i] + adv + (cell - adv) / 2
        body.append(text(label, op, cx, base - 70, 44, cls="muted", anchor="middle"))
    captions = [
        ("쿵", "ㅋ · 가로획 · ㅇ 받침 · 상하 비율"),
        ("튱", "ㅇ 받침 위 ㅠ 다리 위치"),
        ("겹쳐 보기", "쿵(회색) 위 큥 윤곽: 다리만 바뀜"),
        ("큥", "웨이트마다 자동 합성"),
    ]
    for x, (head, sub) in zip(xs, captions):
        cx = x + adv / 2
        body.append(text(face, head, cx, base + 88, 32, anchor="middle", accent=KYUNG if head == KYUNG else None))
        body.append(text(label, sub, cx, base + 130, 20, cls="muted", anchor="middle"))
    return svg(w, h, "".join(body), "큥을 만드는 방법: 쿵 + 튱")


def weights(f):
    sample = "큥큥! 쿵쿵 따리 큥 · Paperlokyung"
    row, size, x0, lx = 92, 54, 260, 64
    h = 56 + row * len(WEIGHTS)
    w = 1280
    label = f["4Regular"]
    body = []
    for i, (key, name) in enumerate(WEIGHTS):
        base = 56 + row * i + 62
        body.append(text(label, name, lx, base - 6, 20, cls="muted"))
        body.append(text(f[key], sample, x0, base, size, accent=KYUNG))
        if i:
            body.append(f'<line class="line" x1="{lx}" x2="{w - lx}" y1="{base - 74}" y2="{base - 74}" stroke-width="1.5"/>')
    return svg(w, h, "".join(body), "Paperlokyung 9개 웨이트")


def main():
    fonts = Path(sys.argv[1] if len(sys.argv) > 1 else "fonts/ttf")
    upstream = Path(sys.argv[2] if len(sys.argv) > 2 else "build/upstream")
    out = Path(sys.argv[3] if len(sys.argv) > 3 else "docs")
    out.mkdir(parents=True, exist_ok=True)
    f = {k: Face(fonts / f"Paperlokyung-{k}.ttf") for k, _ in WEIGHTS}
    up = {"7Bold": Face(upstream / "Paperlogy-7Bold.ttf")}
    for name, content in [
        ("hero.svg", hero(f)),
        ("before-after.svg", before_after(f, up)),
        ("construction.svg", construction(f)),
        ("weights.svg", weights(f)),
    ]:
        (out / name).write_text(content, encoding="utf-8")
        print(out / name, f"{len(content) // 1024} KB")


if __name__ == "__main__":
    main()
