# Robô Claude Code → muse.ai

Automação para Windows em que **o Claude comanda e o bot executa**, todo dia às 16:00:

1. O bot **lê o arquivo que o app Vistoria gera às 16:00** (a fonte do dia) e entrega o texto ao Claude;
2. O bot pergunta ao **Claude Code** qual a próxima atualização (modo `claude -p`, sem olhar a tela);
3. O Claude responde no formato do protocolo (abaixo); o bot **salva como arquivo** e **publica no muse.ai pela API** (cabeçalho `Key`);
4. O bot volta ao Claude (`--continue`, mantendo a memória do dia) e pede a **próxima**;
5. Isso se repete **até o Claude responder `ACAO: nada`** (zerou o que foi pedido) ou atingir o limite de segurança.

### O protocolo (como o Claude comanda)

O Claude responde sempre assim:

```
ACAO: upload
TITULO: nome-curto-sem-espacos
CONTEUDO:
<o texto completo da atualização>
```

E, quando não há mais nada no dia:

```
ACAO: nada
```

Se um upload falhar, o bot **avisa o Claude com a mensagem de erro** e deixa ele decidir (reenviar corrigido ou parar). Assim, o dia inteiro é conduzido pelo Claude, sem você precisar mexer.

> ℹ️ Como o envio ao muse.ai é pela **API**, o robô **não precisa** mexer no seu mouse/teclado nem ter o navegador aberto. (O controle de tela só é usado se você desligar a API e escolher o modo navegador.)

---

## ⭐ Jeito mais fácil (clicar nos `.bat`)

Depois de baixar a pasta no seu PC, você pode fazer quase tudo clicando duas vezes:

| Arquivo | O que faz |
|---|---|
| `instalar.bat` | Instala as bibliotecas (uma vez só) |
| `verificar.bat` | **Confere se está tudo pronto** e diz o que falta |
| `simular.bat` | Roda o dia inteiro **sem enviar ao muse** (teste seguro) |
| `rodar.bat` | Roda de verdade (é o que o Agendador usa às 16:00) |

**Ordem recomendada:** `instalar.bat` → `verificar.bat` → (resolver o que faltar) → `simular.bat` → `rodar.bat`.

Os mesmos passos pela linha de comando:
```bash
python claude_muse_bot.py --verificar
python claude_muse_bot.py --simular
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

3. As bibliotecas:
   ```bash
   pip install requests pyautogui pyperclip
   ```
   (`requests` = API do muse.ai; `pyautogui`/`pyperclip` = só o loop de dúvidas no navegador.)

4. **A chave da API do muse.ai.** Pegue a chave na sua conta do muse.ai e cole no `config.json`, no campo `muse_api.chave`, entre as aspas:
   ```json
   "muse_api": {
     "chave": "cole_sua_chave_aqui",
     ...
   }
   ```
   (Alternativa avançada: deixar `chave` vazio e usar a variável de ambiente `MUSE_API_KEY` via `setx`.) Confira com:
   ```bash
   python claude_muse_bot.py --testar-muse
   ```

---

## 2. Testar se o Claude responde

```bash
python claude_muse_bot.py --testar-claude
```
Deve aparecer algo como *"OK, estou funcionando."*. Se der erro aqui, o problema é o Claude Code (instalação/login) — resolva antes de seguir.

---

## 3. Descobrir as posições da tela (calibrar) — só para o loop de dúvidas

Se você **não** vai usar o loop de dúvidas (`muse.tratar_duvidas: false` no config), **pule este passo** — a API não precisa de coordenadas.

O loop de dúvidas precisa saber **onde clicar** no navegador. Abra a janela na tela e rode:

```bash
python claude_muse_bot.py --calibrar
```

Passe o mouse por cima de cada ponto e anote o `x` e `y` que aparecem:

- **campo_entrada_xy** → onde você digita no muse (a caixa de texto);
- **area_resposta_xy** → onde o muse mostra a resposta/dúvida;
- **botao_enviar_xy** → (opcional) o botão de enviar. Se o muse enviar com Enter, deixe `null`.

Pressione `Ctrl+C` para sair do calibrador.

---

## 4. Ajustar o `config.json`

Abra o `config.json` e preencha:

- Em `vistoria`: **onde o app Vistoria salva o arquivo do dia.**
  - Já vem apontando para a pasta **`VistoriaMuse` na Área de Trabalho** (o código acha a Área de Trabalho sozinho, mesmo com OneDrive). O atalho `AREA_DE_TRABALHO` nos caminhos significa isso.
  - `modo: "arquivo_mais_recente"` + `pasta` + `padrao_arquivo` (ex.: `*.txt`, `*.pdf`) → pega o arquivo mais novo da pasta; **ou**
  - `modo: "caminho_fixo"` + `caminho_fixo` → sempre o mesmo arquivo (se o app sobrescreve diariamente).
  - Se o Vistoria exporta **PDF**, mude o padrão para `*.pdf` e instale: `pip install pypdf`.
  - Teste a leitura: `python claude_muse_bot.py --testar-vistoria`

> 📁 **Organização das pastas (já configurada):**
> - **Entra** (arquivo do Vistoria): `Área de Trabalho\VistoriaMuse`
> - **Sai** (o que o bot envia ao muse): `Área de Trabalho\VistoriaMuse\enviados_muse`
>
> São pastas separadas de propósito: assim o bot nunca confunde o próprio arquivo de saída com o arquivo de entrada do Vistoria.
- Em `claude.prompt_inicial`: a instrução que abre o dia (já traz o protocolo). Ajuste para dizer **o que são as atualizações do dia** e de onde o Claude tira o que precisa fazer. **Quanto mais específico, melhor.**
- Em `claude.prompt_proximo`: a mensagem que pede a próxima atualização (normalmente não precisa mexer).
- Em `claude.continuar_conversa`: `true` para o Claude lembrar o que já foi feito no dia (usa `claude --continue`).
- Em `muse_api.ativo`: `true` para subir pela API (recomendado). `collection_id` é opcional (ID da coleção do muse onde o arquivo deve entrar).
- Em `arquivos.extensao_relatorio`: `txt` ou `md`. (Obs.: o muse.ai é feito para **vídeo** — veja "Limites honestos" abaixo.)
- Em `muse.tratar_duvidas`: `true` só se você vai usar o loop de dúvidas no navegador. Aí preencha também as coordenadas (`campo_entrada_xy`, `area_resposta_xy`) e `usar_enter_para_enviar`.
- Em `loop.texto_que_indica_fim`: palavras que, se aparecerem no navegador, significam "acabou" (ex.: `concluido`, `zerado`).

---

## 5. Rodar uma vez para testar

Abra o muse.ai, posicione a janela, e rode:

```bash
python claude_muse_bot.py --agora
```

Acompanhe o `execucao.log` e a pasta `relatorios/` (cada relatório é salvo lá também).

---

## 6. Fazer rodar sozinho todo dia às 16:00

### Opção A — Agendador de Tarefas do Windows (recomendado)

1. Abra o **Agendador de Tarefas** (Task Scheduler).
2. *Criar Tarefa Básica* → nome: `Relatorio Claude Muse`.
3. Disparador: **Diariamente**, às **16:00**.
4. Ação: **Iniciar um programa** → Programa: o `rodar.bat` desta pasta.
5. Marque "Executar somente quando o usuário estiver conectado" (precisa da tela ativa, pois usa mouse/teclado).

### Opção B — deixar o script vigiando o horário

```bash
python claude_muse_bot.py --daemon
```
Deixe essa janela aberta; ele dispara sozinho quando der 16:00. (Fecha a janela = para.)

---

## Limites honestos

- **O muse.ai é uma plataforma de vídeo.** O endpoint `/api/files/upload` é feito para vídeos. Se ele recusar um `.txt`/`.md`, o script mostra a mensagem exata do servidor. Nesse caso as opções são: transformar o relatório num vídeo (narração/slide) antes de subir, ou pôr o texto como **descrição de um vídeo**. Me avise a mensagem de erro que eu ajusto.
- **Loop de dúvidas** continua por teclado/mouse (é no navegador): depende de coordenadas; se a janela mudar de lugar/tamanho, **recalibre**. Se não precisar dele, deixe `muse.tratar_duvidas: false`.
- A chave da API fica na variável `MUSE_API_KEY`, **nunca** dentro do `config.json` commitado.
- O robô para sozinho por segurança quando: aparece um texto de fim, a resposta não muda, ou atinge `max_iteracoes`.
