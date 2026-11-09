# PT-BR translation status (own translation, from the English source)

Date: 2026-11-09 (v0.1 release candidate). The working text lives outside the repo; `tools/sync_text.py` regenerates `text/` from it. **First version, for testing: nothing is reviewed by a second person yet.**

| Metric | Done | Total |
|---|---|---|
| Entries (ids) filled | 9,971 | 10,196 (98%) |
| Unique source strings | 5,674 | 5,828 (97%) |
| Unique words | 37,285 | 37,548 (99%) |

Everything a player can see is translated: menus, names, items, magic, traits, blood-message words, event text, subtitles and all NPC dialogue. Left on purpose: 154 unique strings of test and debug leftovers that are not shown to players. `text/` holds 9,763 entries (those identical to the original are dropped; the game keeps its own text there).

Dialogue registers (per NPC): archaic "vós" for the priest Urbain, Ostrava and Selen Vinland; archaic "tu" for the Maiden in Black, Old King Doran and the "thou" lines of the Monumental; "você" for everyone else. Speakers are inferred from string order and content (the file has no speaker field), so a few ambiguous lines may have the wrong register.

Archstone is "Arquipedra" everywhere.

Done since 2026-11-07: width pass against the real menu boxes (lines re-broken, long names shortened), movie subtitles for the opening movie, big on-screen messages (VOCÊ MORREU and the rest) rebuilt from the game's own lettering, one-click installer for the official Soulbrandt 0.1.1.

v0.1 release check (2026-11-09): the final zip installed on a fresh test layout in about 4 s; the seven rebuilt files are byte-identical to the copy the game was played with; uninstall restored every original byte for byte and removed the subtitle stand-in.

Open for v0.1: the product owner's play test of the final zip (big messages seen on screen; "Santuário das Tempestades" and two weapon names near the box edge).
Planned for v0.2: official PS5 PT-BR names for rings and items (e.g. the ring now called "Esconder de Inimigos").
