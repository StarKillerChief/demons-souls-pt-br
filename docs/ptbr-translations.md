# Existing PT-BR translations of Demon's Souls (PS3) and how they handled the font

Date: 2026-11-06. Method: public web pages only (search + page reads). Nothing was downloaded, run or contacted. No translation text is reproduced. Pages on nexusmods.com returned HTTP 403 to direct reads, so Nexus facts below come from search-engine summaries of those pages and are marked **(unverified: summary)**. Absence of a project in these searches is not proof it does not exist.

## 1. Projects found

| # | Project | Authors / credits | Status | Covers | Game version | License / permission | Reachable |
|---|---|---|---|---|---|---|---|
| 1 | **Demon's Souls - Nova Traducao PT-BR** (Nexus Mods, demonssouls/mods/182) | AudaxTenebra, IvoryMage (summary) | v2, updated 2026-07-09 (summary); 6 endorsements | Rebuilt from scratch: items, spells, miracles, weapons, armor, special on-screen messages; loading screens not touched. Optional EU pack bundles other emulator fixes and Xbox button glyphs | US (BLUS30443) and an EU option; author reportedly recommends EU because it "already supports accents" (summary) | Not readable (403). Nexus default is author-defined | Page exists per search results. https://www.nexusmods.com/demonssouls/mods/182 |
| 2 | **[PS3] Demon's Souls PT-BR** (JumpManClub Brasil + Traducoes PKG) | AlanMugiwara-san (translation, revision, romhacking), Dirk (romhacking), AndyFF (translation), William Cordeiro (in-game revision) | Released 2019-07-12; texts, revision and in-game revision all listed 100%; only follow-up was a 2020 request to fix some untranslated weapon names | Texts (menus, items, dialogue). A 2019 forum reply says it worked on RPCS3 and real PS3, another says only the intro video changed on PC | Region listed "USA"; no serial on the page | Free distribution ("distribuimos gratuitamente"), donations optional; no license text. Distributed as a patched game folder / PKG on a file host (not linked here, not downloaded) | https://www.romhacking.net.br/index.php?topic=1214.0 and https://www.jumpmanclubbrasil.com.br/post/demons-souls |
| 3 | **Demons Souls Dublado PT-BR** (Nexus, mods/148) | WannaNowProds (summary) | Unknown | Voice dub only, not text | US and EU (summary) | Unknown | https://www.nexusmods.com/demonssouls/mods/148 (403) |

Not found: a PT-BR project on GitHub, RPCS3 forums, Tribo Gamer or other Brazilian sites beyond #1 and #2. YouTube and X posts exist that show a PT-BR game on RPCS3 (e.g. https://www.youtube.com/watch?v=gIWV2uK1P7w, https://x.com/marcelluzduarte/status/1526247039952207874) but those pages could not be read for details, so which translation they use is unknown.

### Other languages (same technique, possibly)
| Project | Notes |
|---|---|
| Polish Translation - Spolszczenie (Nexus mods/103) | Summary: replaces English text **and the font** with Polish; 512 MB file. https://www.nexusmods.com/demonssouls/mods/103 (403) |
| Catalan (mods/186), Improved French texts (mods/52) | Exist per search results; contents unread. https://www.nexusmods.com/demonssouls/mods/186, https://www.nexusmods.com/demonssouls/mods/52 |
| Spanish HD fonts + Xbox buttons (Nexus mods/46) | Credited to Mora2403, EddyHg80, NakuNeko; listed as HD Spanish fonts for **BLES00932** (summary). https://www.nexusmods.com/demonssouls/mods/46 |

EU disc languages: English, French, German, Spanish, Italian per retailer/archive listings (https://gamegear.net/archive/games/ps3/demons-souls-europe-enfrdeesit, https://retrobroker.com/en-US/us/products/demons-souls-ps3-ri6z9k; summaries). The official wiki says only "English, subtitled Spanish" and "at least English, French and German text" (https://www.demonssouls.com/Versions), so which of these are menus vs subtitles is **unverified**. No Portuguese on any official PS3 disc.

## 2. What they did about the font (stated vs inferred)

- **#2 (JumpManClub)**: the project page lists "Acentos: Nao acentuado" (unaccented). **Stated:** no accents. **Inference:** it never touched the font; it replaced the English FMG text with Portuguese written without diacritics, which needs only the existing ASCII glyphs. The page does not mention fonts or tools. The 2019 thread also says nothing about them.
- **#1 (Nova Traducao)**: a search-engine summary of the page says it "adds accent support to the US version, but the author recommends the European version, which already supports accents" **(unverified: summary; a second summary of the same page did not mention accents)**. Technique unknown. **Inference:** on EU the font likely already contains Latin-1 accents (Spanish, French, German, Italian text ship there), so only FMGs change; on US the author must have extended the font.
- **Polish and Spanish mods**: "replaces text and font" / "HD Spanish fonts" (summaries). Technique unread.
- **Tooling that exists** (stated by its README, https://github.com/thegreatgramcracker/CCM-Editor): **CCM Editor**, GPL-3.0, tested with Demon's Souls, adds glyphs by Unicode id, edits texture coordinates, widths and padding; says new languages need "font texture edits + FMG edits + this tool" (no step-by-step). Texture Count must match the TPF. Unknown header fields Unk0E, Unk1C, Unk1D should not be changed. This matches our own parse of the format (docs/fonts.md): the standard technique is **add code groups and glyph records to the CCM, draw the glyphs into free atlas space in the TPF, and use the real Unicode code point in the FMG text** (no re-encoding, no swapping characters onto other codes). That is an inference about what accent mods do; the mechanism itself is verified by our format analysis.
- **Texture packs** (stated: https://github.com/SonofUgly/DeS-Texture-Pack): the "High Resolution Font" re-renders the **English** atlas only ("Currently only supports English"; edits `font/na_english` TPFs; extraction with horkrux's DeS-BNDBuild fork, replace `.dds`, rebuild `.tpf.dcx`). Its `_src` folder names the typeface used ("Iwata Mincho Pro Bold"), a commercial Japanese face; whether the original game font is that face is **unknown**. A summary of the Nexus page says the EU install target is `font/eu/` (unverified).

Licensing consequence: the HD font, CCM Editor (GPL-3.0, so no code reuse; we use the format knowledge only), and the translations are all third-party works; none of their files or text may be copied into the repo.

## 3. Glossary source (PS5 remake PT-BR)

- **Confirmed:** the PS5 remake has Portuguese (Brazil) voice and on-screen text per the official store page (https://www.playstation.com/pt-br/games/demons-souls/). Its text is Sony/Bluepoint copyright.
- **Use:** as a terminology reference only (names of places, items, NPCs, boss names, trophy titles), looked up by the project owner or a maintainer on a legally owned copy or in published guides; record decisions as a glossary of short terms with their source tag and do not copy descriptions or dialogue. No term list was compiled here: searches did not return verifiable PT-BR place names (only "Boletaria" kept as is, and the Old One rendered "Anciao" in press coverage). **Open:** the project owner to confirm the glossary terms from the PS5 game.
- Caution: the 2019 fan translation (#2) was criticized for leaving some weapon names untranslated and rendering one weapon oddly; it is not a safe glossary base. The 2026 retranslation (#1) claims better quality (author's own claim).

## 4. Candidate collaborators (for the project owner to decide; nobody was contacted)

1. AudaxTenebra / IvoryMage, authors of Nova Traducao PT-BR on Nexus (most recent, most complete; likely have the accent solution).
2. AlanMugiwara-san and AndyFF (JumpManClub Brasil), authors of the 2019 translation; Dirk (romhacking) for tooling.
3. William Cordeiro, in-game reviewer of the 2019 project.
4. SonofUgly (HD font), EddyHg80 / Mora2403 / NakuNeko (Spanish HD fonts for EU): font know-how, EU accent coverage.
5. thegreatgramcracker (CCM Editor): format questions.

Ask each about: permission to use their translated strings as a base, their glossary, and the accent method. Model: we would ship tools plus an install-time generator, never their files, unless they explicitly license them.

## Sources
- https://www.nexusmods.com/demonssouls/mods/182 (403; via search summary)
- https://www.romhacking.net.br/index.php?topic=1214.0
- https://www.jumpmanclubbrasil.com.br/post/demons-souls
- https://github.com/thegreatgramcracker/CCM-Editor
- https://github.com/SonofUgly/DeS-Texture-Pack
- https://www.demonssouls.com/Versions
- https://gamegear.net/archive/games/ps3/demons-souls-europe-enfrdeesit
- https://www.playstation.com/pt-br/games/demons-souls/
