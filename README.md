<p align="center">
  <img src="docs/assets/banner.svg" alt="Demon's Souls — Tradução PT-BR para o Soulbrandt" width="900">
</p>

<p align="center">
  <a href="../../releases/latest"><img alt="Versão" src="https://img.shields.io/badge/vers%C3%A3o-0.1%20(teste)-b59a6a?style=flat-square"></a>
  <img alt="Jogo" src="https://img.shields.io/badge/jogo-BLUS30443%20(EUA)-5c5142?style=flat-square">
  <a href="LICENSE"><img alt="Licença das ferramentas" src="https://img.shields.io/badge/ferramentas-MIT-3d6b4a?style=flat-square"></a>
  <img alt="Feito por fãs" src="https://img.shields.io/badge/feito%20por-f%C3%A3s-1e9447?style=flat-square">
</p>

<p align="center">
  <b>Demon's Souls inteiro em português do Brasil, no PC, com o <a href="https://github.com/JonathanDC64/Soulbrandt">Soulbrandt</a>.</b><br>
  Menus, itens, magias, diálogos, legendas dos vídeos, letreiros e telas de carregamento.
</p>

> [!IMPORTANT]
> **Nenhum arquivo do jogo vem neste repositório ou no pacote.** Nem textos em inglês, nem fontes, nem imagens.
> O instalador monta tudo no seu PC, a partir da **sua própria cópia** do jogo, e desfaz tudo quando você desinstala.

> [!NOTE]
> **v0.1 é uma versão de teste.** A tradução ainda está sendo revisada: espere algumas frases estranhas e termos que
> ainda vão mudar. Achou algo? [Abra uma issue](../../issues) com um print.

## Sumário

- [O que é traduzido](#o-que-é-traduzido)
- [Onde funciona](#onde-funciona)
- [Antes de começar](#antes-de-começar)
- [Como instalar](#como-instalar)
- [Fontes HD (opcional)](#fontes-hd-opcional)
- [Atualizações e desinstalação](#atualizações-e-desinstalação)
- [Problemas conhecidos](#problemas-conhecidos)
- [Perguntas frequentes](#perguntas-frequentes)
- [Como ajudar](#como-ajudar)
- [Créditos e avisos](#créditos-e-avisos)
- [English summary](#english-summary)

## O que é traduzido

| | |
|---|---|
| ✅ **Menus e textos de sistema** | Inventário, equipamento, status, opções, mensagens na tela |
| ✅ **Itens, armas, armaduras, anéis e magias** | Nomes e descrições, com a terminologia do remake de PS5 sempre que possível |
| ✅ **Diálogos** | Todos os personagens, escritos por nós a partir do inglês |
| ✅ **Legendas dos vídeos** | Abertura e cenas, com moldura no estilo do jogo (só no Soulbrandt) |
| ✅ **Letreiros grandes** | VOCÊ MORREU, DEMÔNIO DESTRUÍDO, ALMA PERDIDA RECUPERADA e os outros |
| ✅ **Telas de carregamento** | Os 17 nomes de personagens e o CARREGANDO, sobre a arte original |
| ✅ **Acentos de verdade** | á, â, ã, à, ç, é, ê, í, ó, ô, õ, ú, nas fontes originais e nas fontes HD |

Os acentos são feitos a partir das próprias letras do jogo, para combinar com a fonte original. Os textos foram
medidos contra as caixas de cada tela para não passarem das bordas.

## Onde funciona

| Onde | Situação |
|---|---|
| **Soulbrandt** (PC) | ✅ Suportado. É o jeito recomendado. |
| **RPCS3** (emulador) | 🔜 Planejado para o instalador novo (os textos funcionam; as legendas dos vídeos dependem do Soulbrandt) |
| **PS3** | 🔜 Planejado: gerar uma pasta com os arquivos traduzidos para copiar para o console |

Por enquanto, só a versão americana do jogo (**BLUS30443**). A versão europeia (BLES00932) ainda não.

## Antes de começar

1. Tenha o **Soulbrandt** instalado e funcionando com a sua cópia do jogo.
2. Abra o `Soulbrandt.exe` pelo menos uma vez, deixe ele preparar o jogo até o fim e feche.

Não precisa instalar o Python nem mais nada: tudo o que o instalador usa já vem no pacote, como no próprio Soulbrandt.

## Como instalar

1. Baixe o **`PT-BR-Soulbrandt.zip`** na página de [Releases](../../releases/latest).
2. Extraia o zip **dentro da pasta onde está o `Soulbrandt.exe`**. Vai aparecer uma pasta `PT-BR` ao lado dele.
3. Abra a pasta `PT-BR` e dê dois cliques em **`Instalar-PT-BR.bat`**.
   Se o Windows mostrar "O Windows protegeu o computador", clique em *Mais informações* → *Executar assim mesmo*.
4. Espere aparecer **"Pronto!"** (menos de um minuto) e abra o Soulbrandt normalmente.

O passo a passo completo também está no `LEIA-ME.txt` do pacote.

> [!TIP]
> O instalador nunca altera a pasta original do jogo nem a do RPCS3: ele monta uma pasta própria para a tradução e
> aponta o Soulbrandt para ela. Os seus saves não são tocados.

## Fontes HD (opcional)

A tradução funciona com as **fontes originais do jogo**; você **não precisa** de nenhum mod de fonte.

Se você usa o mod de fontes HD (*High Resolution Font* / *DeS_ButtonGlyphs*, do Nexus Mods), o instalador percebe
sozinho e pergunta com qual fonte você quer jogar:

- **Fontes HD do mod**: letras e acentos em alta resolução;
- **Fontes originais do jogo**: como no PS3 (o mod de fontes fica desligado enquanto a tradução estiver instalada).

O mod de fontes HD é de outro autor e não vem neste pacote. Para trocar de fonte depois, rode o instalador de novo.

## Atualizações e desinstalação

- **O Soulbrandt foi atualizado?** A atualização desfaz a tradução. Abra o Soulbrandt uma vez, deixe ele preparar o
  jogo, feche e rode `Instalar-PT-BR.bat` de novo.
- **Voltar ao inglês:** dois cliques em `Desinstalar-PT-BR.bat`, dentro da pasta `PT-BR`.

## Problemas conhecidos

- **Funções novas do Soulbrandt** (por exemplo, a *Respecialization* na estátua) ainda aparecem em inglês: esses textos
  ficam dentro do próprio `Soulbrandt.exe`, não nos arquivos do jogo.
- Alguns nomes longos de armas podem encostar na borda da caixa de itens.
- O símbolo ® não existe na fonte dos diálogos (também não aparece no jogo em inglês).

## Perguntas frequentes

<details>
<summary><b>Isso é pirataria? Preciso ter o jogo?</b></summary>

Precisa ter o jogo. Nada do jogo vem aqui: o instalador transforma os arquivos da **sua** cópia no seu PC.
</details>

<details>
<summary><b>Meus saves vão funcionar?</b></summary>

Sim. Os saves não são alterados, nem na instalação nem na desinstalação. Dá para alternar entre inglês e português
com o mesmo save.
</details>

<details>
<summary><b>O Windows avisou que o arquivo pode ser perigoso.</b></summary>

É o aviso padrão para programas que não são assinados digitalmente. Todo o código do instalador está neste repositório
para quem quiser conferir.
</details>

<details>
<summary><b>Posso jogar online?</b></summary>

A tradução só muda textos e imagens no seu PC; não altera nada da jogabilidade.
</details>

## Como ajudar

- Encontrou um erro de tradução, um texto passando da caixa ou um acento estranho? [Abra uma issue](../../issues)
  com um print e o lugar do jogo onde apareceu.
- Os textos ficam em [`text/`](text), um arquivo por tabela do jogo, só com o português. O glossário de termos está em
  [`docs/glossary-ptbr.md`](docs/glossary-ptbr.md).
- Detalhes técnicos do instalador: [`docs/installer.md`](docs/installer.md).

## Créditos e avisos

- **Soulbrandt**, de [JonathanDC64](https://github.com/JonathanDC64/Soulbrandt): o port de PC que torna tudo isto possível.
- **EB Garamond** (SIL Open Font License), usada nas telas de carregamento.
- **Python** e **Pillow**, embutidos no instalador (licenças em `TERCEIROS.txt`).
- Tradução, ferramentas e revisão: projeto de fãs, feito **com ajuda de inteligência artificial** e revisão humana.

Projeto sem fins lucrativos e **sem nenhuma ligação** com a FromSoftware, a Sony Interactive Entertainment, a Atlus,
a Bandai Namco, a Bluepoint ou com o autor do Soulbrandt. *Demon's Souls* e todos os nomes do jogo pertencem aos seus
donos. As ferramentas estão sob a licença MIT ([`LICENSE`](LICENSE)); o texto em português é uma tradução de fãs, gratuita
(veja [`NOTICE.md`](NOTICE.md)).

---

## English summary

A fan-made **Brazilian Portuguese translation of Demon's Souls** (PS3, BLUS30443) for the
[Soulbrandt](https://github.com/JonathanDC64/Soulbrandt) PC port: menus, items, spells, dialogue, movie subtitles,
banners and loading screens. **No game data is included**: the installer builds the accented fonts, text archives
and images on your PC from your own copy, keeps backups, and restores everything on uninstall. Works with the game's
original fonts and, optionally, with the HD font mod. Made with AI assistance and human review. Not affiliated with
FromSoftware, Sony, Atlus, Bandai Namco, Bluepoint or the author of Soulbrandt. Tools: MIT licence.
