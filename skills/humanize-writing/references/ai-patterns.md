# Patterns that make prose read as machine-written

Use this as the editing checklist for step 4 of `SKILL.md`. Each pattern has
a short example and what to do instead. `scripts/style_check.py` flags most of
the phrase-level ones automatically; the rhythm and structure ones need a read.

## Rhythm

| Pattern | Example | Instead |
|---|---|---|
| Uniform sentence length | Five sentences of 16-20 words each. | Mix in a short sentence. Let one run long when the idea needs it. Target a coefficient of variation of 0.45+. |
| Same sentence shape repeated | "X does A. Y does B. Z does C." | Change the order: start one with the object, a time, a condition, or a short clause. |
| Every paragraph opens the same way | "This…", "This…", "This…" | Start with the subject that matters in that paragraph. |
| Wrap-up sentence at the end of every section | "Overall, these steps ensure success." | Delete it. The section already said it. |
| Balanced pairs and triplets everywhere | "fast, reliable, and secure" | Use the real number of items. Two is fine. One concrete one is better. |

## Word choice

| Pattern | Example | Instead |
|---|---|---|
| Stock openers | "In today's fast-paced digital landscape," | Start with the point. |
| Signposting | "It's important to note that…", "It's worth mentioning…" | State the thing. |
| Filler connectors | "Furthermore,", "Moreover,", "Additionally,", "Consequently," | Usually nothing. Otherwise "also", "so", "but", "and". |
| Inflated verbs | delve, leverage, utilize, foster, bolster, underscore, harness, unlock | look at, use, help, build, support, show. |
| Vague intensifiers | robust, seamless, cutting-edge, pivotal, crucial, transformative, holistic, meticulous | The concrete fact: "handles 10k requests/s", "no manual step". If there's no fact, cut the word. |
| Metaphor stock | tapestry, landscape, journey, realm, beacon, testament | The literal word. |
| "Serves as" / "stands as" | "The dashboard serves as a central hub." | "The dashboard is where…" |
| Contrast framing | "It's not just a tool; it's a mindset." | Say the one claim you actually mean. |
| Trailing participle commentary | "…in 3 days, highlighting our agility." | Cut it, or make it a sentence with a real subject: "That's twice as fast as last quarter." |
| Assistant boilerplate | "I hope this helps!", "Feel free to reach out." | Remove unless the original author wrote it. |

## Punctuation and formatting habits

- **Em-dashes**: models use them several times per paragraph. Keep at most
  one where it truly helps; use commas, parentheses, a colon or a full stop.
- **Colon reveals**: "The result? A 40% drop." Write it straight.
- **Bold sprinkled through prose**: don't add bold. Keep exactly the bold the
  original had (the structure checker counts it).
- **Title Case in sentences or list items** that the author didn't use.

## Voice

When voice is `keep`:
- Keep person (I / we / you / passive), tense, and spelling variant (US/UK).
- Keep contractions if the author uses them; don't add them to formal text.
- Keep the author's recurring terms and phrasing quirks. A distinctive voice
  is the strongest signal that a person wrote something.
- Match their typical sentence length range rather than a generic target.

When voice is `neutral`: plain, direct, professional. Contractions are fine
outside formal or legal text.

## Things a rewrite must never do

- Change a number, date, unit, version, ID, name, quotation, citation, link,
  or code.
- Add a claim, example or statistic that isn't in the original.
- Strengthen or weaken certainty ("may" -> "will", "will" -> "might").
- Merge or split paragraphs, list items or table cells; reorder sections.
- Insert invisible characters, look-alike Unicode, deliberate typos or broken
  grammar to fool a detector.
