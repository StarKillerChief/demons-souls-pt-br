# Demon's Souls: tradução PT-BR para o Soulbrandt (v0.1, versão de teste)

**Esta é a primeira versão, feita para testes. A tradução ainda está sendo lapidada e revisada: espere frases estranhas, textos largos demais para a caixa e termos que vão mudar.**

Projeto de fãs, sem fins lucrativos, **sem qualquer ligação** com a FromSoftware, a Sony, a Atlus, a Bluepoint ou com o autor do Soulbrandt. Demon's Souls e todos os nomes e textos do jogo pertencem aos seus donos. O texto em português aqui é uma tradução própria, feita a partir do inglês, com ajuda de inteligência artificial (IA) e revisão humana em andamento. Os nomes de lugares, itens e personagens seguem, quando possível, a terminologia do remake de PS5; os diálogos são escritos por nós.

## Como instalar (jogadores)
Você precisa do **Soulbrandt** instalado e funcionando, com a **sua própria cópia** do jogo (BLUS30443, versão americana). Nada do jogo está neste repositório nem no pacote: nem textos em inglês, nem fontes, nem imagens.

1. Baixe o `PT-BR-Soulbrandt.zip` na página **Releases** deste repositório.
2. Extraia o zip **dentro da pasta onde está o `Soulbrandt.exe`**.
3. Abra a pasta `PT-BR` e dê dois cliques em `Instalar-PT-BR.bat`. Pronto.

Não precisa instalar o Python: ele vem dentro do pacote, como no próprio Soulbrandt. Para voltar ao inglês, use `Desinstalar-PT-BR.bat`. Depois de atualizar o Soulbrandt, rode o instalador de novo. O passo a passo completo está no `LEIA-ME.txt` do pacote.

O instalador monta as letras com acento, os textos, as legendas dos vídeos e os letreiros grandes no seu PC, a partir da sua cópia, guarda os originais com SHA-256 e desfaz tudo na desinstalação. Seus saves não são alterados. Detalhes técnicos: `docs/installer.md`.

## O que tem aqui
- `text/`: só o português, por arquivo e id (as entradas iguais ao original foram removidas).
- `tools/`: instalador, gerador de fontes, conversor de texto, escritor de `.dcx`.
- `docs/`: glossário, status, formatos, resultados dos testes e a lista do que o repositório público teria.

---

# Demon's Souls: PT-BR translation (test version)

**This is the first version, made for testing. The translation is still being polished and reviewed: expect awkward lines, text too wide for its box, and terms that will change.**

A fan project, non-commercial, **not affiliated** with FromSoftware, Sony, Atlus, Bluepoint or the author of Soulbrandt. Demon's Souls and all its names and text belong to their owners. The Portuguese here is our own translation, written from the English, with **AI assistance** and human review in progress. Names of places, items and characters follow the PS5 remake's terminology where possible; dialogue is our own wording.

## Installing (players)
You need **Soulbrandt** installed and working, with **your own copy** of the game (BLUS30443, US). No game data is in this repository or in the pack: no English text, fonts or images.

1. Download `PT-BR-Soulbrandt.zip` from this repository's **Releases** page.
2. Extract it **inside the folder that holds `Soulbrandt.exe`**.
3. Open the `PT-BR` folder and double-click `Instalar-PT-BR.bat`.

Python is bundled, as in Soulbrandt itself. `Desinstalar-PT-BR.bat` goes back to English; after a Soulbrandt update, run the installer again. The installer builds the accented fonts, the text archives, the movie subtitles and the big on-screen messages on your PC from your copy, keeps the originals with SHA-256 and restores them on uninstall. Saves are never touched. See `docs/installer.md`.

## Status and licence
Draft; nothing is final. The tools are under the MIT licence (`LICENSE`). The Portuguese text is a free fan translation of someone else's copyrighted work; `NOTICE.md` says what that means.
