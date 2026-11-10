# Robô Vistoria → Claude → Relatórios

Automação para Windows em que **o Claude comanda e o bot salva**, todo dia às 16:00:

1. O bot **lê o arquivo que o app Vistoria gera** (a fonte do dia) e entrega o texto ao Claude;
2. O bot pergunta ao **Claude Code** qual o próximo relatório (modo `claude -p`, sem olhar a tela);
3. O Claude responde no formato do protocolo (abaixo); o bot **salva como arquivo** numa pasta;
4. O bot volta ao Claude (`--continue`, mantendo a memória do dia) e pede o **próximo**;
5. Isso se repete **até o Claude responder `ACAO: nada`** (zerou o que foi pedido) ou atingir o limite de segurança.

> ℹ️ **Sobre o muse.ai:** o envio automático ao muse.ai foi **removido**, porque o muse.ai não oferece uma API utilizável para isso. O robô agora apenas **gera e salva** os relatórios em arquivos prontos — o envio ao muse (se você quiser) é feito manualmente, do jeito que preferir.

### O protocolo (como o Claude comanda)

O Claude responde sempre assim:

```
ACAO: salvar
TITULO: nome-curto-sem-espacos
CONTEUDO:
<o texto completo do relatório>
```

E, quando não há mais nada no dia:

```
ACAO: nada
```

---

## ⭐ Jeito mais fácil (clicar nos `.bat`)

Depois de baixar a pasta no seu PC, você faz quase tudo clicando duas vezes:

| Arquivo | O que faz |
|---|---|
| `instalar.bat` | Instala a leitura de PDF (só precisa se o Vistoria for PDF) |
| `verificar.bat` | **Confere se está tudo pronto** e diz o que falta |
| `rodar.bat` | Roda de verdade (é o que o Agendador usa às 16:00) |

**Ordem recomendada:** `verificar.bat` → (resolver o que faltar) → `rodar.bat`.

Os mesmos passos pela linha de comando:
```bash
python claude_muse_bot.py --verificar
python claude_muse_bot.py --agora
```

---

## 1. Pré-requisitos (instalar uma vez)

1. **Claude Code** instalado e já logado nesta máquina. Teste no terminal:
   ```bash
   claude --version
   ```
   Se não reconhecer o comando, instale o Claude Code e faça login antes de continuar.

2. **Python 3** (marque "Add Python to PATH" ao instalar). Teste:
   ```bash
   python --version
   ```

3. **Só se o Vistoria exportar PDF**, instale a leitura de PDF:
   ```bash
   pip install pypdf
   ```
   (Se o Vistoria salva `.txt`, não precisa instalar nada.)

---

## 2. Onde ficam as pastas (já configurado)

- **Entra** (arquivo do Vistoria): `Área de Trabalho\VistoriaMuse`
- **Sai** (relatórios gerados): `Área de Trabalho\VistoriaMuse\relatorios`

São pastas separadas de propósito: o bot nunca confunde o próprio arquivo de saída com o arquivo de entrada do Vistoria. O código encontra a Área de Trabalho sozinho (mesmo com OneDrive).

---

## 3. Ajustar o `config.json`

- Em `vistoria`: **onde o app Vistoria salva o arquivo do dia.**
  - `modo: "arquivo_mais_recente"` + `pasta` + `padrao_arquivo` (ex.: `*.txt`, `*.pdf`) → pega o arquivo mais novo da pasta; **ou**
  - `modo: "caminho_fixo"` + `caminho_fixo` → sempre o mesmo arquivo.
  - Teste a leitura: `python claude_muse_bot.py --testar-vistoria`
- Em `claude.prompt_inicial`: a instrução que abre o dia (já traz o protocolo). Ajuste para dizer **o que são os relatórios do dia**.
- Em `arquivos.extensao_relatorio`: `txt` ou `md`.

---

## 4. Conferir tudo e rodar

```bash
python claude_muse_bot.py --verificar
```
Resolva o que aparecer como `[FALTA]`. Quando der **TUDO PRONTO**, rode:
```bash
python claude_muse_bot.py --agora
```
Os relatórios aparecem em `Área de Trabalho\VistoriaMuse\relatorios`. O `execucao.log` (na pasta do projeto) mostra o que aconteceu.

---

## 5. Fazer rodar sozinho todo dia às 16:00

### Opção A — Agendador de Tarefas do Windows (recomendado)
1. Abra o **Agendador de Tarefas**.
2. *Criar Tarefa Básica* → nome: `Relatorio Vistoria`.
3. Disparador: **Diariamente**, às **16:00**.
4. Ação: **Iniciar um programa** → o `rodar.bat` desta pasta.

### Opção B — deixar o script vigiando o horário
```bash
python claude_muse_bot.py --daemon
```
Deixe a janela aberta; ele dispara sozinho às 16:00.

---

## Comandos do robô

| Comando | Para quê |
|---|---|
| `--verificar` | Confere se está tudo pronto e diz o que falta |
| `--testar-vistoria` | Mostra o texto lido do app Vistoria |
| `--testar-claude` | Testa se o Claude Code responde |
| `--agora` | Roda o dia inteiro uma vez |
| `--daemon` | Fica ligado e dispara sozinho às 16:00 |

## Limites honestos
- Se o Vistoria exporta **PDF**, instale `pypdf`.
- O robô para sozinho por segurança quando o Claude responde `ACAO: nada` ou ao atingir `max_iteracoes`.
