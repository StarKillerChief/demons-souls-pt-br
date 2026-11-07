# PT-BR translation status (own translation, from the English source)

Date: 2026-11-07. The working text lives outside the repo; `tools/sync_text.py` regenerates `text/` from it. **First version, for testing: nothing is reviewed by a second person yet.**

| Metric | Done | Total |
|---|---|---|
| Entries (ids) filled | 9,971 | 10,196 (98%) |
| Unique source strings | 5,674 | 5,828 (97%) |
| Unique words | 37,285 | 37,548 (99%) |

Everything a player can see is translated: menus, names, items, magic, traits, blood-message words, event text, subtitles and all NPC dialogue. Left on purpose: 154 unique strings of test and debug leftovers that are not shown to players. `text/` holds 9,763 entries (those identical to the original are dropped; the game keeps its own text there).

Dialogue registers (per NPC): archaic "vós" for the priest Urbain, Ostrava and Selen Vinland; archaic "tu" for the Maiden in Black, Old King Doran and the "thou" lines of the Monumental; "você" for everyone else. Speakers are inferred from string order and content (the file has no speaker field), so a few ambiguous lines may have the wrong register.

Archstone is "Arquipedra" everywhere.

Open: the width pass (see `soulbrandt-test.md` for three confirmed overflows), review by the project owner, comparison of names with the PS5 version.
