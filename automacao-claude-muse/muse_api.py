# -*- coding: utf-8 -*-
"""
muse_api.py
===========
Fala com o muse.ai pela API oficial (sem clicar na tela).

Autenticacao: cabecalho `Key: <sua_chave>`.
A chave vem da variavel de ambiente MUSE_API_KEY (recomendado) ou do config.json.

Endpoint de upload: POST https://muse.ai/api/files/upload  (multipart, campo "file").
Opcionalmente, "collection" com o ID de uma colecao para ja adicionar o arquivo nela.

OBS: o muse.ai e uma plataforma de VIDEO. Se ele recusar um arquivo .txt, a funcao
avisa com a mensagem exata do servidor para voce decidir (ex.: subir como .md,
anexar a um video, etc.). Nada aqui apaga ou sobrescreve dados sozinho.
"""

import os

try:
    import requests
    _REQUESTS_OK = True
except Exception:  # pragma: no cover
    _REQUESTS_OK = False


def _obter_chave(cfg):
    api = cfg.get("muse_api", {})
    var = api.get("variavel_ambiente_chave", "MUSE_API_KEY")
    chave = os.environ.get(var, "").strip() or api.get("chave", "").strip()
    if not chave:
        raise RuntimeError(
            f"Chave da API do muse.ai nao encontrada.\n"
            f"Defina a variavel de ambiente {var} com a sua chave, por exemplo (CMD):\n"
            f'    setx {var} "sua_chave_aqui"\n'
            f"e abra um novo terminal. (A chave fica na sua conta muse.ai.)"
        )
    return chave


def enviar_arquivo(cfg, caminho_arquivo):
    """Sobe um arquivo para o muse.ai. Retorna a resposta (dict ou texto).

    Levanta RuntimeError com a mensagem do servidor se algo falhar.
    """
    if not _REQUESTS_OK:
        raise RuntimeError(
            "A biblioteca 'requests' nao esta instalada. Rode:  pip install requests"
        )
    if not os.path.isfile(caminho_arquivo):
        raise RuntimeError(f"Arquivo nao encontrado para upload: {caminho_arquivo}")

    api = cfg["muse_api"]
    chave = _obter_chave(cfg)
    url = api.get("url_upload", "https://muse.ai/api/files/upload")
    timeout = api.get("timeout_segundos", 300)

    headers = {"Key": chave}
    data = {}
    if api.get("collection_id"):
        data["collection"] = api["collection_id"]

    with open(caminho_arquivo, "rb") as f:
        files = {"file": (os.path.basename(caminho_arquivo), f)}
        try:
            resp = requests.post(url, headers=headers, data=data, files=files, timeout=timeout)
        except requests.RequestException as e:
            raise RuntimeError(f"Falha de rede ao enviar ao muse.ai: {e}")

    if resp.status_code >= 400:
        raise RuntimeError(
            f"muse.ai recusou o upload (HTTP {resp.status_code}): {resp.text[:800]}"
        )

    ctype = resp.headers.get("content-type", "")
    if "application/json" in ctype:
        try:
            return resp.json()
        except ValueError:
            return resp.text
    return resp.text


def testar_conexao(cfg):
    """Teste simples: confirma que a chave existe. Nao faz upload real."""
    chave = _obter_chave(cfg)
    mascara = chave[:4] + "..." + chave[-3:] if len(chave) > 8 else "(curta)"
    return f"Chave carregada ({mascara}). Endpoint: {cfg['muse_api'].get('url_upload')}"
