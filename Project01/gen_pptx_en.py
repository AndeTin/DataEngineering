#!/usr/bin/env python3
"""
gen_pptx_en.py — 由 PPT_Outline_EN.md + esort.c 產生 esort_Report_EN.pptx

與 gen_pptx.py 共用同一套版面工具（import gen_pptx），因此中英文兩份
投影片的配色、字級、間距完全一致；只有文字內容不同。
程式碼片段同樣直接從 esort.c 依行號抽取。
"""

import re
import gen_pptx as K
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# 英文版不需要 East Asian 字型，直接沿用同一套拉丁字型
K.CJK_FONT = "Segoe UI"

OUTLINE = f"{K.HERE}/PPT_Outline_EN.md"
OUTPUT = f"{K.HERE}/esort_Report_EN.pptx"

NAVY, BLUE, ORANGE, GREEN, RED = K.NAVY, K.BLUE, K.ORANGE, K.GREEN, K.RED
GREY, LGREY, CODEBG, WHITE = K.GREY, K.LGREY, K.CODEBG, K.WHITE
RGBColor = K.RGBColor


# ---------------------------------------------------------------- 工具
def parse_outline(path):
    txt = open(path, encoding="utf-8").read()
    slides = {}
    for b in re.split(r"\n## ", txt)[1:]:
        head = b.split("\n")[0]
        m = re.match(r"(\d+)\.\s*(.+)", head)
        if m:
            key, title = int(m.group(1)), m.group(2)
        elif head.startswith("Appendix A1"):
            key, title = 101, head.split(":", 1)[1].strip()
        elif head.startswith("Appendix A2"):
            key, title = 102, head.split(":", 1)[1].strip()
        else:
            continue                                    # Timing Overview / A3 略過
        notes, tm, in_notes = [], 30, False
        for line in b.split("\n")[1:]:
            t = re.search(r"\*\*Time\*\*: (\d+)", line)
            if t:
                tm = int(t.group(1))
            if line.startswith(">"):
                in_notes = True
                notes.append(line[1:].strip())
            elif in_notes and line.strip() and "Key takeaway" not in line:
                notes.append("")
            elif line.strip():
                in_notes = False
        keymsg = ""
        km = re.search(r"\*\*Key takeaway\*\*: (.+)", b)
        if km:
            keymsg = km.group(1).strip()
        slides[key] = dict(title=title, notes="\n".join(notes).strip(), time=tm,
                           keymsg=keymsg)
    return slides


def footer(slide, page, total=19):
    """英文版頁尾（覆寫 gen_pptx 的中文頁尾）。"""
    tf = K.textbox(slide, Inches(0.55), Inches(7.05), Inches(8), Inches(0.3))
    K.para(tf, "esort — External Sort: Design and Implementation", 10, False,
           RGBColor(0x9A, 0xA3, 0xAD), first=True, space_after=0)
    tf2 = K.textbox(slide, Inches(11.9), Inches(7.05), Inches(0.9), Inches(0.3))
    K.para(tf2, f"{page} / {total}", 10, False, RGBColor(0x9A, 0xA3, 0xAD),
           first=True, space_after=0)
    tf2.paragraphs[0].alignment = PP_ALIGN.RIGHT


def excerpt(*ranges):
    """依 (起, 訖) 抽取 esort.c 原始碼，非連續區段插入省略號（英文版用 ...）。"""
    out = []
    for i, (a, b) in enumerate(ranges):
        if i:
            out.append("        ...")
        out.extend(K.SRC_LINES[a - 1:b])
    return out


# ---------------------------------------------------------------- 主程式
def build():
    outline = parse_outline(OUTLINE)
    prs = Presentation()
    prs.slide_width, prs.slide_height = K.SW, K.SH

    rect, textbox, para, rich_para = K.rect, K.textbox, K.para, K.rich_para
    code_block, table = K.code_block, K.table   # footer 由本檔案的英文版覆寫

    # ---------- 1 Title ----------
    s = K.base_slide(prs)
    rect(s, 0, 0, K.SW, Inches(2.55), NAVY, shape=MSO_SHAPE.RECTANGLE)
    rect(s, 0, Inches(2.55), K.SW, Pt(4), ORANGE, shape=MSO_SHAPE.RECTANGLE)
    tf = textbox(s, Inches(0.9), Inches(0.72), Inches(11.5), Inches(0.7))
    para(tf, "esort", 54, True, WHITE, first=True, space_after=0)
    tf = textbox(s, Inches(0.95), Inches(1.62), Inches(11.5), Inches(0.6))
    para(tf, "External Merge Sort with a Hard Memory Ceiling", 22, False,
         RGBColor(0xC8, 0xD6, 0xE5), first=True, space_after=0)

    tf = textbox(s, Inches(0.95), Inches(3.15), Inches(11.5), Inches(1.9))
    rich_para(tf, [("A sorting tool that never uses more than ", {"color": GREY}),
                   ("-m", {"mono": True, "bold": True, "color": BLUE}),
                   (" of memory", {"color": GREY, "bold": True})],
              22, first=True, space_after=10)
    para(tf, "1,413 lines of C   ·   zero compiler warnings   ·   288 automated "
             "differential test cases, all passing",
         16, False, GREY, space_after=16)
    para(tf, "Key designs: shared comparator  ·  arena memory pool  ·  Min-Heap "
             "k-way merge  ·  multi-pass fallback",
         14, False, BLUE, space_after=0)

    tf = textbox(s, Inches(0.95), Inches(5.85), Inches(11.5), Inches(1.0))
    para(tf, "Course: Data Engineering      Presenter: ____________      Date: ____________",
         14, False, RGBColor(0x8A, 0x93, 0x9D), first=True, space_after=6)
    para(tf, "Toolchain: gcc -Wall -Wextra -O2 -std=c11  /  GNU Make", 12, False,
         RGBColor(0xA8, 0xB0, 0xB8), space_after=0)
    K.notes(s, outline, 1)

    # ---------- 2 Motivation ----------
    s = K.content_slide(prs, "Motivation: Why External Sorting",
                        "Sorting algorithms assume the data fits in memory")
    tf = textbox(s, Inches(0.82), Inches(1.72), Inches(11.7), Inches(2.3))
    rich_para(tf, [("The assumption behind ", {"color": GREY}),
                   ("qsort()", {"mono": True, "bold": True, "color": BLUE}),
                   (": the entire dataset must fit in memory.", {"color": GREY})],
              18, first=True, space_after=10, bullet="▪")
    rich_para(tf, [("Real workloads are tens of GB of logs and transaction dumps — "
                    "that assumption ", {}),
                   ("simply does not hold", {"bold": True, "color": RED}), (".", {})],
              18, space_after=10, bullet="▪")
    rich_para(tf, [("External sort: ", {"bold": True, "color": NAVY}),
                   ("sort in memory → spill to disk → merge", {"bold": True, "color": BLUE}),
                   (".", {})], 18, space_after=14, bullet="▪")

    box = rect(s, Inches(0.82), Inches(4.25), Inches(11.7), Inches(1.55),
               RGBColor(0xF2, 0xF6, 0xFA), LGREY)
    tf = box.text_frame
    tf.vertical_anchor = K.MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.25)
    tf.margin_top = Inches(0.18)
    rich_para(tf, [("Complexity split ", {"bold": True, "color": NAVY, "size": 16}),
                   ("   (M records fit in memory, N total, k runs merged at once)",
                    {"color": GREY, "size": 13})], 16, first=True, space_after=8)
    rich_para(tf, [("Internal sort  ", {"color": GREY}),
                   ("O(N/M × M log M)", {"mono": True, "bold": True, "color": BLUE}),
                   ("        I/O cost  ", {"color": GREY}),
                   ("O(N log_k N)", {"mono": True, "bold": True, "color": ORANGE})],
              16, space_after=8)
    para(tf, "The base of that logarithm decides everything: the larger k, the fewer "
             "times we read and write temp files.", 14, False, GREY, space_after=0)
    footer(s, 2)
    K.notes(s, outline, 2)

    # ---------- 3 Goals & constraints ----------
    s = K.content_slide(prs, "Goals and Constraints",
                        "Five hard constraints drive every design decision")
    tf = textbox(s, Inches(0.82), Inches(1.72), Inches(6.2), Inches(0.4))
    para(tf, "Feature: six command-line options", 18, True, NAVY, first=True, space_after=0)
    rows = [["Option", "Function", "Purpose"],
            ["-c", "strcasecmp()", "case-insensitive"],
            ["-m <size>", "atoi()", "memory ceiling (MB)"],
            ["-r", "negate result", "reverse order"],
            ["-n", "atoi()", "numeric sort"],
            ["-l", "strlen()", "length first"],
            ["-o <file>", "fopen()", "output (default stdout)"]]
    table(s, Inches(0.82), Inches(2.2), Inches(6.2), rows, [1.3, 1.9, 3.2], 13)

    tf = textbox(s, Inches(7.45), Inches(1.72), Inches(5.2), Inches(0.4))
    para(tf, "Hard constraints", 18, True, NAVY, first=True, space_after=0)
    items = [("1", "Memory must never exceed -m", "strictly, not approximately"),
             ("2", "Two-phase external sort", "memory + spill + merge"),
             ("3", "Runs may exceed the fd limit", "needs multi-pass merging"),
             ("4", "-o must not damage the input", "it may be the same file"),
             ("5", "Release every resource on exit", "files, memory, temp files")]
    y = 2.22
    for num, title, sub in items:
        c = rect(s, Inches(7.45), Inches(y), Inches(0.34), Inches(0.34), BLUE)
        p = c.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = num
        K.set_font(r, 14, True, WHITE)
        tf2 = textbox(s, Inches(7.92), Inches(y - 0.02), Inches(4.7), Inches(0.75))
        para(tf2, title, 15, True, GREY, first=True, space_after=1)
        para(tf2, sub, 12, False, RGBColor(0x93, 0x9C, 0xA6), space_after=0)
        y += 0.86
    footer(s, 3)
    K.notes(s, outline, 3)

    # ---------- 4 Architecture ----------
    s = K.content_slide(prs, "System Architecture: Two-Phase External Merge Sort",
                        "The whole flow on one slide")

    def stage(x, w, title, color):
        rect(s, x, Inches(1.85), w, Inches(2.5), WHITE, color)
        rect(s, x, Inches(1.85), w, Inches(0.42), color, shape=MSO_SHAPE.RECTANGLE)
        t = textbox(s, x + Inches(0.15), Inches(1.92), w - Inches(0.3), Inches(0.3))
        para(t, title, 15, True, WHITE, first=True, space_after=0)

    box = rect(s, Inches(0.82), Inches(2.7), Inches(1.55), Inches(0.85), NAVY)
    p = box.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "Input"
    K.set_font(r, 14, True, WHITE)

    stage(Inches(2.62), Inches(3.9), "Phase 1   Run Generation", BLUE)
    tf = textbox(s, Inches(2.85), Inches(2.45), Inches(3.5), Inches(1.8))
    para(tf, "1. Read into memory pool (budget-checked)", 13.5, True, GREY, first=True,
         space_after=8, bullet="▪")
    para(tf, "2. qsort() the batch", 13.5, True, GREY, space_after=8, bullet="▪")
    para(tf, "3. Write one run file", 13.5, True, GREY, space_after=8, bullet="▪")
    para(tf, "4. Repeat until EOF (K runs)", 13.5, True, GREY, space_after=0, bullet="▪")

    stage(Inches(6.82), Inches(3.9), "Phase 2   K-way Merge", ORANGE)
    tf = textbox(s, Inches(7.05), Inches(2.45), Inches(3.6), Inches(1.8))
    para(tf, "1. Open all runs, read first line each", 13.5, True, GREY, first=True,
         space_after=8, bullet="▪")
    para(tf, "2. Push onto the Min-Heap", 13.5, True, GREY, space_after=8, bullet="▪")
    para(tf, "3. Pop root, refill from same run", 13.5, True, GREY, space_after=8, bullet="▪")
    para(tf, "4. If runs > k, merge in passes", 13.5, True, GREY, space_after=0, bullet="▪")

    box = rect(s, Inches(11.0), Inches(2.7), Inches(1.55), Inches(0.85), NAVY)
    p = box.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "Output"
    K.set_font(r, 14, True, WHITE)

    for ax in (Inches(2.37), Inches(6.52), Inches(10.72)):
        ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, ax, Inches(2.95), Inches(0.25), Inches(0.34))
        ar.fill.solid(); ar.fill.fore_color.rgb = LGREY
        ar.line.fill.background(); ar.shadow.inherit = False

    box = rect(s, Inches(0.82), Inches(4.68), Inches(11.73), Inches(1.72),
               RGBColor(0xF7, 0xF9, 0xFB), LGREY)
    tf = box.text_frame
    tf.vertical_anchor = K.MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.22)
    tf.margin_top = Inches(0.14)
    rich_para(tf, [("Memory budget split ", {"bold": True, "color": NAVY, "size": 15}),
                   ("total = -m MB; subtract what phase 2 is guaranteed to need, "
                    "the rest goes to phase 1", {"color": GREY, "size": 13})],
              15, first=True, space_after=10)
    rect(s, Inches(1.05), Inches(5.42), Inches(6.9), Inches(0.5), WHITE, LGREY,
         MSO_SHAPE.RECTANGLE)
    rect(s, Inches(1.05), Inches(5.42), Inches(6.9) * 0.06, Inches(0.5), ORANGE,
         shape=MSO_SHAPE.RECTANGLE)
    t = textbox(s, Inches(1.05), Inches(5.98), Inches(3.4), Inches(0.35))
    para(t, "merge reserve (k × per-run buffers)", 12, True, ORANGE, first=True, space_after=0)
    t = textbox(s, Inches(4.35), Inches(5.98), Inches(3.6), Inches(0.35))
    para(t, "phase 1 pool (chunk_budget)", 12, True, BLUE, first=True, space_after=0)
    t = textbox(s, Inches(8.15), Inches(5.40), Inches(4.2), Inches(0.55))
    para(t, "Why reserve first?", 14, True, NAVY, first=True, space_after=2)
    para(t, "otherwise we discover too late that memory ran out", 12, False, RED, space_after=0)
    footer(s, 4)
    K.notes(s, outline, 4)

    # ---------- 5 Five ideas ----------
    s = K.content_slide(prs, "Five Design Ideas at a Glance",
                        "Each idea answers exactly one of the five constraints")
    cards = [
        ("1", "One shared comparator", "internal sort and external merge\ncall cmp_strings()", "constraint: correctness", BLUE),
        ("2", "Arena memory pool", "64 KB blocks chained,\npointers never dangle", "constraint: memory", GREEN),
        ("3", "Budget split + derived k", "k follows -m, capped at 512", "constraint: memory / fds", GREEN),
        ("4", "Min-Heap merge", "root replacement: one\nsift-down per line", "constraint: I/O cost", ORANGE),
        ("5", "Resource safety", "same-file output, mkstemp,\nover-long lines", "constraint: data safety", RED),
    ]
    x = Inches(0.82)
    for i, (num, title, desc, tag, color) in enumerate(cards):
        cx = x + i * Inches(2.42)
        c = rect(s, cx, Inches(2.15), Inches(2.22), Inches(3.3), WHITE, color)
        tf = c.text_frame
        tf.vertical_anchor = K.MSO_ANCHOR.TOP
        tf.margin_top = Inches(0.18)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = num
        K.set_font(r, 34, True, color)
        tf2 = textbox(s, cx + Inches(0.14), Inches(3.05), Inches(1.94), Inches(1.6))
        para(tf2, title, 14, True, NAVY, first=True, space_after=6, line=1.2)
        para(tf2, desc, 11.5, False, GREY, space_after=0, line=1.3)
        t = textbox(s, cx + Inches(0.14), Inches(4.78), Inches(1.94), Inches(0.6))
        para(t, tag, 10.5, True, color, first=True, space_after=0, line=1.2)

    tf = textbox(s, Inches(0.82), Inches(5.78), Inches(11.7), Inches(0.8))
    rich_para(tf, [("Through-line: ", {"bold": True, "color": NAVY}),
                   ("how do we make correctness and the memory limit hold at the same time?",
                    {"bold": True, "color": BLUE})], 17, first=True, space_after=6)
    para(tf, "Every design decision answers one question: what breaks if I do it this "
             "way, and how do I prove it won't?", 14, False, GREY, space_after=0)
    footer(s, 5)
    K.notes(s, outline, 5)

    # ---------- 6 Idea 1 ----------
    s = K.content_slide(prs, "Idea 1: One Shared Comparator",
                        "Written once, so the two phases cannot disagree")
    tf = textbox(s, Inches(0.82), Inches(1.68), Inches(5.6), Inches(4.6))
    rich_para(tf, [("Classic bug: ", {"bold": True, "color": RED}),
                   ("writing the comparison twice — phase one sorts lexicographically, "
                    "phase two merges numerically.", {})], 15.5, first=True,
              space_after=8, bullet="✗")
    para(tf, "The result is silently wrong, and with large data the only symptom is "
             "\"looks mostly sorted\" — very hard to notice.", 13.5, False, GREY,
         space_after=16, indent=0.35, line=1.4)
    rich_para(tf, [("Fix: ", {"bold": True, "color": GREEN}),
                   ("both paths call cmp_strings(); only the interface differs.", {})],
              15.5, space_after=8, bullet="✓")
    para(tf, "qsort() gets char** → one extra dereference\nMin-Heap gets HeapItem → uses the pointer inside",
         12.5, False, GREY, mono=True, space_after=16, indent=0.35, line=1.5)
    rich_para(tf, [("Order  ", {"bold": True, "color": NAVY}),
                   ("-l length → -n numeric → dictionary (-c) → -r reverse",
                    {"mono": True, "color": BLUE})], 13.5, space_after=8)
    rich_para(tf, [("-n compares with < and > instead of subtracting: ", {"color": GREY}),
                   ("atoi() returns int; subtracting large values overflows.",
                    {"color": RED})], 13.5, space_after=0)

    code_block(s, Inches(6.75), Inches(1.95), Inches(5.8),
               excerpt((133, 135), (138, 145), (149, 159), (166, 170)),
               "esort.c : cmp_strings()  (L133)", 9.5, max_h=4.55)
    footer(s, 6)
    K.notes(s, outline, 6)

    # ---------- 7 Idea 2 ----------
    s = K.content_slide(prs, "Idea 2: Arena Memory Pool",
                        "Fixed-size chained blocks — pointers never dangle, peak never doubles")
    tf = textbox(s, Inches(0.82), Inches(1.68), Inches(5.45), Inches(2.6))
    rich_para(tf, [("Problem: ", {"bold": True, "color": RED}),
                   ("the pointer array must grow, so realloc() may move the whole block.",
                    {})], 15.5, first=True, space_after=8, bullet="▪")
    para(tf, "1. every pointer is invalidated at once\n2. during the move both copies exist → peak doubles",
         12.5, False, GREY, space_after=16, indent=0.35, line=1.5)
    rich_para(tf, [("Fix: ", {"bold": True, "color": GREEN}),
                   ("64 KB blocks chained together, never moved.", {})],
              15.5, space_after=8, bullet="▪")
    para(tf, "A line's pointer stays valid from write until the batch is sorted, and peak "
             "memory is fully under my control because I choose the block size.",
         12.5, False, GREY, space_after=0, indent=0.35, line=1.4)

    bx = rect(s, Inches(0.95), Inches(4.62), Inches(5.2), Inches(1.5),
              RGBColor(0xF7, 0xF9, 0xFB), LGREY)
    tf = bx.text_frame
    tf.vertical_anchor = K.MSO_ANCHOR.TOP
    tf.margin_top = Inches(0.1)
    para(tf, "ArenaBlock chain (64 KB each, never moved)", 12, True, NAVY,
         first=True, space_after=6)
    bx2 = rect(s, Inches(1.15), Inches(5.22), Inches(1.25), Inches(0.55), BLUE,
               shape=MSO_SHAPE.RECTANGLE)
    bx3 = rect(s, Inches(2.55), Inches(5.22), Inches(1.25), Inches(0.55), BLUE,
               shape=MSO_SHAPE.RECTANGLE)
    bx4 = rect(s, Inches(3.95), Inches(5.22), Inches(1.95), Inches(0.55), LGREY,
               shape=MSO_SHAPE.RECTANGLE)
    for bx_ in (bx2, bx3, bx4):
        p = bx_.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = "used / size"
        K.set_font(r, 10, False, WHITE if bx_ is not bx4 else GREY)

    yb = code_block(s, Inches(6.55), Inches(1.95), Inches(6.0),
                    excerpt((450, 450), (459, 473)),
                    "esort.c : CHUNK_USED + chunk_alloc()  (L450)", 10, max_h=3.3)
    box = rect(s, Inches(6.55), yb + Inches(0.25), Inches(6.0), Inches(0.9),
               RGBColor(0xFF, 0xF6, 0xEC), ORANGE)
    tf = box.text_frame
    tf.vertical_anchor = K.MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.18)
    rich_para(tf, [("Pointers count too! ", {"bold": True, "color": ORANGE}),
                   ("the spec counts dynamically allocated arrays; capacity grows as a "
                    "power of two, so it gets expensive.", {"color": GREY})],
              13, first=True, space_after=0, line=1.3)
    footer(s, 7)
    K.notes(s, outline, 7)

    # ---------- 8 Idea 3 ----------
    s = K.content_slide(prs, "Idea 3: Splitting the Budget and Deriving k",
                        "k is not hard-coded — small -m degrades instead of crashing")
    tf = textbox(s, Inches(0.82), Inches(1.68), Inches(6.4), Inches(2.5))
    rich_para(tf, [("Budget: ", {"bold": True, "color": NAVY}),
                   ("every run stays open during merging, each with an 8 KB read buffer "
                    "and a 4 KB line buffer.", {})], 15.5, first=True, space_after=8, bullet="▪")
    para(tf, "That memory must be reserved before phase one even finishes, or we read "
             "everything and only then find none is left.", 12.5, False, GREY,
         space_after=16, indent=0.35, line=1.4)
    rich_para(tf, [("Classic bug: ", {"bold": True, "color": RED}),
                   ("hard-coding k = 512 costs 512 × 12 KB ≈ 6 MB on its own; with "
                    "-m 1 it simply does not fit.", {})], 15.5, space_after=8, bullet="✗")
    rich_para(tf, [("Fix: ", {"bold": True, "color": GREEN}),
                   ("derive k from the budget, cap at 512, and fall back to multi-pass "
                    "merging.", {})], 15.5, space_after=0, bullet="✓")

    rows = [["-m", "derived k", "merge reserve", "phase 1 budget", "runs > k ?"],
            ["100", "512", "6.16 MB", "93.84 MB", "no"],
            ["16", "512", "6.16 MB", "9.84 MB", "no"],
            ["8", "328", "3.99 MB", "4.01 MB", "no"],
            ["4", "158", "1.99 MB", "2.01 MB", "no"],
            ["1", "31", "0.49 MB", "0.51 MB", "yes → multi-pass"]]
    t = table(s, Inches(0.82), Inches(4.62), Inches(6.4), rows,
              [0.9, 1.1, 1.5, 1.6, 2.2], 12, row_h=Inches(0.31))
    for p in t.cell(5, 4).text_frame.paragraphs:
        for r in p.runs:
            r.font.color.rgb = ORANGE

    code_block(s, Inches(7.45), Inches(1.95), Inches(5.1),
               K.src(983, 1002), "esort.c : calc_fanin()  (L983)", 10.5, max_h=4.4)
    footer(s, 8)
    K.notes(s, outline, 8)

    # ---------- 9 Idea 4 ----------
    s = K.content_slide(prs, "Idea 4: Min-Heap Merge with Root Replacement",
                        "One sift-down per line instead of two passes")
    tf = textbox(s, Inches(0.82), Inches(1.68), Inches(5.5), Inches(3.0))
    rich_para(tf, [("Textbook: ", {"bold": True, "color": GREY}),
                   ("pop the root, write it, push a new item back.", {})],
              15.5, first=True, space_after=8, bullet="▪")
    para(tf, "pop needs sift_down, push needs sift_up → two heap passes per line.",
         12.5, False, GREY, space_after=16, indent=0.35, line=1.4)
    rich_para(tf, [("Property to exploit: ", {"bold": True, "color": NAVY}),
                   ("the popped element and the replacement always come from the "
                    "same run.", {})], 15.5, space_after=8, bullet="▪")
    para(tf, "Only the root position changes, so overwrite it and do one sift_down — "
             "semantically identical, minus the sift_up.", 12.5, False, GREY,
         space_after=16, indent=0.35, line=1.4)
    rich_para(tf, [("Measured: ", {"bold": True, "color": GREEN}),
                   ("−8 to 11% comparator calls, 3 to 4% faster",
                    {"bold": True, "color": GREEN})], 15.5, space_after=8, bullet="→")
    para(tf, "Honest caveat: less than the \"nearly half\" I expected — sift_up after a "
             "push usually stops at the first level. The real win is halving the worst "
             "case; the deeper the heap, the more it helps.", 12.5, False, GREY,
         space_after=0, indent=0.35, line=1.4)

    yb = code_block(s, Inches(6.65), Inches(1.95), Inches(5.9),
                    K.src(819, 847), "esort.c : merge loop  (L819)", 9.5, max_h=3.9)
    box = rect(s, Inches(6.65), yb + Inches(0.22), Inches(5.9), Inches(0.7),
               RGBColor(0xFF, 0xF6, 0xEC), ORANGE)
    tf = box.text_frame
    tf.margin_left = Inches(0.18)
    rich_para(tf, [("Careful: ", {"bold": True, "color": ORANGE}),
                   ("run->line is the buffer the root points at — write it out before "
                    "overwriting it.", {"color": GREY})], 12.5, first=True, space_after=0)
    footer(s, 9)
    K.notes(s, outline, 9)

    # ---------- 10 Idea 5 ----------
    s = K.content_slide(prs, "Idea 5: Resource-Safety Details",
                        "Small things that silently corrupt results")
    items = [
        ("A", "-o may name the input file", RED,
         "Opening it for writing destroys data that has not been read yet.\n"
         "Fix: compare the path strings and stat() st_dev/st_ino; if identical, write to "
         "a temporary file and overwrite only after the merge completes."),
        ("B", "Temp file names must not be invented", ORANGE,
         "A shared /tmp has races — another process may take or overwrite the name.\n"
         "Fix: mkstemp() lets the kernel guarantee uniqueness."),
        ("C", "Input edge cases", BLUE,
         "A final line with no newline, Windows \\r\\n, lines longer than 4,096 bytes.\n"
         "Fix: truncate over-long lines but still count them as one line — the line "
         "count must never drift."),
    ]
    y = Inches(1.85)
    for tag, title, color, desc in items:
        rect(s, Inches(0.82), y, Inches(11.73), Inches(1.45),
             RGBColor(0xFA, 0xFB, 0xFC), LGREY)
        c = rect(s, Inches(1.05), y + Inches(0.42), Inches(0.6), Inches(0.6), color)
        p = c.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = tag
        K.set_font(r, 20, True, WHITE)
        tf = textbox(s, Inches(1.95), y + Inches(0.18), Inches(10.4), Inches(1.15))
        para(tf, title, 16.5, True, NAVY, first=True, space_after=5)
        para(tf, desc, 12.5, False, GREY, space_after=0, line=1.35)
        y += Inches(1.62)
    footer(s, 10)
    K.notes(s, outline, 10)

    # ---------- 11 vs sort ----------
    s = K.content_slide(prs, "Relationship to sort, and Complexity",
                        "Same algorithm family, different memory model")
    rows = [["Aspect", "esort (this project)", "GNU sort"],
            ["Algorithm", "external merge sort, two phases", "also external merge sort"],
            ["Memory", "-m is a hard ceiling, precisely set", "uses whatever is available"],
            ["When memory is tight", "k shrinks automatically → multi-pass, predictable",
             "picks its own merge strategy"],
            ["Output", "stdout by default; -o may sort in place", "stdout"],
            ["Stability", "not stable (qsort never guarantees it)", "not stable by default"]]
    table(s, Inches(0.82), Inches(1.85), Inches(11.73), rows, [2.3, 4.8, 3.8], 13.5,
          row_h=Inches(0.42))
    box = rect(s, Inches(0.82), Inches(4.55), Inches(11.73), Inches(2.0),
               RGBColor(0xF2, 0xF6, 0xFA), BLUE)
    tf = box.text_frame
    tf.vertical_anchor = K.MSO_ANCHOR.TOP
    tf.margin_top = Inches(0.16)
    tf.margin_left = Inches(0.22)
    rich_para(tf, [("Practical finding: more memory is not always faster",
                    {"bold": True, "color": NAVY})], 16, first=True, space_after=8)
    rich_para(tf, [("-m 4 → 0.97 s     -m 8 → 1.06 s     ", {"color": GREY}),
                   ("-m 100 → 1.67 s", {"bold": True, "color": ORANGE}),
                   ("   (75 MB, 1.5 M lines)", {"color": GREY})], 15, space_after=6)
    para(tf, "A bigger in-memory batch hurts qsort() cache locality, and the final write "
             "is sequential I/O, so the time saved by writing fewer temp files does not pay "
             "for itself. This tool is I/O bound, not CPU bound.",
         13, False, GREY, space_after=0, line=1.35)
    footer(s, 11)
    K.notes(s, outline, 11)

    # ---------- 12 Performance ----------
    s = K.content_slide(prs, "Performance Measurements",
                        "75 MB / 1,500,000 lines, numeric sort, warm cache, best of 3")
    rows = [["-m", "Peak RSS (MB)", "Time (s)", "Verdict"],
            ["4", "5.6", "0.97", "memory respected"],
            ["8", "6.2", "1.06", "memory respected"],
            ["16", "12.1", "1.16", "memory respected"],
            ["100", "98.8", "1.63", "memory respected"]]
    t = table(s, Inches(0.82), Inches(1.95), Inches(6.0), rows, [1.1, 2.2, 1.5, 2.4], 14,
              row_h=Inches(0.4))
    for ri in range(1, 5):
        for p in t.cell(ri, 3).text_frame.paragraphs:
            for r in p.runs:
                r.font.color.rgb = GREEN

    tf = textbox(s, Inches(7.3), Inches(1.95), Inches(5.3), Inches(2.6))
    rich_para(tf, [("Memory really tracks -m", {"bold": True, "color": NAVY})],
              18, first=True, space_after=10)
    para(tf, "-m 100 → 98.8 MB\n-m 16  → 12.1 MB\n-m 4   → 5.6 MB", 15, False, GREY,
         mono=True, space_after=10, line=1.6)
    para(tf, "The extra 1.5–2 MB is the program image and libc overhead, not my buffers.",
         13, False, GREY, space_after=0)

    box = rect(s, Inches(0.82), Inches(4.85), Inches(11.73), Inches(1.35),
               RGBColor(0xF2, 0xF8, 0xF4), GREEN)
    tf = box.text_frame
    tf.vertical_anchor = K.MSO_ANCHOR.TOP
    tf.margin_top = Inches(0.15)
    tf.margin_left = Inches(0.22)
    rich_para(tf, [("Other verification results", {"bold": True, "color": NAVY})],
              16, first=True, space_after=8)
    rich_para(tf, [("Root replacement: ", {"color": GREY}),
                   ("−8 to 11% comparator calls, 3 to 4% faster",
                    {"bold": True, "color": GREEN}),
                   ("    |    ", {"color": LGREY}),
                   ("Differential tests: ", {"color": GREY}),
                   ("288 / 288 passing", {"bold": True, "color": GREEN}),
                   ("    |    ", {"color": LGREY}),
                   ("ASAN / UBSan: ", {"color": GREY}),
                   ("no leaks, no UB", {"bold": True, "color": GREEN})],
              13.5, space_after=0)
    footer(s, 12)
    K.notes(s, outline, 12)

    # ---------- 13/14 Bugs ----------
    def bug_slide(page, title, kicker, bugs):
        sl = K.content_slide(prs, title, kicker)
        y = 1.78
        for tag, name, rows_ in bugs:
            def wrapped(v):
                # 每行約可容納 105 個字元（12.5pt、寬 9.7 吋），估算自動換行後的行數
                n = 0
                for ln in v.split("\n"):
                    n += max(1, -(-len(ln) // 105))
                return n
            heights = [wrapped(v) * 0.235 + 0.10 for _, v, _ in rows_]
            card_h = 0.62 + sum(heights) + 0.16
            rect(sl, Inches(0.82), Inches(y), Inches(11.73), Inches(card_h),
                 RGBColor(0xFA, 0xFB, 0xFC), LGREY)
            c = rect(sl, Inches(1.02), Inches(y + 0.16), Inches(0.48), Inches(0.48), RED)
            p = c.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = tag
            K.set_font(r, 15, True, WHITE)
            tf = textbox(sl, Inches(1.70), Inches(y + 0.14), Inches(10.6), Inches(0.42))
            para(tf, name, 16, True, NAVY, first=True, space_after=0)
            yy = y + 0.62
            for (k, v, c_), hh in zip(rows_, heights):
                t1 = textbox(sl, Inches(1.70), Inches(yy), Inches(0.95), Inches(0.4))
                para(t1, k, 12.5, True, c_, first=True, space_after=0)
                t2 = textbox(sl, Inches(2.66), Inches(yy), Inches(9.7), Inches(hh))
                for i, line in enumerate(v.split("\n")):
                    para(t2, line, 12.5, False, GREY, mono=(k == "Fix"),
                         first=(i == 0), space_after=2, line=1.25)
                yy += hh
            y += card_h + 0.26
        footer(sl, page)
        return sl

    bug_slide(13, "Debugging I: Dropped Lines and a Heap Bug",
              "Both were silent errors — the program completed but the answer was wrong",
              [("1", "One line lost per run",
                [("Symptom", "with -m 1 forcing several runs, the output was shorter than "
                             "the input — exactly one line per run.", RED),
                 ("Cause", "when chunk_alloc() returned NULL we broke out of the read loop, "
                           "but that line had already been consumed from the file and was "
                           "simply discarded.", RED),
                 ("Fix", "keep a pending buffer and install that line as the first line of "
                         "the next chunk.", GREEN)]),
               ("2", "Merge order wrong, but \"mostly sorted\"",
                [("Diagnosis", "unsure whether phase one or phase two → copied all nine "
                               "run files out and checked each; every run was internally\n"
                               "sorted, which proved the bug was in the merge layer.", BLUE),
                 ("Cause", "the sift_up exit condition was written as <= 0 when it should "
                           "be >= 0, so new elements never floated up.", RED),
                 ("Fix", "correct the comparison direction; merge output then matches the "
                         "in-memory sort exactly.", GREEN)])])
    K.notes(prs.slides[-1], outline, 13)

    bug_slide(14, "Debugging II: What the Tools Caught",
              "Found by sanitizers, not by staring at the output",
              [("3", "Memory leak: the program was perfectly correct",
                [("Symptom", "results were right and only a little memory leaked — exactly "
                             "the kind of bug you never notice by eye.", RED),
                 ("Measured", "ASAN reported 589,824 bytes in 9 objects — nine runs × 64 KB.", BLUE),
                 ("Cause", "each run file allocated a 64 KB output buffer that was never "
                           "freed.", RED),
                 ("Fix", "free it immediately after writing; make ASAN + UBSan a routine "
                         "check on every refactor.", GREEN)]),
               ("4", "An out-of-bounds access I introduced while refactoring",
                [("Cause", "while optimising the heap I let one function do both \"replace "
                           "root\" and \"remove root\", and called it twice per iteration; the\n"
                           "second call drove the heap size from 0 to SIZE_MAX.", RED),
                 ("Fix", "split it into heap_set_top() and heap_remove_top() — two mutually "
                         "exclusive operations.", GREEN),
                 ("Lesson", "tests have to travel with the refactor: only re-running the full "
                            "differential suite revealed that the previous build was broken\n"
                            "too. Unit tests alone would not have caught it.", BLUE)])])
    K.notes(prs.slides[-1], outline, 14)

    # ---------- 15 Testing ----------
    s = K.content_slide(prs, "Testing Methodology",
                        "The pass criterion is \"line-by-line identical\", not \"no crash\"")
    tf = textbox(s, Inches(0.82), Inches(1.75), Inches(6.1), Inches(3.3))
    rich_para(tf, [("Reference: ", {"bold": True, "color": NAVY}),
                   ("a Python implementation of the comparison order from the "
                    "specification, using cmp_to_key.", {})], 15.5, first=True,
              space_after=10, bullet="▪")
    para(tf, "The C program's output is then compared line by line; any differing row "
             "fails the case.", 13, False, GREY, space_after=16, indent=0.35)
    rich_para(tf, [("Matrix: ", {"bold": True, "color": NAVY}),
                   ("16 flag combinations × 3 memory limits × 6 data profiles",
                    {"bold": True, "color": BLUE})], 15.5, space_after=10, bullet="▪")
    para(tf, "Profiles: plain words / pure numbers / mixed text with spaces /\n"
             "4,000-character lines / empty file / single-line file\n"
             "Flags: all 2⁴ arrangements of -c -r -n -l\n"
             "Memory: 1 MB / 2 MB / 100 MB",
         12.5, False, GREY, space_after=0, indent=0.35, line=1.5)

    box = rect(s, Inches(7.2), Inches(1.95), Inches(5.35), Inches(1.5),
               RGBColor(0xF2, 0xF8, 0xF4), GREEN)
    tf = box.text_frame
    tf.vertical_anchor = K.MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "288 / 288"
    K.set_font(r, 34, True, GREEN)
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = "all passing"
    K.set_font(r2, 15, True, GREY)

    box = rect(s, Inches(7.2), Inches(3.7), Inches(5.35), Inches(2.2),
               RGBColor(0xFF, 0xF6, 0xEC), ORANGE)
    tf = box.text_frame
    tf.vertical_anchor = K.MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.22)
    tf.margin_top = Inches(0.16)
    rich_para(tf, [("The sharpest single check", {"bold": True, "color": ORANGE})],
              16, first=True, space_after=8)
    rich_para(tf, [("-m 1", {"mono": True, "bold": True, "color": NAVY}),
                   (" and ", {"color": GREY}),
                   ("-m 100", {"mono": True, "bold": True, "color": NAVY}),
                   (" must produce byte-identical output.", {"color": GREY})], 15, space_after=8)
    para(tf, "It catches errors only external sorting can produce — the dropped-line bug "
             "never appears if the file fits in a single run.",
         13, False, GREY, space_after=0, line=1.35)
    footer(s, 15)
    K.notes(s, outline, 15)

    # ---------- 16 Limitations ----------
    s = K.content_slide(prs, "Limitations and Possible Improvements",
                        "Evaluated, then traded away for correctness")
    rows = [["Item", "Current state", "If I had more time"],
            ["Parallelism", "single-threaded; runs cannot merge in parallel",
             "threads plus locking"],
            ["Input source", "files only, no stdin", "accept stdin for pipelines"],
            ["Temp cleanup", "cleaned on normal exit; leaks on SIGKILL/crash",
             "atexit() or a signal handler (SIGKILL is uncatchable)"],
            ["Over-long lines", "silently truncated at 4,095 bytes", "emit a warning"]]
    table(s, Inches(0.82), Inches(2.0), Inches(11.73), rows, [2.0, 4.9, 4.0], 13.5,
          row_h=Inches(0.52))
    tf = textbox(s, Inches(0.82), Inches(5.35), Inches(11.73), Inches(0.9))
    rich_para(tf, [("These are not oversights — they are the result of putting ", {"color": GREY}),
                   ("correctness before speed", {"bold": True, "color": NAVY}),
                   (" within the available time.", {"color": GREY})],
              16, first=True, space_after=0)
    footer(s, 16)
    K.notes(s, outline, 16)

    # ---------- 17 Conclusion ----------
    s = K.base_slide(prs)
    rect(s, 0, 0, K.SW, K.SH, NAVY, shape=MSO_SHAPE.RECTANGLE)
    rect(s, 0, Inches(2.15), K.SW, Pt(3), ORANGE, shape=MSO_SHAPE.RECTANGLE)
    tf = textbox(s, Inches(0.95), Inches(1.35), Inches(11.4), Inches(0.7))
    para(tf, "Conclusion", 40, True, WHITE, first=True, space_after=0)

    trio = [("Holds", "-m means exactly what it says",
             "proven by measured peak RSS"),
            ("Correct", "both phases share one comparator",
             "the budget even counts pointers"),
            ("Verifiable", "288 differential cases + sanitizers",
             "caught bugs I never anticipated")]
    x = Inches(0.95)
    for i, (word, l1, l2) in enumerate(trio):
        cx = x + i * Inches(3.85)
        c = rect(s, cx, Inches(2.85), Inches(3.5), Inches(2.5),
                 RGBColor(0x24, 0x3D, 0x60), RGBColor(0x3C, 0x59, 0x82))
        tf = c.text_frame
        tf.vertical_anchor = K.MSO_ANCHOR.TOP
        tf.margin_top = Inches(0.28)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = word
        K.set_font(r, 28, True, ORANGE)
        for line in (l1, l2):
            pp = tf.add_paragraph()
            pp.alignment = PP_ALIGN.CENTER
            pp.space_before = Pt(10)
            rr = pp.add_run(); rr.text = line
            K.set_font(rr, 12.5, False, RGBColor(0xC8, 0xD6, 0xE5))

    tf = textbox(s, Inches(0.95), Inches(5.85), Inches(11.4), Inches(0.8))
    para(tf, "Thank you — questions welcome", 20, True, WHITE, first=True, space_after=0)
    footer(s, 17)
    K.notes(s, outline, 17)

    # ---------- A1 ----------
    s = K.content_slide(prs, "Appendix A1: Constants and Option Cross-Reference",
                        "for reference")
    rows = [["Constant", "Value", "Meaning"],
            ["MAX_LINE_LENGTH", "4096", "maximum line length (from spec)"],
            ["DEFAULT_MEM_MB", "100", "default for -m"],
            ["MAX_MERGE_FANIN", "512", "max merge fan-in (FOPEN_MAX bound)"],
            ["ARENA_BLOCK_SIZE", "64 KB", "arena block size"],
            ["IO_BUF_SIZE", "64 KB", "read / write buffer"],
            ["RUN_READER_BUF_SIZE", "8 KB", "per-run read buffer"],
            ["MIN_CHUNK_BUDGET", "4096 + 256×8", "guarantees one line + 256 ptrs"]]
    table(s, Inches(0.82), Inches(1.9), Inches(6.6), rows, [2.75, 1.15, 3.9], 12,
          row_h=Inches(0.36))
    rows2 = [["Option", "Function", "esort.c line"],
             ["-c", "strcasecmp()", "L161"],
             ["-n", "atoi()", "L151"],
             ["-l", "strlen()", "L139"],
             ["-r", "negate result", "L167"],
             ["-m", "atoi() → bytes", "L960"],
             ["-o", "fopen() / is_same_file()", "L1160 / L882"]]
    table(s, Inches(7.7), Inches(1.9), Inches(4.85), rows2, [0.9, 2.8, 1.9], 12,
          row_h=Inches(0.36))
    tf = textbox(s, Inches(0.82), Inches(5.35), Inches(11.7), Inches(0.8))
    para(tf, "Build: gcc -Wall -Wextra -O2 -std=c11 -o esort esort.c    |    "
             "also builds under C99; zero warnings", 13, False, GREY, first=True, space_after=4)
    para(tf, "Usage: esort [-c] [-m <MB>] [-r] [-n] [-l] [-o <file>] FileName",
         13, False, BLUE, mono=True, space_after=0)
    footer(s, 18, 19)
    K.notes(s, outline, 101)

    # ---------- A2 ----------
    s = K.content_slide(prs, "Appendix A2: Q&A Preparation",
                        "likely questions and how to answer them")
    rows = [["Likely question", "Answer"],
            ["Why not getline()?", "A hand-written lr_next() strips \\r\\n while reading, "
             "truncates over-long lines, and avoids per-line allocation; memchr scanning "
             "beats reading char by char."],
            ["Why is k 512?", "A conservative value for FOPEN_MAX / ulimit -n, and the "
             "balance point between memory and I/O count. Tunable via MAX_MERGE_FANIN."],
            ["Is memory really O(1)?", "It depends on -m: with -m fixed, memory is "
             "independent of file size — but temp file DISK space is O(N)."],
            ["Must the sort be stable?", "No. qsort() does not guarantee stability; the "
             "test data uses unique values to avoid ambiguity."],
            ["How is the input protected?", "stat() compares st_dev / st_ino; if identical, "
             "write to a temporary output first and overwrite afterwards."],
            ["Does multi-pass merging blow up disk usage?", "Each round unlinks its source "
             "runs immediately, so peak temp space stays O(N)."],
            ["What if -m cannot hold one line?", "MIN_CHUNK_BUDGET guarantees one line plus "
             "256 pointers; otherwise a clear error and a non-zero exit status."]]
    table(s, Inches(0.82), Inches(1.9), Inches(11.73), rows, [3.3, 8.4], 11.5,
          row_h=Inches(0.58))
    footer(s, 19, 19)
    K.notes(s, outline, 102)

    prs.save(OUTPUT)
    print(f"saved: {OUTPUT}")
    print(f"slides: {len(prs.slides.__iter__.__self__._sldIdLst)}")


if __name__ == "__main__":
    build()