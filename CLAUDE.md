# OneNote pages

You build OneNote pages for a teacher. You write each page as Markdown in `pages/`, build it, and the teacher pastes it into OneNote with Cmd+V. You never connect to OneNote.

## Setting up (first time only)

1. Check `python3` works. On a new Mac this may ask to install Apple's command line tools. Let it finish.
2. In this folder, run: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
3. Check Calibri can be found: `ls "/Applications/Microsoft OneNote.app/Contents/Resources/DFonts/Calibri.ttf"`. If it isn't there, tell the teacher that lines may wrap differently until OneNote or Word is installed in Applications.
4. Build the sample to the clipboard: `.venv/bin/python builder/onenote_paste.py samples/homework-how-sound-travels.md --subtitle "Week 1 · w/c 7 September 2026"`
5. Tell the teacher to make a new OneNote page they don't mind deleting, click on it and press Cmd+V. Ask them to check every coloured bar ends at the same right edge.

## Making a page

1. Write `pages/<short-name>.md` in the shape below.
2. If the teacher dictates or has a clipboard tool running, warn them it may overwrite the page.
3. Build it: `.venv/bin/python builder/onenote_paste.py pages/<short-name>.md --subtitle "Week 3 · w/c 21 September 2026"`
4. If Chrome is installed, check it: `.venv/bin/python builder/onenote_grid.py pages/<short-name>.md --check`. It must print a single right-edge number. Otherwise find the block that sticks out and fix the page.
5. Read any `grid:` warnings the builder prints and fix them.
6. Say it's on the clipboard and to press Cmd+V on a blank OneNote page.

Build several pages one at a time. Each build replaces the clipboard, so wait for the teacher to paste each page first.

Never tell the teacher to copy a page out of this conversation. The design only exists in what the builder puts on the clipboard.

## On a Windows PC

Nobody has tried this on Windows yet, so tell the teacher that first.

- Use `python -m venv .venv` and `.venv\Scripts\python` in place of the commands above. Skip the Calibri check and `--check`, which look in Mac folders.
- The builder doesn't touch the clipboard there. It saves the page as an `.html` file beside the Markdown and prints where.
- Tell the teacher to open that file in a browser, select all, copy, and paste into a blank OneNote page.
- Ask them to check every bar ends on the same right edge. The measurements below come from OneNote for Mac and may not hold.

## The shape of a page

The first line is `# Title`. OneNote names an untitled page after its first words, and students find their work in that list, so the title must say which task it is and fit on one line. Write `# Homework 1, Week 7: what a filter does`. The builder moves `Week 7` to the right of the top band.

| You write | The student sees |
|---|---|
| `**Set:** Monday 2 November · **Due:** Friday 6 November` (straight after the title, with that dot) | The dates in the navy strip, and a Finished card at the end if the page has boxes to fill in |
| Paragraphs before the first `##` | The at-a-glance card. The Immersive Reader line is added for you |
| `## Key words` | A section with an orange number and an icon, and three blank lines before it |
| `## Monday evening, part 1: Key words` | A navy and amber band for Monday evening, with Part 1 under it |
| `### 1. Key words` or `**1. Key words**` | A numbered part inside a section |
| `### A smaller heading` | A small heading |
| `\| Question \| Your answer \|`, with the answer cells empty | Numbered pale blue questions, each with its own amber Write here box |
| `\| Explain why... **(4 marks)** \|` with blank rows under it, one per line of writing | A marks chip, the question and an amber box |
| `**Explain why... (4 marks)**` on its own line | A marks chip and the question, with no box |
| Any other table | A grid measured to end on the shared right edge. It works up to about 5 columns |
| `☐` in a table cell, or `- ☐ Do this` | A box to type x in |
| `1. Step` | Navy numbered rows |
| `- Point` | Bullet rows |
| `> [!tip] Heading`, also `warning`, `success`, `question`, `example`, `abstract` | A card with its own icon |
| `> [!quote] A student wrote`, then `> Their words`, with no quotation marks | A quotation card, for spotting mistakes. The builder adds the marks |
| `> - [ ] Section name` inside a card | A list with a circle on each line. `>` alone is a gap, and a line ending in `\` breaks there |
| `![What it shows](Figures/name.png)` | The picture beside an eye icon. Always write the alt text, because Immersive Reader reads it |
| `**Going further:** ...` | A star row |
| `If it will not open, ...` | A help row |

`samples/` has one homework and one class task. Read them before writing your first page.

### How icons get chosen

The builder chooses icons from your words, so one icon always means the same thing. Use the plain word and the icon follows.

- **Headings:** listen or hear = headphones; read or chapter = book; write, explain or describe = pencil; look, figure or picture = eye; quiz, test or marks = tick; open, link or computer = open; tip or hint = bulb; question, exam or paper = page; what is wrong or mistake = magnifier; film, video or watch and do = play; going further = star.
- **Paragraphs:** a line starting Read, Open, Go to, Click, Press, Watch, Write, Fill in, Answer, Look, See, Listen, Play, Hint, Tip or Remember gets the matching icon. So does any line with "20 minutes" (clock) or "type x" (tick).

## The design rules

Keep these on every page. The teacher chose them for a reason and the builder depends on them.

- **Colour means the same thing everywhere.** Amber is the student's to write in, pale blue is to read, cream is to do, navy is a door or a date, orange is a Part number.
- **One right edge.** Every band, card and table ends on the same pixel.
- **One job at a time.** Mark off each task with its own section. Keep sentences short and put each step on its own line. Students with dyslexia rely on the gaps.
- **Lists, not runs.** Never write a list of names or sections as a sentence. Put one on each line.
- **"Type x in the box", never "tick".** No pasted box in OneNote can be clicked, and OneNote's own To Do tags can't be added from outside it. Don't try: this was tested.
- **Bold, not italics.** The builder turns italics into plain text, because italics are harder to read.
- **Room to write.** Every answer gets an amber box. A longer answer gets more blank rows.

## What OneNote for Mac does on paste

These were measured from real pastes. Don't "simplify" the builder without knowing them.

- It ignores CSS widths and `cellpadding`, puts about 3 px inside each cell and draws borders 2 px wide.
- It keeps `<img>` widths. So each column is held open by a 6 px strip picture in the cell's own colour. It throws away 1 px pictures, probably as tracking pixels.
- A table of n columns ends on the shared edge when its widths add up to 620 - 8n.
- It drops margins, so every gap is a real empty paragraph.
- It has no merged cells and keeps nothing nested, so everything is one flat table at a time.

## Student data

- Keep real student names, marks and personal links out of everything except files in `pages/`, which git ignores.
- Never add, commit or push anything from `pages/`.
- Use "Test Student" in anything that might be shared.

## Your own rules

The teacher adds their own rules here: subject terms, exam board wording, how they like to be quoted, what they call homework.
