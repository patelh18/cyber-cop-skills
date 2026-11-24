---
name: humanize-writing
description: Rewrite a document so it reads like a person wrote it - varied rhythm, plain concrete wording, no stock AI phrases, filler transitions, em-dash habits or reflexive triplets - while keeping its structure exactly (headings, section order, lists, tables, code, links, citations, numbers and formatting) and optionally the author's own voice. Use when asked to humanize, de-AI, naturalize or "make this sound human" for a Markdown, plain-text or Word document, or to check a draft for AI-sounding prose.
---

# Humanize writing

Rewrites the wording of a document and nothing else. The skeleton of the
document is treated as locked; only the sentences inside paragraphs, list
items, quotes and table cells change. Two bundled scripts keep that honest:

| Script | What it checks |
|---|---|
| `scripts/structure_diff.py ORIGINAL REWRITTEN` | Block sequence (heading levels and text, paragraphs, list type and nesting, quotes, table shapes, rules), code blocks and inline code byte for byte, link targets, citations and footnotes, numbers / dates / versions / IDs, bold and italic counts. Exit `0` preserved, `1` differences, `2` bad input. |
| `scripts/style_check.py BEFORE AFTER` | Sentence-length variation, stock phrases, em-dashes, triplets, trailing "-ing" commentary, repeated openers. Prints a before/after table plus findings with block numbers. |

Both are standard-library Python 3.8+ and read `.md`, `.txt` and `.docx`.

## What it will and won't do

It improves the prose the way a good human editor would. That usually also
lowers the scores AI-text detectors give, because detectors key on the same
habits (uniform sentences, predictable word choice, stock phrasing). It makes
no promise about any particular detector: they disagree with each other, flag
human writing too, and change without notice. Say so if the user asks for a
guarantee.

It never uses tricks that game a detector while making the document worse:
no invisible or zero-width characters, no look-alike Unicode letters, no
planted typos or broken grammar, no random synonym swaps that change meaning.
Those are easy to detect, corrupt the file for search and screen readers, and
are exactly what a QC reviewer would catch.

## Steps

1. **Get the document and the settings.** Ask only if it isn't clear:
   - *Voice*: `keep` (default; match the author's existing tone, person,
     formality, spelling variant, and any signature phrases) or `neutral`
     (plain professional). If the user gives a writing sample, read it and
     match its sentence length, contractions and vocabulary.
   - *Strength*: `light` (fix flagged phrases and rhythm only), `standard`
     (default; rework sentences freely inside each block), `heavy` (restate
     each block from scratch, same facts).
   - *Headings*: locked by default. Pass `--allow-heading-edits` to the
     checker only if the user says heading wording may change.
   - *Audience and register* if the document doesn't make it obvious.

   For `.docx`, edit the text runs in place (the `docx` skill can do this)
   so styles, numbering and tables stay the same; never rebuild the file.

2. **Baseline.** Save the original untouched (e.g. `original.md`) and run
   `python3 <skill_dir>/scripts/style_check.py original.md`. Note the worst
   blocks and the patterns that dominate.

3. **Protect.** Before rewriting, list what may not change in each block:
   numbers, dates, names, product and package names, IDs (CVE-…), quotes,
   defined terms, inline code, link targets, citations, and any legal or
   compliance wording. Direct quotations stay verbatim.

4. **Rewrite block by block.** Keep one output block per input block, in the
   same order, with the same markers (`#`, `-`, `1.`, `|`, `>`), indentation,
   emphasis and links. Work through [references/ai-patterns.md](references/ai-patterns.md);
   in short:
   - Vary sentence length on purpose. Mix short sentences with longer ones.
     Don't let three sentences in a row land at the same length.
   - Cut stock phrases and filler connectors ("Furthermore,", "Moreover,",
     "It's important to note that", "In today's fast-paced…"). Most sentences
     need no connector at all.
   - Replace vague praise words (robust, seamless, crucial, transformative)
     with the concrete fact behind them, or delete them if there is none.
     Never invent facts to fill the gap.
   - Use em-dashes rarely. Commas, parentheses, colons or a full stop usually
     read better.
   - Break reflexive groups of three. Use the real number of items.
   - Drop trailing "-ing" commentary (", highlighting the need for…"). Make it
     its own sentence with a subject, or cut it.
   - Don't open every paragraph or list item the same way, and don't end
     sections with a summary sentence that repeats the section.
   - Prefer plain verbs and active voice; contractions are fine where the
     author's voice allows them.
   - Keep the meaning, claims and level of certainty. Don't add hedges the
     author didn't have or remove the ones they did.

5. **Self-check, then fix and repeat.**
   ```bash
   python3 <skill_dir>/scripts/structure_diff.py original.md rewritten.md
   python3 <skill_dir>/scripts/style_check.py original.md rewritten.md
   ```
   - `structure_diff` must print `OK`. Any `FAIL` line names the block and
     what changed (a merged paragraph, a lost number, a dropped link): fix
     that block and run it again. Do not hand back a document that fails.
   - `style_check` is guidance, not a gate. Aim for `sentence_len_cv` of
     0.45 or more, stock phrases near zero, em-dashes at or under 0.5 per 100
     words, and no `ing_tails`. Review each remaining finding; some are fine
     in context (a real list of three, a technical term like "robust
     statistics").
   - Read the rewrite once as the intended reader would. If a sentence now
     says something the original didn't, put the original meaning back.

6. **Deliver.** Hand back the rewritten document in the original format and
   a short note: the settings used, the before/after table from
   `style_check`, the `structure_diff` result, and anything you left alone
   on purpose (quotes, legal text, terms) or think the author should check.

## Tests

```bash
python3 -m unittest discover -s <skill_dir>/tests
```

`tests/fixtures/before.md` is a machine-sounding report and `after.md` a
rewrite with the same structure; the tests check that the pair passes and
that each kind of structural or factual drift (merged paragraphs, heading
edits, list or table changes, code, numbers, dates, IDs, links, citations,
emphasis, `.docx` styles and numbering) is caught.
