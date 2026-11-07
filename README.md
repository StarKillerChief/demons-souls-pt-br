# Demon's Souls: tradução PT-BR (versão de teste)

**Esta é a primeira versão, feita para testes. A tradução ainda está sendo lapidada e revisada: espere frases estranhas, textos largos demais para a caixa e termos que vão mudar.**

Projeto de fãs, sem fins lucrativos, **sem qualquer ligação** com a FromSoftware, a Sony, a Atlus, a Bluepoint ou com o autor do Soulbrandt. Demon's Souls e todos os nomes e textos do jogo pertencem aos seus donos. O texto em português aqui é uma tradução própria, feita a partir do inglês, com ajuda de inteligência artificial (IA) e revisão humana em andamento. Os nomes de lugares, itens e personagens seguem, quando possível, a terminologia do remake de PS5; os diálogos são escritos por nós.

## Como usar
Você precisa da **sua própria cópia** do jogo (BLUS30443, versão americana). Nada do jogo está neste repositório: nem textos em inglês, nem fontes, nem imagens. O instalador reconstrói as fontes com acentos e os arquivos de texto no seu PC, a partir da sua cópia.

```
python tools/install_ptbr.py install --game "PASTA_COM_PS3_GAME" --out "NOVA_PASTA"
python tools/install_ptbr.py uninstall --game "NOVA_PASTA"
```
O instalador **copia** o jogo para a pasta nova antes de aplicar (a sua pasta original nunca é alterada), mexe só em 6 arquivos, guarda os originais com SHA-256 e desfaz tudo com `uninstall`. Veja `docs/installer.md`.

## O que tem aqui
- `text/`: só o português, por arquivo e id (as entradas iguais ao original foram removidas).
- `tools/`: instalador, gerador de fontes, conversor de texto, escritor de `.dcx`.
- `docs/`: glossário, status, formatos, resultados dos testes e a lista do que o repositório público teria.

---

# Demon's Souls: PT-BR translation (test version)

**This is the first version, made for testing. The translation is still being polished and reviewed: expect awkward lines, text too wide for its box, and terms that will change.**

A fan project, non-commercial, **not affiliated** with FromSoftware, Sony, Atlus, Bluepoint or the author of Soulbrandt. Demon's Souls and all its names and text belong to their owners. The Portuguese here is our own translation, written from the English, with **AI assistance** and human review in progress. Names of places, items and characters follow the PS5 remake's terminology where possible; dialogue is our own wording.

## Usage
You need **your own copy** of the game (BLUS30443, US). No game data is in this repository: no English text, fonts or images. The installer rebuilds the accented fonts and the text archives on your PC from your copy. It copies the game to a new folder first, so your original folder is never modified, touches six files only, saves the originals with SHA-256 and undoes everything with `uninstall` (see `docs/installer.md`).

## Status and licence
Draft; nothing is final. The tools are under the MIT licence (`LICENSE`). The Portuguese text is a free fan translation of someone else's copyrighted work; `NOTICE.md` says what that means.
