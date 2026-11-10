# -*- coding: utf-8 -*-
"""
claude_muse_bot.py
==================
Robo que, todo dia as 16:00:
  1. Le o arquivo que o app Vistoria gera (a fonte do dia).
  2. Entrega esse texto ao Claude Code (modo automatico `claude -p`), que comanda
     os relatorios do dia UMA DE CADA VEZ (protocolo ACAO/TITULO/CONTEUDO).
  3. Para cada um, salva um arquivo de texto pronto na pasta de saida.
  4. Volta ao Claude (mantendo a memoria do dia) e pede o proximo, ate 'ACAO: nada'.

OBS: NAO ha mais envio ao muse.ai (o muse.ai nao tem API utilizavel). O robo
apenas gera e SALVA os relatorios em arquivos; o envio ao muse voce faz do jeito
que preferir.

IMPORTANTE - leia o README.md antes de usar. Roda NA SUA MAQUINA WINDOWS.

Uso (comandos):
  python claude_muse_bot.py --verificar        -> confere se esta tudo pronto para rodar
  python claude_muse_bot.py --testar-vistoria  -> mostra o texto lido do app Vistoria
  python claude_muse_bot.py --testar-claude    -> testa se o Claude Code responde
  python claude_muse_bot.py --agora            -> roda o fluxo completo UMA vez, agora
  python claude_muse_bot.py --daemon           -> fica rodando e dispara sozinho no horario
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

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
    """Cria as pastas de entrada (Vistoria) e saida (relatorios), se faltarem.
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


# ============================================================================
# Claude Code (modo automatico, sem olhar a tela)
# ============================================================================
def prompt_escape(texto):
    """Escapa aspas duplas para a linha de comando do Windows."""
    return texto.replace('"', '""')


def perguntar_ao_claude(cfg, prompt, continuar=False):
    """Chama `claude -p "<prompt>"` e devolve a resposta em texto.

    continuar=True adiciona `--continue`, para o Claude LEMBRAR o que ja foi feito
    hoje (mantem a mesma conversa). Assim ele vai comandando um relatorio de cada
    vez ate zerar o que foi pedido.
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
#     ACAO: salvar        (ou 'nada' quando nao ha mais nada hoje)
#     TITULO: nome-curto
#     CONTEUDO:
#     <texto do relatorio>
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
    # Normaliza: aceita 'salvar' (ou 'upload', por compatibilidade). Sem conteudo = parar.
    if acao in ("salvar", "upload") and conteudo:
        acao = "salvar"
    else:
        acao = "nada"
    return {"acao": acao, "titulo": titulo, "conteudo": conteudo}


def _limpar_nome(titulo):
    """Transforma um titulo em nome de arquivo seguro."""
    seguro = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in titulo).strip("-")
    return seguro or "relatorio"


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
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                texto = f.read().strip()
        except UnicodeDecodeError:
            with open(caminho, "r", encoding="latin-1") as f:
                texto = f.read().strip()

    if not texto:
        raise RuntimeError(f"O arquivo do Vistoria foi lido mas esta vazio: {caminho}")
    return texto


# ============================================================================
# Saida: salva cada relatorio num arquivo pronto
# ============================================================================
def salvar_relatorio(cfg, texto, titulo=""):
    """Salva o relatorio num arquivo e devolve o caminho completo."""
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
# Fluxo principal de um dia: o Claude comanda, o bot salva, ate zerar.
# ============================================================================
def rodar_uma_vez(cfg):
    """O Claude vai mandando os relatorios um a um; o bot salva cada um em arquivo
    e volta ao Claude, ate ele responder que nao ha mais nada (zerou)."""
    log(cfg, "=== Iniciando execucao do dia (Claude comanda, bot salva) ===")
    _, saida = garantir_pastas(cfg)
    c = cfg["claude"]
    max_it = cfg["loop"]["max_iteracoes"]

    # Primeira mensagem = protocolo + pedido do 1o relatorio.
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

    salvos = 0
    for i in range(1, max_it + 1):
        continuar = i > 1  # da 2a chamada em diante, mantem a memoria da conversa
        log(cfg, f"Pedindo o relatorio #{i} ao Claude...")
        try:
            resposta = perguntar_ao_claude(cfg, prompt, continuar=continuar)
        except RuntimeError as e:
            log(cfg, f"ERRO ao falar com o Claude: {e}. Encerrando.")
            break

        ordem = parsear_resposta_claude(resposta)
        if ordem["acao"] == "nada":
            log(cfg, f"Claude indicou que nao ha mais nada hoje. Zerado. "
                     f"Total salvo: {salvos}.")
            break

        caminho = salvar_relatorio(cfg, ordem["conteudo"], titulo=ordem["titulo"])
        salvos += 1
        log(cfg, f"Relatorio '{ordem['titulo'] or '(sem titulo)'}' salvo "
                 f"({len(ordem['conteudo'])} chars) -> {caminho}")

        prompt = c.get("prompt_proximo") or (
            "Salvei o relatorio anterior. Qual o proximo? Responda no mesmo formato "
            "(ACAO/TITULO/CONTEUDO), ou 'ACAO: nada' se zeramos tudo hoje."
        )
        time.sleep(cfg["loop"].get("segundos_entre_acoes", 2.0))
    else:
        log(cfg, "Limite de iteracoes atingido. Encerrando por seguranca.")

    if salvos:
        log(cfg, f"Relatorios do dia salvos em: {saida}")
    log(cfg, "=== Execucao do dia finalizada ===")


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
    print("\n=== VERIFICACAO DO ROBO VISTORIA -> relatorios ===\n")
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

    # 2) pypdf (so se o Vistoria for PDF)
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

    # 3) Claude Code
    ok_claude, det_claude = _claude_responde(cfg)
    linha(ok_claude, f"Claude Code responde ({det_claude[:60] if ok_claude else 'nao'})",
          "Instale e faca login no Claude Code. Teste:  claude --version")

    # 4) Pastas (cria se faltar)
    entrada, saida = garantir_pastas(cfg)
    if entrada:
        linha(os.path.isdir(entrada), f"Pasta de entrada do Vistoria: {entrada}")
    if saida:
        linha(os.path.isdir(saida), f"Pasta de saida (relatorios): {saida}")

    # 5) Arquivo do Vistoria encontrado e legivel
    try:
        texto = ler_texto_vistoria(cfg)
        linha(True, f"Arquivo do Vistoria encontrado ({len(texto)} caracteres)")
    except Exception as e:
        linha(False, "Arquivo do Vistoria encontrado", f"{e}")

    print()
    if problemas == 0:
        print(">>> TUDO PRONTO! Agora rode:  python claude_muse_bot.py --agora")
    else:
        print(f">>> Faltam {problemas} item(ns) acima. Resolva e rode --verificar de novo.")
    print()
    return problemas == 0


# ============================================================================
# main
# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="Robo Vistoria -> Claude -> relatorios")
    ap.add_argument("--config", default=CONFIG_PADRAO, help="caminho do config.json")
    ap.add_argument("--verificar", action="store_true", help="confere se esta tudo pronto para rodar")
    ap.add_argument("--testar-claude", action="store_true", help="so testa o Claude Code")
    ap.add_argument("--testar-vistoria", action="store_true", help="mostra o texto lido do app Vistoria")
    ap.add_argument("--agora", action="store_true", help="roda o fluxo completo uma vez")
    ap.add_argument("--daemon", action="store_true", help="fica rodando e dispara no horario")
    args = ap.parse_args()

    cfg = carregar_config(args.config)

    if args.verificar:
        verificar(cfg)
        return

    if args.testar_claude:
        print("Testando o Claude Code (pode levar alguns segundos)...")
        r = perguntar_ao_claude(cfg, "Responda apenas: OK, estou funcionando.")
        print("Resposta do Claude:\n", r)
        return

    if args.testar_vistoria:
        texto = ler_texto_vistoria(cfg)
        print(f"--- Texto do Vistoria ({len(texto)} caracteres) ---\n")
        print(texto[:2000] + ("\n\n[...truncado...]" if len(texto) > 2000 else ""))
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
