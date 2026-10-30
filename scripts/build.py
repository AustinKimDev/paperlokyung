"""Build Paperlokyung from the upstream Paperlogy TTFs.

Paperlogy maps 큥 (U+D065) to an empty glyph with a 1000-unit advance, so the
syllable renders as a wide blank. This script draws 큥 for every weight from
glyphs the font already has:

- 쿵 (U+CFF5) supplies ㅋ, the vowel bar, the ㅇ final and the vertical split
  that the font uses for a ㅋ initial.
- 튱 (U+D2F1) supplies the ㅠ leg positions used above an ㅇ final.

쿵's single ㅜ stem is replaced by the two ㅠ legs, which are joined to 쿵's ㅇ
ring by splitting its top arcs at the leg edges. The family is then renamed to
Paperlokyung / 페이퍼로큥.

Usage: python3 scripts/build.py [UPSTREAM_DIR] [OUT_DIR]
"""

import sys
from pathlib import Path

from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

WEIGHTS = [
    "1Thin", "2ExtraLight", "3Light", "4Regular", "5Medium",
    "6SemiBold", "7Bold", "8ExtraBold", "9Black",
]
TARGET = "큥"
BASE = "쿵"  # ㅋ + ㅜ + ㅇ
LEGS = "튱"  # ㅌ + ㅠ + ㅇ
CHECK_LEGS = "퓽"  # second ㅠ + ㅇ reference, used as a sanity check

FAMILY = {"Paperlogy": "Paperlokyung", "페이퍼로지": "페이퍼로큥"}
DESCRIPTION = {
    0x409: "Paperlokyung is a derivative of Paperlogy (SIL OFL 1.1) "
    "that adds a harmonized 큽 (U+D065) glyph.".replace("큽", "큥"),
    0x412: "페이퍼로큥은 페이퍼로지(SIL OFL 1.1)를 기반으로 "
    "'큥'(U+D065) 글리프를 보완한 파생 글꼴입니다.",
}


# --- outline helpers -------------------------------------------------------

def glyph_name(font, char):
    return font.getBestCmap()[ord(char)]


def contours(glyph_set, name):
    """Return the glyph's contours as lists of explicit segments.

    A segment is ("L", p0, p1) or ("Q", p0, c, p1); implied on-curve points
    between consecutive off-curves are made explicit.
    """
    pen = RecordingPen()
    glyph_set[name].draw(pen)
    result, segs, start, cur = [], [], None, None
    for op, args in pen.value:
        if op == "moveTo":
            segs, start = [], args[0]
            cur = start
        elif op == "lineTo":
            segs.append(("L", cur, args[0]))
            cur = args[0]
        elif op == "qCurveTo":
            pts = list(args)
            if pts[-1] is None:
                raise ValueError(f"{name}: all-off-curve contour")
            *offs, end = pts
            for i, c in enumerate(offs):
                nxt = end if i == len(offs) - 1 else mid(c, offs[i + 1])
                segs.append(("Q", cur, c, nxt))
                cur = nxt
        elif op == "closePath":
            if cur != start:
                segs.append(("L", cur, start))
            result.append(segs)
        else:
            raise ValueError(f"{name}: unexpected pen op {op}")
    return result


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def points(segs):
    return [p for s in segs for p in s[1:]]


def bbox(segs):
    pts = points(segs)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def signed_area(segs):
    pts = [s[1] for s in segs]
    return sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1])
    ) / 2


def split(seg, t):
    """Split a segment at parameter t into (head, tail)."""
    if seg[0] == "L":
        _, p0, p1 = seg
        m = lerp(p0, p1, t)
        return ("L", p0, m), ("L", m, p1)
    _, p0, c, p1 = seg
    q0, q1 = lerp(p0, c, t), lerp(c, p1, t)
    m = lerp(q0, q1, t)
    return ("Q", p0, q0, m), ("Q", m, q1, p1)


def t_at_x(seg, x):
    """Parameter in [0, 1] where the segment crosses x, or None."""
    if seg[0] == "L":
        _, p0, p1 = seg
        if p0[0] == p1[0]:
            return None
        t = (x - p0[0]) / (p1[0] - p0[0])
        return t if 0 <= t <= 1 else None
    _, p0, c, p1 = seg
    a = p0[0] - 2 * c[0] + p1[0]
    b = 2 * (c[0] - p0[0])
    k = p0[0] - x
    if abs(a) < 1e-9:
        roots = [-k / b] if b else []
    else:
        disc = b * b - 4 * a * k
        if disc < 0:
            return None
        r = disc ** 0.5
        roots = [(-b - r) / (2 * a), (-b + r) / (2 * a)]
    roots = [t for t in roots if -1e-9 <= t <= 1 + 1e-9]
    return min(max(roots[0], 0.0), 1.0) if roots else None


def point_at(seg, t):
    return split(seg, t)[0][-1]


def find_stems(segs, xmin, xmax):
    """Indices of the left (rising) and right (falling) vertical stem edges.

    The left edge rises into the bar bottom, which then runs left to xmin; the
    right edge drops from the bar bottom, which arrives from xmax.
    """
    n = len(segs)
    left = right = None
    for i, s in enumerate(segs):
        if s[0] != "L" or s[1][0] != s[2][0] or not xmin < s[1][0] < xmax:
            continue
        nxt, prv = segs[(i + 1) % n], segs[(i - 1) % n]
        if s[2][1] > s[1][1] and nxt[0] == "L" and nxt[2] == (xmin, s[2][1]):
            left = i
        if s[2][1] < s[1][1] and prv[0] == "L" and prv[1] == (xmax, s[1][1]):
            right = i
    if left is None or right is None:
        raise ValueError("stem edges not found")
    return left, right


def classify(segs_list):
    """Split a ㅇ-final syllable into (initial, block outer, counters)."""
    outers = [c for c in segs_list if signed_area(c) < 0]
    counters = [c for c in segs_list if signed_area(c) > 0]
    block = min(outers, key=lambda c: bbox(c)[1])
    initial = [c for c in outers if c is not block]
    return initial, block, counters


def cut_on_arc(segs, start, step, x, floor, ceil):
    """Walk the ring's top arc from `start` in direction `step` to x.

    Returns (segment index, t). The crossing must lie above the ring counter
    (`floor`) and below the bar (`ceil`), otherwise the leg would not land on
    the ring's top arc.
    """
    n = len(segs)
    i = start
    for _ in range(n):
        t = t_at_x(segs[i], x)
        if t is not None:
            y = point_at(segs[i], t)[1]
            if not floor < y < ceil:
                raise ValueError(f"leg x={x} meets the ring at y={y:.1f}")
            return i, t
        i = (i + step) % n
    raise ValueError(f"no ring arc crosses x={x}")


def leg_edges(font, char):
    """Outer and inner x of the two ㅠ legs above an ㅇ final."""
    gs = font.getGlyphSet()
    _, block, counters = classify(contours(gs, glyph_name(font, char)))
    xmin, _, xmax, _ = bbox(block)
    left, right = find_stems(block, xmin, xmax)
    leg_counter = max(counters, key=lambda c: bbox(c)[3])
    cx0, _, cx1, _ = bbox(leg_counter)
    return block[left][1][0], cx0, cx1, block[right][1][0]


def build_kyung(font):
    """Return the 큥 glyph drawn from 쿵 and 튱's leg positions."""
    gs = font.getGlyphSet()
    base = contours(gs, glyph_name(font, BASE))
    if len(base) != 3:
        raise ValueError(f"{BASE}: expected 3 contours, got {len(base)}")
    initial, block, counters = classify(base)
    if len(initial) != 1 or len(counters) != 1:
        raise ValueError(f"{BASE}: unexpected contour layout")
    ring_hole = counters[0]
    hole_top = bbox(ring_hole)[3]

    xmin, _, xmax, _ = bbox(block)
    iL, iR = find_stems(block, xmin, xmax)
    n = len(block)
    stem_l, stem_r = block[iL], block[iR]
    bar_y = stem_l[2][1]
    if stem_r[1][1] != bar_y:
        raise ValueError(f"{BASE}: uneven bar bottom")

    xa, xb, xc, xd = leg_edges(font, LEGS)
    if not (xmin < xa < xb < stem_l[1][0] < stem_r[1][0] < xc < xd < xmax):
        raise ValueError(f"leg edges {xa, xb, xc, xd} do not straddle the stem")

    jA, tA = cut_on_arc(block, (iL - 1) % n, -1, xa, hole_top, bar_y)
    jB, tB = cut_on_arc(block, (iL - 1) % n, -1, xb, hole_top, bar_y)
    kC, tC = cut_on_arc(block, (iR + 1) % n, 1, xc, hole_top, bar_y)
    kD, tD = cut_on_arc(block, (iR + 1) % n, 1, xd, hole_top, bar_y)

    def run(i, j):
        """Segments i..j inclusive, walking forward cyclically."""
        out = [block[i]]
        while i != j:
            i = (i + 1) % n
            out.append(block[i])
        return out

    def line(p, q):
        return ("L", p, q)

    a_head = split(block[jA], tA)[0]
    d_tail = split(block[kD], tD)[1]
    A, D = a_head[-1], d_tail[1]
    # Outer: ring bottom from D round to A, up the left leg, along the bar,
    # down the right leg back to D.
    outer = [d_tail]
    if (kD + 1) % n != jA:
        outer += run((kD + 1) % n, (jA - 1) % n)
    outer.append(a_head)
    outer.append(line(A, (xa, bar_y)))
    outer.append(line((xa, bar_y), (xmin, bar_y)))
    outer += run((iL + 2) % n, (iR - 2) % n)
    outer.append(line((xmax, bar_y), (xd, bar_y)))
    outer.append(line((xd, bar_y), D))

    b_tail = split(block[jB], tB)[1]
    c_head = split(block[kC], tC)[0]
    B, C = b_tail[1], c_head[-1]
    # Counter between the legs: down the left leg, along 쿵's ring top
    # (including the strip the stem used to cover), up the right leg.
    counter = [line((xb, bar_y), B), b_tail]
    if jB != (iL - 1) % n:
        counter += run((jB + 1) % n, (iL - 1) % n)
    counter.append(line(stem_l[1], stem_r[2]))
    if kC != (iR + 1) % n:
        counter += run((iR + 1) % n, (kC - 1) % n)
    counter.append(c_head)
    counter.append(line(C, (xc, bar_y)))

    pen = TTGlyphPen(gs)
    for segs in (initial[0], outer, counter, ring_hole):
        draw(pen, segs)
    return pen.glyph()


def draw(pen, segs):
    start = segs[0][1]
    pen.moveTo(start)
    for i, s in enumerate(segs):
        last = i == len(segs) - 1
        if s[0] == "L":
            if not (last and s[2] == start):
                pen.lineTo(s[2])
        else:
            pen.qCurveTo(s[2], s[3])
    pen.closePath()


# --- font-level changes -----------------------------------------------------

def rename(font):
    name = font["name"]
    for rec in name.names:
        text = rec.toUnicode()
        if rec.nameID in (1, 3, 4, 6, 16):
            for old, new in FAMILY.items():
                text = text.replace(old, new)
            rec.string = text
        elif rec.nameID == 10:
            rec.string = DESCRIPTION.get(rec.langID, DESCRIPTION[0x409])
    for rec in name.names:
        if rec.nameID in (1, 3, 4, 6, 16):
            text = rec.toUnicode()
            assert "Paperlogy" not in text and "페이퍼로지" not in text, text


def build(src, dst):
    font = TTFont(src)
    glyph = build_kyung(font)
    target, base = glyph_name(font, TARGET), glyph_name(font, BASE)
    glyf = font["glyf"]
    glyf[target] = glyph
    glyph.recalcBounds(glyf)
    font["hmtx"][target] = (font["hmtx"][base][0], glyph.xMin)
    font["vmtx"][target] = font["vmtx"][base]
    if "DSIG" in font:
        del font["DSIG"]  # the edit invalidates the signature
    rename(font)
    font.save(dst)
    return leg_edges(font, LEGS), leg_edges(font, CHECK_LEGS)


def main():
    upstream = Path(sys.argv[1] if len(sys.argv) > 1 else "build/upstream")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "fonts/ttf")
    out.mkdir(parents=True, exist_ok=True)
    for w in WEIGHTS:
        dst = out / f"Paperlokyung-{w}.ttf"
        legs, check = build(upstream / f"Paperlogy-{w}.ttf", dst)
        drift = max(abs(a - b) for a, b in zip(legs, check))
        print(f"{dst}  legs={legs}  퓽 drift={drift}")


if __name__ == "__main__":
    main()
