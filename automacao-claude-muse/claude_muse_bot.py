# -*- coding: utf-8 -*-
"""
claude_muse_bot.py
==================
Robo que, todo dia as 16:00:
  1. Pede ao Claude Code (modo automatico `claude -p`) para gerar o relatorio em texto.
  2. Cola esse relatorio no muse.ai (navegador ja aberto).
  3. Le o que o muse.ai respondeu. Se houver uma "duvida", manda a duvida para o
     Claude, pega a resposta e cola de volta no muse.
  4. Repete ate o muse indicar que terminou (ou ate o limite de iteracoes).

IMPORTANTE - leia o README.md antes de usar.

Este script roda NA SUA MAQUINA WINDOWS. Ele controla teclado/mouse, entao durante
a execucao nao mexa no computador. Deixe o navegador com o muse.ai aberto e visivel.

Uso:
  python claude_muse_bot.py --calibrar     -> ajuda a descobrir as posicoes (x,y) da tela
  python claude_muse_bot.py --testar-claude -> so testa se o Claude Code responde
  python claude_muse_bot.py --agora         -> roda o fluxo completo UMA vez, agora
  python claude_muse_bot.py --daemon        -> fica rodando e dispara sozinho no horario da agenda
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

# ----------------------------------------------------------------------------
# Dependencias externas (instale com: pip install pyautogui pyperclip)
# Importadas de forma tolerante para que --testar-claude funcione sem elas.
# ----------------------------------------------------------------------------
try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = True  # jogue o mouse no canto superior esquerdo para abortar
    _GUI_OK = True
except Exception:  # pragma: no cover
    _GUI_OK = False

import muse_api  # modulo local: fala com o muse.ai pela API (sem clicar na tela)

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG_PADRAO = os.path.join(AQUI, "config.json")


# ============================================================================
# Utilidades
# ============================================================================
def carregar_config(caminho):
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def log(cfg, mensagem):
    carimbo = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{carimbo}] {mensagem}"
    print(linha, flush=True)
    try:
        caminho = os.path.join(AQUI, cfg["arquivos"]["arquivo_log"])
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass


def exigir_gui():
    if not _GUI_OK:
        print(
            "ERRO: as bibliotecas pyautogui/pyperclip nao estao instaladas.\n"
            "Rode:  pip install pyautogui pyperclip",
            file=sys.stderr,
        )
        sys.exit(2)


# ============================================================================
# Claude Code (modo automatico, sem olhar a tela)
# ============================================================================
def perguntar_ao_claude(cfg, prompt):
    """Chama `claude -p "<prompt>"` e devolve a resposta em texto.

    Esse e o jeito confiavel de falar com o Claude Code: nada de ler o terminal
    pela tela. O Claude Code precisa estar instalado e ja logado nesta maquina.
    """
    c = cfg["claude"]
    comando = [c["comando"], "-p", prompt]
    if c.get("modelo"):
        comando += ["--model", c["modelo"]]

    kwargs = {
        "capture_output": True,
        "text": True,
        "timeout": c.get("timeout_segundos", 300),
        "encoding": "utf-8",
        "errors": "replace",
    }
    if c.get("diretorio_de_trabalho"):
        kwargs["cwd"] = c["diretorio_de_trabalho"]

    # No Windows o executavel costuma ser claude.cmd; shell=True ajuda a encontrar.
    if os.name == "nt":
        kwargs["shell"] = True
        comando = " ".join(
            (f'"{p}"' if " " in p else p) for p in comando[:2]
        ) + f' "{prompt_escape(prompt)}"' + (
            f' --model {c["modelo"]}' if c.get("modelo") else ""
        )

    try:
        proc = subprocess.run(comando, **kwargs)
    except FileNotFoundError:
        raise RuntimeError(
            f"Nao encontrei o comando '{c['comando']}'. O Claude Code esta instalado "
            f"e no PATH? Teste no terminal:  claude --version"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("O Claude demorou demais para responder (timeout).")

    saida = (proc.stdout or "").strip()
    if proc.returncode != 0 and not saida:
        raise RuntimeError(
            f"Claude retornou erro (codigo {proc.returncode}): {(proc.stderr or '').strip()}"
        )
    return saida


def prompt_escape(texto):
    """Escapa aspas duplas para a linha de comando do Windows."""
    return texto.replace('"', '""')


# ============================================================================
# Interacao com o muse.ai (via teclado/mouse + area de transferencia)
# ============================================================================
def colar_texto(cfg, xy_campo, texto):
    """Clica no campo informado e cola o texto via Ctrl+V."""
    exigir_gui()
    pyperclip.copy(texto)
    time.sleep(0.3)
    pyautogui.click(xy_campo[0], xy_campo[1])
    time.sleep(0.4)
    # Limpa o campo antes de colar (Ctrl+A, Delete)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)


def enviar_no_muse(cfg):
    m = cfg["muse"]
    if m.get("botao_enviar_xy"):
        pyautogui.click(m["botao_enviar_xy"][0], m["botao_enviar_xy"][1])
    elif m.get("usar_enter_para_enviar", True):
        pyautogui.press("enter")
    time.sleep(0.5)


def ler_resposta_do_muse(cfg):
    """Seleciona a area de resposta do muse e copia o texto para a area de transferencia.

    Usa Ctrl+A/Ctrl+C na area clicada em vez de OCR -> bem mais confiavel.
    Retorna o texto lido (pode vir vazio se o site nao permitir selecionar).
    """
    exigir_gui()
    m = cfg["muse"]
    pyperclip.copy("")  # zera para detectar se algo foi copiado
    time.sleep(0.2)
    pyautogui.click(m["area_resposta_xy"][0], m["area_resposta_xy"][1])
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.3)
    try:
        return pyperclip.paste().strip()
    except Exception:
        return ""


# ============================================================================
# Fluxo principal de um dia
# ============================================================================
def rodar_uma_vez(cfg):
    log(cfg, "=== Iniciando execucao do dia ===")

    # 1) Gera o relatorio das 16:00 com o Claude
    log(cfg, "Pedindo o relatorio ao Claude Code...")
    relatorio = perguntar_ao_claude(cfg, cfg["claude"]["prompt_relatorio"])
    if not relatorio:
        log(cfg, "ERRO: o Claude devolveu um relatorio vazio. Abortando.")
        return
    caminho = salvar_relatorio(cfg, relatorio)
    log(cfg, f"Relatorio gerado ({len(relatorio)} caracteres) -> {caminho}")

    # 2) Envia o relatorio ao muse.ai
    if cfg.get("muse_api", {}).get("ativo", False):
        # Caminho CONFIAVEL: sobe o arquivo pela API (cabecalho Key), sem clicar na tela.
        log(cfg, "Enviando o relatorio ao muse.ai via API (upload de arquivo)...")
        try:
            resultado = muse_api.enviar_arquivo(cfg, caminho)
            log(cfg, f"Upload concluido. Resposta do muse.ai: {resultado}")
        except RuntimeError as e:
            log(cfg, f"ERRO no upload via API: {e}")
            return
    else:
        # Alternativa antiga: colar no navegador (depende de coordenadas da tela).
        log(cfg, "Colando o relatorio no muse.ai pelo navegador...")
        colar_texto(cfg, cfg["muse"]["campo_entrada_xy"], relatorio)
        enviar_no_muse(cfg)

    # 3) Loop de duvidas (opcional): quando a execucao trava esperando uma resposta,
    #    le a pergunta no navegador -> pergunta ao Claude -> cola a resposta de volta.
    if not cfg.get("muse", {}).get("tratar_duvidas", True):
        log(cfg, "Loop de duvidas desativado no config. Execucao do dia finalizada.")
        log(cfg, "=== Execucao do dia finalizada ===")
        return

    max_it = cfg["loop"]["max_iteracoes"]
    fins = [t.lower() for t in cfg["loop"].get("texto_que_indica_fim", [])]
    ultima_resposta = ""

    for i in range(1, max_it + 1):
        log(cfg, f"Aguardando resposta do muse (iteracao {i}/{max_it})...")
        time.sleep(cfg["muse"].get("segundos_espera_resposta", 20))

        resposta_muse = ler_resposta_do_muse(cfg)

        if not resposta_muse:
            log(cfg, "Nao consegui ler texto do muse (vazio). Encerrando o loop.")
            break

        # Condicao de fim: muse sinalizou que terminou
        baixo = resposta_muse.lower()
        if any(marca in baixo for marca in fins):
            log(cfg, "O muse sinalizou que o dia esta concluido. Encerrando.")
            break

        # Evita loop infinito se o conteudo nao mudou
        if resposta_muse == ultima_resposta:
            log(cfg, "A resposta do muse nao mudou. Encerrando o loop.")
            break
        ultima_resposta = resposta_muse

        # Trata como "duvida" -> manda ao Claude
        log(cfg, "Duvida recebida do muse. Perguntando ao Claude...")
        prompt_duvida = (
            "No contexto do relatorio das 16:00 que voce gerou, responda a esta "
            "pergunta/duvida de forma direta e pronta para colar:\n\n"
            + resposta_muse
        )
        try:
            resposta_claude = perguntar_ao_claude(cfg, prompt_duvida)
        except RuntimeError as e:
            log(cfg, f"ERRO ao falar com o Claude: {e}. Encerrando.")
            break

        if not resposta_claude:
            log(cfg, "Claude devolveu resposta vazia. Encerrando.")
            break

        log(cfg, "Colando a resposta do Claude de volta no muse...")
        colar_texto(cfg, cfg["muse"]["campo_entrada_xy"], resposta_claude)
        enviar_no_muse(cfg)
        time.sleep(cfg["loop"].get("segundos_entre_acoes", 2.0))
    else:
        log(cfg, "Limite de iteracoes atingido. Encerrando por seguranca.")

    log(cfg, "=== Execucao do dia finalizada ===")


def salvar_relatorio(cfg, texto):
    """Salva o relatorio num arquivo e devolve o caminho completo."""
    pasta = os.path.join(AQUI, cfg["arquivos"]["pasta_relatorios"])
    os.makedirs(pasta, exist_ok=True)
    ext = cfg["arquivos"].get("extensao_relatorio", "txt").lstrip(".")
    nome = dt.datetime.now().strftime(f"relatorio_%Y-%m-%d_%H%M.{ext}")
    caminho = os.path.join(pasta, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    return caminho


# ============================================================================
# Daemon: fica rodando e dispara no horario
# ============================================================================
def rodar_daemon(cfg):
    horario = cfg["agenda"]["rodar_todo_dia_as"]  # "16:00"
    log(cfg, f"Modo daemon ativo. Vou disparar todo dia as {horario}. (Ctrl+C para parar)")
    ja_rodou_hoje = None
    while True:
        agora = dt.datetime.now()
        hhmm = agora.strftime("%H:%M")
        hoje = agora.date()
        if hhmm == horario and ja_rodou_hoje != hoje:
            ja_rodou_hoje = hoje
            try:
                rodar_uma_vez(cfg)
            except Exception as e:
                log(cfg, f"ERRO inesperado na execucao: {e}")
        time.sleep(20)


# ============================================================================
# Calibrador: ajuda a descobrir as coordenadas (x,y) da tela
# ============================================================================
def calibrar():
    exigir_gui()
    print(
        "CALIBRADOR\n"
        "----------\n"
        "Mova o mouse ate o ponto desejado e leia a posicao (x, y) abaixo.\n"
        "Anote os valores e coloque no config.json:\n"
        "  - campo_entrada_xy  = onde voce digita no muse.ai\n"
        "  - area_resposta_xy  = onde o muse mostra a resposta/duvida\n"
        "  - botao_enviar_xy   = (opcional) o botao de enviar\n\n"
        "Pressione Ctrl+C para sair.\n"
    )
    try:
        while True:
            x, y = pyautogui.position()
            print(f"  posicao atual -> x={x:5d}  y={y:5d}", end="\r", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nCalibrador encerrado.")


# ============================================================================
# main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="Robo Claude Code <-> muse.ai")
    ap.add_argument("--config", default=CONFIG_PADRAO, help="caminho do config.json")
    ap.add_argument("--calibrar", action="store_true", help="descobrir coordenadas da tela")
    ap.add_argument("--testar-claude", action="store_true", help="so testa o Claude Code")
    ap.add_argument("--testar-muse", action="store_true", help="confere a chave da API do muse.ai")
    ap.add_argument("--agora", action="store_true", help="roda o fluxo completo uma vez")
    ap.add_argument("--daemon", action="store_true", help="fica rodando e dispara no horario")
    args = ap.parse_args()

    if args.calibrar:
        calibrar()
        return

    cfg = carregar_config(args.config)

    if args.testar_claude:
        print("Testando o Claude Code (pode levar alguns segundos)...")
        r = perguntar_ao_claude(cfg, "Responda apenas: OK, estou funcionando.")
        print("Resposta do Claude:\n", r)
        return

    if args.testar_muse:
        print(muse_api.testar_conexao(cfg))
        return

    if args.agora:
        rodar_uma_vez(cfg)
        return

    if args.daemon:
        rodar_daemon(cfg)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
