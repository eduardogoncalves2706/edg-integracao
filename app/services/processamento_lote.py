"""Processa um lote de cadastro em background (thread separada da requisição
HTTP) — cada chamada real à API pode levar 20-40s, então processar tudo
dentro da própria requisição deixava a tela "pensando" por minutos.

O upload grava as linhas como ChamadaApi(status="pendente") e devolve a
resposta na hora; esta função roda numa thread à parte, processa uma linha
por vez e vai commitando o progresso — a tela de resultado faz polling em
`/lotes/<id>/status` pra mostrar isso ao vivo.

Limitação conhecida: a thread vive dentro do processo do worker gunicorn que
recebeu o upload. Se esse worker for reciclado no meio do processamento (ex.:
deploy, crash), o lote fica travado em "processando" com linhas pendentes.
Aceitável para o volume atual (poucos usuários, lotes pequenos); se o volume
crescer, migrar para um worker dedicado (processo ECS separado lendo a fila
do Postgres) em vez de thread in-process.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from flask import Flask

from app.extensions import db
from app.models import (
    STATUS_ERRO,
    STATUS_PENDENTE,
    STATUS_SUCESSO,
    ChamadaApi,
    LoteImportacao,
)
from config.settings import ApisulConfig

# Dispatch por tipo_cadastro -> função(cfg, token, payload) -> ResultadoChamada.
# Registrar aqui novos cadastros (Motorista, Rota...) conforme forem implementados.
_EXECUTORES = {}


def registrar_executor(tipo_cadastro: str):
    def decorator(func):
        _EXECUTORES[tipo_cadastro] = func
        return func
    return decorator


def _carregar_executores():
    if _EXECUTORES:
        return
    from app.services.ponto_geografico_service import inserir_ponto_geografico
    _EXECUTORES["ponto_geografico"] = inserir_ponto_geografico


def iniciar_processamento_async(app: Flask, lote_id: int, cfg: ApisulConfig, token: int) -> None:
    thread = threading.Thread(
        target=_processar_lote,
        args=(app, lote_id, cfg, token),
        daemon=True,
    )
    thread.start()


def _processar_lote(app: Flask, lote_id: int, cfg: ApisulConfig, token: int) -> None:
    _carregar_executores()
    with app.app_context():
        lote = db.session.get(LoteImportacao, lote_id)
        if lote is None:
            return

        executor = _EXECUTORES.get(lote.tipo_cadastro)
        pendentes = (
            ChamadaApi.query
            .filter_by(lote_id=lote.id, status=STATUS_PENDENTE)
            .order_by(ChamadaApi.linha_excel)
            .all()
        )

        for chamada in pendentes:
            if executor is None:
                chamada.status = STATUS_ERRO
                chamada.mensagem_erro = f"Tipo de cadastro '{lote.tipo_cadastro}' sem executor registrado."
                lote.linhas_erro += 1
                db.session.commit()
                continue

            resultado = executor(cfg, token, chamada.payload_enviado or {})

            chamada.status = STATUS_SUCESSO if resultado.sucesso else STATUS_ERRO
            chamada.resposta_recebida = _json_safe(resultado.resposta)
            chamada.mensagem_erro = resultado.mensagem_erro
            chamada.duracao_ms = resultado.duracao_ms
            chamada.processado_em = datetime.now(timezone.utc)

            if resultado.sucesso:
                lote.linhas_sucesso += 1
            else:
                lote.linhas_erro += 1

            db.session.commit()

        lote.status = "concluido"
        lote.concluido_em = datetime.now(timezone.utc)
        db.session.commit()


def _json_safe(valor):
    from app.utils import json_safe
    return json_safe(valor)
