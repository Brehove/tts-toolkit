# Narration Rules

Guidelines for preparing text content for TTS narration. Follow these
rules when converting written content (articles, chapters, documentation,
etc.) into narration-ready plain text.

## What to Include

- All body text — narrate every paragraph in full, no condensation
- Callout boxes, sidebars, and highlighted content — narrate in full
  unless purely decorative

## What to Exclude

- **References / bibliography** — do not narrate
- **Raw table data** — skip cell-by-cell data; insert a brief spoken
  placeholder like: "The text includes a comparison table here. Refer
  to the original for the full breakdown."
- **Figure captions** — do not narrate
- **Image markers** — strip any bracketed image references

## TTS Formatting

These rules optimize the text for natural-sounding TTS output without
changing the prose content:

- **Sentence length**: Split sentences over 30 words at natural breaks
- **Abbreviations**: Spell out on first use ("for example" not "e.g.")
- **ALL CAPS**: Replace with regular case (TTS may read letter-by-letter)
- **Numbers**: Spell out small numbers ("three" not "3")
- **Parentheticals**: Keep under 8 words (TTS handles long asides poorly)
- **Quotes**: Short inline quotes are fine. Paraphrase long block quotes.

## Narration Flow

Since there may be no visual transitions, the narration must flow as
one continuous read:

- **Section markers**: Insert a brief spoken header at each major
  boundary (e.g., "Section two: The Ethics of Care.") so the listener
  can track position
- **Bridge sentences**: Add brief transitions between sections so
  adjacent sections don't feel disconnected
- **Read-through check**: Read all narration text back-to-back before
  finalizing. If any two adjacent sections feel disconnected, add a
  bridge sentence.
- **Transitional phrases**: Keep under 8 words. Examples: "So what
  happens when...", "That brings us to...", "Which raises a question."
- **`[SECTION]` markers**: Insert `[SECTION]` on its own line between
  major sections. The script splits narration at these markers for
  parallel TTS generation. If omitted, the script falls back to
  splitting at paragraph boundaries.
