#!/usr/bin/env python3
"""Build the 15-minute slide deck (16:9) for the multi-vector ANN paper.

Outputs
  MultiVector_ANN_Slides.pptx
  SPEAKER_NOTES.md
"""
import os
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

BASE = os.path.dirname(os.path.abspath(__file__))
FIG = lambda n: os.path.join(BASE, "figures", n)

# ------------------------------------------------------------------ palette
INK     = RGBColor(0x12, 0x20, 0x3A)
MUTED   = RGBColor(0x6B, 0x7A, 0x90)
GRID    = RGBColor(0xDD, 0xE3, 0xEC)
BLUE    = RGBColor(0x2F, 0x6F, 0xEB)
ORANGE  = RGBColor(0xE8, 0x59, 0x0C)
GREEN   = RGBColor(0x1F, 0x9D, 0x55)
PURPLE  = RGBColor(0x70, 0x48, 0xE8)
GOLD    = RGBColor(0xF2, 0xB7, 0x05)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
PANEL   = RGBColor(0xF3, 0xF6, 0xFB)
BLUE_T  = RGBColor(0xE8, 0xF0, 0xFE)
ORANGE_T= RGBColor(0xFD, 0xEB, 0xE1)
GREEN_T = RGBColor(0xE6, 0xF4, 0xEA)
GOLD_T  = RGBColor(0xFF, 0xF6, 0xD8)

FONT = "Liberation Sans"

SW, SH = 13.333, 7.5
M = 0.55
CW = SW - 2 * M

I = Inches

# ------------------------------------------------------------------ text helpers

def _font(run, size, color=INK, bold=False, italic=False, font=FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font
    run.font.color.rgb = color


def _spacing(p, before=0, after=0, line=None):
    p.space_before = Pt(before)
    p.space_after = Pt(after)
    if line:
        p.line_spacing = line


def _bullet(p, char="•", color=None, marL=0.28, indent=-0.28):
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", str(int(Inches(marL))))
    pPr.set("indent", str(int(Inches(indent))))
    for tag in ("a:buNone", "a:buChar", "a:buAutoNum", "a:buClr"):
        for e in pPr.findall(qn(tag)):
            pPr.remove(e)
    if color is not None:
        buClr = pPr.makeelement(qn("a:buClr"), {})
        srgb = buClr.makeelement(qn("a:srgbClr"), {"val": str(color)})
        buClr.append(srgb)
        pPr.append(buClr)
    bu = pPr.makeelement(qn("a:buChar"), {"char": char})
    pPr.append(bu)


def _no_bullet(p):
    pPr = p._p.get_or_add_pPr()
    for tag in ("a:buChar", "a:buAutoNum", "a:buClr"):
        for e in pPr.findall(qn(tag)):
            pPr.remove(e)
    pPr.append(pPr.makeelement(qn("a:buNone"), {}))


def rich(p, text, size, color=INK, bold=False, italic=False, font=FONT):
    """Add runs to paragraph, honouring **bold** and `mono` markup."""
    import re
    tokens = re.split(r"(\*\*.+?\*\*|`.+?`)", text)
    for tok in tokens:
        if not tok:
            continue
        b, it, f = bold, italic, font
        if tok.startswith("**") and tok.endswith("**"):
            tok, b = tok[2:-2], True
        elif tok.startswith("`") and tok.endswith("`"):
            tok, f = tok[1:-1], "Liberation Mono"
        r = p.add_run()
        r.text = tok
        _font(r, size, color, b, it, f)


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(I(x), I(y), I(w), I(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tb, tf


def para(tf, text, size, color=INK, bold=False, first=False, before=0, after=0,
         align=PP_ALIGN.LEFT, bullet=False, bullet_color=None, line=1.15, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    _spacing(p, before, after, line)
    rich(p, text, size, color, bold, italic)
    if bullet:
        _bullet(p, color=bullet_color)
    else:
        _no_bullet(p)
    return p


def shape(slide, kind, x, y, w, h, fill=None, line=None, line_w=1.0, adj=None):
    s = slide.shapes.add_shape(kind, I(x), I(y), I(w), I(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
    if adj is not None and len(s.adjustments) > 0:
        s.adjustments[0] = adj
    s.text_frame.word_wrap = True
    s.text_frame.margin_left = s.text_frame.margin_right = I(0.12)
    s.text_frame.margin_top = s.text_frame.margin_bottom = I(0.06)
    return s


def rounded(slide, x, y, w, h, fill, line=None, adj=0.08):
    return shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, line, adj=adj)


def arrow(slide, x1, y, x2, color=MUTED, w=1.5):
    a = slide.shapes.add_connector(1, I(x1), I(y), I(x2), I(y))
    a.line.color.rgb = color
    a.line.width = Pt(w)
    ln = a.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return a


def pic_fit(slide, path, x, y, max_w, max_h, align="center", valign="middle"):
    w, h = Image.open(path).size
    ar = w / h
    if max_w / max_h > ar:
        ph, pw = max_h, max_h * ar
    else:
        pw, ph = max_w, max_w / ar
    px = x + (max_w - pw) / 2 if align == "center" else x
    py = y + (max_h - ph) / 2 if valign == "middle" else y
    return slide.shapes.add_picture(path, I(px), I(py), I(pw), I(ph))


def _cell_border(cell, color="DDE3EC", width=0.75):
    tcPr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        for e in tcPr.findall(qn(tag)):
            tcPr.remove(e)
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        ln = tcPr.makeelement(qn(tag), {"w": str(int(width * 12700)), "cap": "flat",
                                        "cmpd": "sng", "algn": "ctr"})
        fill = ln.makeelement(qn("a:solidFill"), {})
        clr = fill.makeelement(qn("a:srgbClr"), {"val": color})
        fill.append(clr)
        ln.append(fill)
        tcPr.insert(0, ln)


def table(slide, data, x, y, col_w, row_h=0.44, font=12, header_font=11,
          header_fill=PANEL, header_color=MUTED, align=None, first_bold=False):
    rows, cols = len(data), len(data[0])
    shp = slide.shapes.add_table(rows, cols, I(x), I(y), I(sum(col_w)), I(row_h * rows))
    t = shp.table
    t.first_row = False
    t.horz_banding = False
    for i, w in enumerate(col_w):
        t.columns[i].width = I(w)
    for r in range(rows):
        t.rows[r].height = I(row_h)
        for c in range(cols):
            cell = t.cell(r, c)
            cell.margin_left = cell.margin_right = I(0.08)
            cell.margin_top = cell.margin_bottom = I(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            _cell_border(cell)
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill if r == 0 else WHITE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = (align[c] if align else
                           (PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER))
            _no_bullet(p)
            _spacing(p, 0, 0, 1.0)
            rich(p, str(data[r][c]), header_font if r == 0 else font,
                 header_color if r == 0 else INK,
                 bold=(r == 0) or (first_bold and c == 0))
    return t


# ------------------------------------------------------------------ deck

class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width = I(SW)
        self.prs.slide_height = I(SH)
        self.blank = self.prs.slide_layouts[6]
        self.index = 0
        self.toc = []

    def slide(self, kicker, title, accent=BLUE, timing="", notes="", title_size=30):
        s = self.prs.slides.add_slide(self.blank)
        self.index += 1

        # kicker
        _, tf = textbox(s, M, 0.40, CW, 0.26)
        p = tf.paragraphs[0]
        _spacing(p, 0, 0, 1.0)
        r = p.add_run()
        r.text = kicker.upper()
        _font(r, 10.5, accent, bold=True)
        r.font._rPr.set("spc", "160")

        # title
        _, tf = textbox(s, M, 0.68, CW, 0.80)
        p = tf.paragraphs[0]
        _spacing(p, 0, 0, 0.95)
        rich(p, title, title_size, INK, bold=True)

        # accent rule
        shape(s, MSO_SHAPE.RECTANGLE, M, 1.52, 1.05, 0.045, accent)

        # footer
        _, tf = textbox(s, M, 7.10, 6.0, 0.24)
        p = tf.paragraphs[0]
        _spacing(p, 0, 0, 1.0)
        r = p.add_run()
        r.text = "Multi-vector ANN search  ·  WWW '26"
        _font(r, 8.5, MUTED)

        _, tf = textbox(s, SW - M - 5.0, 7.10, 5.0, 0.24)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        _spacing(p, 0, 0, 1.0)
        r = p.add_run()
        r.text = f"{self.index:02d}   ·   {timing}" if timing else f"{self.index:02d}"
        _font(r, 8.5, MUTED)

        self.toc.append((self.index, title))
        if notes:
            s.notes_slide.notes_text_frame.text = notes
        return s

    def save(self, name):
        path = os.path.join(BASE, name)
        self.prs.save(path)
        print("wrote", path)
        return path


# ------------------------------------------------------------------ slides

def build():
    d = Deck()

    # ---------------------------------------------------------------- 1 title
    s = d.prs.slides.add_slide(d.blank)
    d.index += 1
    d.toc.append((1, "Title"))

    shape(s, MSO_SHAPE.RECTANGLE, 0.55, 1.42, 0.07, 4.55, BLUE)

    _, tf = textbox(s, 0.95, 1.35, 7.4, 0.3)
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.0)
    r = p.add_run()
    r.text = "THE WEB CONFERENCE 2026  ·  MULTI-VECTOR SEARCH"
    _font(r, 11, BLUE, bold=True)
    r.font._rPr.set("spc", "140")

    _, tf = textbox(s, 0.95, 1.78, 7.55, 2.35)
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 0.92)
    rich(p, "Breaking the Single-Reference-Vector Barrier in Approximate Nearest Neighbor Search",
         32, INK, bold=True)

    _, tf = textbox(s, 0.95, 4.22, 7.4, 0.8)
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.15)
    rich(p, "All-of / any-of multi-vector queries — and a **10× speedup**", 18, MUTED)

    _, tf = textbox(s, 0.95, 5.35, 7.4, 1.1)
    para(tf, "Jiadong Xie · Jeffrey Liang · Siyi Teng · Jeffrey Xu Yu · Yingfan Liu",
         12.5, INK, first=True, after=4)
    para(tf, "CUHK  ·  Australian National University  ·  HKUST (GZ)  ·  Xidian University",
         11, MUTED, after=4)
    para(tf, "Presented by  ______________________         15 minutes", 11, MUTED)

    pic_fit(s, FIG("fig_title.png"), 8.55, 2.05, 4.35, 2.55)

    _, tf = textbox(s, 0.95, 6.75, 7.5, 0.3)
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.0)
    rich(p, "`max` for all  ·  `min` for any  —  the whole paper in six words", 11, GOLD, bold=True)

    s.notes_slide.notes_text_frame.text = (
        "[0:00–0:30]  Opening.\n\n"
        "Good morning. Vector databases today take one reference vector per query. "
        "This paper makes the query a *set* of vectors — 'similar to all of these' or "
        "'similar to any of these' — and makes it about ten times faster than the "
        "obvious approach.\n\n"
        "In the next 15 minutes: why anyone wants that, the problem with the obvious fix, "
        "the one idea that solves it, and the results. The whole paper is in six words: "
        "max for all, min for any. I'll unpack that."
    )

    # ---------------------------------------------------------------- 2 why
    s = d.slide(
        "Motivation", "Why would a query need more than one vector?",
        accent=BLUE, timing="0:30–2:00",
        notes=(
            "[0:30–2:00]  Three stories, 30 seconds each.\n\n"
            "1. Two people, two offices. You want a flat that is a fair compromise for "
            "both — formally, the flat with the best *worst* commute. That's 'similar to "
            "all of the reference points'.\n\n"
            "2. Logo deduplication. You have five rotated or cropped copies of a logo and "
            "want the original. The original should be near *all* of them.\n\n"
            "3. Recommendations. 'More like any of my last three clicks' — deliberately "
            "broad, to avoid a filter bubble.\n\n"
            "Now the punchline: every production system forces you to squash those vectors "
            "into one — concatenate or average. Averaging 'jazz' and 'death metal' gives a "
            "vector in the meaningless middle. That is the barrier in the title."
        ))

    cards = [
        ("ALL-OF", BLUE, "The fair apartment",
         "Two people, two offices. Find the flat with the best **worst** commute."),
        ("ALL-OF", BLUE, "Logo deduplication",
         "Five rotated / cropped copies. Find the original that is near **all** of them."),
        ("ANY-OF", ORANGE, "Diverse recommendations",
         "“More like **any** of my last three clicks” — deliberately broad."),
    ]
    for i, (tag, col, head, body) in enumerate(cards):
        x = M + i * (3.85 + 0.29)
        rounded(s, x, 1.92, 3.85, 3.05, PANEL)
        shape(s, MSO_SHAPE.RECTANGLE, x, 1.92, 0.055, 3.05, col)
        _, tf = textbox(s, x + 0.28, 2.12, 3.3, 0.26)
        p = tf.paragraphs[0]
        _spacing(p, 0, 0, 1.0)
        r = p.add_run()
        r.text = tag
        _font(r, 10, col, bold=True)
        r.font._rPr.set("spc", "120")

        _, tf = textbox(s, x + 0.28, 2.48, 3.3, 0.55)
        para(tf, head, 19, INK, bold=True, first=True, line=1.0)

        _, tf = textbox(s, x + 0.28, 3.18, 3.3, 1.4)
        para(tf, body, 13.5, MUTED, first=True, line=1.25)

    bar = rounded(s, M, 5.45, CW, 1.15, INK)
    tf = bar.text_frame
    tf.margin_left = I(0.35)
    tf.margin_right = I(0.35)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.2)
    rich(p, "Every production system forces you to squash these into ONE vector — "
            "concatenate or average.", 15, WHITE, bold=True)

    _, tf = textbox(s, M, 6.78, CW, 0.3)
    para(tf, "Averaging “jazz” and “death metal” gives a vector in the meaningless middle.",
         11.5, MUTED, first=True)

    # ---------------------------------------------------------------- 3 background
    s = d.slide(
        "Background", "Two things you already know — and one to remember",
        accent=BLUE, timing="2:00–3:30",
        notes=(
            "[2:00–3:30]  Keep this short; it is scaffolding.\n\n"
            "Ordinary k-NN: put a ball around the query, grow it until it holds k points. "
            "The score of a point is just its distance.\n\n"
            "Graph indexes like HNSW: start at some node and repeatedly step to a "
            "neighbour that is closer to the query. That works because nearby points have "
            "similar distances — the score landscape has no cliffs. Remember that "
            "sentence; it comes back in five minutes and it is the reason this whole "
            "approach is legal."
        ))

    pic_fit(s, FIG("fig_background.png"), M, 1.72, CW, 4.55)

    for i, t in enumerate([
        "Score = Euclidean distance; the answers are the **k smallest**.",
        "Nearby points have **similar distances** → no cliffs in the score landscape.",
    ]):
        _, tf = textbox(s, M + i * 6.15, 6.45, 5.9, 0.55)
        p = tf.paragraphs[0]
        _spacing(p, 0, 0, 1.15)
        rich(p, t, 13.5, INK)
        _bullet(p, color=BLUE)

    # ---------------------------------------------------------------- 4 definitions
    s = d.slide(
        "The problem", "Two new query types: all-k and any-k",
        accent=BLUE, timing="3:30–5:30",
        notes=(
            "[3:30–5:30]  The definition slide — go slowly.\n\n"
            "Give the query m vectors. Two natural semantics.\n\n"
            "ALL-k: similar to every q_i. Geometrically, the intersection of m balls. "
            "Ranking a database vector: its maximum distance to the query set.\n\n"
            "ANY-k: similar to at least one q_i. The union of the balls. Ranking: the "
            "minimum distance.\n\n"
            "Emphasise: m is the number of query vectors, k is the number of results. "
            "Students mix these up.\n\n"
            "Concrete example from the paper's Recipe dataset: find a recipe with both "
            "daikon and pork (all), versus a recipe like a burger or a coffee (any). "
            "The all result genuinely combines the inputs; the any result resembles one "
            "of them."
        ))

    blocks = [
        ("ALL-k", BLUE, BLUE_T, "similar to **every** qᵢ",
         "rank(u) = maxᵢ δ(qᵢ, u)", "intersection of m balls", 1.82),
        ("ANY-k", ORANGE, ORANGE_T, "similar to **at least one** qᵢ",
         "rank(u) = minᵢ δ(qᵢ, u)", "union of m balls", 3.72),
    ]
    for tag, col, tint, head, formula, geom, y in blocks:
        rounded(s, M, y, 5.25, 1.68, tint)
        shape(s, MSO_SHAPE.RECTANGLE, M, y, 0.055, 1.68, col)
        _, tf = textbox(s, M + 0.28, y + 0.16, 4.75, 0.25)
        p = tf.paragraphs[0]
        _spacing(p, 0, 0, 1.0)
        r = p.add_run()
        r.text = tag
        _font(r, 10, col, bold=True)
        r.font._rPr.set("spc", "120")

        _, tf = textbox(s, M + 0.28, y + 0.44, 4.75, 0.35)
        para(tf, head, 17, INK, bold=True, first=True, line=1.0)

        _, tf = textbox(s, M + 0.28, y + 0.86, 4.75, 0.32)
        para(tf, formula, 14, col, first=True, line=1.0)

        _, tf = textbox(s, M + 0.28, y + 1.22, 4.75, 0.3)
        para(tf, geom, 12, MUTED, first=True, line=1.0)

    _, tf = textbox(s, M, 5.62, 5.25, 0.6)
    para(tf, "m = number of query vectors     k = number of results", 12, MUTED,
         first=True, italic=True)

    pic_fit(s, FIG("fig_all_any.png"), 6.05, 1.95, 6.75, 3.55)

    _, tf = textbox(s, 6.05, 5.55, 6.75, 0.7)
    para(tf, "Same dataset, same query — only the ranking rule changes.",
         12.5, MUTED, first=True, align=PP_ALIGN.CENTER, italic=True)

    # ---------------------------------------------------------------- 5 worked example
    s = d.slide(
        "The problem", "A four-point example you can do in your head",
        accent=BLUE, timing="5:30–7:00",
        notes=(
            "[5:30–7:00]  Build the picture step by step.\n\n"
            "Two query points, q1 at the origin and q2 at (10,0). Four database points. "
            "A sits exactly between them. D is the compromise above. B and C are each "
            "close to one query.\n\n"
            "Compute the two columns: max and min distance. Rank by max: A (5), D (7.07), "
            "then B and C (10.05). So all-2 is {A, D}. Rank by min: B and C at 1, then A, "
            "then D. So any-2 is {B, C}.\n\n"
            "Now the key observation. A is nobody's nearest neighbour — B is q1's nearest, "
            "C is q2's. Yet A is the all-1 NN. It lives in the valley between the queries, "
            "where no single-vector search ever goes. That is the whole difficulty in one "
            "picture."
        ))

    pic_fit(s, FIG("fig_example_build.png"), M, 1.72, 7.15, 5.18)

    table(s,
          [["point", "→ q1", "→ q2", "max", "min"],
           ["A  (5,0)", "5", "5", "5.00", "5.00"],
           ["D  (5,5)", "7.07", "7.07", "7.07", "7.07"],
           ["B  (0,1)", "1", "10.05", "10.05", "1.00"],
           ["C  (10,1)", "10.05", "1", "10.05", "1.00"]],
          x=7.85, y=1.88, col_w=[1.15, 0.9, 0.9, 0.95, 0.95], row_h=0.42, font=11.5)

    for i, (txt, col, tint) in enumerate([
            ("all-2 = {A, D}", BLUE, BLUE_T),
            ("any-2 = {B, C}", ORANGE, ORANGE_T)]):
        chip = rounded(s, 7.85 + i * 2.5, 4.28, 2.3, 0.44, tint)
        tf = chip.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        _spacing(p, 0, 0, 1.0)
        rich(p, txt, 13, col, bold=True)

    box = rounded(s, 7.85, 4.95, 4.9, 1.55, GOLD_T)
    tf = box.text_frame
    tf.margin_left = I(0.22)
    tf.margin_right = I(0.22)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.18)
    rich(p, "A is **nobody's** nearest neighbour — yet it is the all-1 NN.",
         13.5, INK, bold=False)

    _, tf = textbox(s, 7.85, 6.6, 4.9, 0.35)
    para(tf, "It lives in the valley between the queries.", 11, MUTED, first=True, italic=True)

    # ---------------------------------------------------------------- 6 baseline
    s = d.slide(
        "The problem", "Why the obvious fix fails",
        accent=ORANGE, timing="7:00–8:30",
        notes=(
            "[7:00–8:30]  The baseline everyone would write first.\n\n"
            "Run a k'-ANN search per query vector, merge the pools, rank the pool by max "
            "or min.\n\n"
            "For all-2 with k'=2: q1 returns B and A, q2 returns C and A. The pool is "
            "{A,B,C} — wrong. D is third for *both* queries, so it never enters the pool. "
            "You needed k'=3.\n\n"
            "With k'=3 it is correct, but you paid 50% more work per query. And for any-2, "
            "k'=1 already gives the right answer — less work than k'=2. So the optimal k' "
            "is unknown in advance, and it differs by semantics and by query vector.\n\n"
            "Milvus patches this by doubling k' until the result set stops changing: "
            "correct, but repeated searches. That is exactly the inefficiency this paper "
            "removes."
        ))

    steps = [("m separate searches", "k′-ANN for each qᵢ"), ("merge the pools", "union of results"),
             ("rank by max / min", "top-k of the pool")]
    for i, (head, sub) in enumerate(steps):
        x = M + i * 4.05
        b = rounded(s, x, 1.82, 3.55, 0.92, PANEL)
        tf = b.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        _spacing(p, 0, 0, 1.0)
        rich(p, head, 13.5, INK, bold=True)
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        _spacing(p2, 0, 0, 1.0)
        rich(p2, sub, 10.5, MUTED)
        if i < 2:
            arrow(s, x + 3.6, 2.28, x + 4.02, color=MUTED, w=1.4)

    table(s,
          [["strategy", "merged pool", "verdict"],
           ["k′ = 2  (all-2)", "{A, B, C}", "✗  wrong — D is 3rd for **both** queries"],
           ["k′ = 3  (all-2)", "{A, B, C, D}", "✓  correct, but 50% more work"],
           ["k′ = 1  (any-2)", "{B, C}", "✓  correct, and cheaper than k′ = 2"]],
          x=M, y=3.05, col_w=[2.55, 2.45, 7.2], row_h=0.56, font=12.5)

    box = rounded(s, M, 5.55, CW, 0.85, GOLD_T)
    tf = box.text_frame
    tf.margin_left = I(0.3)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.1)
    rich(p, "The optimal k′ is unknown in advance — and differs by **semantics** "
            "and by **query vector**.", 14.5, INK)

    _, tf = textbox(s, M, 6.55, CW, 0.45)
    para(tf, "Milvus doubles k′ until the answer is stable: correct, but it repeats the "
             "searches. That is the inefficiency the paper removes.", 11.5, MUTED, first=True)

    # ---------------------------------------------------------------- 7 core idea
    s = d.slide(
        "The idea", "Score = the moment a point gets captured",
        accent=GOLD, timing="8:30–10:30",
        notes=(
            "[8:30–10:30]  This is the heart of the talk. Let the GIF play; talk over it.\n\n"
            "Put a balloon on every query vector and inflate them all at exactly the same "
            "rate. A point's score is the moment it gets captured.\n\n"
            "For all-k, the point must be inside every balloon, so it is captured by the "
            "LAST one — that is the maximum distance.\n\n"
            "For any-k, the first balloon is enough — the minimum distance.\n\n"
            "That is it. Both problems become ordinary top-k ranking with a different "
            "score. No k' anywhere. And notice that the same point can be first for all "
            "and third for any: these are genuinely different queries, not a cosmetic "
            "tweak.\n\n"
            "If the animation does not play, use the three-frame strip on the backup slide."
        ))

    pic_fit(s, FIG("fig_balloon.gif"), 1.15, 1.72, 11.0, 4.12)

    bar = rounded(s, M, 6.02, CW, 0.78, INK)
    tf = bar.text_frame
    tf.margin_left = I(0.3)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _spacing(p, 0, 0, 1.1)
    rich(p, "Both problems collapse to ordinary top-k ranking  —  no k′ anywhere.",
         16, WHITE, bold=True)

    _, tf = textbox(s, M, 6.88, CW, 0.28)
    para(tf, "ALL = last balloon to arrive → max        ANY = first balloon to arrive → min",
         10.5, MUTED, first=True, align=PP_ALIGN.CENTER)

    # ---------------------------------------------------------------- 8 lipschitz
    s = d.slide(
        "The idea", "Why the graph still works: the score has no cliffs",
        accent=GOLD, timing="10:30–11:15",
        notes=(
            "[10:30–11:15]  Anticipate the objection before it is asked.\n\n"
            "'Max and min are not distances — why should graph search still be valid?'\n\n"
            "Because the score is 1-Lipschitz: if two points are close, their scores "
            "differ by at most their distance. Geometrically, the score can only move "
            "inside a cone of slope plus or minus one. That is exactly the 'no cliffs' "
            "property from the background slide.\n\n"
            "Consequence one: the downhill walk still converges. Consequence two: "
            "neighbours of a good point are likely good too. So we reuse the existing "
            "HNSW index unchanged — only the distance function changes. Same time and "
            "space complexity as beam search."
        ))

    pic_fit(s, FIG("fig_lipschitz.png"), M, 1.82, 6.9, 4.35)

    _, tf = textbox(s, 7.75, 1.95, 5.0, 0.6)
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.0)
    rich(p, "| r(u) − r(v) |  ≤  δ(u, v)", 21, INK, bold=True)

    _, tf = textbox(s, 7.75, 2.65, 5.0, 0.35)
    para(tf, "1-Lipschitz  ·  the triangle inequality, restated", 12, MUTED, first=True, italic=True)

    _, tf = textbox(s, 7.75, 3.25, 5.0, 2.1)
    for i, t in enumerate([
        "Close points ⇒ **close scores** ⇒ the downhill walk still converges.",
        "Neighbours of a good point are **likely good too** — the cluster effect.",
        "So: **same HNSW index**, only the distance function changes.",
    ]):
        para(tf, t, 14, INK, first=(i == 0), after=12, bullet=True, bullet_color=GOLD, line=1.18)

    chip = rounded(s, 7.75, 5.55, 4.55, 0.5, GREEN_T)
    tf = chip.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _spacing(p, 0, 0, 1.0)
    rich(p, "Same time & space complexity as beam search", 11.5, GREEN, bold=True)

    # ---------------------------------------------------------------- 9 MEB
    s = d.slide(
        "The improvements", "Where to start for all-k: minimise the MAX",
        accent=GREEN, timing="11:15–12:15",
        notes=(
            "[11:15–12:15]  First engineering wrinkle.\n\n"
            "Graph search is a downhill walk, so the start matters. For all-k the naive "
            "start is the centroid of the queries. Wrong.\n\n"
            "The best compromise minimises the *maximum* distance — that is the centre of "
            "the minimum enclosing ball, not the average. Concrete: one office at the "
            "origin and nine at (4,4). The centroid gives the lone office a 5.09 commute. "
            "The MEB centre gives 2.83. Minimise the max, don't average.\n\n"
            "The authors also show the centroid baseline is worse than doing nothing "
            "clever, because it starts off the HNSW entry point and breaks the hierarchy.\n\n"
            "Pipeline: compute the MEB centre, run an ordinary 1-NN search with it, hand "
            "that node to the radius search. Cost is O(m squared d plus m to the 3.5), "
            "once per query."
        ))

    pic_fit(s, FIG("fig_meb.png"), M, 1.80, 7.25, 3.55)

    _, tf = textbox(s, 7.95, 1.95, 4.85, 0.9)
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.05)
    rich(p, "Best compromise = minimise the **maximum** distance.", 16, INK, bold=False)

    _, tf = textbox(s, 7.95, 2.95, 4.85, 1.9)
    for i, t in enumerate([
        "That is the centre of the **minimum enclosing ball** (MEB).",
        "The centroid is pulled toward the majority — it is **not** the fair point.",
        "The authors show centroid-start is worse than doing nothing clever.",
    ]):
        para(tf, t, 13, MUTED, first=(i == 0), after=10, bullet=True, bullet_color=GREEN, line=1.15)

    steps = [("MEB centre v̄", "convex QP"), ("1-NN of v̄", "Euclidean"), ("radius search", "seeded")]
    for i, (head, sub) in enumerate(steps):
        x = M + i * 4.05
        b = rounded(s, x, 5.62, 3.55, 0.82, PANEL)
        tf = b.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        _spacing(p, 0, 0, 1.0)
        rich(p, head, 13, INK, bold=True)
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        _spacing(p2, 0, 0, 1.0)
        rich(p2, sub, 10, MUTED)
        if i < 2:
            arrow(s, x + 3.6, 6.03, x + 4.02, color=MUTED, w=1.4)

    _, tf = textbox(s, M, 6.6, CW, 0.3)
    para(tf, "One-off cost per query:  O(m²d + m³·⁵)  —  cheap when d ≫ m.", 11.5, MUTED,
         first=True, italic=True)

    # ---------------------------------------------------------------- 10 disconnected
    s = d.slide(
        "The improvements", "Why any-k needs more than one starting point",
        accent=GREEN, timing="12:15–13:00",
        notes=(
            "[12:15–13:00]  Second wrinkle, specific to any-k.\n\n"
            "The answer can live in disconnected regions. Two query points 100 apart, A "
            "near one and B near the other. any-2 is {A,B} — two points 100 apart.\n\n"
            "Now start a walk at A and try to reach B. The min-distance gets *worse* as you "
            "move: 50 at the midpoint. There is no downhill path, so the walk never leaves "
            "A. A single descent can only find one region.\n\n"
            "Fix: seed the queue with the 1-NN of every query vector, so the search starts "
            "inside all the relevant regions at once. Same search, better starting points. "
            "That is the two-stage method."
        ))

    pic_fit(s, FIG("fig_disconnected.png"), M, 1.82, 7.25, 3.5)

    _, tf = textbox(s, 7.95, 1.95, 4.85, 0.9)
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.05)
    rich(p, "The any-k answer can live in **m disconnected regions**.", 16, INK)

    _, tf = textbox(s, 7.95, 2.95, 4.85, 1.8)
    for i, t in enumerate([
        "From A, every step toward B makes the score **worse**.",
        "No downhill path ⇒ the walk never leaves the first region.",
        "Plain RadiusSearch can therefore **lose to Milvus** on any-k.",
    ]):
        para(tf, t, 13, MUTED, first=(i == 0), after=10, bullet=True, bullet_color=GREEN, line=1.15)

    box = rounded(s, M, 5.62, CW, 0.85, GREEN_T)
    tf = box.text_frame
    tf.margin_left = I(0.3)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    _spacing(p, 0, 0, 1.1)
    rich(p, "Fix: seed the queue with the 1-NN of **every** qᵢ  —  same search, better start.",
         14.5, INK)

    _, tf = textbox(s, M, 6.62, CW, 0.3)
    para(tf, "This is the whole of RadiusSearch+: a proper seed, then the radius-based beam search.",
         11.5, MUTED, first=True, italic=True)

    # ---------------------------------------------------------------- 11 results
    s = d.slide(
        "Evaluation", "Up to ~10× the QPS at the same recall",
        accent=BLUE, timing="13:00–14:15",
        notes=(
            "[13:00–14:15]  Do not read the axes; read the gap.\n\n"
            "Five real datasets, one to two million vectors, 128 to 2048 dimensions. "
            "Every method uses the same HNSW index, EF 400, M 32, single thread, k=10, "
            "m=5 by default.\n\n"
            "Up to about ten times the QPS at equal recall, consistently across datasets.\n\n"
            "RadiusSearch+ wins most at high recall, because the seeding cost is fixed and "
            "amortises — at low recall it can be slightly worse than plain RadiusSearch.\n\n"
            "Honest caveat the authors report: plain RadiusSearch can lose to Milvus on "
            "any-k. That is exactly the disconnected-region problem we just saw, and the "
            "reason the two-stage version exists.\n\n"
            "Both charts are schematics of the reported trends; exact curves are in the "
            "paper."
        ))

    pic_fit(s, FIG("fig_qps_recall.png"), M, 1.72, 5.85, 3.95)
    pic_fit(s, FIG("fig_qps_bar.png"), 6.7, 1.72, 5.9, 3.95)

    items = [
        ("~10×", "QPS at equal recall — all-k, all datasets", BLUE),
        ("5", "datasets, 1–2 M vectors, 128–2048 dims", INK),
        ("high recall", "where RadiusSearch+ wins most", GREEN),
    ]
    for i, (big, sub, col) in enumerate(items):
        x = M + i * 4.1
        _, tf = textbox(s, x, 5.82, 3.8, 0.45)
        para(tf, big, 22, col, bold=True, first=True, line=1.0)
        _, tf = textbox(s, x, 6.30, 3.8, 0.5)
        para(tf, sub, 11.5, MUTED, first=True, line=1.1)

    _, tf = textbox(s, M, 7.02, CW, 0.25)
    para(tf, "Schematics redrawn from the paper's reported trends (Figs. 5–8); exact values in the paper.",
         9, MUTED, first=True, italic=True)

    # ---------------------------------------------------------------- 12 conclusion
    s = d.slide(
        "Conclusion", "Change the distance, not the index",
        accent=GOLD, timing="14:15–15:00",
        notes=(
            "[14:15–15:00]  Close on the three ideas, then the limits.\n\n"
            "One: reformulate. all/any-k is just top-k by max or min distance. That kills "
            "the k' knob and turns m searches into one.\n\n"
            "Two: prove. The score is 1-Lipschitz, so existing graph indexes work as-is.\n\n"
            "Three: seed. MEB centre for all-k, one seed per query for any-k. That is "
            "where the speed comes from.\n\n"
            "Limits, stated honestly: the fast variant is specific to graph indexes; exact "
            "guarantees need an index with quadratic build cost; and recall is empirical, "
            "not guaranteed. But as a systems idea it is clean: change the distance, not "
            "the index.\n\n"
            "Then: 'Max for all, min for any.' Questions."
        ))

    items = [
        ("1", "Reformulate", "all/any-k = top-k by **max / min distance**. Kills the k′ knob.", BLUE),
        ("2", "Prove", "The score is **1-Lipschitz** — existing graph indexes work as-is.", PURPLE),
        ("3", "Seed", "**MEB centre** for all-k, **one seed per query** for any-k.", GREEN),
    ]
    for i, (n, head, body, col) in enumerate(items):
        y = 1.82 + i * 0.92
        circ = shape(s, MSO_SHAPE.OVAL, M, y, 0.52, 0.52, col)
        tf = circ.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        _spacing(p, 0, 0, 1.0)
        rich(p, n, 15, WHITE, bold=True)

        _, tf = textbox(s, M + 0.78, y - 0.03, 7.6, 0.35)
        para(tf, head, 17, INK, bold=True, first=True, line=1.0)
        _, tf = textbox(s, M + 0.78, y + 0.33, 7.9, 0.45)
        para(tf, body, 12.5, MUTED, first=True, line=1.1)

    box = rounded(s, 8.65, 1.82, 4.15, 2.55, PANEL)
    tf = box.text_frame
    tf.margin_left = I(0.28)
    tf.margin_right = I(0.28)
    tf.margin_top = I(0.2)
    p = tf.paragraphs[0]
    _spacing(p, 0, 6, 1.0)
    rich(p, "LIMITS", 10, ORANGE, bold=True)
    for t in ["RadiusSearch+ is graph-index specific.",
              "Exact guarantees need LMG — O(n²d) build.",
              "Recall is empirical, not guaranteed."]:
        p = tf.add_paragraph()
        _spacing(p, 0, 6, 1.12)
        rich(p, t, 11.5, MUTED)
        _bullet(p, color=ORANGE)

    _, tf = textbox(s, M, 5.0, CW, 1.0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _spacing(p, 0, 0, 1.0)
    rich(p, "max for all      ·      min for any", 30, INK, bold=True)

    _, tf = textbox(s, M, 5.85, CW, 0.4)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _spacing(p, 0, 0, 1.0)
    rich(p, "One score, one search, no k′ tuning.", 13, MUTED, italic=True)

    # ---------------------------------------------------------------- 13 Q&A
    s = d.slide(
        "Discussion", "Questions",
        accent=BLUE, timing="15:00+",
        notes=(
            "Happy to take questions.\n\n"
            "Backup slides follow: the formal definitions and theorems, the dataset table, "
            "the time breakdown, and a complexity summary.\n\n"
            "Short answers ready: averaging is only right for balanced queries; recall is "
            "not guaranteed; no new index is needed; the MEB is amortised at useful recall; "
            "runtime grows sublinearly in m."
        ))

    _, tf = textbox(s, M, 2.15, CW, 0.9)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _spacing(p, 0, 0, 1.0)
    rich(p, "Questions", 54, INK, bold=True)

    _, tf = textbox(s, M, 3.2, CW, 0.45)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _spacing(p, 0, 0, 1.0)
    rich(p, "max for all  ·  min for any", 18, GOLD, bold=True)

    _, tf = textbox(s, M, 4.55, CW, 1.2)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _spacing(p, 0, 8, 1.0)
    rich(p, "BACKUP SLIDES", 10, MUTED, bold=True)
    for t in ["B1 · Formal definitions & theorems",
              "B2 · Datasets",
              "B3 · Time decomposition & other metrics",
              "B4 · Complexity summary"]:
        p = tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        _spacing(p, 0, 3, 1.0)
        rich(p, t, 12, MUTED)

    # ---------------------------------------------------------------- B1
    s = d.slide(
        "Backup", "Formal definitions and the two key theorems",
        accent=MUTED, timing="backup",
        notes=(
            "Use only if asked for rigor.\n\n"
            "Theorem 4.1 says the all-radius is the maximum distance and the any-radius is "
            "the minimum — which is why ranking by radius is exactly ranking by capture "
            "time.\n\n"
            "Theorem 4.2 is the Lipschitz bound that licenses graph search. The appendix "
            "also proves that the merge baseline is correct for any-k with exact per-vector "
            "search, and for all-k only when the final set is contained in every per-vector "
            "result set."
        ))

    _, tf = textbox(s, M, 1.78, 5.9, 4.9)
    for i, t in enumerate([
        "**all-k:**  r* is the smallest radius with  |∩ᵢ B(qᵢ, r)| ≥ k",
        "**any-k:**  r* is the smallest radius with  |∪ᵢ B(qᵢ, r)| ≥ k",
    ]):
        para(tf, t, 13, INK, first=(i == 0), after=14, line=1.2)

    para(tf, "**Theorem 4.1**", 13, BLUE, before=8, after=4)
    para(tf, "r̂(u) = maxᵢ δ(qᵢ, u)   for all-k", 12.5, INK, after=2)
    para(tf, "r̂(u) = minᵢ δ(qᵢ, u)   for any-k", 12.5, INK, after=14)

    para(tf, "**Theorem 4.2**", 13, BLUE, before=6, after=4)
    para(tf, "| r̂(u) − r̂(v) | ≤ δ(u, v)  for all u, v", 12.5, INK, after=8)
    para(tf, "Proof: apply the triangle inequality to each δ(qᵢ, ·), then take the max / min.",
         11, MUTED, italic=True)

    _, tf = textbox(s, 6.75, 1.78, 6.05, 4.9)
    para(tf, "Why the merge baseline is correct (appendix)", 13.5, INK, bold=True, first=True, after=8)
    for t in [
        "**any-k:** with exact per-vector k-NN, the merged pool provably contains the answer.",
        "**all-k:** correct only when the final set is contained in every per-vector result set — hence the iterative doubling.",
        "RadiusSearch keeps the same time and space complexity as beam search: only the comparison key changes.",
    ]:
        para(tf, t, 12, MUTED, after=10, bullet=True, bullet_color=MUTED, line=1.2)

    # ---------------------------------------------------------------- B2
    s = d.slide(
        "Backup", "Datasets and experimental setup",
        accent=MUTED, timing="backup",
        notes=(
            "Five datasets spanning image, audio and text. All methods share one HNSW "
            "index, EF 400, M 32. k=10, m=5 by default, 1000 queries, single thread. "
            "Metrics are QPS and recall@k against exact ground truth."
        ))

    table(s,
          [["dataset", "dim.", "#vectors", "#queries", "type"],
           ["Recipe", "2,048", "887,536", "1,000", "image"],
           ["Msong", "420", "992,272", "200", "audio"],
           ["SIFT", "128", "1,000,000", "10,000", "image"],
           ["GIST", "960", "1,000,000", "1,000", "image"],
           ["Crawl", "300", "1,989,995", "10,000", "text"]],
          x=M, y=1.95, col_w=[2.2, 2.0, 2.6, 2.2, 2.2], row_h=0.56, font=13)

    _, tf = textbox(s, M, 5.45, CW, 1.2)
    for i, t in enumerate([
        "**Index:** identical HNSW for every method — EF = 400, M = 32.",
        "**Query load:** k = 10, m = 5 by default, 1,000 queries, single thread.",
        "**Metrics:** QPS (efficiency) and recall@k against exact ground truth (quality).",
    ]):
        para(tf, t, 13, INK, first=(i == 0), after=8, bullet=True, bullet_color=MUTED, line=1.15)

    # ---------------------------------------------------------------- B3
    s = d.slide(
        "Backup", "Time breakdown, scaling, and other metrics",
        accent=MUTED, timing="backup",
        notes=(
            "Time breakdown: for all-k the MEB phase can exceed half the runtime at small "
            "beam widths, i.e. low recall. That is why RadiusSearch+ looks worse than plain "
            "RadiusSearch at low recall and better at high recall. For any-k the m one-NN "
            "searches are the fixed first-stage cost.\n\n"
            "Scaling: runtime grows sublinearly in m up to 20.\n\n"
            "Other metrics: with normalised embeddings, inner product, cosine and Euclidean "
            "are equivalent; for non-normalised inner product the authors adjust a small "
            "portion of HNSW edges. RadiusSearch+ stays consistent."
        ))

    _, tf = textbox(s, M, 1.85, 5.9, 4.6)
    para(tf, "Where the time goes (all-k, RadiusSearch+)", 13.5, INK, bold=True, first=True, after=10)
    for t in [
        "**Phase 1 — MEB centre:** > 50% of runtime when the beam width is small.",
        "**Phase 2 — 1-NN of v̄:** fixed cost, independent of beam width.",
        "**Phase 3 — radius search:** dominates at high recall.",
        "⇒ RadiusSearch+ wins exactly where it matters: recall ≥ 0.99.",
    ]:
        para(tf, t, 12, MUTED, after=9, bullet=True, bullet_color=MUTED, line=1.18)

    _, tf = textbox(s, 6.75, 1.85, 6.05, 4.6)
    para(tf, "Scaling and extensions", 13.5, INK, bold=True, first=True, after=10)
    for t in [
        "**m = 2 → 20:** runtime grows sublinearly — seeding is fixed, the walk dominates.",
        "**k = 5 → 30:** stable QPS at recall 0.99.",
        "**Cosine / inner product:** supported; normalised embeddings make the three metrics equivalent.",
        "**Query selection:** perturbation-style queries are easier than random ones.",
    ]:
        para(tf, t, 12, MUTED, after=9, bullet=True, bullet_color=MUTED, line=1.18)

    # ---------------------------------------------------------------- B4
    s = d.slide(
        "Backup", "Complexity summary",
        accent=MUTED, timing="backup",
        notes=(
            "Per distance evaluation: m-d for the radius, d for the Euclidean seed. One-off "
            "MEB: m squared d plus m to the 3.5. The graph walk itself is the same as beam "
            "search. That is the whole cost story."
        ))

    table(s,
          [["operation", "cost", "when"],
           ["all/any-radius of one vector", "O(m · d)", "every distance evaluation"],
           ["MEB centre of the query", "O(m²d + m³·⁵)", "once per query (all-k)"],
           ["1-NN of the MEB centre", "O(d) per distance", "once per query (all-k)"],
           ["1-NN of each qᵢ", "O(d) per distance", "m times per query (any-k)"],
           ["radius beam search", "same as beam search", "the search itself"]],
          x=M, y=1.95, col_w=[4.6, 3.6, 4.0], row_h=0.62, font=12.5)

    _, tf = textbox(s, M, 5.75, CW, 0.8)
    para(tf, "The only structural change to the index: none. The comparison key is swapped; "
             "the graph is reused.", 13, MUTED, first=True, italic=True)

    path = d.save("MultiVector_ANN_Slides.pptx")
    write_notes(d)
    return path


def write_notes(d):
    lines = ["# Speaker notes — Multi-Vector ANN Search", "",
             "Generated from the deck's notes pane. Timing in brackets.", ""]
    for num, title in d.toc:
        slide = d.prs.slides[num - 1]
        notes = slide.notes_slide.notes_text_frame.text.strip()
        lines.append(f"## {num:02d} · {title}")
        lines.append("")
        lines.append(notes if notes else "_(no notes)_")
        lines.append("")
    path = os.path.join(BASE, "SPEAKER_NOTES.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print("wrote", path)


if __name__ == "__main__":
    build()
