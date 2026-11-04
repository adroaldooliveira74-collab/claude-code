# Robô Claude Code → muse.ai

Automação para Windows que, todo dia às 16:00:

1. Pede ao **Claude Code** para gerar o relatório em texto (modo automático `claude -p`, sem olhar a tela — confiável);
2. Cola o relatório no **muse.ai** aberto no navegador;
3. Lê o que o muse respondeu; se vier uma **dúvida**, manda para o Claude, pega a resposta e cola de volta;
4. Repete até o muse indicar que terminou (ou até o limite de segurança).

> ⚠️ **Leia isto antes de usar.** O robô controla seu teclado e mouse. Enquanto ele roda, **não mexa no computador** e deixe a janela do muse.ai aberta e visível. Para abortar na hora: jogue o mouse rápido para o **canto superior esquerdo** da tela.

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

3. As bibliotecas de automação:
   ```bash
   pip install pyautogui pyperclip
   ```

---

## 2. Testar se o Claude responde

```bash
python claude_muse_bot.py --testar-claude
```
Deve aparecer algo como *"OK, estou funcionando."*. Se der erro aqui, o problema é o Claude Code (instalação/login) — resolva antes de seguir.

---

## 3. Descobrir as posições da tela (calibrar)

O robô precisa saber **onde clicar** no muse.ai. Abra o muse.ai no navegador, deixe-o na tela e rode:

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

- Em `muse`: as coordenadas que você anotou.
- Em `claude.prompt_relatorio`: o texto exato do que o Claude deve gerar às 16:00. **Quanto mais específico, melhor.**
- Em `loop.texto_que_indica_fim`: palavras que, se aparecerem na resposta do muse, significam "acabou o dia" (ex.: `concluido`, `zerado`).
- Em `muse.usar_enter_para_enviar`: `true` se o site envia com Enter; senão preencha `botao_enviar_xy`.

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

- Como o muse.ai é operado **"clicando no site"** (sem API), tudo depende das coordenadas: se o layout do site mudar ou a janela mudar de lugar/tamanho, **recalibre**.
- A "dúvida" é lida copiando o texto da área que você apontou. Se o site não deixar selecionar/copiar aquele texto, essa parte do loop não funciona — aí o ideal seria usar a **API do muse.ai** (se existir na sua conta) e eu reescrevo essa parte de forma muito mais robusta.
- O robô para sozinho por segurança quando: o muse sinaliza fim, a resposta não muda, ou atinge `max_iteracoes`.
