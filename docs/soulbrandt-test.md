# Test in Soulbrandt (2026-11-07)

Build: the unmodified `des_boot.exe` of a Soulbrandt 0.1.1-dev build (read-only), US disc BLUS30443. A new copy of the player's files was made, the pack was generated **from this repository only** (`tools/install_ptbr.py`, `text/`) and applied to the copy; saves, caches and settings were separate. Online off, sound muted, 1714x964 window. Screenshots stay local (they show game graphics and text).

## Result
The pack works. The game opens the `.dcx` names and shows Portuguese text with correct accents in: title ("PRESSIONE O BOTÃO START", "NOVO JOGO"), server dialog, brightness screen, Options, character creation, HUD item name, inventory (names, short descriptions, stats), equipment screen. `talkfont24` accents display correctly (its files were run in the menu font slot of a test copy; see `fonts.md`).

## Overflow and missing glyphs
- Missing glyphs: none. `®` is absent from `talkfont24` (installer note); the three strings containing it are dialogs drawn in `dsfont24`.
- Options: the label "Câmera Esquerda/Direita" is wider than its box and runs into the value field's arrow.
- Inventory: a short description ("Recupera uma pequena quantidade de PV do usuário") runs into the weight column on the same line.
- Inventory hint bar: ":Mudar Exibição de Status" is cut off at the right edge of the screen (the Equipment screen shows it whole).
- The validator also flags 533 entries as much wider or longer than the English; the real box sizes are unknown, so only on-screen checks count.

## Not reached
- NPC conversation boxes: needs a walk to an NPC after the tutorial.
- Movie subtitles with `ã` in Soulbrandt: this exe handed out no video frames for movies (log: "0 frames handed out"; the FFmpeg DLLs are not in the play folder), so no subtitle was drawn.
- Item long descriptions, blood messages.
