# Installer (`tools/install_ptbr.py`)

Applies the pack to a **copy** of the player's own BLUS30443 files and undoes it. Python 3 standard library only; no network.

```
install_ptbr.py install   --game GAMEDIR --out NEWDIR     copy GAMEDIR to NEWDIR (plain copy, no links), apply there
install_ptbr.py install   --game GAMEDIR --in-place       apply to GAMEDIR itself (only for a folder that is already a copy)
install_ptbr.py uninstall --game GAMEDIR [--force]        put the saved originals back
install_ptbr.py status    --game GAMEDIR
```
`GAMEDIR` is the folder that contains `PS3_GAME` (or `PS3_GAME/USRDIR`).

## What it does
1. Refuses anything that is not BLUS30443 (checked in `PS3_GAME/PARAM.SFO`) and refuses `--out` inside or around `--game`.
2. Decodes the player's own `font/na_english/{dsfont24,talkfont24}` and `msg/na_english/{item,menu}.msgbnd` (from their `.dcx`, or the plain file if that is all there is), derives the accented glyphs (`gen_ptbr_glyphs.py`), builds the Portuguese archives (`fmg_tool.py import`; ids missing from `text/` keep the game's own text) and checks that every character of the Portuguese text has a glyph in `dsfont24` (a symbol missing from `talkfont24` only gets a note).
3. Writes **six files** as `.dcx` (the game opens only the `.dcx` names): `font/na_english/{dsfont24,talkfont24}.{ccm,tpf}.dcx` and `msg/na_english/{item,menu}.msgbnd.dcx`. The plain twins are untouched.
4. Before overwriting, saves each original under `USRDIR/.ptbr-backup/` with a `manifest.json` (SHA-256 of the original and of the installed file).

`uninstall` restores the originals and removes the backup folder. It skips a file whose hash no longer matches the installed one (something else changed it) unless `--force`. Tested: uninstall gives six files byte-identical to the original dump, and installing again works.

## Interaction with Soulbrandt (public information only; unverified where marked)
- The runtime reads the game through `PS3_VFS_ROOT`, a folder holding `PS3_GAME`; the installer targets exactly such a folder. Verified: with the pack applied to a copy and `PS3_VFS_ROOT` pointing at it, the unmodified exe shows the Portuguese text.
- Soulbrandt's public README does not say whether its setup copies the game, re-verifies files or checks hashes. **Unknown.** If a setup step re-copies or re-imports the game, run the installer again afterwards. A hash check against the original dump would see six changed files; `manifest.json` lists the original hashes, and `uninstall` restores them.
- Its self-update replaces the program (it asks first and keeps saves and settings); it is not documented to touch the game folder, so the pack should survive updates. Unverified.
- Never run the installer on the dump you keep as the source: use `--out`.

## Soulbrandt: the game folder is never written (2026-11-10)
Soulbrandt's setup can use the game straight from RPCS3's library ("Import from RPCS3"); its `setup/ready.txt` then names RPCS3's own folder (`game=C:\...\rpcs3...\games\Demons Souls BLUS30443`). An earlier draft of `ptbr_soulbrandt.py` would have written there; it never did, because it stopped earlier on another error. Now the tool never writes to the folder ready.txt names. It builds `<setup's folder>/ptbr-game`: real copies of `PS3_GAME/USRDIR/{font,msg,menu}` (about 85 MB) and of the loose files (EBOOT.BIN, PARAM.SFO and the rest, about 35 MB), and directory junctions to every other folder. ready.txt's `game=` line is pointed there and the original path is kept in `ptbr-game/.ptbr-source.txt`; `desinstalar` points it back, removes the junctions as links only and deletes the folder. A failed install puts ready.txt back at once. Tested on a sandbox layout: install, reinstall, status and uninstall; the source folder's 213 files were byte-identical afterwards and ready.txt was restored byte for byte.

Also: when `setup-folder.txt` names a folder setup never built in, the tool uses the usual folder (`%LOCALAPPDATA%\DemonsSoulsRecomp`) if that one holds ready.txt. And the installer finds `Soulbrandt.exe` up to three folders above the pack, for the extra folder Windows' "Extract all" adds.

## Loading screens (`gen_ptbr_loading.py`)

`menu/00.tpf.dcx` ... `16.tpf.dcx` are the 17 loading screens: one 1024x1024 DXT1 texture each, full mip chain
(699064 bytes). The upper 1024x720 is the picture; the character's name is painted at the top left (dark
lettering that darkens the parchment) and NOW LOADING next to the emblem (gold lettering that lightens it).
NOW LOADING is in the same place on all 17 screens (x 305..501, cap top y 652); the name's position is found per
screen. The HD font mod (DeS_ButtonGlyphs) changes only the strip below y 720 of these files, so the tool works
on both.

On the player's PC, from the player's copy: the English letter pixels (found against an 11 px median of the paper)
are filled back by normalised blur plus the paper grain of the rows next to them; the Portuguese line is set in
EB Garamond semibold (SIL OFL, `tools/fonts/`) at the size and spacing fitted to the English lines
(name 33.5 px + 7.4, NOW LOADING 23.6 px + 4.3), coloured with the factor or offset measured from the original
letters. Only the changed 4x4 blocks of level 0 are replaced; mips down to 4x4 are rebuilt. Names that are the
same in both languages (Satsuki, Selen Vinland) keep the original lettering. About 1 s per screen.

## HD font mod: an explicit choice (`--fonts hd|original`)

Decided with the product owner (2026-11-10): the HD font mod (DeS_ButtonGlyphs 1.00 / SonofUgly's High Resolution
Font) is optional and most players will not have it. One installer covers both; the player chooses explicitly.

- `install_ptbr.font_mod(usr)` compares each font `.dcx` the game opens (from `.ptbr-backup` if installed) with
  the disc's plain twin: equal -> the game's own fonts; different with an identical CCM and a 4x atlas -> `hd`;
  anything else -> `other` (unknown mod: the original fonts are used, with a note).
- `ptbr_soulbrandt.py instalar` asks only when `hd` is found ("1 - Fontes HD do mod / 2 - Fontes originais");
  `--fontes hd|original` answers it on the command line.
- `--fonts original` builds on the plain twins (the HD mod is off while the translation is installed);
  `--fonts hd` builds on the mod's own `.dcx`.
- `gen_ptbr_glyphs.py` works at the atlas scale it finds (S = atlas / CCM size: 1 or 4). With S = 1 the output is
  byte-identical to the tested build. With S = 4 the accents are the font's own HD marks (`~` `^` `` ` `` and the
  rest; dsfont24's acute and diaeresis were left at the old resolution by the mod, so the acute is the mirrored
  grave and the diaeresis two periods), scaled to the room; letters' cells are cleaned of neighbours' ink that
  reaches into them (`drop_edge_specks`); the new CCM rects are written normalised to the 2048 atlas.
- Uninstall restores the mod's HD files byte for byte (tested).
- The HD mod also replaces `menu/menu.tpf.dcx` and the strip below y 720 of the loading screens; the banners and
  loading screens are built on whatever is there.
