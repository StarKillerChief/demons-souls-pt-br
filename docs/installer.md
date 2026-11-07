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
