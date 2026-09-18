"""Orquestra o cadastro de Ponto Geográfico: chama o SOAP com o token
informado pelo usuário e normaliza o retorno para gravar em ChamadaApi.

O token é digitado na tela (ver app/routes/ponto_geografico.py) em vez de
vir de uma credencial fixa em config/apisul_config.json — assim dá pra testar
com qualquer token de integração sem reconfigurar o app."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from config.settings import ApisulConfig
from app.services.soap_client import chamar_operacao

SERVICO = "ponto_geografico"
OPERACAO_INSERE = "InserePontoGeografico"

# Código de erro da Apisul pra token expirado/inválido (confirmado em teste
# real em 2026-09-18: mesmo token que funcionou minutos antes passou a
# devolver isso). Ajuda no diagnóstico exibindo uma dica mais clara.
CODIGO_ERRO_TOKEN_INVALIDO = 1002


@dataclass
class ResultadoChamada:
    sucesso: bool
    payload_enviado: dict[str, Any]
    resposta: dict[str, Any] | None
    mensagem_erro: str | None
    duracao_ms: int


def inserir_ponto_geografico(cfg: ApisulConfig, token: int, payload: dict[str, Any]) -> ResultadoChamada:
    inicio = time.monotonic()
    try:
        resposta = chamar_operacao(
            cfg, SERVICO, OPERACAO_INSERE,
            token=token,
            pontoModeloIntegracao=payload,
        )
    except Exception as exc:  # noqa: BLE001 - queremos capturar qualquer falha de rede/SOAP e logar
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        return ResultadoChamada(
            sucesso=False,
            payload_enviado=payload,
            resposta=None,
            mensagem_erro=str(exc),
            duracao_ms=duracao_ms,
        )

    duracao_ms = int((time.monotonic() - inicio) * 1000)
    transacao_ok = bool(resposta.get("TransacaoOk"))
    mensagens_erro = resposta.get("MensagensErro") or {}
    lista_erros = mensagens_erro.get("RetornoMensagem") if isinstance(mensagens_erro, dict) else None
    mensagem_erro = None
    if not transacao_ok:
        if lista_erros:
            mensagem_erro = "; ".join(
                f"[{m.get('Codigo')}] {m.get('Mensagem')}" for m in lista_erros
            )
            if any(m.get("Codigo") == CODIGO_ERRO_TOKEN_INVALIDO for m in lista_erros):
                mensagem_erro += " — gere um token novo (o anterior expirou ou já foi usado) e envie de novo."
        else:
            mensagem_erro = "API retornou TransacaoOk=false sem detalhar o motivo."

    return ResultadoChamada(
        sucesso=transacao_ok,
        payload_enviado=payload,
        resposta=resposta,
        mensagem_erro=mensagem_erro,
        duracao_ms=duracao_ms,
    )
