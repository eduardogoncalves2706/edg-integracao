"""Obtém e armazena em cache o token de integração da API ApisulLog.

POST {base_url}/v1/Auth/Token com {"Usuario", "Senha"} -> token usado como
parâmetro `token` (int) em todas as chamadas SOAP de cadastro.

O swagger não documenta o formato exato da resposta (schema "object"), então
o parsing abaixo é defensivo e cobre os formatos mais comuns de APIs .NET
(campo "Token"/"token"/"access_token", string/int puro, ou dict aninhado em
"Result"/"Data"). Ajustar `_extrair_token` assim que o primeiro teste real
contra a homologação mostrar o formato verdadeiro.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

from config.settings import ApisulConfig


class ErroAutenticacaoApisul(RuntimeError):
    pass


@dataclass
class _TokenCache:
    valor: Optional[int] = None
    expira_em: float = 0.0


_cache = _TokenCache()


def _extrair_token(payload) -> int:
    if isinstance(payload, (int, str)):
        return int(payload)
    if isinstance(payload, dict):
        for chave in ("Token", "token", "access_token", "AccessToken"):
            if chave in payload:
                return int(payload[chave])
        for chave in ("Result", "Data", "data", "result"):
            if chave in payload:
                return _extrair_token(payload[chave])
    raise ErroAutenticacaoApisul(
        f"Não foi possível localizar o token na resposta da API: {payload!r}"
    )


def obter_token(cfg: ApisulConfig, forcar_renovacao: bool = False) -> int:
    agora = time.monotonic()
    if not forcar_renovacao and _cache.valor is not None and agora < _cache.expira_em:
        return _cache.valor

    url = f"{cfg.base_url}{cfg.auth_token_path}"
    resposta = requests.post(
        url,
        json={"Usuario": cfg.usuario, "Senha": cfg.senha},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=30,
    )
    if not resposta.ok:
        raise ErroAutenticacaoApisul(
            f"Falha ao autenticar em {url}: HTTP {resposta.status_code} - {resposta.text[:500]}"
        )

    try:
        corpo = resposta.json()
    except ValueError:
        corpo = resposta.text.strip()

    token = _extrair_token(corpo)
    _cache.valor = token
    _cache.expira_em = agora + (cfg.token_ttl_minutos * 60)
    return token
