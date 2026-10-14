#!/usr/bin/env python3
"""
gen_pptx.py — 由 PPT_大綱與講稿.md + esort.c 產生 esort_報告.pptx

設計原則：
  1. 講稿（speaker notes）直接從 PPT_大綱與講稿.md 解析，避免兩份檔案不同步。
  2. 投影片上的程式碼片段直接從 esort.c 依行號抽取，確保與實作一致。
  3. 16:9 版面、統一配色與字型（含 East Asian 字型設定，避免中文字型跑版）。
"""

import re
import sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

HERE = "/home/jc/homework/DataEngineering/Project01"
SRC = f"{HERE}/esort.c"
OUTLINE = f"{HERE}/PPT_大綱與講稿.md"
OUTPUT = f"{HERE}/esort_報告.pptx"

# ---------------------------------------------------------------- 配色
NAVY = RGBColor(0x1B, 0x2F, 0x4B)     # 主色：深藍
BLUE = RGBColor(0x2E, 0x6D, 0xA4)     # 次色：藍
ORANGE = RGBColor(0xE0, 0x6C, 0x2E)   # 強調：橘
GREEN = RGBColor(0x2E, 0x8B, 0x57)    # 正向：綠
RED = RGBColor(0xC0, 0x39, 0x2B)      # 警示：紅
GREY = RGBColor(0x5A, 0x5A, 0x5A)
LGREY = RGBColor(0xD8, 0xDC, 0xE0)
CODEBG = RGBColor(0xF4, 0xF5, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

CJK_FONT = "Microsoft JhengHei"       # 微軟正黑體
LATIN_FONT = "Segoe UI"
MONO_FONT = "Consolas"

SW, SH = Inches(13.333), Inches(7.5)


# ---------------------------------------------------------------- 工具
def set_font(run, size=18, bold=False, color=GREY, mono=False, italic=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    name = MONO_FONT if mono else LATIN_FONT
    f.name = name
    # East Asian 字型：python-pptx 不支援，需直接改 XML
    rPr = run._r.get_or_add_rPr()
    for tag, typeface in (("a:latin", name), ("a:ea", CJK_FONT if not mono else MONO_FONT),
                          ("a:cs", name)):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", typeface)


def textbox(slide, x, y, w, h, wrap=True):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    return tf


def para(tf, text, size=18, bold=False, color=GREY, mono=False, space_before=0,
         space_after=6, first=False, bullet=None, indent=0, line=1.35):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    p.line_spacing = line
    if indent:
        p.left_indent = Inches(indent)
    if bullet:
        text = f"{bullet}  {text}"
    run = p.add_run()
    run.text = text
    set_font(run, size, bold, color, mono)
    return p


def rich_para(tf, parts, size=18, space_before=0, space_after=6, first=False,
              indent=0, line=1.35, bullet=None):
    """parts = [(text, {bold/color/mono/size}), ...]"""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    p.line_spacing = line
    if indent:
        p.left_indent = Inches(indent)
    if bullet:
        r = p.add_run()
        r.text = f"{bullet}  "
        set_font(r, size, True, BLUE)
    for text, opt in parts:
        r = p.add_run()
        r.text = text
        set_font(r, opt.get("size", size), opt.get("bold", False),
                 opt.get("color", GREY), opt.get("mono", False))
    return p


def rect(slide, x, y, w, h, fill, line_color=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
         adj=None):
    sh = slide.shapes.add_shape(shape, x, y, w, h)
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line_color is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line_color
        sh.line.width = Pt(1.25)
    sh.shadow.inherit = False
    if adj is not None and sh.adjustments:
        sh.adjustments[0] = adj
    tf = sh.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.14)
    tf.margin_right = Inches(0.14)
    tf.margin_top = Inches(0.08)
    tf.margin_bottom = Inches(0.08)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return sh


def excerpt(*ranges):
    """依「(起, 訖)」區段抽取原始碼，非連續區段之間插入省略標記 ⋮。
    所有顯示的程式碼都逐字取自 esort.c，只有 ⋮ 是插入的。"""
    out = []
    for i, (a, b) in enumerate(ranges):
        if i:
            out.append("        ⋮")
        out.extend(SRC_LINES[a - 1:b])
    return out


def condense(lines):
    """投影片上的程式碼只留重點：去掉註解列與空行，讓片段放得進版面。"""
    out = []
    for l in lines:
        s = l.strip()
        if not s:
            continue
        if s.startswith(("/*", "*", "//")):
            continue
        out.append(l)
    return out


def code_block(slide, x, y, w, lines, caption=None, size=10.5, max_h=None):
    """程式碼區塊：淺灰底 + 等寬字體，高度依行數自動計算。"""
    lines = condense(lines)
    line_h = size * 1.18 / 72.0          # 單行高度（inch）
    h = Inches(len(lines) * line_h + 0.26)
    if max_h and h > Inches(max_h):      # 塞不下就自動縮小字級
        line_h = (max_h - 0.26) / len(lines)
        size = line_h * 72.0 / 1.18
        h = Inches(len(lines) * line_h + 0.26)
    bg = rect(slide, x, y, w, h, CODEBG, LGREY, MSO_SHAPE.RECTANGLE)
    tf = bg.text_frame
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.14)
    tf.margin_top = Inches(0.08)
    tf.margin_bottom = Inches(0.04)
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(0)
        p.space_before = Pt(0)
        p.line_spacing = 1.0
        r = p.add_run()
        r.text = ln
        set_font(r, size, False, RGBColor(0x24, 0x29, 0x2E), mono=True)
    if caption:
        tf2 = textbox(slide, x, y - Inches(0.27), w, Inches(0.25))
        para(tf2, caption, 11.5, True, BLUE, first=True, space_after=0)
    return y + h


def table(slide, x, y, w, rows, col_widths=None, size=13, header=True,
          row_h=Inches(0.34)):
    nrows, ncols = len(rows), len(rows[0])
    gf = slide.shapes.add_table(nrows, ncols, x, y, w, row_h * nrows)
    tbl = gf.table
    if col_widths:
        total = sum(col_widths)
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = Emu(int(w * cw / total))
    for ri, row in enumerate(rows):
        tbl.rows[ri].height = row_h
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = ""
            cell.margin_left = Inches(0.1)
            cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.02)
            cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = cell.text_frame.paragraphs[0]
            r = p.add_run()
            r.text = str(val)
            is_head = header and ri == 0
            set_font(r, size, is_head or ci == 0,
                     WHITE if is_head else GREY)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if is_head else (
                WHITE if ri % 2 else RGBColor(0xF2, 0xF5, 0xF8))
    return tbl


# ---------------------------------------------------------------- 解析大綱
def parse_outline():
    """從 PPT_大綱與講稿.md 取出每頁的標題、講稿、關鍵訊息、時間"""
    slides = {}
    txt = open(OUTLINE, encoding="utf-8").read()
    blocks = re.split(r"\n## ", txt)[1:]
    for b in blocks:
        head = b.split("\n")[0]
        m = re.match(r"(\d+)\.\s*(.+)", head)
        key = int(m.group(1)) if m else None
        title = m.group(2) if m else head.replace("附錄 ", "")
        if key is None:                      # 附錄 A1 / A2
            key = 101 if "A1" in head else 102
        notes, tm = [], 30
        in_notes = False
        for line in b.split("\n")[1:]:
            t = re.search(r"\*\*時間\*\*：(\d+) 秒", line)
            if t:
                tm = int(t.group(1))
            if line.startswith(">"):
                in_notes = True
                notes.append(line[1:].strip())
            elif in_notes and not line.startswith(">") and line.strip():
                if "這頁要讓聽眾記住" in line:
                    in_notes = False
                else:
                    in_notes = False
        keymsg = ""
        km = re.search(r"\*\*這頁要讓聽眾記住\*\*：(.+)", b)
        if km:
            keymsg = km.group(1).strip()
        slides[key] = dict(title=title, notes="\n".join(notes), time=tm, keymsg=keymsg)
    return slides


SRC_LINES = open(SRC, encoding="utf-8").read().split("\n")


def src(start, end):
    """從 esort.c 依 1-based 行號抽取程式碼片段"""
    return [l.rstrip() for l in SRC_LINES[start - 1:end]]


# ---------------------------------------------------------------- 版面
def base_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])   # 空白版面


def content_slide(prs, title, kicker=None):
    s = base_slide(prs)
    # 標題左側色條
    rect(s, Inches(0.55), Inches(0.52), Inches(0.09), Inches(0.52), ORANGE,
         shape=MSO_SHAPE.RECTANGLE)
    tf = textbox(s, Inches(0.82), Inches(0.46), Inches(11.6), Inches(0.62))
    para(tf, title, 30, True, NAVY, first=True, space_after=0)
    if kicker:
        tf2 = textbox(s, Inches(0.84), Inches(1.10), Inches(11.6), Inches(0.3))
        para(tf2, kicker, 14, False, BLUE, first=True, space_after=0)
    # 底線
    ln = rect(s, Inches(0.55), Inches(1.42), Inches(12.23), Pt(1.2), LGREY,
              shape=MSO_SHAPE.RECTANGLE)
    return s


def footer(slide, page, total=19):
    tf = textbox(slide, Inches(0.55), Inches(7.05), Inches(8), Inches(0.3))
    para(tf, "esort — 外部排序工具設計與實作", 10, False, RGBColor(0x9A, 0xA3, 0xAD),
         first=True, space_after=0)
    tf2 = textbox(slide, Inches(11.9), Inches(7.05), Inches(0.9), Inches(0.3))
    para(tf2, f"{page} / {total}", 10, False, RGBColor(0x9A, 0xA3, 0xAD),
         first=True, space_after=0, )
    tf2.paragraphs[0].alignment = PP_ALIGN.RIGHT


def notes(slide, outline, key):
    d = outline.get(key)
    if not d:
        return
    tf = slide.notes_slide.notes_text_frame
    tf.text = f"【建議時間】{d['time']} 秒\n"
    tf.add_paragraph().text = d["notes"]
    if d["keymsg"]:
        p = tf.add_paragraph()
        p.text = f"\n【這頁要讓聽眾記住】{d['keymsg']}"


# ---------------------------------------------------------------- 主程式
def build():
    outline = parse_outline()
    prs = Presentation()
    prs.slide_width, prs.slide_height = SW, SH

    # ---------- 1 封面 ----------
    s = base_slide(prs)
    rect(s, 0, 0, SW, Inches(2.55), NAVY, shape=MSO_SHAPE.RECTANGLE)
    rect(s, 0, Inches(2.55), SW, Pt(4), ORANGE, shape=MSO_SHAPE.RECTANGLE)
    tf = textbox(s, Inches(0.9), Inches(0.72), Inches(11.5), Inches(0.7))
    para(tf, "esort", 54, True, WHITE, first=True, space_after=0)
    tf = textbox(s, Inches(0.95), Inches(1.62), Inches(11.5), Inches(0.6))
    para(tf, "外部合併排序（External Merge Sort）工具 — 設計與實作", 22, False,
         RGBColor(0xC8, 0xD6, 0xE5), first=True, space_after=0)

    tf = textbox(s, Inches(0.95), Inches(3.15), Inches(11.5), Inches(1.9))
    rich_para(tf, [("受限於 ", {"color": GREY}),
                   ("-m", {"mono": True, "bold": True, "color": BLUE}),
                   (" 記憶體上限的排序工具", {"color": GREY, "bold": True})],
              22, first=True, space_after=10)
    para(tf, "1413 行 C 語言實作　·　零編譯警告　·　288 組自動化差異測試全數通過",
         16, False, GREY, space_after=16)
    para(tf, "關鍵設計：統一 Comparator　·　Arena 記憶體池　·　Min-Heap 多路合併　·　多輪合併退避",
         14, False, BLUE, space_after=0)

    tf = textbox(s, Inches(0.95), Inches(5.85), Inches(11.5), Inches(1.0))
    para(tf, "課程：資料工程　　報告人：＿＿＿＿　　日期：＿＿＿＿", 14, False,
         RGBColor(0x8A, 0x93, 0x9D), first=True, space_after=6)
    para(tf, "工具：gcc -Wall -Wextra -O2 -std=c11 / GNU Make", 12, False,
         RGBColor(0xA8, 0xB0, 0xB8), space_after=0)
    notes(s, outline, 1)

    # ---------- 2 動機 ----------
    s = content_slide(prs, "動機：為什麼需要外部排序", "排序演算法的前提是「整份資料放得進記憶體」")
    tf = textbox(s, Inches(0.82), Inches(1.72), Inches(11.7), Inches(2.3))
    rich_para(tf, [("qsort() 這類內部排序的前提：", {"bold": True, "color": NAVY}),
                   ("整份資料必須放得進記憶體。", {})], 18, first=True,
              space_after=10, bullet="▪")
    rich_para(tf, [("實務上處理的是幾十 GB 的日誌、交易檔 —— 這個前提", {}),
                   ("根本不成立", {"bold": True, "color": RED}),
                   ("。", {})], 18, space_after=10, bullet="▪")
    rich_para(tf, [("外部排序的解法：", {"bold": True, "color": NAVY}),
                   ("記憶體排序 → 暫存檔 → 合併", {"bold": True, "color": BLUE}),
                   ("，把無法一次載入的資料分段處理。", {})], 18, space_after=14,
              bullet="▪")

    box = rect(s, Inches(0.82), Inches(4.25), Inches(11.7), Inches(1.55),
               RGBColor(0xF2, 0xF6, 0xFA), LGREY)
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.25)
    tf.margin_top = Inches(0.18)
    rich_para(tf, [("複雜度拆解　", {"bold": True, "color": NAVY, "size": 16}),
                   ("（記憶體可放 M 筆、總共 N 筆、一次合併 k 個 run）", {"color": GREY, "size": 13})],
              16, first=True, space_after=8)
    rich_para(tf, [("內部排序　", {"color": GREY}), ("O(N/M × M log M)", {"mono": True, "bold": True, "color": BLUE}),
                   ("　　　I/O 成本　", {"color": GREY}), ("O(N log_k N)", {"mono": True, "bold": True, "color": ORANGE})],
              16, space_after=8)
    para(tf, "關鍵在於 log 的底數 k —— k 越大，讀寫暫存檔的次數越少。",
         14, False, GREY, space_after=0)
    footer(s, 2)
    notes(s, outline, 2)

    # ---------- 3 目標與限制 ----------
    s = content_slide(prs, "目標與限制", "五條硬性限制，直接決定了後面每一個設計決策")
    tf = textbox(s, Inches(0.82), Inches(1.72), Inches(6.2), Inches(0.4))
    para(tf, "功能：六個命令列選項", 18, True, NAVY, first=True, space_after=0)
    rows = [["選項", "功能", "對應函式"],
            ["-c", "不分大小寫", "strcasecmp()"],
            ["-m <size>", "記憶體上限（MB）", "atoi()"],
            ["-r", "反向（遞減）", "結果 × -1"],
            ["-n", "數值排序", "atoi()"],
            ["-l", "長度優先", "strlen()"],
            ["-o <file>", "輸出檔（預設 stdout）", "fopen()"]]
    table(s, Inches(0.82), Inches(2.2), Inches(6.2), rows, [1.3, 3.0, 2.0], 13)

    tf = textbox(s, Inches(7.45), Inches(1.72), Inches(5.2), Inches(0.4))
    para(tf, "硬性限制（對應後續巧思）", 18, True, NAVY, first=True, space_after=0)
    items = [("1", "記憶體嚴格不超過 -m", "不是「大概」"),
             ("2", "必須支援兩階段外部排序", "記憶體 + 暫存檔 + 合併"),
             ("3", "run 數可能超過開檔上限", "需多輪合併"),
             ("4", "-o 不得毀損輸入檔", "可能同檔"),
             ("5", "結束前釋放所有資源", "檔案、記憶體、暫存檔")]
    y = 2.22
    for num, title, sub in items:
        c = rect(s, Inches(7.45), Inches(y), Inches(0.34), Inches(0.34), BLUE)
        ctf = c.text_frame
        p = ctf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = num
        set_font(r, 14, True, WHITE)
        tf2 = textbox(s, Inches(7.92), Inches(y - 0.02), Inches(4.7), Inches(0.75))
        para(tf2, title, 15, True, GREY, first=True, space_after=1)
        para(tf2, sub, 12, False, RGBColor(0x93, 0x9C, 0xA6), space_after=0)
        y += 0.86
    footer(s, 3)
    notes(s, outline, 3)

    # ---------- 4 系統架構圖 ----------
    s = content_slide(prs, "系統架構：兩階段外部合併排序", "整體流程一頁看完")

    def stage(x, w, title, sub, color):
        bx = rect(s, x, Inches(1.85), w, Inches(2.5), WHITE, color)
        rect(s, x, Inches(1.85), w, Inches(0.42), color, shape=MSO_SHAPE.RECTANGLE)
        t = textbox(s, x + Inches(0.15), Inches(1.92), w - Inches(0.3), Inches(0.3))
        para(t, title, 15, True, WHITE, first=True, space_after=0)
        return bx

    # 輸入
    box = rect(s, Inches(0.82), Inches(2.7), Inches(1.55), Inches(0.85), NAVY)
    p = box.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "輸入檔"
    set_font(r, 14, True, WHITE)

    stage(Inches(2.62), Inches(3.9), "階段一　Run Generation", "", BLUE)
    tf = textbox(s, Inches(2.85), Inches(2.45), Inches(3.5), Inches(1.8))
    para(tf, "① 記憶體池讀入（嚴格控預算）", 14, True, GREY, first=True, space_after=8, bullet="▪")
    para(tf, "② qsort() 內部排序", 14, True, GREY, space_after=8, bullet="▪")
    para(tf, "③ 輸出成 run 暫存檔", 14, True, GREY, space_after=8, bullet="▪")
    para(tf, "④ 重複直到讀完（K 個 run）", 14, True, GREY, space_after=0, bullet="▪")

    stage(Inches(6.82), Inches(3.9), "階段二　K-way Merge", "", ORANGE)
    tf = textbox(s, Inches(7.05), Inches(2.45), Inches(3.5), Inches(1.8))
    para(tf, "① 開啟所有 run，各讀第一行", 14, True, GREY, first=True, space_after=8, bullet="▪")
    para(tf, "② 放入 Min-Heap", 14, True, GREY, space_after=8, bullet="▪")
    para(tf, "③ 取堆頂輸出，補同一 run 下一行", 14, True, GREY, space_after=8, bullet="▪")
    para(tf, "④ run > k 時先多輪合併", 14, True, GREY, space_after=0, bullet="▪")

    box = rect(s, Inches(11.0), Inches(2.7), Inches(1.55), Inches(0.85), NAVY)
    p = box.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "輸出檔"
    set_font(r, 14, True, WHITE)

    for ax in (Inches(2.37), Inches(6.52), Inches(10.72)):
        ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, ax, Inches(2.95), Inches(0.25), Inches(0.34))
        ar.fill.solid(); ar.fill.fore_color.rgb = LGREY
        ar.line.fill.background(); ar.shadow.inherit = False

    # 記憶體預算
    box = rect(s, Inches(0.82), Inches(4.68), Inches(11.73), Inches(1.72),
               RGBColor(0xF7, 0xF9, 0xFB), LGREY)
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.22)
    tf.margin_top = Inches(0.14)
    rich_para(tf, [("記憶體預算切分　", {"bold": True, "color": NAVY, "size": 15}),
                   ("總預算 = -m MB，先扣除合併階段的必要預留，剩下的才給階段一",
                    {"color": GREY, "size": 13})], 15, first=True, space_after=10)
    bar = rect(s, Inches(1.05), Inches(5.42), Inches(6.9), Inches(0.5), WHITE, LGREY,
               MSO_SHAPE.RECTANGLE)
    r1 = rect(s, Inches(1.05), Inches(5.42), Inches(6.9) * 0.06, Inches(0.5), ORANGE,
              shape=MSO_SHAPE.RECTANGLE)
    t = textbox(s, Inches(1.05), Inches(5.98), Inches(3.4), Inches(0.35))
    para(t, "合併預留（k × 每 run 緩衝）", 12, True, ORANGE, first=True, space_after=0)
    t = textbox(s, Inches(4.35), Inches(5.98), Inches(3.6), Inches(0.35))
    para(t, "階段一記憶體池 chunk_budget", 12, True, BLUE, first=True, space_after=0)
    t = textbox(s, Inches(8.15), Inches(5.40), Inches(4.2), Inches(0.55))
    para(t, "為什麼先扣合併？", 14, True, NAVY, first=True, space_after=2)
    para(t, "否則讀到最後才發現記憶體不夠，只能失敗", 12, False, RED, space_after=0)
    footer(s, 4)
    notes(s, outline, 4)

    # ---------- 5 巧思總覽 ----------
    s = content_slide(prs, "五個設計巧思總覽", "每一個巧思，都是為了回應規格書裡的一條限制")
    cards = [
        ("1", "統一 Comparator", "內部排序與外部合併共用 cmp_strings()", "限制：正確性", BLUE),
        ("2", "Arena 記憶體池", "64KB 區塊鏈結串列，指標永不失效", "限制：記憶體上限", GREEN),
        ("3", "預算切分 + k 推導", "k 隨 -m 動態推導，封頂 512", "限制：記憶體 / 開檔數", GREEN),
        ("4", "Min-Heap 合併", "堆頂取代法，每行只做一次 sift_down", "限制：I/O 效率", ORANGE),
        ("5", "資源安全細節", "同檔輸出、mkstemp、長行截斷", "限制：資料安全", RED),
    ]
    x = Inches(0.82)
    for i, (num, title, desc, tag, color) in enumerate(cards):
        cx = x + i * Inches(2.42)
        c = rect(s, cx, Inches(2.15), Inches(2.22), Inches(3.3), WHITE, color)
        tf = c.text_frame
        tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.margin_top = Inches(0.18)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = num
        set_font(r, 34, True, color)
        tf2 = textbox(s, cx + Inches(0.16), Inches(3.05), Inches(1.9), Inches(1.6))
        para(tf2, title, 15, True, NAVY, first=True, space_after=6, line=1.2)
        para(tf2, desc, 12, False, GREY, space_after=0, line=1.3)
        t = textbox(s, cx + Inches(0.16), Inches(4.72), Inches(1.9), Inches(0.6))
        para(t, tag, 11, True, color, first=True, space_after=0, line=1.2)

    tf = textbox(s, Inches(0.82), Inches(5.75), Inches(11.7), Inches(0.8))
    rich_para(tf, [("全場主線：", {"bold": True, "color": NAVY}),
                   ("資料放不進記憶體時，如何讓「結果正確」與「記憶體守約」同時成立？",
                    {"bold": True, "color": BLUE})], 18, first=True, space_after=6)
    para(tf, "每個設計決策都回答同一句話：如果這樣做會出什麼事，我怎麼證明它不會？",
         14, False, GREY, space_after=0)
    footer(s, 5)
    notes(s, outline, 5)

    # ---------- 6 巧思一 Comparator ----------
    s = content_slide(prs, "巧思一：統一的 Comparator", "比較邏輯只寫一次，兩階段不可能不一致")
    tf = textbox(s, Inches(0.82), Inches(1.68), Inches(5.6), Inches(4.6))
    rich_para(tf, [("最常見的錯誤：", {"bold": True, "color": RED}),
                   ("內部排序與外部合併各寫一份比較函式。", {})], 16, first=True,
              space_after=8, bullet="✗")
    para(tf, "結果「內部用字典序、合併用數值序」，合併結果必然錯誤；"
             "且因資料量大，症狀只是「看起來大致有排」，極難察覺。", 14, False, GREY,
         space_after=16, indent=0.35)
    rich_para(tf, [("解法：", {"bold": True, "color": GREEN}),
                   ("兩邊共用同一個 cmp_strings()，只有最外層介面不同。", {})],
              16, space_after=8, bullet="✓")
    para(tf, "qsort() 傳 char** → 多解一層參考\nMin-Heap 傳 HeapItem → 取其中的指標",
         13, False, GREY, mono=True, space_after=16, indent=0.35, line=1.5)
    rich_para(tf, [("判斷順序　", {"bold": True, "color": NAVY}),
                   ("-l 長度 → -n 數值 → 字典序（-c）→ -r 反轉", {"mono": True, "color": BLUE})],
              14, space_after=8)
    rich_para(tf, [("-n 用 < 和 > 比較而非相減：", {"color": GREY}),
                   ("atoi() 回傳 int，兩個大數相減會溢位。", {"color": RED})],
              14, space_after=0)

    code_block(s, Inches(6.75), Inches(1.95), Inches(5.8),
               excerpt((133, 135), (138, 145), (149, 159), (166, 170)),
               "esort.c : cmp_strings()（L133）", 9.5, max_h=4.55)
    footer(s, 6)
    notes(s, outline, 6)

    # ---------- 7 巧思二 Arena ----------
    s = content_slide(prs, "巧思二：Arena 記憶體池", "固定區塊鏈結串列 —— 指標不失效、峰值不翻倍")
    tf = textbox(s, Inches(0.82), Inches(1.68), Inches(5.45), Inches(2.6))
    rich_para(tf, [("問題：", {"bold": True, "color": RED}),
                   ("指標陣列要長大只能 realloc()，可能把整塊搬到新位置。", {})],
              16, first=True, space_after=8, bullet="▪")
    para(tf, "① 所有指標立刻失效\n② 搬移瞬間新舊兩份同時存在，峰值記憶體直接翻倍",
         13, False, GREY, space_after=16, indent=0.35, line=1.5)
    rich_para(tf, [("解法：", {"bold": True, "color": GREEN}),
                   ("固定 64KB 區塊用鏈結串列串起來，永不搬移。", {})],
              16, space_after=8, bullet="▪")
    para(tf, "每個字串的指標從寫入到排序完成都不會失效；峰值完全可控，因為區塊大小是自己定的。",
         13, False, GREY, space_after=0, indent=0.35, line=1.4)

    # 區塊示意
    bx = rect(s, Inches(0.95), Inches(4.62), Inches(5.2), Inches(1.5), RGBColor(0xF7, 0xF9, 0xFB), LGREY)
    tf = bx.text_frame
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_top = Inches(0.1)
    para(tf, "ArenaBlock 鏈結串列（每塊 64KB，永不搬移）", 12, True, NAVY, first=True, space_after=6)
    bx2 = rect(s, Inches(1.15), Inches(5.22), Inches(1.25), Inches(0.55), BLUE, shape=MSO_SHAPE.RECTANGLE)
    bx3 = rect(s, Inches(2.55), Inches(5.22), Inches(1.25), Inches(0.55), BLUE, shape=MSO_SHAPE.RECTANGLE)
    bx4 = rect(s, Inches(3.95), Inches(5.22), Inches(1.95), Inches(0.55), LGREY, shape=MSO_SHAPE.RECTANGLE)
    for bx_ in (bx2, bx3, bx4):
        p = bx_.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = "used / size"
        set_font(r, 10, False, WHITE if bx_ is not bx4 else GREY)

    yb = code_block(s, Inches(6.55), Inches(1.95), Inches(6.0),
                    excerpt((450, 450), (459, 473)),
                    "esort.c : CHUNK_USED 與 chunk_alloc()（L450）", 10, max_h=3.3)
    box = rect(s, Inches(6.55), yb + Inches(0.25), Inches(6.0), Inches(0.9),
               RGBColor(0xFF, 0xF6, 0xEC), ORANGE)
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.18)
    rich_para(tf, [("連指標都要算！", {"bold": True, "color": ORANGE}),
                   ("　規格要求動態配置的陣列也算進去；指標容量是 2 的冪次，越長越貴。",
                    {"color": GREY})], 13, first=True, space_after=0, line=1.3)
    footer(s, 7)
    notes(s, outline, 7)

    # ---------- 8 巧思三 預算與 k ----------
    s = content_slide(prs, "巧思三：預算切分與 k 值推導", "k 不寫死 —— 讓 -m 小的使用者不會直接崩潰")
    tf = textbox(s, Inches(0.82), Inches(1.68), Inches(6.4), Inches(2.4))
    rich_para(tf, [("預算：", {"bold": True, "color": NAVY}),
                   ("合併階段每個 run 都必須同時開檔，各配 8KB 讀取緩衝 + 4KB 行緩衝。", {})],
              16, first=True, space_after=8, bullet="▪")
    para(tf, "這些記憶體必須在「階段一結束前」就先保留，否則讀到最後才發現不夠。",
         13, False, GREY, space_after=16, indent=0.35)
    rich_para(tf, [("常見錯誤：k 寫死 512。", {"bold": True, "color": RED}),
                   ("光這一項就要 512 × 12KB ≈ 6MB；使用者只給 -m 1 就直接撐不住。", {})],
              16, space_after=8, bullet="✗")
    rich_para(tf, [("解法：", {"bold": True, "color": GREEN}),
                   ("k 隨預算動態推導，再用 512 封頂。記憶體不足時自動降級為多輪合併。",
                    {})], 16, space_after=0, bullet="✓")

    rows = [["-m", "推導 k", "合併預留", "階段一預算", "run > k ?"],
            ["100", "512", "6.16 MB", "93.84 MB", "否"],
            ["16", "512", "6.16 MB", "9.84 MB", "否"],
            ["8", "328", "3.99 MB", "4.01 MB", "否"],
            ["4", "158", "1.99 MB", "2.01 MB", "否"],
            ["1", "31", "0.49 MB", "0.51 MB", "是 → 多輪合併"]]
    t = table(s, Inches(0.82), Inches(4.62), Inches(6.4), rows,
              [1.0, 1.1, 1.4, 1.5, 2.2], 12, row_h=Inches(0.31))
    cell = t.cell(5, 4)
    cell.text_frame.paragraphs[0].runs[0].font.color.rgb = ORANGE

    code_block(s, Inches(7.45), Inches(1.95), Inches(5.1),
               src(983, 1002), "esort.c : calc_fanin()（L983）", 10.5, max_h=4.4)
    footer(s, 8)
    notes(s, outline, 8)

    # ---------- 9 巧思四 heap ----------
    s = content_slide(prs, "巧思四：Min-Heap 合併與堆頂取代法", "每行只要一趟 sift_down")
    tf = textbox(s, Inches(0.82), Inches(1.68), Inches(5.5), Inches(2.9))
    rich_para(tf, [("標準寫法：", {"bold": True, "color": GREY}),
                   ("取堆頂 → 輸出 → push 回去。", {})], 16, first=True, space_after=8, bullet="▪")
    para(tf, "pop 需要 sift_down，push 需要 sift_up → 每行跑兩趟堆積調整。",
         13, False, GREY, space_after=16, indent=0.35, line=1.4)
    rich_para(tf, [("可利用的性質：", {"bold": True, "color": NAVY}),
                   ("取出的堆頂與補進的元素，一定來自同一個 run。", {})],
              16, space_after=8, bullet="▪")
    para(tf, "所以整個堆只有「堆頂一個位置」改變 —— 直接覆寫堆頂，只做一次 sift_down，語意完全等價。",
         13, False, GREY, space_after=16, indent=0.35, line=1.4)
    rich_para(tf, [("實測：", {"bold": True, "color": GREEN}),
                   ("比較次數 −8～11%，實際快 3～4%。", {"bold": True, "color": GREEN})],
              16, space_after=8, bullet="→")
    para(tf, "誠實說：比我預期的少。因為 push 後的 sift_up 通常第一層就停（新元素多半已大於父節點）。"
             "真正價值在於把最壞情況從兩趟降成一趟，堆越深收益越明顯。",
         13, False, GREY, space_after=0, indent=0.35, line=1.4)

    yb = code_block(s, Inches(6.65), Inches(1.95), Inches(5.9),
                    src(819, 847), "esort.c : 合併主迴圈（L819）", 9.5, max_h=3.9)
    box = rect(s, Inches(6.65), yb + Inches(0.22), Inches(5.9), Inches(0.7),
               RGBColor(0xFF, 0xF6, 0xEC), ORANGE)
    tf = box.text_frame
    tf.margin_left = Inches(0.18)
    rich_para(tf, [("注意：", {"bold": True, "color": ORANGE}),
                   ("run->line 就是堆頂所在的緩衝區，必須先輸出再覆寫。",
                    {"color": GREY})], 12.5, first=True, space_after=0)
    footer(s, 9)
    notes(s, outline, 9)

    # ---------- 10 巧思五 資源安全 ----------
    s = content_slide(prs, "巧思五：資源安全細節", "三個看起來很小、但會靜默毀損結果的地方")
    items = [
        ("A", "-o 指定的輸出檔可能就是輸入檔", RED,
         "直接開檔覆蓋，還沒讀完的資料就已被寫掉。\n解法：stat() 比對路徑字串與 st_dev/st_ino，"
         "確認同檔就先寫暫存檔，全部完成後再覆蓋回去。"),
        ("B", "暫存檔名不能自己亂取", ORANGE,
         "多人共用的 /tmp 有搶名風險，可能被別人讀走或覆蓋。\n解法：用 mkstemp() 讓核心保證唯一性。"),
        ("C", "輸入格式的邊界", BLUE,
         "最後一行沒有換行符、Windows 的 \\r\\n、超過 4096 字元的長行。\n"
         "解法：長行截斷但仍佔一行 —— 重點是行數不能亂掉。"),
    ]
    y = Inches(1.85)
    for tag, title, color, desc in items:
        b = rect(s, Inches(0.82), y, Inches(11.73), Inches(1.45),
                 RGBColor(0xFA, 0xFB, 0xFC), LGREY)
        c = rect(s, Inches(1.05), y + Inches(0.42), Inches(0.6), Inches(0.6), color)
        p = c.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = tag
        set_font(r, 20, True, WHITE)
        tf = textbox(s, Inches(1.95), y + Inches(0.18), Inches(10.4), Inches(1.15))
        para(tf, title, 17, True, NAVY, first=True, space_after=5)
        para(tf, desc, 13, False, GREY, space_after=0, line=1.35)
        y += Inches(1.62)
    footer(s, 10)
    notes(s, outline, 10)

    # ---------- 11 與 sort 對照 ----------
    s = content_slide(prs, "與系統 sort 的關係 / 複雜度對照", "演算法同源，但記憶體模型不同")
    rows = [["面向", "esort（本專題）", "GNU sort"],
            ["演算法", "外部合併排序，兩階段", "同樣是外部合併排序"],
            ["記憶體", "-m 為硬性上限，可精準指定", "盡量使用可用記憶體"],
            ["記憶體不足時", "k 自動縮小 → 多輪合併，行為可預測", "自行決定合併策略"],
            ["輸出", "預設 stdout，可 -o 同檔就地排序", "預設 stdout"],
            ["排序穩定性", "不穩定（qsort 規格本來就不保證）", "不穩定（預設）"]]
    table(s, Inches(0.82), Inches(1.85), Inches(11.73), rows, [2.2, 4.6, 4.2], 14,
          row_h=Inches(0.42))
    box = rect(s, Inches(0.82), Inches(4.55), Inches(11.73), Inches(2.0),
               RGBColor(0xF2, 0xF6, 0xFA), BLUE)
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_top = Inches(0.16)
    tf.margin_left = Inches(0.22)
    rich_para(tf, [("實務發現：記憶體不是越多越快", {"bold": True, "color": NAVY})],
              16, first=True, space_after=8)
    rich_para(tf, [("-m 4 → 0.97 秒　　-m 8 → 1.06 秒　　", {"color": GREY}),
                   ("-m 100 → 1.67 秒", {"bold": True, "color": ORANGE}),
                   ("（75MB、150 萬行）", {"color": GREY})], 15, space_after=6)
    para(tf, "記憶體越多 → 單一批次越大 → qsort 的 cache 命中率變差；且最後輸出階段是循序 I/O，"
             "中間少寫幾次暫存檔省下的時間抵不過。這個工具是 I/O bound，不是 CPU bound。",
         13, False, GREY, space_after=0, line=1.35)
    footer(s, 11)
    notes(s, outline, 11)

    # ---------- 12 效能實測 ----------
    s = content_slide(prs, "效能實測", "75MB ／ 1,500,000 行，數值排序，頁面快取已預熱，取 3 次最佳值")
    rows = [["-m 設定", "峰值 RSS (MB)", "耗時 (s)", "判定"],
            ["4", "5.6", "0.97", "記憶體受控"],
            ["8", "6.2", "1.06", "記憶體受控"],
            ["16", "12.1", "1.16", "記憶體受控"],
            ["100", "98.8", "1.63", "記憶體受控"]]
    t = table(s, Inches(0.82), Inches(1.95), Inches(6.0), rows, [1.6, 2.2, 1.6, 2.0], 14,
              row_h=Inches(0.4))
    for ri in range(1, 5):
        for p in t.cell(ri, 3).text_frame.paragraphs:
            for r in p.runs:
                r.font.color.rgb = GREEN

    tf = textbox(s, Inches(7.3), Inches(1.95), Inches(5.3), Inches(2.6))
    rich_para(tf, [("記憶體真的被 -m 控住了", {"bold": True, "color": NAVY})],
              18, first=True, space_after=10)
    para(tf, "-m 100 → 98.8MB\n-m 16  → 12.1MB\n-m 4   → 5.6MB", 15, False, GREY,
         mono=True, space_after=10, line=1.6)
    para(tf, "多出 1.5～2MB 是程式基底與 libc 開銷，不是緩衝區。", 13, False, GREY, space_after=0)

    box = rect(s, Inches(0.82), Inches(4.85), Inches(11.73), Inches(1.35),
               RGBColor(0xF2, 0xF8, 0xF4), GREEN)
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_top = Inches(0.15)
    tf.margin_left = Inches(0.22)
    rich_para(tf, [("其他驗證指標", {"bold": True, "color": NAVY})], 16, first=True, space_after=8)
    rich_para(tf, [("堆頂取代法：", {"color": GREY}),
                   ("比較次數 −8～11%，實際快 3～4%", {"bold": True, "color": GREEN}),
                   ("　｜　", {"color": LGREY}),
                   ("差異測試：", {"color": GREY}),
                   ("288 組全數通過", {"bold": True, "color": GREEN}),
                   ("　｜　", {"color": LGREY}),
                   ("ASAN / UBSan：", {"color": GREY}),
                   ("無洩漏、無 UB", {"bold": True, "color": GREEN})],
              14, space_after=0)
    footer(s, 12)
    notes(s, outline, 12)

    # ---------- 13/14 除錯案例 ----------
    def bug_slide(page, title, kicker, bugs):
        """卡片高度依內容行數計算，避免文字溢出壓到下一張卡片。"""
        sl = content_slide(prs, title, kicker)
        y = 1.78
        for tag, name, rows_ in bugs:
            # 每列高度 = 行數 × 0.235 + 0.10
            heights = [len(v.split("\n")) * 0.235 + 0.10 for _, v, _ in rows_]
            card_h = 0.62 + sum(heights) + 0.16
            rect(sl, Inches(0.82), Inches(y), Inches(11.73), Inches(card_h),
                 RGBColor(0xFA, 0xFB, 0xFC), LGREY)
            c = rect(sl, Inches(1.02), Inches(y + 0.16), Inches(0.48), Inches(0.48), RED)
            p = c.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = tag
            set_font(r, 15, True, WHITE)
            tf = textbox(sl, Inches(1.70), Inches(y + 0.14), Inches(10.6), Inches(0.42))
            para(tf, name, 16, True, NAVY, first=True, space_after=0)
            yy = y + 0.62
            for (k, v, c_), hh in zip(rows_, heights):
                t1 = textbox(sl, Inches(1.70), Inches(yy), Inches(0.95), Inches(0.4))
                para(t1, k, 12.5, True, c_, first=True, space_after=0)
                t2 = textbox(sl, Inches(2.66), Inches(yy), Inches(9.7), Inches(hh))
                for i, line in enumerate(v.split("\n")):
                    para(t2, line, 12.5, False, GREY, mono=(k == "修法"),
                         first=(i == 0), space_after=2, line=1.25)
                yy += hh
            y += card_h + 0.26
        footer(sl, page)
        return sl

    bug_slide(13, "除錯案例（上）：掉行 與 堆積條件寫反",
              "兩者都是「看起來跑得完、但結果不對」的靜默錯誤",
              [("1", "每多一個 run，就少輸出一行",
                [("症狀", "-m 1 強制多 run 時，輸出行數比輸入少，且恰好「每個 run 少一行」。", RED),
                 ("原因", "chunk_alloc() 回傳 NULL 時直接 break，但那一行已經從輸入檔讀出來、"
                          "只是還沒放進記憶體池 —— 等於被丟掉了。", RED),
                 ("修法", "加 pending 緩衝記住那一行，下一個 chunk 的第一行先補回去。", GREEN)]),
               ("2", "合併結果順序錯誤，但「大致有排」",
                [("診斷", "不確定在階段一或階段二 → 把 9 個 run 暫存檔全部複製出來逐一檢查，\n"
                          "結果每個 run 內部都排序正確 ⇒ 問題一定在合併層。", BLUE),
                 ("原因", "heap_sift_up() 的跳出條件寫成 <= 0，正確應是 >= 0，\n"
                          "導致新元素永遠不會往上浮。", RED),
                 ("修法", "修正比較方向，合併結果即與內部排序一致。", GREEN)])])
    notes(prs.slides[-1], outline, 13)

    bug_slide(14, "除錯案例（下）：工具抓到的問題",
              "這兩個不是「看起來對」發現的，是 sanitizer 報出來的",
              [("3", "記憶體洩漏：功能完全正常，卻在偷偷漏",
                [("症狀", "程式結果正確、記憶體只漏一點點，肉眼與量測都很難察覺。", RED),
                 ("量測", "ASAN 報告 589,824 bytes in 9 objects —— 剛好是 9 個 run × 64KB。", BLUE),
                 ("原因", "每寫一個 run 檔就配置一個 64KB 輸出緩衝區，寫完忘了釋放。", RED),
                 ("修法", "寫完立即 lw_destroy()；並用 ASAN + UBSan 當成每次重構的固定檢查。", GREEN)]),
               ("4", "重構時自己引入的越界（double free）",
                [("原因", "優化堆頂取代法時，讓同一函式同時負責「取代」與「移除」，\n"
                          "同一輪迴圈呼叫兩次 → 堆大小由 0 減成 SIZE_MAX，造成越界。", RED),
                 ("修法", "拆成 heap_set_top() / heap_remove_top() 兩個語意互斥的函式。", GREEN),
                 ("體悟", "測試要跟著重構一起走：改完重跑完整差異測試才發現前一版也壞了，\n"
                          "只看單元測試發現不了。", BLUE)])])
    notes(prs.slides[-1], outline, 14)

    # ---------- 15 測試方法論 ----------
    s = content_slide(prs, "測試方法論", "通過標準不是「跑起來沒 crash」，而是「逐行比對正確」")
    tf = textbox(s, Inches(0.82), Inches(1.75), Inches(6.1), Inches(3.3))
    rich_para(tf, [("參考實作：", {"bold": True, "color": NAVY}),
                   ("用 Python 直接照規格書的比較順序實作 cmp_to_key 排序。", {})],
              16, first=True, space_after=10, bullet="▪")
    para(tf, "再與 C 程式產出的輸出「逐行比對」，任何一列不一致就算失敗。",
         13, False, GREY, space_after=16, indent=0.35)
    rich_para(tf, [("測試矩陣：", {"bold": True, "color": NAVY}),
                   ("16 種旗標組合 × 3 種記憶體上限 × 6 種資料型態", {"bold": True, "color": BLUE})],
              16, space_after=10, bullet="▪")
    para(tf, "資料型態：純字串／純數字／含空白的混合字元／4000 字元長行／空檔／單行檔\n"
             "旗標組合：-c -r -n -l 的 2⁴ 種排列\n記憶體上限：1 MB／2 MB／100 MB",
         13, False, GREY, space_after=0, indent=0.35, line=1.5)

    box = rect(s, Inches(7.2), Inches(1.95), Inches(5.35), Inches(1.5),
               RGBColor(0xF2, 0xF8, 0xF4), GREEN)
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = "288 / 288"
    set_font(r, 34, True, GREEN)
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = "全部通過"
    set_font(r2, 15, True, GREY)

    box = rect(s, Inches(7.2), Inches(3.7), Inches(5.35), Inches(2.2),
               RGBColor(0xFF, 0xF6, 0xEC), ORANGE)
    tf = box.text_frame
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = Inches(0.22)
    tf.margin_top = Inches(0.16)
    rich_para(tf, [("最有效的一條判準", {"bold": True, "color": ORANGE})], 16, first=True, space_after=8)
    rich_para(tf, [("-m 1", {"mono": True, "bold": True, "color": NAVY}),
                   (" 與 ", {"color": GREY}),
                   ("-m 100", {"mono": True, "bold": True, "color": NAVY}),
                   (" 必須產生位元組完全相同的輸出。", {"color": GREY})], 15, space_after=8)
    para(tf, "它能抓到「只有外部排序才會出現」的錯誤 —— 檔案小到只產生一個 run 時完全不會發生。",
         13, False, GREY, space_after=0, line=1.35)
    footer(s, 15)
    notes(s, outline, 15)

    # ---------- 16 檢討 ----------
    s = content_slide(prs, "檢討與可改善處", "開發過程中評估過、但判斷優先做正確性的取捨")
    rows = [["項目", "現況", "若要改進"],
            ["平行化", "單執行緒，run 合併無法並行", "多執行緒 + 鎖，可再加速"],
            ["輸入來源", "只支援檔案，不支援 stdin", "接上 stdin 方便管線操作"],
            ["暫存檔殘留", "正常結束會清理；SIGKILL/崩潰會殘留", "atexit() 或訊號處理（SIGKILL 無法攔截）"],
            ["超長行", "靜默截斷到 4095 字元", "改為輸出警告訊息"]]
    table(s, Inches(0.82), Inches(2.0), Inches(11.73), rows, [2.0, 4.6, 4.2], 14,
          row_h=Inches(0.52))
    tf = textbox(s, Inches(0.82), Inches(5.35), Inches(11.73), Inches(0.9))
    rich_para(tf, [("這些都不是沒想到，而是", {"color": GREY}),
                   ("在時程內把「正確」排在「更快」前面的選擇。", {"bold": True, "color": NAVY})],
              16, first=True, space_after=0)
    footer(s, 16)
    notes(s, outline, 16)

    # ---------- 17 結論 ----------
    s = base_slide(prs)
    rect(s, 0, 0, SW, SH, NAVY, shape=MSO_SHAPE.RECTANGLE)
    rect(s, 0, Inches(2.15), SW, Pt(3), ORANGE, shape=MSO_SHAPE.RECTANGLE)
    tf = textbox(s, Inches(0.95), Inches(1.35), Inches(11.4), Inches(0.7))
    para(tf, "結論", 40, True, WHITE, first=True, space_after=0)

    trio = [("守約", "-m 說多少就是多少", "實測峰值 RSS 證明得了"),
            ("正確", "兩階段共用同一個 Comparator", "預算精確到連指標都算"),
            ("可驗證", "288 組差異測試 + sanitizer", "抓到自己都沒預期到的 bug")]
    x = Inches(0.95)
    for i, (word, l1, l2) in enumerate(trio):
        cx = x + i * Inches(3.85)
        c = rect(s, cx, Inches(2.85), Inches(3.5), Inches(2.5),
                 RGBColor(0x24, 0x3D, 0x60), RGBColor(0x3C, 0x59, 0x82))
        tf = c.text_frame
        tf.vertical_anchor = MSO_ANCHOR.TOP
        tf.margin_top = Inches(0.28)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = word
        set_font(r, 30, True, ORANGE)
        for line in (l1, l2):
            pp = tf.add_paragraph()
            pp.alignment = PP_ALIGN.CENTER
            pp.space_before = Pt(10)
            rr = pp.add_run(); rr.text = line
            set_font(rr, 13, False, RGBColor(0xC8, 0xD6, 0xE5))

    tf = textbox(s, Inches(0.95), Inches(5.85), Inches(11.4), Inches(0.8))
    para(tf, "謝謝聆聽，歡迎提問", 20, True, WHITE, first=True, space_after=0)
    footer(s, 17)
    notes(s, outline, 17)

    # ---------- 附錄 A1 ----------
    s = content_slide(prs, "附錄 A1：常數表與選項對照", "備查用")
    rows = [["常數", "值", "意義"],
            ["MAX_LINE_LENGTH", "4096", "單行最大長度（規格指定）"],
            ["DEFAULT_MEM_MB", "100", "-m 預設值"],
            ["MAX_MERGE_FANIN", "512", "單輪合併最大路數（受 FOPEN_MAX 限制）"],
            ["ARENA_BLOCK_SIZE", "64 KB", "Arena 區塊大小"],
            ["IO_BUF_SIZE", "64 KB", "讀寫緩衝區"],
            ["RUN_READER_BUF_SIZE", "8 KB", "每個 run 的讀取緩衝區"],
            ["MIN_CHUNK_BUDGET", "4096 + 256×8", "保證至少容納一行 + 256 個指標"]]
    table(s, Inches(0.82), Inches(1.9), Inches(6.6), rows, [2.75, 1.15, 3.9], 12,
          row_h=Inches(0.36))
    rows2 = [["選項", "對應函式", "esort.c 行號"],
             ["-c", "strcasecmp()", "L161"],
             ["-n", "atoi()", "L151"],
             ["-l", "strlen()", "L139"],
             ["-r", "結果乘以 -1", "L167"],
             ["-m", "atoi() → Bytes", "L960"],
             ["-o", "fopen() / is_same_file()", "L1160 / L882"]]
    table(s, Inches(7.7), Inches(1.9), Inches(4.85), rows2, [1.0, 2.6, 2.0], 12,
          row_h=Inches(0.36))
    tf = textbox(s, Inches(0.82), Inches(5.35), Inches(11.7), Inches(0.8))
    para(tf, "編譯：gcc -Wall -Wextra -O2 -std=c11 -o esort esort.c　｜　"
             "C99 亦可通過；零警告", 13, False, GREY, first=True, space_after=4)
    para(tf, "使用：esort [-c] [-m <MB>] [-r] [-n] [-l] [-o <file>] FileName",
         13, False, BLUE, mono=True, space_after=0)
    footer(s, 18, 19)
    notes(s, outline, 101)

    # ---------- 附錄 A2 ----------
    s = content_slide(prs, "附錄 A2：Q&A 預備", "可能被追問的問題與回答方向")
    rows = [["可能的提問", "回答方向"],
            ["為什麼不用 getline()？", "自寫 lr_next() 可在讀取時直接去除 \\r\\n、截斷超長行，且避免逐字元配置；memchr 掃描比逐字元讀快"],
            ["k 為什麼是 512？", "FOPEN_MAX 與 ulimit -n 的保守值，同時是記憶體與 I/O 次數的平衡點；可透過 MAX_MERGE_FANIN 調整"],
            ["記憶體真的是 O(1) 嗎？", "取決於 -m：-m 固定時與檔案大小無關；但暫存檔所需的磁碟空間是 O(N)"],
            ["怎麼處理排序穩定性？", "不要求穩定（qsort 規格本來就不保證）；測試資料刻意取唯一值以避免歧義"],
            ["怎麼保證不覆蓋輸入檔？", "stat() 比對 st_dev/st_ino；同檔時先寫暫存輸出，完成後再覆蓋"],
            ["多輪合併的暫存檔會暴增嗎？", "每輪結束立即 unlink 掉上一輪來源 run，峰值暫存空間仍為 O(N)"],
            ["-m 小到連一行都放不下？", "MIN_CHUNK_BUDGET 保證至少容納一行 + 256 指標；否則印明確錯誤並回傳非 0"]]
    table(s, Inches(0.82), Inches(1.9), Inches(11.73), rows, [3.4, 8.3], 12,
          row_h=Inches(0.58))
    footer(s, 19, 19)
    notes(s, outline, 102)

    prs.save(OUTPUT)
    print(f"已輸出：{OUTPUT}")
    print(f"投影片數：{len(prs.slides.__iter__.__self__._sldIdLst)}")


if __name__ == "__main__":
    build()