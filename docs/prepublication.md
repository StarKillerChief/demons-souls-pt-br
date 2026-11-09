# Pre-publication check (the repository stays private; this is what a public one would contain)

Checked 2026-11-07 on the working tree and on history; commits after the squash re-checked 2026-11-09 (no local paths, e-mail, keys or game files; author is the noreply address).

| Check | Result |
|---|---|
| Local paths, e-mail or machine names in files | Removed from docs and tools (work-folder paths are now "a local work folder"; the default text source is read from the git-ignored `tools/.sync_src` or `PTBR_SRC`). Commit author is the GitHub noreply address. |
| Same in commit history | History squashed to one root commit of the cleaned tree on 2026-11-07. GitHub can keep old commits reachable by their hash, so publish from a NEW repository holding only this tree rather than flipping this one to public. |
| English source strings | `text/` compared with the English source: 0 entries equal, 7 near-equal (cries such as "Hehehe", a name, button-tag strings). Docs and tools quote no game sentence (every line of 18+ characters of the English corpus was searched in them: only the place name "Valley of Defilement" matched, in the glossary). |
| Game files | No fonts, atlases, previews, archives or images in tree or history; `.gitignore` blocks `*.ccm *.tpf *.dcx *.msgbnd *.fmg *.png *.bnd`. |
| Key material | None (no hex strings of 32+ digits, no key headers). |
| README | PT-BR and English: fan project, AI assistance, own copy required, not affiliated, first test version, draft status. |

## Licences
- **Tools** (`tools/`): **MIT** (`LICENSE`). They contain no game data.
- **Portuguese text** (`text/`): a translation of Demon's Souls, which belongs to its rights holders. See `NOTICE.md`. We claim nothing beyond our own wording; it is strings only and works only with the player's own copy. Item lore, dialogue and names are derivative of the original. No permission has been asked of anyone.
- **Glossary names**: taken from public pages about the PS5 remake where marked `PS5-press`; dialogue is never copied from it.
- Third-party translations are not used or bundled.

## What a public repository would contain
`README.md`, `text/` (32 JSON files, 9,763 Portuguese entries), `tools/` (`ptbr_soulbrandt.py`, `install_ptbr.py`, `gen_ptbr_glyphs.py`, `gen_ptbr_banners.py`, `fmg_tool.py`, `dcx_tool.py`, `font_mark.py`, `sync_text.py`, `movie_subs/`, `release/`), `docs/` (this file, `installer.md`, `soulbrandt-test.md`, `fonts.md`, `localization.md`, `glossary-ptbr.md`, `ptbr-translations.md`, `status.md`).

## The release zip (built by `tools/release/build_pack.py`, attached to a GitHub release, never committed)
- Our tools and `text/`, the subtitle stand-in DLL compiled from `tools/movie_subs/avcodec_shim.cpp` (our code, no FFmpeg code), the official Python 3.13.9 embeddable package (PSF licence, checked by SHA-256) and the Pillow 12.0.0 wheel (MIT-CMU/HPND). Their licence texts ship inside the zip; `TERCEIROS.txt` points to them.
- `gen_ptbr_banners.py` names the five English banner phrases (a few words each) so it can find the letters in the player's own textures; no other game text is quoted.
