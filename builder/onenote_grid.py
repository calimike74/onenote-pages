#!/usr/bin/env python3
"""The grid design: every OneNote page on one grid.

onenote_paste.py calls build() for every page. It reads a page .md and lays everything on one grid:
a 64 px spine (numbers, icons) and a 540 px column.

usage: python3 onenote_grid.py PAGE.md [--subtitle ...] [--kind ...] [--footer ...] [--out page.html] [--check]
       --check draws the page in Chrome with OneNote's own cell padding and borders and prints the right
       edge of every block; they must all match.

OneNote for Mac's metrics (measured on real pastes, October 2026): it drops cellpadding and puts
about 3 px inside every cell, draws borders 2 px wide, and keeps <img> widths. So a table of n columns
ends on the shared edge when its column widths add up to 620 - 8n, and each column's width is held by a
6 px strip of that width in its first row (1 px strips are thrown away). Words are wrapped to their
column with Calibri's real letter widths (the font files inside OneNote or Word), so no line can push a table wider.

Colour means the same thing everywhere: amber = yours (every box to write or type x in), pale blue =
read this, cream = do this, navy = a door or a date, orange = a Part number.
"""
import argparse, base64, html as H, io, pathlib, re, subprocess, sys, tempfile
from PIL import Image, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE / "grid-assets"            # icon tiles: make_grid_assets.py
FONT_FOLDERS = [pathlib.Path(f"/Applications/Microsoft {app}.app/Contents/Resources/DFonts") for app in ("OneNote", "Word")]
FONT_FOLDERS.append(pathlib.Path("C:/Windows/Fonts"))
CALIBRI = next((d for d in FONT_FOLDERS if (d / "Calibri.ttf").exists()), FONT_FOLDERS[0])
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SPINE, COL = 64, 540
NAVY, AMBER, ORANGE = "#1F3864", "#F9C74F", "#C24E10"    # white on orange is 4.8:1
DO_BG, LOOK_BG, WRITE_BG, GLANCE_BG = "#FFFAF0", "#EAF0F8", "#FEF7E5", "#F4F1EA"
LINE = "#D3D8E0"
INK, GREY, HINT = "#1A1A1A", "#595959", "#666666"        # HINT: 5.4:1 on the amber write tint
WHITE = "#FFFFFF"
FONT = "font-family:Calibri,sans-serif;font-size:12pt;"
GAP = '<p style="margin:0;">&nbsp;</p>'
SECTION_GAP = 3        # blank lines before every section, so a student can settle on one task at a time
PAD = 3                # OneNote's own cell padding, in px
STRIP_H = 6
TEXT_W = COL - 14      # a little inside the column, so OneNote's own text rendering has room
READER = "Want it read to you? In OneNote, <b>View</b>, then <b>Immersive Reader</b>."
TYPE_X = "&#9744;"


def widths_sum(n):
    """What the column widths of an n-column table must add up to, to end on the grid's edge."""
    return 620 - 8 * n


# ---------------------------------------------------------------- words, measured
FONTS = {}


def font(size, bold):
    key = (size, bold)
    if key not in FONTS:
        try:
            FONTS[key] = ImageFont.truetype(str(CALIBRI / ("Calibrib.ttf" if bold else "Calibri.ttf")), size * 4 / 3)
        except OSError:     # no Calibri on this Mac: a generous guess per letter
            FONTS[key] = None
    return FONTS[key]


def text_w(s, size, bold=False):
    s, f = H.unescape(s), font(size, bold)
    return f.getlength(s) if f else len(s) * size * 0.62


def lines(text, width, size=12, bold=False):
    """Greedy wrap of text that may hold <b> and <a href> to width px, with Calibri's real widths.
    Each line comes back with its own tags opened and closed, ready for its own paragraph."""
    words, b, a, spaced = [], bold, None, True
    for tok in re.findall(r'<b>|</b>|<a href="[^"]+">|</a>|[^<]+', text):
        if tok in ("<b>", "</b>"):
            b = tok == "<b>" or bold
        elif tok.startswith("<a "):
            a = tok
        elif tok == "</a>":
            a = None
        else:
            for i, w in enumerate(tok.split(" ")):
                if w:   # glued: runs straight on from the word before, with no space (a comma after </b>)
                    words.append((w, b, a, i == 0 and bool(words) and not spaced and not tok.startswith(" ")))
            spaced = tok.endswith(" ")
    space = text_w(" ", size)
    fitted = []                            # a word wider than the column (a file name, a web address) is cut
    for w, wb, wa, glued in words:         # into pieces that fit, so it cannot push the table wider
        while text_w(w, size, wb) > width and len(w) > 1:
            k = len(w) - 1
            while k > 1 and text_w(w[:k], size, wb) > width:
                k -= 1
            fitted.append((w[:k], wb, wa, glued)); w, glued = w[k:], False
        fitted.append((w, wb, wa, glued))
    words = fitted
    rows, cur, cur_w = [], [], 0.0
    for w, wb, wa, glued in words:
        ww = text_w(w, size, wb)
        gap = 0 if (glued or not cur) else space
        if cur and not glued and cur_w + gap + ww > width:
            rows.append(cur); cur, cur_w, gap = [], 0.0, 0
        elif cur and glued and cur_w + ww > width and len(cur) > 1:
            # punctuation glued to a link or bold word ("chapter 3</a>:"): take that word down with it
            prev = cur.pop()
            rows.append(cur)
            cur = [(prev[0], prev[1], prev[2], False)]
            cur_w = text_w(prev[0], size, prev[1])
        cur.append((w, wb, wa, glued and bool(cur))); cur_w += gap + ww
    if cur:
        rows.append(cur)
    if len(rows) > 1 and len(rows[-1]) == 1 and len(rows[-2]) > 3:   # no single word left on a line of its own
        w, wb, wa, _ = rows[-2].pop()
        rows[-1].insert(0, (w, wb, wa, False))
    out = []
    for row in rows:
        runs = []                         # consecutive words with the same bold and link
        for w, wb, wa, glued in row:
            if runs and runs[-1][0] == (wb, wa):
                runs[-1][1].append((w, glued))
            else:
                runs.append(((wb, wa), [(w, glued)]))
        s_ = ""
        for (wb, wa), ws in runs:
            body = "".join(("" if (g or j == 0) else " ") + w for j, (w, g) in enumerate(ws))
            if wb and not bold:
                body = f"<b>{body}</b>"
            if wa:
                body = f"{wa}{body}</a>"
            s_ += ("" if (ws[0][1] or not s_) else " ") + body
        out.append(s_)
    return out


def longest_word(text, size, bold=False):
    plain = re.sub(r"<[^>]+>", "", text)
    return max((text_w(w, size, bold or "<b>" in text) for w in plain.split()), default=0)


def one_line(text, size, bold=False):
    return text_w(re.sub(r"<[^>]+>", "", text), size, bold or "<b>" in text)


def inline(s):
    """One line of the page's markdown -> the only tags lines() knows: <b> and <a href>.
    Italics become plain (the BDA style guide: bold, not italics)."""
    s = H.escape(H.unescape(s).strip(" \xa0"), quote=False)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<!\w)_(?!\s)([^_]+?)_(?!\w)", r"\1", s)
    return s.replace("\\", "")


def plain(s):
    return re.sub(r"<[^>]+>", "", s)


# ---------------------------------------------------------------- cells and tables
_URI = {}


def uri(path):
    if path not in _URI:
        _URI[path] = "data:image/png;base64," + base64.b64encode(pathlib.Path(path).read_bytes()).decode()
    return _URI[path]


def p(text, size=12, colour=INK, bold=False):
    b = "font-weight:bold;" if bold else ""
    return f'<p style="margin:0;font-size:{size}pt;color:{colour};{b}">{text}</p>'


def para(text, width=TEXT_W, size=12, colour=INK, bold=False):
    return "".join(p(ln, size, colour, bold) for ln in lines(text, width, size, bold))


def icon(ground, name, alt=""):
    """A 64 x 30 spine tile (or a Part title's 30 x 26 icon with ground 'part'), drawn at 2x."""
    path = ASSETS / f"{ground}-{name}.png"
    w, h = Image.open(path).size
    tag = f'<img src="{uri(path)}" width="{w // 2}" height="{h // 2}" alt="{alt}">'
    return tag if ground == "part" else f'<p style="margin:0;">{tag}</p>'


STRIPS = {}


def strip(w, colour):
    """A 6 px strip in the cell's own colour: it holds the column at w px (OneNote ignores widths)."""
    key = (w, colour)
    if key not in STRIPS:
        buf = io.BytesIO()
        Image.new("RGB", (w, STRIP_H), tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))).save(buf, "PNG", optimize=True)
        STRIPS[key] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return f'<p style="margin:0;"><img src="{STRIPS[key]}" width="{w}" height="{STRIP_H}" alt=""></p>'


def td(bg, inner, centre=False, valign="top", border=True):
    edge = f"border:1px solid {LINE if border else bg};"
    align = "text-align:center;" if centre else ""
    return f'<td style="background-color:{bg};{edge}vertical-align:{valign};{align}">{inner}</td>'


def table(rows, grid=(SPINE, COL)):
    """rows of td() strings. The first row gets a strip of each column's width, so no table can shrink
    to its words; the widths must add up to 620 - 8n."""
    assert sum(grid) == widths_sum(len(grid)), grid
    assert all(len(r) == len(grid) for r in rows), (len(grid), [len(r) for r in rows])
    first = [c[:-5] + strip(w, re.search(r"background-color:(#[0-9A-Fa-f]{6})", c).group(1)) + "</td>"
             for c, w in zip(rows[0], grid)]
    return (f'<table cellpadding="{PAD}" style="border-collapse:collapse;{FONT}">'
            + "".join("<tr>" + "".join(r) + "</tr>" for r in [first] + list(rows[1:])) + "</table>")


# ---------------------------------------------------------------- icons by meaning
KEYWORDS = [  # first match wins; the same key on every page
    ("headphones", r"\blisten|\bhear\b|\bhear it|headphones|\bear\b|\bear check"),
    ("star", r"going further|step further|extension|\bfor more\b"),
    ("search", r"what is wrong|wrong with|mistake|\bspot\b|candidate|lost the mark"),
    ("book", r"\bread\b|reading|chapter"),
    ("play", r"\bfilm\b|video|watch and do"),
    ("pencil", r"\bwrit|essay|explain|describe|your line|own words|\bnotes?\b|fill in"),
    ("eye", r"\blook\b|\bsee\b|show me|figure|picture|drawing|name the|diagram|watch"),
    ("tick", r"\bquiz\b|\btest\b|check|mark yourself|\bmarks?\b|answers"),
    ("open", r"\bopen\b|\blink\b|dashboard|computer|machine|bench|site|explore|at the front"),
    ("bulb", r"\btip\b|\bhint|help|remember"),
    ("doc", r"question|exam|paper"),
]


CUES = [  # a paragraph's icon: from how it starts, or one of these cues anywhere in it
    ("tick", r"\btick\b|\btype x\b"),
    ("clock", r"\b\d+\s+minutes?\b"),
    ("search", r"lost the mark|what is wrong|wrong with"),
    ("headphones", r"^(headphones|listen|play |hear )"),
    ("book", r"^(read |open the chapter)"),
    ("open", r"^(open |go to |click |press |on your own (machine|computer))"),
    ("play", r"^watch "),
    ("pencil", r"^(fill in|write|finish this line|then finish|answer )"),
    ("eye", r"^(look |see )"),
    ("bulb", r"^(the answer is|hint|tip|remember)"),
]


def cue_for(text):
    t = plain(H.unescape(text)).lower().strip()
    return next((name for name, pat in CUES if re.search(pat, t)), None)


def icon_for(text, default=None):
    t = plain(H.unescape(text)).lower()
    for name, pat in KEYWORDS:
        if re.search(pat, t):
            return name
    return default


# ---------------------------------------------------------------- the page's markdown, as blocks
def split_cells(line):
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


IMG_MD = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)|!\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def parse(md):
    """-> blocks: ('h2'|'h3'|'p', text) ('table', header, rows) ('callout', kind, head, body)
    ('img', alt, src) ('ul'|'ol', items) ('setdue', set, due)"""
    out, buf, lines_ = [], [], md.split("\n")

    def flush():
        if buf:
            out.append(("p", " ".join(x.strip() for x in buf)))
            buf.clear()
    i = 0
    while i < len(lines_):
        ln = lines_[i]
        s = ln.strip()
        if not s or re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush(); i += 1; continue
        m = re.match(r"^(#{2,6})\s+(.*)$", s)
        if m:
            flush(); out.append(("h2" if len(m.group(1)) == 2 else "h3", m.group(2).strip())); i += 1; continue
        m = re.match(r"^\*\*Set:\*\*\s*(.*?)\s*·\s*\*\*Due:\*\*\s*(.*)$", s)
        if m:
            flush(); out.append(("setdue", m.group(1), m.group(2))); i += 1; continue
        if s.startswith(">"):
            flush()
            m = re.match(r"^>\s*\[!(\w+)\][-+]?\s*(.*)$", s)
            kind, head = (m.group(1).lower(), m.group(2)) if m else ("quote", "")
            body = [] if m else [s[1:].strip()]
            i += 1
            while i < len(lines_) and lines_[i].strip().startswith(">"):
                body.append(lines_[i].strip()[1:].strip())
                i += 1
            # A blank ">" line is a gap; a line ending in "\" breaks there.
            parts, fresh = [], True
            for b in body:
                if not b:
                    if parts and parts[-1]:
                        parts.append("")
                    fresh = True
                    continue
                text = b.rstrip("\\").rstrip()
                if b.startswith(("- ", "* ")) or fresh:
                    parts.append(text)
                else:
                    parts[-1] += " " + text
                fresh = b.endswith("\\")
            out.append(("callout", kind, head, parts[:-1] if parts and not parts[-1] else parts))
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines_) and lines_[i].strip().startswith("|"):
                r = lines_[i].strip()
                if not re.fullmatch(r"\|?(\s*:?-{2,}:?\s*\|)+\s*:?-*:?\s*\|?", r):
                    rows.append(split_cells(r))
                i += 1
            n = max(len(r) for r in rows)
            rows = [r + [""] * (n - len(r)) for r in rows]
            out.append(("table", rows[0], rows[1:]))
            continue
        if IMG_MD.search(s) and not IMG_MD.sub("", s).strip():
            flush()
            for m in IMG_MD.finditer(s):
                out.append(("img", m.group(1) or "", m.group(2) or m.group(3)))
            i += 1; continue
        m = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", s)
        if m and not ln.startswith(("  ", "\t")):
            flush()
            kind = "ol" if m.group(1)[0].isdigit() else "ul"
            items = []
            while i < len(lines_):
                t = lines_[i]
                mm = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", t.strip())
                if mm and not t.startswith(("  ", "\t")) and (mm.group(1)[0].isdigit()) == (kind == "ol"):
                    items.append(mm.group(2))
                elif t.strip() and t.startswith(("  ", "\t")) and items:
                    items[-1] += " " + re.sub(r"^([-*+]|\d+[.)])\s+", "", t.strip())
                else:
                    break
                i += 1
            out.append((kind, items))
            continue
        m = re.fullmatch(r"\*\*(\d+[a-z]?[.):]\s+[^*]+?)\*\*", s)
        if m and not buf:                        # "**1. Key terms**" on its own line: a Part's heading
            out.append(("h3", m.group(1))); i += 1; continue
        buf.append(s)
        i += 1
    flush()
    return out


# ---------------------------------------------------------------- rows on the two-column grid
def spine_text(text, bg=LOOK_BG, size=14, colour=NAVY):
    return td(bg, p(text, size, colour, True), centre=True)


def text_row(bg, spine_html, text, size=12, colour=INK, bold=False):
    return [td(bg, spine_html, centre=True), td(bg, para(text, TEXT_W, size, colour, bold))]


def q_row(text, spine):
    return [td(LOOK_BG, spine, centre=True), td(LOOK_BG, para(text, TEXT_W, 12, NAVY, True))]


def write_row(label=None, blank=1):
    head = para(label, TEXT_W, 10, NAVY, True) if label else ""
    return [td(WRITE_BG, icon("write", "pencil", "Write here"), centre=True),
            td(WRITE_BG, head + p("Write here", 10, HINT) + GAP * blank)]


def marks_row(n, question):
    word = "mark" if n == "1" else "marks"
    return [td(NAVY, p(n, 18, WHITE, True) + p(word, 9, WHITE, True), centre=True),
            td(LOOK_BG, para(question, TEXT_W, 12, NAVY, True))]


def tick_cell(bg=WRITE_BG):
    return td(bg, p(TYPE_X, 14, NAVY), centre=True, valign="middle")


MARKS = re.compile(r"\*\*([^*]+?)\s*\((\d+)\s*marks?\)\*\*", re.I)
GCSE_MARKS = re.compile(r"^(.*?)\s*\*\*\((\d+)\)\*\*\s*$")


def paragraph_rows(md_text, first_icon=None, bg=DO_BG):
    """One paragraph -> rows. A question with its marks gets the marks chip; Going further, a self-mark
    line and an 'if it will not open' line get their own icon; any other line gets its meaning's icon."""
    m = MARKS.search(md_text)
    if m:
        rows = []
        pre, post = md_text[:m.start()].strip(), md_text[m.end():].strip()
        if pre:
            rows += paragraph_rows(pre, first_icon, bg)
        rows.append(marks_row(m.group(2), inline(m.group(1))))
        if post:
            rows += paragraph_rows(post, None, bg)
        return rows
    m = GCSE_MARKS.match(md_text)
    if m and m.group(1).strip():
        return [marks_row(m.group(2), inline(m.group(1)))]
    text = inline(md_text)
    low = plain(text).lower()
    if re.match(r"(going further|a step further)", low):
        return [text_row(GLANCE_BG, icon("glance", "star", "Going further"), text)]
    if "check your understanding" in low or "mark yourself" in low:
        return [text_row(DO_BG, icon("do", "tick", "Mark it yourself"), text)]
    if re.match(r"if it (will not|won.t|asks|does not)", low):
        return [text_row(DO_BG, icon("navy", "help", "If it will not open"), text)]
    name = first_icon or cue_for(text)
    spine = icon(bg_ground(bg), name) if name else p("&rsaquo;", 16, NAVY, True)
    return [text_row(bg, spine, text)]


def bg_ground(bg):
    return {DO_BG: "do", LOOK_BG: "look", GLANCE_BG: "glance", WRITE_BG: "write", NAVY: "navy", AMBER: "amber"}[bg]


def callout_rows(kind, head, parts):
    head = inline(head)
    paras, helps = [], []
    parts = [y for x in parts for y in re.split(r"(?<=[.!?])\s+(?=If it (?:will not|won't|asks|does not))", x)]
    for x in parts:
        circle = re.match(r"^[-*] \[ \]\s*", x)
        if circle:
            t = "&nbsp;&nbsp;&#9675;&nbsp;" + inline(x[circle.end():])
        else:
            t = inline(x[2:]) if x.startswith(("- ", "* ")) else inline(x)
            t = ("&bull;&nbsp;" + t) if x.startswith(("- ", "* ")) else t
        (helps if re.match(r"if it (will not|won.t|asks|does not)", plain(t).lower()) else paras).append(t)
    body = "".join(para(t, TEXT_W) if t else p("&nbsp;") for t in paras)
    if kind == "quote":
        top = [td(LOOK_BG, icon("look", "quote", "What a candidate wrote"), centre=True),
               td(LOOK_BG, (para(head, TEXT_W, 10, NAVY, True) if head else "")
                  + "".join(para("&ldquo;" + t.strip().strip('"“”') + "&rdquo;", TEXT_W) for t in paras if t))]
    else:
        name = {"tip": "bulb", "warning": "warning", "caution": "warning", "danger": "warning", "success": "tick",
                "question": "help", "example": "eye"}.get(kind) or icon_for(head, "info")
        spine_bg = ORANGE if name == "warning" else NAVY
        cell_bg = GLANCE_BG if kind == "tip" else (DO_BG if name == "warning" else LOOK_BG)
        top = [td(spine_bg, icon("orange" if spine_bg == ORANGE else "navy", name, kind), centre=True),
               td(cell_bg, (para(head, TEXT_W, 13, NAVY, True) if head else "") + body)]
    return [top] + [[td(NAVY, icon("navy", "help", "If it will not open"), centre=True), td(DO_BG, para(t, TEXT_W))]
                    for t in helps]


def image_rows(alt, src, base):
    path = pathlib.Path(H.unescape(src))
    for cand in (base / path, base / "Figures" / path.name, base.parent / "Figures" / path.name):
        if cand.exists():
            path = cand
            break
    else:
        print(f"grid: picture not found, left out: {src}", file=sys.stderr)
        return []
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        flat = Image.new("RGB", im.size, (255, 255, 255))
        flat.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
        im = flat
    w, h = im.size
    if w > 2 * COL:
        im = im.resize((2 * COL, round(h * 2 * COL / w)), Image.LANCZOS); w, h = im.size
    cw = w // 2 if w > 600 else min(w, COL)
    ch = round(h * cw / w)
    buf = io.BytesIO(); im.convert("RGB").save(buf, "PNG", optimize=True)
    alt = alt or "Figure: " + re.sub(r"[-_]+", " ", path.stem)
    tag = f'<img src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}" width="{cw}" height="{ch}" alt="{H.escape(alt)}">'
    return [[td(LOOK_BG, icon("look", "eye", "Look"), centre=True), td(DO_BG, f'<p style="margin:0;">{tag}</p>')]]


def list_rows(kind, items):
    rows = []
    for n, it in enumerate(items, 1):
        box = re.match(r"^(☐|\[ \])\s*", it)
        text = inline(it[box.end():] if box else it)
        if kind == "ol":
            rows.append([td(NAVY, p(str(n), 13, WHITE, True), centre=True), td(DO_BG, para(text, TEXT_W))])
        elif box:
            rows.append([tick_cell(), td(DO_BG, para(text, TEXT_W))])
        else:
            rows.append([td(DO_BG, p("&bull;", 14, NAVY, True), centre=True), td(DO_BG, para(text, TEXT_W))])
    return rows


# ---------------------------------------------------------------- tables
GENERIC = {"", "#", "no.", "question", "the question", "questions", "your answer", "answer", "your answers",
           "write here", "your notes", "part", "step", "item"}


def is_blank(c):
    return not plain(H.unescape(c)).replace("\xa0", "").strip()


def is_box(c):
    return plain(H.unescape(c)).strip() in ("☐", "[ ]", "☐ ☐")


def alloc(cols, kinds, n):
    """Column widths that add up to 620 - 8n: every column gets its longest word, then grows towards one
    line of its longest cell; what is left goes to the text columns."""
    total = widths_sum(n)
    mins, nats = [], []
    for j in range(n):
        if kinds[j] == "spine":
            mins.append(SPINE); nats.append(SPINE); continue
        head, body = cols[j][0], cols[j][1:]
        mn = max([longest_word(head, 10, True)] + [longest_word(c, 11) for c in body]) + 10
        nat = max([one_line(head, 10, True)] + [one_line(c, 11) for c in body]) + 10
        if kinds[j] == "box":
            mn, nat = max(mn, 44), min(max(nat, 60), 110)
        mins.append(max(mn, 40)); nats.append(max(nat, mn, 40))
    w = [float(x) for x in mins]
    if sum(w) > total:
        print(f"grid: a {n}-column table's longest words need {int(sum(w))} px of {total}: they are cut to fit",
              file=sys.stderr)
        scale = total / sum(w)
        w = [x * scale for x in w]
    extra = total - sum(w)
    grow = [j for j in range(n) if kinds[j] != "spine"]
    want = {j: max(0.0, nats[j] - w[j]) for j in grow}
    if sum(want.values()) > 0 and extra > 0:
        give = min(extra, sum(want.values()))
        tot = sum(want.values())
        for j in grow:
            w[j] += give * want[j] / tot
        extra -= give
    if extra > 0:
        recv = [j for j in grow if kinds[j] == "text"] or grow or list(range(n))
        tot = sum(nats[j] for j in recv)
        for j in recv:
            w[j] += extra * nats[j] / tot
    w = [int(x) for x in w]
    w[max(grow or [0], key=lambda j: w[j])] += total - sum(w)
    return w


def table_segments(header, body, counter):
    """One markdown table -> segments: ('rows', [...]) on the two-column grid, or ('table', html)."""
    n = len(header)
    hdr = [inline(h) for h in header]
    rows = [[inline(c) for c in r] for r in body]
    blank_col = [bool(rows) and all(is_blank(r[j]) for r in rows) for j in range(n)]
    box_col = [bool(rows) and any(is_box(r[j]) for r in rows) and all(is_box(r[j]) or is_blank(r[j]) for r in rows)
               for j in range(n)]
    write_cols = [j for j in range(n) if blank_col[j]]
    text_cols = [j for j in range(n) if not blank_col[j] and not box_col[j]]
    generic = [plain(h).strip().lower().rstrip("?:") in GENERIC for h in hdr]

    # one column: a question and its box, or a short card
    if n == 1:
        if not rows or blank_col[0]:
            mk = re.search(r"\s*(?:<b>)?\((\d+) marks?\)(?:</b>)?\s*$", hdr[0])
            if mk:                               # a question with its marks: the marks chip
                return [("rows", [marks_row(mk.group(1), hdr[0][:mk.start()]), write_row(blank=max(1, len(rows)))])]
            out = [q_row(hdr[0], icon("look", "pencil", "Write"))] if not is_blank(hdr[0]) else []
            return [("rows", out + [write_row(blank=max(1, len(rows)))])]
        out = [] if is_blank(hdr[0]) else [q_row(hdr[0], icon("look", "list"))]
        return [("rows", out + [[td(DO_BG, p("&rsaquo;", 16, NAVY, True), centre=True), td(DO_BG, para(r[0]))] for r in rows])]

    # every column written in: a few rows = room to write each answer, stacked full width
    if not text_cols and not any(box_col) and len(rows) <= 3:
        return [("rows", [write_row(hdr[j], blank=len(rows)) for j in range(n)])]

    # questions down the side, answers to write: each question over its own amber box
    if text_cols and write_cols and not any(box_col) and max(write_cols) == n - 1 and min(write_cols) > max(text_cols):
        numbered = (plain(hdr[0]).strip() in ("#", "No.", "") or all(re.fullmatch(r"\(?\d+[.)]?|[A-Z]", plain(r[0]).strip())
                                                                     for r in rows)) and len(text_cols) > 1
        qcols = text_cols[1:] if numbered else text_cols
        short = all(one_line(" ".join(r[j] for j in qcols), 12, True) < TEXT_W - 60 and len(plain(r[qcols[0]])) <= 45
                    for r in rows) and len(write_cols) == 1
        out = []
        label = None if generic[write_cols[0]] else hdr[write_cols[0]]
        if short and not generic[0]:             # labels down the side (Reverb: Natural, Chamber...; Candidate A)
            if label:
                out.append(q_row(label, icon("look", "pencil", "Write")))
            for r in rows:
                out.append(write_row(" ".join(r[j] for j in qcols), blank=1))
            return [("rows", out)]
        for r in rows:
            if numbered:
                num = plain(r[0]).strip() or str(counter[0] + 1)
            else:
                counter[0] += 1
                num = str(counter[0])
            q = " ".join(r[j] for j in qcols)
            own = re.match(r"^(\d+[a-z]?)[.)]\s+", plain(q))   # "4a. Click Hip-hop": the question's own number
            if own and not numbered:
                num, q = own.group(1), q[own.end():] if q.startswith(own.group(0)) else q
                counter[0] -= 1
            out.append(q_row(q, p(num, 14, NAVY, True)))
            for j in write_cols:
                out.append(write_row(None if (generic[j] or len(write_cols) == 1) else hdr[j]))
        return [("rows", out)]

    # anything else: a grid that still ends on the edge
    order = list(range(n))
    if n == 2 and box_col[1] and not box_col[0]:
        order = [1, 0]                                   # one tick column: it becomes the spine
    hdr = [hdr[j] for j in order]
    rows = [[r[j] for j in order] for r in rows]
    box_col = [box_col[j] for j in order]
    blank_col = [blank_col[j] for j in order]
    kinds = []
    for j in range(n):
        short = all(text_w(plain(r[j]), 12, True) <= SPINE - 10 for r in rows) and longest_word(hdr[j], 9, True) <= SPINE - 8
        if j == 0 and (box_col[j] or (short and not blank_col[j])) and rows:
            kinds.append("spine")
        elif box_col[j]:
            kinds.append("box")
        else:
            kinds.append("text")
    grid = alloc([[hdr[j]] + [r[j] for r in rows] for j in range(n)], kinds, n)
    head_row = []
    for j in range(n):
        size = 9 if kinds[j] == "spine" else 10
        inner = para(hdr[j], grid[j] - 6, size, NAVY, True) if not is_blank(hdr[j]) else GAP
        head_row.append(td(LOOK_BG, inner, centre=kinds[j] != "text"))
    out = [head_row] if any(not is_blank(h) for h in hdr) else []
    for r in rows:
        cells = []
        for j in range(n):
            c = r[j]
            if is_box(c):
                cells.append(tick_cell())
            elif is_blank(c):
                cells.append(td(WRITE_BG, p("Write here", 9, HINT) if j == 0 else GAP))
            elif kinds[j] == "spine":
                cells.append(td(LOOK_BG, p(c, 12, NAVY, True), centre=True))
            else:
                cells.append(td(LOOK_BG, "".join(para(x, grid[j] - 6, 11, INK) for x in re.split(r"&lt;br\s*/?&gt;", c))))
        out.append(cells)
    if not out:
        return []
    if tuple(grid) == (SPINE, COL):
        return [("rows", out)]
    return [("table", table(out, grid))]


# ---------------------------------------------------------------- sections and the page
PART_HEAD = re.compile(r"^(.+?),\s+part\s+(\d+):\s*(.+)$", re.I)
DAYS = {"monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thu", "friday": "Fri",
        "saturday": "Sat", "sunday": "Sun"}


def render_units(units):
    """units: lists of segments. Rows next to each other merge into one table; units are a blank line apart."""
    out = []
    for unit in units:
        parts, rows = [], []
        for kind, seg in unit:
            if kind == "rows":
                rows += seg
            else:
                if rows:
                    parts.append(table(rows)); rows = []
                parts.append(seg)
        if rows:
            parts.append(table(rows))
        if parts:
            out.append("\n".join(parts))
    return ("\n" + GAP + "\n").join(out)


def units_of(blocks, base, counter):
    """The blocks under one heading -> units. A paragraph, callout, picture or sub-heading starts a unit;
    a table or list joins the unit before it (the line that introduces it sits right on it)."""
    units, blocks = [], list(blocks)
    while blocks:
        b = blocks.pop(0)
        kind = b[0]
        num = NUMBERED.match(plain(inline(b[1]))) if kind == "h3" else None
        if num:                                  # "### 1. Key terms": a Part, as on every worksheet
            notes = take_notes(blocks)
            title = num.group(2)[:1].upper() + num.group(2)[1:]
            units.append([("rows", header_rows(td(ORANGE, p(num.group(1), 22, WHITE, True), centre=True), "",
                                               title, icon_for(title), notes))])
        elif kind == "p":
            units.append([("rows", paragraph_rows(b[1]))])
        elif kind == "h3":
            units.append([("rows", [[td(LOOK_BG, p("&rsaquo;", 16, NAVY, True), centre=True),
                                     td(LOOK_BG, para(inline(b[1]), TEXT_W, 13, NAVY, True))]])])
        elif kind == "callout":
            units.append([("rows", callout_rows(b[1], b[2], b[3]))])
        elif kind == "img":
            rows = image_rows(b[1], b[2], base)
            if rows:
                units.append([("rows", rows)])
        elif kind == "table":
            segs = table_segments(b[1], b[2], counter)
            (units[-1].extend(segs) if units else units.append(segs))
        elif kind in ("ul", "ol"):
            seg = ("rows", list_rows(kind, b[1]))
            (units[-1].append(seg) if units else units.append([seg]))
    return units


def take_notes(body):
    """The paragraphs straight after a heading belong with it. A marks question's opening sentence stays
    with them; the question itself, and Going further, start the next block. Changes body in place."""
    notes = []
    while body and body[0][0] == "p" and not GCSE_MARKS.match(body[0][1]) \
            and not re.match(r"\**(going further|a step further)", body[0][1], re.I):
        mk = MARKS.search(body[0][1])
        if mk:
            if body[0][1][:mk.start()].strip():
                notes.append(body[0][1][:mk.start()].strip())
            body[0] = ("p", body[0][1][mk.start():])
            break
        notes.append(body.pop(0)[1])
    return notes


NUMBERED = re.compile(r"^(\d+[a-z]?)[.):]\s+(.+)$")


def header_rows(spine_cell, kicker, title, icon_name, notes):
    t = inline(title)
    first, *rest = lines(t, TEXT_W - 34 if icon_name else TEXT_W, 14, True) or [""]
    lead = (icon("part", icon_name, "") + "&nbsp;&nbsp;") if icon_name else ""
    inner = (p(kicker, 11, NAVY, True) if kicker else "") + p(lead + first, 14, NAVY, True) + "".join(p(x, 14, NAVY, True) for x in rest)
    inner += "".join(para(inline(x), TEXT_W) for x in notes)
    return [[spine_cell, td(DO_BG, inner)]]


def masthead(title, subtitle, kind, setdue):
    m = re.search(r"\bWeek\s+0*(\d+)", f"{title} {subtitle}", re.I)
    # The week sits on the right, after the title. OneNote names an untitled page after its first words,
    # so a number on the left would make "7" the page's name in the list of pages.
    grid = (SPINE, widths_sum(3) - 2 * SPINE, SPINE) if m else (SPINE, COL)
    width = grid[1] - 14
    spine = td(AMBER, icon("amber", "doc"), centre=True, border=False)
    # The big title comes first for the same reason, and whole: a page named only "My lecture" tells a student
    # nothing, so it reads "Homework 1, part 2: my lecture". The week is on the right, so not here.
    big = re.sub(r",?\s*\bWeek\s+0*\d+\b(?=:)", "", title, count=1, flags=re.I).lstrip(": ")
    big = big[:1].upper() + big[1:]
    if len(lines(inline(big), width, 20, True)) > 1:
        print(f"grid: the title wraps, and OneNote names the page after its first line only: {big}", file=sys.stderr)
    kicker = kind.capitalize() if kind and kind.lower() not in title.lower() else ""
    top = td(AMBER, para(inline(big), width, 20, NAVY, True)
             + (para(kicker, width, 11, NAVY, True) if kicker else ""), border=False)
    rows = [[spine, top]]
    if m:
        rows[0].append(td(AMBER, p("Week", 10, NAVY, True) + p(m.group(1), 30, NAVY, True), centre=True, border=False))
    facts = [H.escape(subtitle, quote=False)] if subtitle else []
    if setdue:
        facts += [f"Set {inline(setdue[0])}", f"<b>Due {inline(setdue[1])}</b>"]
    if facts:
        rows.append([td(NAVY, icon("navy", "calendar", "Dates"), centre=True, valign="middle", border=False),
                     td(NAVY, para(" &middot; ".join(facts), width, 11, WHITE), valign="middle", border=False)])
        if m:
            rows[-1].append(td(NAVY, p("&nbsp;", 11, WHITE), border=False))
    return table(rows, grid)


def build(md_path, subtitle="", kind="", footer=""):
    md_path = pathlib.Path(md_path)
    md = md_path.read_text(encoding="utf-8")
    if md.startswith("---"):
        end = md.find("\n---", 3)
        md = md[end + 4:] if end != -1 else md
    m = re.search(r"^# (.+)$", md, re.M)
    title = m.group(1).strip() if m else ""
    md = re.sub(r"^# .+\n?", "", md, count=1, flags=re.M)
    blocks = parse(md)
    if "☐" in md and re.search(r"\btick\b", md, re.I):
        print("grid: this page says 'tick', but no pasted box can be clicked: say 'type x in the box'",
              file=sys.stderr)
    setdue = next(((b[1], b[2]) for b in blocks if b[0] == "setdue"), None)
    blocks = [b for b in blocks if b[0] != "setdue"]
    base = md_path.parent

    # the blocks before the first heading, then one list of blocks per heading
    intro, sections = [], []
    for b in blocks:
        if b[0] == "h2":
            sections.append((b[1], []))
        elif sections:
            sections[-1][1].append(b)
        else:
            intro.append(b)

    out = [masthead(title, subtitle, kind, setdue), GAP]

    # the page at a glance: its opening lines, and the Immersive Reader line
    lead = []
    while intro and intro[0][0] == "p":
        lead.append(intro.pop(0)[1])
    glance = []
    for k, t in enumerate(lead):
        rows = paragraph_rows(t, ("pencil" if setdue else "doc") if k == 0 else None, GLANCE_BG)
        glance += rows
    glance.append(text_row(GLANCE_BG, icon("glance", "reader", "Immersive Reader"), READER))
    first = [[("rows", glance)]]
    out.append(render_units(first + units_of(intro, base, [0])))

    halves = {}
    for head, _ in sections:
        pm = PART_HEAD.match(plain(inline(head)))
        if pm:
            halves.setdefault(pm.group(1).strip(), len(halves) + 1)
    n_section, seen_half = 0, set()
    for head, body in sections:
        text = plain(inline(head))
        if any(b[0] == "h3" and NUMBERED.match(plain(inline(b[1]))) for b in body):
            word = re.search(r"\b(first|second|third|fourth)\b", text, re.I)
            label = (DAYS.get(text.split()[0].lower()) if text.split() else None) or \
                ({"first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th"}[word.group(1).lower()] if word else None)
            spine = td(NAVY, p(label, 16, WHITE, True) if label else icon("navy", icon_for(text, "list")),
                       centre=True, valign="middle", border=False)
            out += [GAP] * SECTION_GAP
            out.append(table([[spine, td(AMBER, para(inline(text[:1].upper() + text[1:]), TEXT_W, 18, NAVY, True),
                                         valign="middle", border=False)]]))
            out.append(GAP)
            out.append(render_units(units_of(body, base, [0])))
            continue
        pm = PART_HEAD.match(text)
        half, title_, number = None, text, None
        if halves:
            if pm:
                half, number, title_ = pm.group(1).strip(), pm.group(2), pm.group(3).strip()
            else:
                h_, colon, rest = text.partition(":")
                if colon and h_.strip() in halves and rest.strip():
                    half, title_ = h_.strip(), rest.strip()
        else:
            n_section += 1
            number = str(n_section)
            title_ = re.sub(r"^(step\s+)?\d+[.):]\s+", "", title_, flags=re.I)   # "1. Open it": the spine has the number
        title_ = title_[:1].upper() + title_[1:]
        out += [GAP] * SECTION_GAP
        if half and half not in seen_half:      # the evening's own band, before its first section
            seen_half.add(half)
            day = DAYS.get(half.split()[0].lower(), str(halves[half]))
            out.append(table([[td(NAVY, p(day, 16, WHITE, True), centre=True, valign="middle", border=False),
                               td(AMBER, p(H.escape(half[:1].upper() + half[1:], quote=False), 18, NAVY, True),
                                  valign="middle", border=False)]]))
            out.append(GAP)
        notes = take_notes(body)
        name = icon_for(title_)
        if number:
            spine = td(ORANGE, p(number, 22, WHITE, True), centre=True)
            hrows = header_rows(spine, f"Part {number}" if halves else "", title_, name, notes)
        else:
            spine = td(NAVY, icon("navy", name or "list", ""), centre=True)
            hrows = header_rows(spine, "", title_, None, notes)
        units = units_of(body, base, [0])
        if units:
            units[0].insert(0, ("rows", hrows))
        else:
            units.append([("rows", hrows)])
        out.append(render_units(units))

    if setdue and re.search(r"\|\s*(?:&nbsp;)?\s*\|", md):  # no amber box to fill, no card (a page that is only a link)
        out += [GAP] * SECTION_GAP
        out.append(table([[td(NAVY, icon("navy", "flag", "Finished"), centre=True),
                           td(DO_BG, p("Finished?", 14, NAVY, True) + para("Every amber box has your words in it.", TEXT_W)
                              + para(f"<b>Due {inline(setdue[1])}</b>, done on this page.", TEXT_W))]]))
    if footer:
        out += [GAP, p(H.escape(footer, quote=False), 9, GREY)]
    page = f'<html><head><meta charset="utf-8"></head><body style="{FONT}">' + "\n".join(out) + "</body></html>"
    return title, page


# ---------------------------------------------------------------- the check
ONENOTE = "<style>td{padding:3px!important;border-width:2px!important}</style>"
EDGES = """<script>document.fonts.ready.then(() => { document.title = [...document.querySelectorAll('body > table')]
  .map(t => Math.round(t.getBoundingClientRect().right)).join(' ') + ' ' + document.fonts.check('12pt Calibri'); });</script>"""


def faces():
    return "".join(f'@font-face{{font-family:Calibri;font-weight:{wt};src:url("{(CALIBRI / f_).as_uri()}")}}'
                   for f_, wt in (("Calibri.ttf", "normal"), ("Calibrib.ttf", "bold")))


def check(page, shot=None):
    """Right edge of every block, drawn with OneNote's padding and borders. Returns the list of edges."""
    shown = page.replace("<head>", f"<head>{ONENOTE}<style>{faces()}</style>", 1)
    with tempfile.TemporaryDirectory() as d:
        src = pathlib.Path(d) / "edges.html"
        src.write_text(shown.replace("</body>", EDGES + "</body>"), encoding="utf-8")
        dom = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                              "--virtual-time-budget=3000", "--window-size=760,4000", "--dump-dom", src.as_uri()],
                             check=True, capture_output=True, text=True).stdout
        if shot:
            src.write_text(shown, encoding="utf-8")
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                            "--virtual-time-budget=3000", "--window-size=700,9000", f"--screenshot={shot}", src.as_uri()],
                           check=True, capture_output=True)
    *edges, calibri = re.search(r"<title>(.*?)</title>", dom).group(1).split()
    assert calibri == "true", "Calibri did not load, so the widths are not OneNote's"
    return edges


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--kind", default="")
    ap.add_argument("--footer", default="")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--shot")
    a = ap.parse_args()
    title, page = build(a.md, a.subtitle, a.kind, a.footer)
    if a.out:
        pathlib.Path(a.out).write_text(page, encoding="utf-8")
    print("TITLE:", title, "| bytes:", len(page.encode()))
    if a.check or a.shot:
        if not pathlib.Path(CHROME).exists():
            sys.exit("--check needs Google Chrome on a Mac; the page itself builds without it")
        edges = check(page, a.shot)
        print(f"{len(edges)} blocks, right edges:", " ".join(sorted(set(edges))), "" if len(set(edges)) == 1 else "<- NOT ALIGNED")
