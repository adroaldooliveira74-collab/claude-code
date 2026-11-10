# -*- coding: utf-8 -*-
"""
claude_muse_bot.py
==================
Robo que, todo dia as 16:00:
  1. Le o arquivo que o app Vistoria gera (a fonte do dia).
  2. Entrega esse texto ao Claude Code (modo automatico `claude -p`), que comanda
     as atualizacoes do dia UMA DE CADA VEZ (protocolo ACAO/TITULO/CONTEUDO).
  3. Para cada atualizacao, salva um arquivo e publica no muse.ai pela API.
  4. Volta ao Claude (mantendo a memoria do dia) e pede a proxima, ate 'ACAO: nada'.

IMPORTANTE - leia o README.md antes de usar. Roda NA SUA MAQUINA WINDOWS.

Uso (comandos):
  python claude_muse_bot.py --verificar        -> confere se esta tudo pronto para rodar
  python claude_muse_bot.py --testar-vistoria  -> mostra o texto lido do app Vistoria
  python claude_muse_bot.py --testar-claude    -> testa se o Claude Code responde
  python claude_muse_bot.py --testar-muse      -> confere a chave da API do muse.ai
  python claude_muse_bot.py --simular          -> roda o dia inteiro SEM enviar ao muse (teste seguro)
  python claude_muse_bot.py --agora            -> roda o fluxo completo UMA vez, de verdade
  python claude_muse_bot.py --daemon           -> fica rodando e dispara sozinho no horario
  python claude_muse_bot.py --calibrar         -> (so para o modo navegador) descobre posicoes da tela
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
# Caminhos
# ============================================================================
def pasta_area_de_trabalho():
    """Descobre a Area de Trabalho do Windows (considera OneDrive)."""
    lar = os.path.expanduser("~")
    candidatos = [
        os.path.join(lar, "OneDrive", "Desktop"),
        os.path.join(lar, "OneDrive", "Area de Trabalho"),
        os.path.join(lar, "Desktop"),
        os.path.join(lar, "Area de Trabalho"),
    ]
    for c in candidatos:
        if os.path.isdir(c):
            return c
    return os.path.join(lar, "Desktop")  # padrao, mesmo que ainda nao exista


def expandir_caminho(p):
    """Expande atalhos nos caminhos do config:
      AREA_DE_TRABALHO  -> a Area de Trabalho do usuario
      ~                 -> a pasta do usuario
    Caminhos relativos ficam relativos a pasta do script.
    """
    if not p:
        return p
    p = p.strip()
    marcador = "AREA_DE_TRABALHO"
    if p.upper().startswith(marcador):
        resto = p[len(marcador):].lstrip("\\/").replace("\\", os.sep).replace("/", os.sep)
        return os.path.join(pasta_area_de_trabalho(), resto) if resto else pasta_area_de_trabalho()
    p = os.path.expanduser(p).replace("\\", os.sep)
    if not os.path.isabs(p):
        p = os.path.join(AQUI, p)
    return p


def garantir_pastas(cfg):
    """Cria as pastas de entrada (Vistoria) e saida (enviados ao muse), se faltarem.
    Devolve (pasta_entrada, pasta_saida)."""
    entrada = ""
    v = cfg.get("vistoria", {})
    if v.get("modo", "arquivo_mais_recente") != "caminho_fixo":
        entrada = expandir_caminho(v.get("pasta", ""))
        if entrada:
            os.makedirs(entrada, exist_ok=True)
    saida = expandir_caminho(cfg.get("arquivos", {}).get("pasta_relatorios", ""))
    if saida:
        os.makedirs(saida, exist_ok=True)
    return entrada, saida


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
def perguntar_ao_claude(cfg, prompt, continuar=False):
    """Chama `claude -p "<prompt>"` e devolve a resposta em texto.

    Esse e o jeito confiavel de falar com o Claude Code: nada de ler o terminal
    pela tela. O Claude Code precisa estar instalado e ja logado nesta maquina.

    continuar=True adiciona `--continue`, para o Claude LEMBRAR o que ja foi feito
    hoje (mantem a mesma conversa). Assim ele vai comandando uma atualizacao de
    cada vez ate zerar o que foi pedido.
    """
    c = cfg["claude"]
    flags = []
    if c.get("modelo"):
        flags += ["--model", c["modelo"]]
    if continuar and c.get("continuar_conversa", True):
        flags += ["--continue"]

    kwargs = {
        "capture_output": True,
        "text": True,
        "timeout": c.get("timeout_segundos", 300),
        "encoding": "utf-8",
        "errors": "replace",
    }
    if c.get("diretorio_de_trabalho"):
        kwargs["cwd"] = c["diretorio_de_trabalho"]

    if os.name == "nt":
        # No Windows o executavel costuma ser claude.cmd; shell=True ajuda a encontrar.
        kwargs["shell"] = True
        comando = (
            f'"{c["comando"]}" -p "{prompt_escape(prompt)}"'
            + ("".join(f" {f}" for f in flags))
        )
    else:
        comando = [c["comando"], "-p", prompt] + flags

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


# ----------------------------------------------------------------------------
# Protocolo: o Claude comanda, o bot executa.
# O Claude responde SEMPRE neste formato:
#     ACAO: upload        (ou 'nada' quando nao ha mais nada hoje)
#     TITULO: nome-curto
#     CONTEUDO:
#     <texto da atualizacao>
# ----------------------------------------------------------------------------
def parsear_resposta_claude(texto):
    """Le a resposta do Claude no protocolo e devolve {acao, titulo, conteudo}."""
    acao, titulo, conteudo_linhas = "nada", "", []
    coletando = False
    for linha in (texto or "").splitlines():
        sem = linha.strip()
        baixo = sem.lower()
        if not coletando and baixo.startswith("acao:"):
            acao = sem.split(":", 1)[1].strip().lower()
        elif not coletando and baixo.startswith("titulo:"):
            titulo = sem.split(":", 1)[1].strip()
        elif not coletando and baixo.startswith("conteudo:"):
            coletando = True
            resto = sem.split(":", 1)[1]
            if resto.strip():
                conteudo_linhas.append(resto.lstrip())
        elif coletando:
            conteudo_linhas.append(linha)
    conteudo = "\n".join(conteudo_linhas).strip()
    # Normaliza a acao: qualquer coisa que nao seja upload com conteudo = parar.
    if acao != "upload" or not conteudo:
        acao = "nada"
    return {"acao": acao, "titulo": titulo, "conteudo": conteudo}


def _limpar_nome(titulo):
    """Transforma um titulo em nome de arquivo seguro."""
    seguro = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in titulo).strip("-")
    return seguro or "atualizacao"


# ============================================================================
# App Vistoria: le o arquivo que o app gera todo dia as 16:00
# ============================================================================
def ler_texto_vistoria(cfg):
    """Le o texto gerado pelo app Vistoria (fonte do dia) a partir de um arquivo.

    Dois modos (config 'vistoria.modo'):
      - 'caminho_fixo'       : sempre o mesmo arquivo (o app sobrescreve diariamente)
      - 'arquivo_mais_recente': o arquivo mais novo da pasta que bate com o padrao
    Suporta .txt/.csv/.md direto; .pdf precisa da lib 'pypdf' (pip install pypdf).
    """
    import glob

    v = cfg.get("vistoria", {})
    modo = v.get("modo", "arquivo_mais_recente")

    if modo == "caminho_fixo":
        caminho = expandir_caminho(v.get("caminho_fixo", ""))
        if not caminho:
            raise RuntimeError("Config 'vistoria.caminho_fixo' esta vazio.")
        if not os.path.isfile(caminho):
            raise RuntimeError(f"Arquivo do Vistoria nao encontrado: {caminho}")
    else:
        pasta = expandir_caminho(v.get("pasta", ""))
        padrao = v.get("padrao_arquivo", "*.txt").strip()
        if not pasta or not os.path.isdir(pasta):
            raise RuntimeError(f"Pasta do Vistoria invalida: {pasta!r}")
        candidatos = glob.glob(os.path.join(pasta, padrao))
        if not candidatos:
            raise RuntimeError(
                f"Nenhum arquivo em {pasta} bate com o padrao {padrao!r}."
            )
        caminho = max(candidatos, key=os.path.getmtime)

    log(cfg, f"Lendo texto do Vistoria: {caminho}")
    ext = os.path.splitext(caminho)[1].lower()

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except Exception:
            raise RuntimeError(
                "O arquivo do Vistoria e PDF. Instale a leitura de PDF:  pip install pypdf"
            )
        leitor = PdfReader(caminho)
        texto = "\n".join((pg.extract_text() or "") for pg in leitor.pages).strip()
    else:
        # txt/csv/md e afins: tenta utf-8, cai para latin-1.
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                texto = f.read().strip()
        except UnicodeDecodeError:
            with open(caminho, "r", encoding="latin-1") as f:
                texto = f.read().strip()

    if not texto:
        raise RuntimeError(f"O arquivo do Vistoria foi lido mas esta vazio: {caminho}")
    return texto


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
# Fluxo principal de um dia: o Claude comanda, o bot executa, ate zerar.
# ============================================================================
def publicar_no_muse(cfg, caminho, simular=False):
    """Publica o arquivo no muse.ai. API se ativa (confiavel); senao, pelo navegador.
    Em modo simular, nao envia nada: apenas registra que o arquivo ficou pronto."""
    if simular:
        log(cfg, f"[SIMULACAO] NAO enviei ao muse. Arquivo pronto em: {caminho}")
        return
    if cfg.get("muse_api", {}).get("ativo", False):
        log(cfg, f"Enviando '{os.path.basename(caminho)}' ao muse.ai via API...")
        resultado = muse_api.enviar_arquivo(cfg, caminho)
        log(cfg, f"Upload concluido. Resposta do muse.ai: {resultado}")
    else:
        with open(caminho, "r", encoding="utf-8") as f:
            texto = f.read()
        log(cfg, "Colando no muse.ai pelo navegador...")
        colar_texto(cfg, cfg["muse"]["campo_entrada_xy"], texto)
        enviar_no_muse(cfg)


def rodar_uma_vez(cfg, simular=False):
    """O Claude vai mandando as atualizacoes uma a uma; o bot publica cada uma
    no muse.ai e volta ao Claude, ate ele responder que nao ha mais nada (zerou).
    simular=True faz tudo menos enviar ao muse (teste seguro)."""
    modo = " [SIMULACAO]" if simular else ""
    log(cfg, f"=== Iniciando execucao do dia (Claude comanda, bot executa){modo} ===")
    garantir_pastas(cfg)
    c = cfg["claude"]
    max_it = cfg["loop"]["max_iteracoes"]

    # Primeira mensagem = protocolo + pedido da 1a atualizacao.
    prompt = c.get("prompt_inicial") or c.get("prompt_relatorio")

    # Anexa o texto do app Vistoria (fonte do dia), se configurado.
    if cfg.get("vistoria", {}).get("ativo", False):
        try:
            texto_vistoria = ler_texto_vistoria(cfg)
        except RuntimeError as e:
            log(cfg, f"ERRO ao ler o texto do Vistoria: {e}. Abortando o dia.")
            return
        log(cfg, f"Texto do Vistoria carregado ({len(texto_vistoria)} caracteres).")
        prompt = (
            prompt
            + "\n\n=== TEXTO DO APP VISTORIA (fonte do dia, use como base) ===\n"
            + texto_vistoria
        )

    publicadas = 0

    for i in range(1, max_it + 1):
        continuar = i > 1  # da 2a chamada em diante, mantem a memoria da conversa
        log(cfg, f"Pedindo a atualizacao #{i} ao Claude...")
        try:
            resposta = perguntar_ao_claude(cfg, prompt, continuar=continuar)
        except RuntimeError as e:
            log(cfg, f"ERRO ao falar com o Claude: {e}. Encerrando.")
            break

        ordem = parsear_resposta_claude(resposta)
        if ordem["acao"] == "nada":
            log(cfg, f"Claude indicou que nao ha mais nada hoje. Zerado. "
                     f"Total publicado: {publicadas}.")
            break

        caminho = salvar_relatorio(cfg, ordem["conteudo"], titulo=ordem["titulo"])
        log(cfg, f"Atualizacao '{ordem['titulo'] or '(sem titulo)'}' "
                 f"gerada ({len(ordem['conteudo'])} chars) -> {caminho}")

        # Executa a publicacao. Se falhar, avisa o Claude e deixa ele decidir.
        try:
            publicar_no_muse(cfg, caminho, simular=simular)
            publicadas += 1
            prompt = c.get("prompt_proximo") or (
                "Publiquei com sucesso. Qual a proxima atualizacao? Responda no mesmo "
                "formato (ACAO/TITULO/CONTEUDO), ou 'ACAO: nada' se zeramos tudo hoje."
            )
        except RuntimeError as e:
            log(cfg, f"ERRO ao publicar no muse.ai: {e}")
            prompt = (
                "Falha ao publicar a atualizacao anterior no muse.ai. Mensagem do "
                "servidor:\n" + str(e) + "\n\nDecida: reenvie corrigido no mesmo "
                "formato (ACAO/TITULO/CONTEUDO) ou responda 'ACAO: nada' para parar."
            )

        time.sleep(cfg["loop"].get("segundos_entre_acoes", 2.0))
    else:
        log(cfg, "Limite de iteracoes atingido. Encerrando por seguranca.")

    log(cfg, "=== Execucao do dia finalizada ===")


def salvar_relatorio(cfg, texto, titulo=""):
    """Salva a atualizacao num arquivo e devolve o caminho completo."""
    pasta = expandir_caminho(cfg["arquivos"]["pasta_relatorios"])
    os.makedirs(pasta, exist_ok=True)
    ext = cfg["arquivos"].get("extensao_relatorio", "txt").lstrip(".")
    prefixo = _limpar_nome(titulo) if titulo else "relatorio"
    nome = dt.datetime.now().strftime(f"{prefixo}_%Y-%m-%d_%H%M%S.{ext}")
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
# Verificador: confere se esta tudo pronto para rodar
# ============================================================================
def _claude_responde(cfg):
    """Retorna (ok, detalhe) testando `claude --version`."""
    c = cfg["claude"]
    try:
        if os.name == "nt":
            proc = subprocess.run(
                f'"{c["comando"]}" --version', shell=True, capture_output=True,
                text=True, timeout=30, encoding="utf-8", errors="replace",
            )
        else:
            proc = subprocess.run(
                [c["comando"], "--version"], capture_output=True, text=True,
                timeout=30, encoding="utf-8", errors="replace",
            )
    except Exception as e:
        return False, str(e)
    if proc.returncode == 0:
        return True, (proc.stdout or "").strip()
    return False, (proc.stderr or proc.stdout or "codigo != 0").strip()


def verificar(cfg):
    """Checa cada pre-requisito e imprime um relatorio simples do que falta."""
    print("\n=== VERIFICACAO DO ROBO VISTORIA -> muse.ai ===\n")
    problemas = 0

    def linha(ok, titulo, dica=""):
        nonlocal problemas
        marca = "[ OK ]" if ok else "[FALTA]"
        print(f"{marca} {titulo}")
        if not ok:
            problemas += 1
            if dica:
                print(f"        -> {dica}")

    # 1) Python
    linha(sys.version_info >= (3, 7), f"Python {sys.version.split()[0]}",
          "Instale o Python 3 em python.org (marque 'Add to PATH').")

    # 2) Biblioteca requests (API do muse)
    usa_api = cfg.get("muse_api", {}).get("ativo", False)
    try:
        import requests  # noqa: F401
        tem_requests = True
    except Exception:
        tem_requests = False
    if usa_api:
        linha(tem_requests, "Biblioteca 'requests' (envio ao muse.ai)",
              "Rode:  pip install requests")

    # 3) pyautogui/pyperclip (so no modo navegador)
    if not usa_api:
        linha(_GUI_OK, "Bibliotecas pyautogui/pyperclip (modo navegador)",
              "Rode:  pip install pyautogui pyperclip")

    # 4) pypdf (so se o Vistoria for PDF)
    padrao = cfg.get("vistoria", {}).get("padrao_arquivo", "*.txt").lower()
    if cfg.get("vistoria", {}).get("modo") == "caminho_fixo":
        padrao = cfg["vistoria"].get("caminho_fixo", "").lower()
    if padrao.endswith(".pdf") or padrao.endswith("*.pdf"):
        try:
            import pypdf  # noqa: F401
            tem_pypdf = True
        except Exception:
            tem_pypdf = False
        linha(tem_pypdf, "Biblioteca 'pypdf' (ler PDF do Vistoria)",
              "Rode:  pip install pypdf")

    # 5) Claude Code
    ok_claude, det_claude = _claude_responde(cfg)
    linha(ok_claude, f"Claude Code responde ({det_claude[:60] if ok_claude else 'nao'})",
          "Instale e faca login no Claude Code. Teste:  claude --version")

    # 6) Pastas (cria se faltar)
    entrada, saida = garantir_pastas(cfg)
    if entrada:
        linha(os.path.isdir(entrada), f"Pasta de entrada do Vistoria: {entrada}")
    if saida:
        linha(os.path.isdir(saida), f"Pasta de saida (enviados ao muse): {saida}")

    # 7) Arquivo do Vistoria encontrado e legivel
    try:
        texto = ler_texto_vistoria(cfg)
        linha(True, f"Arquivo do Vistoria encontrado ({len(texto)} caracteres)")
    except Exception as e:
        linha(False, "Arquivo do Vistoria encontrado",
              f"{e}")

    # 8) Chave da API do muse
    if usa_api:
        try:
            muse_api.testar_conexao(cfg)
            linha(True, "Chave da API do muse.ai configurada")
        except Exception as e:
            linha(False, "Chave da API do muse.ai configurada", f"{e}")

    print()
    if problemas == 0:
        print(">>> TUDO PRONTO! Agora rode um teste seguro:  python claude_muse_bot.py --simular")
    else:
        print(f">>> Faltam {problemas} item(ns) acima. Resolva e rode --verificar de novo.")
    print()
    return problemas == 0


# ============================================================================
# main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="Robo Claude Code <-> muse.ai")
    ap.add_argument("--config", default=CONFIG_PADRAO, help="caminho do config.json")
    ap.add_argument("--verificar", action="store_true", help="confere se esta tudo pronto para rodar")
    ap.add_argument("--calibrar", action="store_true", help="descobrir coordenadas da tela (modo navegador)")
    ap.add_argument("--testar-claude", action="store_true", help="so testa o Claude Code")
    ap.add_argument("--testar-muse", action="store_true", help="confere a chave da API do muse.ai")
    ap.add_argument("--testar-vistoria", action="store_true", help="mostra o texto lido do app Vistoria")
    ap.add_argument("--simular", action="store_true", help="roda o dia inteiro SEM enviar ao muse")
    ap.add_argument("--agora", action="store_true", help="roda o fluxo completo uma vez, de verdade")
    ap.add_argument("--daemon", action="store_true", help="fica rodando e dispara no horario")
    args = ap.parse_args()

    if args.calibrar:
        calibrar()
        return

    cfg = carregar_config(args.config)

    if args.verificar:
        verificar(cfg)
        return

    if args.testar_claude:
        print("Testando o Claude Code (pode levar alguns segundos)...")
        r = perguntar_ao_claude(cfg, "Responda apenas: OK, estou funcionando.")
        print("Resposta do Claude:\n", r)
        return

    if args.testar_muse:
        print(muse_api.testar_conexao(cfg))
        return

    if args.testar_vistoria:
        texto = ler_texto_vistoria(cfg)
        print(f"--- Texto do Vistoria ({len(texto)} caracteres) ---\n")
        print(texto[:2000] + ("\n\n[...truncado...]" if len(texto) > 2000 else ""))
        return

    if args.simular:
        rodar_uma_vez(cfg, simular=True)
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
