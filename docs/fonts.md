# Fonts: CCM + TPF, and how the accented letters are derived (BLUS30443, US disc)

Everything here was measured on the player's own copy of the game; no game data is stored in this repository. The tool is `tools/gen_ptbr_glyphs.py`; `tools/install_ptbr.py` runs it for you.

## 1. Format (confirmed by parsing both fonts end to end)

### CCM (big-endian; size is exactly `0x20 + 12*groups + 24*glyphs`)
| Offset | Type | Meaning |
|---|---|---|
| 0x00 | u32 | version `0x00010000` |
| 0x04 | u32 | file size |
| 0x08 | u16 | font height (26 in `dsfont24`, 28 in `talkfont24`; the atlas cell rows are 26 in both) |
| 0x0A / 0x0C | u16 | texture width / height (512 / 512) |
| 0x0E | u16 | unknown (32), left unchanged |
| 0x10 / 0x12 | u16 | number of code groups / number of glyphs |
| 0x14 / 0x18 | u32 | offset of the code groups (0x20) / of the glyph records |
| 0x1C..0x1F | bytes | `01 01 <texture count> 00` |

Code group = `u32 first, u32 last, u32 index of the first glyph`: Unicode code points, sorted ascending. Glyph record (24 bytes) = `f32 u0, v0, u1, v1` (normalised rectangle in the atlas) then `u16 left-pad, width, advance, texture index`. The meaning of pad and advance is inferred from the data; the in-game results below are consistent with it.

### TPF texture
`TPF\0` header with 32-byte entries. Each font texture is DXT5, 512x512, full mip chain (349,552 bytes), standard DXT blocks (not byte-swapped). `dsfont24.tpf` has two textures (0: button icons, 1: letters), `talkfont24.tpf` one. The glyph's texture index equals the TPF entry order.

**What the texture channels hold (corrected after the in-game test):**
- `dsfont24`: alpha is the glyph shape and the colour is plain white.
- `talkfont24`: alpha is a solid silhouette and **the colour channel carries the letter's inner detail** (bright strokes, dark fill, four grey levels per block with the endpoint 0). A glyph built from alpha alone draws in the game as a solid blob. The generator therefore decodes and re-encodes both planes.

### Which glyphs exist (US fonts)
Both fonts hold ASCII, a few symbols, Greek, Cyrillic, punctuation, Roman numerals, arrows, math and 237 empty box placeholders for CJK; there are **no Latin letters with diacritics**. `talkfont24` has no `®`. The atlas is used down to row 391; rows 392 to 511 are empty (four cell rows of 26 pixels).

## 2. Text encoding
Message archives are BND3 files of FMGs with NUL-terminated UTF-16BE strings. Characters are looked up by Unicode code point in the CCM groups, so Portuguese text stores `U+00E1` for a-acute and the font needs a group that covers it. **Verified in the game:** a code point that exists only in a group we added is found and drawn.

## 3. Technique: derive the accented letters from the game's own glyphs
The tool reads the player's atlas, composes `base letter + accent mark` (marks are cut from the font's own accent glyphs, or drawn with the measured stroke weight for circumflex and tilde), writes the new cells into the empty band, adds code groups and glyph records, and re-encodes only the DXT blocks that overlap the new cells at every mip level. Nothing from the game is shipped: the result exists only on the player's PC.

- 28 glyphs for PT-BR: `á â ã à ç é ê í ó ô õ ú`, the same in capitals, `ü Ü`, and the ordinals `ª º`.
- Capitals have no headroom (2 rows in `dsfont24`, 0 in `talkfont24`) and the glyph record has no vertical offset, so accented capitals are squashed vertically to make room for the mark. This is the one visible compromise.
- Lowercase marks keep one empty row above the letter, or two in `talkfont24` (bold face with little headroom; with one row the mark merged into the letter when the game scaled the text down).
- Each new glyph copies the base letter's pad, width and advance, so line layout is unchanged.
- Latin-1 for other languages is available with `--set latin1`.

## 4. In-game results (BLUS30443 US, Soulbrandt build, 1714x964 window)
- Text and fonts must be delivered under the **`.dcx` names**: the game opens only those for `msg/na_english` and `font/na_english` and does not fall back to the plain files.
- `dsfont24` accents display correctly in menus, dialogs, Options, character creation, inventory, equipment and the HUD; capitals such as `Ã` in "PADRÃO" read well at this size.
- `talkfont24` accents display correctly after the colour-plane fix (checked by running its files in the menu font slot of a test copy, which exercises the same glyph data at menu size).
- Early builds of the tool showed accents as dark stripes (wrong colour block copied) and, in `talkfont24`, as blobs (colour channel ignored). Both are fixed.

## 5. Which font draws which text
Proven with marker glyphs (a test copy where `e` was drawn as another letter in one font at a time): `dsfont24` draws the title menu, the server dialog, Options, profile creation, the START menu, item names and short descriptions and the HUD item name. `talkfont24` draws the bottom-of-screen subtitle line seen during a movie. Not established: NPC conversation boxes, item long descriptions and blood messages.

## 6. Open
European disc fonts (`font/eu/`) are not examined; the tool skips any code point the font already has. The look of squashed capitals in `talkfont24` is unchecked.
