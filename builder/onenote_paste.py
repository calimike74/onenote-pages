#!/usr/bin/env python3
"""Turn one OneNote page .md into HTML in the page design and put it on the macOS clipboard as rich
HTML, ready for Cmd+V into a OneNote page body. The design itself is in onenote_grid.py.

usage: onenote_paste.py PAGE.md --subtitle "Week 1 · w/c 7 September" [--kind ...] [--footer ...]
       [--out page.html] [--no-clip]

Everything is a table, because tables (cell colour, cell border, font) are what OneNote for Mac keeps
from pasted HTML. No nesting, no colspan (OneNote has no merged cells), no CSS widths (ignored).
"""
import argparse, os, pathlib, subprocess, sys
import onenote_grid


def to_clipboard(page_html):
    # The script goes through a file, not "-e": a page with embedded figures runs to megabytes,
    # and a command-line argument that long fails with "Argument list too long".
    import tempfile
    hexdata = page_html.encode("utf-8").hex()
    script = f'set the clipboard to «data HTML{hexdata}»'
    with tempfile.NamedTemporaryFile("w", suffix=".applescript", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        subprocess.run(["osascript", path], check=True)
    finally:
        os.unlink(path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--kind", default="", help="a small label under the title, e.g. HOMEWORK or CLASS TASK")
    ap.add_argument("--footer", default="")
    ap.add_argument("--out")
    ap.add_argument("--no-clip", action="store_true")
    a = ap.parse_args()
    title, page = onenote_grid.build(a.md, a.subtitle, a.kind, a.footer)
    if a.out:
        pathlib.Path(a.out).write_text(page, encoding="utf-8")
    if not a.no_clip:
        if sys.platform == "darwin":
            to_clipboard(page)
        else:   # no clipboard step outside a Mac yet: save the page, to copy from a browser
            saved = a.out or str(pathlib.Path(a.md).with_suffix(".html"))
            pathlib.Path(saved).write_text(page, encoding="utf-8")
            print(f"Not a Mac, so nothing went on the clipboard. Open {saved} in a browser, select all, copy, and paste into OneNote.")
    print("TITLE:", title)
    print("bytes:", len(page.encode("utf-8")))
