# OneNote pages with Claude Code

You ask Claude Code for a page, it builds it, and you press Cmd+V in OneNote. The whole designed page arrives in one paste: coloured bands, icons, numbered parts, amber boxes to write in, and the same right edge all the way down. Students get the same layout on every page, with room to settle on one task at a time. It was designed with dyslexic readers in mind.

This is the page design Mike Lehnert uses with his classes. It works for any subject.

## What you need

- **Claude Code**, on your own account
- **A Mac with OneNote.** The clipboard step only works on a Mac so far, and the design was measured on OneNote for Mac. It has not been tried on Windows.

You don't need an MCP server, a plugin or a skill. Claude Code never connects to OneNote. It puts the page on your clipboard and you paste it.

## Set it up

Open Claude Code and paste this one sentence:

```text
Clone https://github.com/calimike74/onenote-pages into my home folder, set it up by following its CLAUDE.md, and put the sample homework on my clipboard.
```

Claude Code may ask you to sign in to GitHub first, because this repo is private. Then make a new page in OneNote, one you don't mind deleting, and press Cmd+V.

## Using it

Open Claude Code in the `onenote-pages` folder and ask for what you want:

> Make me a homework on the causes of the First World War: a short reading box, five key words, three questions and one 6-mark question.

When Claude says it's on your clipboard, click on a blank OneNote page and press Cmd+V.

Always let Claude Code do the build. Copying a page's text out of the chat gets you plain words with no design.

`USAGE.md` has the rest: what you can change, and what it can't do.
