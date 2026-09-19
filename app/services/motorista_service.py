"""Orquestra o cadastro de Motorista: chama a rota REST InsereMotorista com
o token informado pelo usuário e normaliza o retorno para gravar em
ChamadaApi.

Diferente do PontoGeografico (SOAP): token vai no header, corpo é JSON puro,
e a resposta não tem `TransacaoOk` — sucesso se infere pela ausência de
`MensagensErro`. HTTP 400 devolve um array de mensagens direto, sem o
envelope padrão (ver docs/API_MAPEAMENTO.md)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from config.settings import ApisulConfig
from app.services.rest_client import post_json

CAMINHO_INSERE = "/insereMotorista"


@dataclass
class ResultadoChamada:
    sucesso: bool
    payload_enviado: dict[str, Any]
    resposta: dict[str, Any] | None
    mensagem_erro: str | None
    duracao_ms: int


def inserir_motorista(cfg: ApisulConfig, token: int, payload: dict[str, Any]) -> ResultadoChamada:
    inicio = time.monotonic()
    try:
        resultado = post_json(cfg, CAMINHO_INSERE, token, payload)
    except Exception as exc:  # noqa: BLE001 - falha de rede/timeout, loga em vez de derrubar o worker
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        return ResultadoChamada(
            sucesso=False, payload_enviado=payload, resposta=None,
            mensagem_erro=str(exc), duracao_ms=duracao_ms,
        )

    duracao_ms = int((time.monotonic() - inicio) * 1000)
    status_http = resultado["status_http"]
    corpo = resultado["corpo"]

    if status_http == 400:
        # HTTP 400 devolve array de RetornoMensagem direto, sem envelope.
        mensagens = corpo if isinstance(corpo, list) else []
        mensagem_erro = "; ".join(f"[{m.get('Codigo')}] {m.get('Mensagem')}" for m in mensagens) or f"HTTP 400: {corpo}"
        return ResultadoChamada(
            sucesso=False, payload_enviado=payload, resposta=corpo,
            mensagem_erro=mensagem_erro, duracao_ms=duracao_ms,
        )

    if not (200 <= status_http < 300):
        return ResultadoChamada(
            sucesso=False, payload_enviado=payload, resposta=corpo,
            mensagem_erro=f"HTTP {status_http}: {corpo}", duracao_ms=duracao_ms,
        )

    mensagens_erro = corpo.get("MensagensErro") or []
    sucesso = not mensagens_erro
    mensagem_erro = None
    if not sucesso:
        mensagem_erro = "; ".join(f"[{m.get('Codigo')}] {m.get('Mensagem')}" for m in mensagens_erro)

    return ResultadoChamada(
        sucesso=sucesso, payload_enviado=payload, resposta=corpo,
        mensagem_erro=mensagem_erro, duracao_ms=duracao_ms,
    )
