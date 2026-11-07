# Localization pipeline: msgbnd/FMG text, tools, and how a language pack ships

Date: 2026-11-06. Tools: `tools/fmg_tool.py` (text), `tools/gen_ptbr_glyphs.py` (font). Fonts: `docs/fonts.md`. Third-party work: `docs/ptbr-translations.md`. Glossary: `docs/glossary-ptbr.md`.

## 1. Real size of the game text (BLUS30443, `msg/na_english`, measured by `fmg_tool.py report`)

| | Strings | Words |
|---|---|---|
| All FMG entries (32 FMGs in `item.msgbnd` + `menu.msgbnd`) | 10,196 | 112,356 |
| Unique source strings (exact English match, the real translation workload) | **5,828** | **37,548** |

Repetition is large: weapon lore has 1,821 entries but only 110 distinct texts (the same text for every upgrade level), weapon "descriptions" 38 distinct of 1,835. Translating by unique string (a translation memory keyed by the English text) and applying it to every id is the right model.

| Category (FMG id) | Strings | Words | Unique strings |
|---|---|---|---|
| dialogue (menu 1: NPC speech) | 1,347 | 12,286 | 1,300 |
| weapon lore (item 25) | 1,821 | 71,808 | 110 |
| weapon names (11) / descriptions (21) | 1,837 / 1,835 | 4,206 / 4,589 | 1,789 / 38 |
| goods names, descriptions, lore (10, 20, 24) | 132 each | 393 / 757 / 4,257 | 132 / 124 / 131 |
| armor names, desc, lore (12, 22, 26) | 112 / 93 / 93 | 232 / 128 / 2,181 | |
| accessories (13, 23, 27), magic (14, 28, 29), traits (15, 16, 17) | 27 to 40 each | small | |
| NPC names (18), place names (19) | 91, 35 | 177, 44 | 89, 35 |
| blood messages (menu 2: the message templates and word list) | 724 | 1,756 | 682 |
| event text (30), subtitles (3) | 345, 51 | 2,201, 461 | 282, 51 |
| menus: ingame (70), common (76), misc (77), dialogs (78), key guide (79), one-line help (80), item help (81), tag list (90) | 1,138 | about 4,000 | about 600 |

Not covered by FMG: about 7,100 UTF-16 strings inside the EBOOT (mostly debug menus), the movie subtitles inside the PAMF movies (if any), and any text baked into menu textures (title logo, some HUD labels). Not measured yet.

## 2. Formats (confirmed)

- `msg/<lang>/item.msgbnd`, `menu.msgbnd`: BND3 (big-endian), 0x18-byte entries, Shift-JIS names such as `N:\DemonsSoul\data\Msg\Data\<name>.fmg`. Entry id = FMG id.
- FMG: `u32 0x00010000, u32 size, u32 flags (0x01FF0000), u32 group count, u32 string count, u32 offset table position, u32 0`; then groups `(index of first string, first id, last id)`; then `u32` string offsets (0 = no text); then NUL-terminated UTF-16BE strings. Newline is U+000A: **line breaks are hard-coded in the strings** (the original wraps manually at about 46 characters in descriptions).
- Control codes are tags of the form `<?name?>` (for example `<?conclusion?>` for the confirm-button icon, `<?bmsg?>` for the blood-message slot, `<?joinChara?>` for a player name) plus printf-like `%%`. They must be preserved exactly. 40 distinct tags seen; the validator checks that the multiset of tags is identical to the English one.
- Characters are looked up by Unicode code point in the font's CCM groups, so Portuguese text is stored as ordinary UTF-16 (`U+00E1` for a-acute); the font must contain the glyph (`fonts.md`).
- The `.dcx` twin of each file is opened by the game whenever it exists (`overview.md` section 1.1), so a replacement pack must provide the `.dcx` name: the game never falls back to the plain file (proven in-game). `tools/dcx_tool.py pack` writes the EDGE variant the game itself uses, and the game loaded packs built with it (PT-BR menus, item names and dialogs displayed).

## 3. Tools (`tools/fmg_tool.py`; output stays outside the repo, e.g. `a local work folder`)

```
report   <USRDIR>                       strings / words / chars per category, plus unique counts
extract  <USRDIR> <dir>                 <dir>/<bnd>/<fmg>_<category>.json: id, en, pt, max_lines, max_chars, tags
worklist <dir> <category> <workdir>     numbered unique source strings (one per line) for a translator or an LLM
merge    <workdir> <category> <tmdir>   n<TAB>text translation lines -> translation memory {english: portuguese}
apply    <dir> <tmdir>                  fill pt of every entry from the memory (exact English match)
validate <dir> [--ccm a.ccm b.ccm]      untranslated, line count, pixel width vs English, tags, control chars, missing glyphs
import   <USRDIR> <dir> <outdir>        rebuild msgbnd files (untranslated entries keep the English text)
```
Limits: ids carry no speaker or screen. Context is the FMG category plus the neighbouring ids; per-NPC grouping is a TODO (ids of dialogue are grouped by character in ranges, `re-analyst` item). The width check uses the CCM advance widths against the English line (UI boxes were sized for English); the true box widths are not known and must be confirmed in game screenshots.

## 4. How the language pack should ship (options; not decided here)

Hard rules (the project rules): no copyrighted game data in the repo or in releases. The English source text and any translated string set that embeds it are game data for this purpose.

| Option | What ships | Legal risk | Notes |
|---|---|---|---|
| A. Translated strings only, merged on the player's PC | A file with Portuguese strings keyed by FMG id plus a hash of the English source (for sanity), and the generator tools | Medium: the Portuguese text is our own work, but it is a derivative of the game's expression (item lore, dialogue) and keyed to it. Short names and UI words are low risk; long lore and dialogue are the sensitive part | The player's machine builds the msgbnd from their own dump plus the strings; nothing of the English text ships. Most practical |
| B. Pack distributed as patched FMG/BND files | Complete replacement msgbnd | High: it contains the original structure and all untranslated strings | Avoid |
| C. Key by English string (translation memory) | `{english: portuguese}` | High: ships the English text as keys | Avoid; use a hash of the English instead (A) |
| D. Ask rights holders | Permission or a clean-room position | Cannot be settled by us | Requires the project owner's decision |

**Recommendation: option A**, with the key being the FMG id and an `en_hash` (SHA-256 of the English string) so the tool verifies that the player's dump matches (and reports mismatches instead of writing wrong text); the strings file is an optional language pack; plus generated fonts (`fonts.md`), all produced at install time, with a clear note in the README that the Portuguese text is a fan translation of copyrighted material shared as strings only, and an ADR before release. Legal review of the long lore/dialogue text belongs to the project owner; if a risk-averse path is wanted, ship UI strings and names first and keep lore and dialogue as a user-run import. Third-party translations are never bundled without written permission.

## 5. Status of the PT-BR translation

See `docs/status.md` (counts of translated and reviewed strings, updated per session). Nothing is reviewed by the project owner yet; everything is draft.
