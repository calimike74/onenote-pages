# Using the OneNote page builder

## What it does

`builder/onenote_paste.py` turns one page written in Markdown into HTML in the page design, then puts it on the Mac's clipboard. Cmd+V in OneNote brings the whole page in, with its icons and pictures, because they are carried inside the page itself.

## How to use it

Ask Claude Code for a page, in the `onenote-pages` folder. It writes the page into `pages/`, builds it and tells you when to paste. To build one yourself:

```bash
.venv/bin/python builder/onenote_paste.py samples/homework-how-sound-travels.md --subtitle "Week 1 · w/c 7 September 2026"
```

Then press Cmd+V on a blank OneNote page straight away. Dictation tools such as Wispr overwrite the clipboard. If you use one, paste before you dictate anything else.

To save the page without touching the clipboard, add `--out page.html --no-clip`.

To check the layout, add `--check` to `builder/onenote_grid.py` instead. It prints the right edge of every block, and there should be only one number. This step needs Google Chrome.

## What you can change

- **Your own rules.** Add how you write pages, your subject's terms and your exam board's wording to the "Your own rules" section of `CLAUDE.md`. Claude Code reads it every time.
- **A page's words.** Ask Claude Code, or edit the file in `pages/` and ask it to build again.
- **Colours of the bands and boxes.** These are at the top of `builder/onenote_grid.py`. The icons are ready-made pictures on the current colours, so a new colour needs new icons, and the script that draws them isn't in this repo.
- **Room between sections.** `SECTION_GAP` in the same place.

## Limits

- **Tested on a Mac only.** On Windows the builder saves the page as a file instead of using the clipboard. Nobody has tried pasting it there yet, and the layout may not line up.
- **Word wrapping depends on Calibri.** The builder finds it inside OneNote or Word. Without either it guesses the letter widths, and lines may wrap differently.
- **Boxes can't be clicked.** No pasted box in OneNote can be clicked, so pages say "type x in the box". A pen user can tick it by hand.
- **Only the next paste changes.** Pages already in OneNote stay as they are.
- **Pictures don't draw themselves.** A picture appears where the page names one. Anything drawn specially for one page is a separate job.
- **One page at a time.** A long list of pages means one paste each. Paste each page before you build the next.
