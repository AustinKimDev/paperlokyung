"""Build the Paperlokyung web package (WOFF2 + CSS) from fonts/ttf.

Paperlogy maps 8,392 Hangul syllables to empty glyphs, which makes browsers
show blanks instead of falling back to another font. This script drops every
Hangul codepoint whose glyph has no outline from the cmap, so the browser
falls back for them. CJK ideographs (hanja) and Japanese kana are dropped too,
since the web build targets Hangul and Latin text. Other codepoints (symbols,
punctuation, whitespace etc.) are kept as is.
WOFF2 output needs the Python brotli module (pip install brotli).

Usage: python3 scripts/web.py [TTF_DIR] [OUT_DIR]
"""

import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

WEIGHTS = [
    "1Thin", "2ExtraLight", "3Light", "4Regular", "5Medium",
    "6SemiBold", "7Bold", "8ExtraBold", "9Black",
]
HANGUL_RANGES = [
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xAC00, 0xD7A3),  # Hangul Syllables
    (0xD7B0, 0xD7FF),  # Hangul Jamo Extended-B
]
SYLLABLES = (0xAC00, 0xD7A3)
DROPPED_RANGES = [
    (0x3040, 0x30FF),  # Hiragana, Katakana
    (0x31F0, 0x31FF),  # Katakana Phonetic Extensions
    (0x3400, 0x4DBF),  # CJK Extension A
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
]


def is_hangul(cp):
    return any(lo <= cp <= hi for lo, hi in HANGUL_RANGES)


def is_dropped(cp):
    return any(lo <= cp <= hi for lo, hi in DROPPED_RANGES)


def is_empty(font, name):
    glyf = font["glyf"]
    g = glyf[name]
    return not g.isComposite() and g.numberOfContours == 0


def keep_codepoints(font):
    cmap = font.getBestCmap()
    return sorted(cp for cp, name in cmap.items()
                  if not is_dropped(cp)
                  and not (is_hangul(cp) and is_empty(font, name)))


def build_weight(src, dst):
    font = TTFont(src)
    unicodes = keep_codepoints(font)
    options = subset.Options()
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.notdef_outline = True
    options.glyph_names = False
    options.flavor = "woff2"
    sub = subset.Subsetter(options)
    sub.populate(unicodes=unicodes)
    sub.subset(font)
    font.flavor = "woff2"
    font.save(dst)


def verify(path):
    font = TTFont(path)
    cmap = font.getBestCmap()
    glyf = font["glyf"]
    assert 0xD065 in cmap, "U+D065 missing"
    assert glyf[cmap[0xD065]].numberOfContours != 0, "U+D065 has no contours"
    kept = 0
    for cp, name in cmap.items():
        assert not is_dropped(cp), f"ideograph/kana U+{cp:04X} remains"
        if is_hangul(cp):
            assert not is_empty(font, name), f"empty Hangul U+{cp:04X}"
        if SYLLABLES[0] <= cp <= SYLLABLES[1]:
            kept += 1
    for cp in list(range(0x41, 0x5B)) + list(range(0x30, 0x3A)) + [0x20]:
        assert cp in cmap, f"U+{cp:04X} missing"
    return kept, len(cmap)


def css(weights):
    blocks = []
    for i, w in enumerate(weights, start=1):
        blocks.append(
            '@font-face {\n'
            '  font-family: "Paperlokyung";\n'
            f'  font-weight: {i * 100};\n'
            '  font-style: normal;\n'
            '  font-display: swap;\n'
            f'  src: url("Paperlokyung-{w}.woff2") format("woff2");\n'
            '}\n'
        )
    return "\n".join(blocks)


def main():
    root = Path(__file__).resolve().parent.parent
    ttf_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "fonts" / "ttf"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "web"
    out.mkdir(parents=True, exist_ok=True)
    for w in WEIGHTS:
        dst = out / f"Paperlokyung-{w}.woff2"
        build_weight(ttf_dir / f"Paperlokyung-{w}.ttf", dst)
        kept, total = verify(dst)
        print(f"{dst.name}: {dst.stat().st_size / 1024:.0f} KB, "
              f"{kept} Hangul syllables, {total} codepoints, verify OK")
    (out / "paperlokyung.css").write_text(css(WEIGHTS))


if __name__ == "__main__":
    main()
