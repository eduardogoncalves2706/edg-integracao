"""Wrapper genérico para os serviços SOAP ApisulLog.Integracao.*.svc.

Um único cliente zeep por serviço (WSDL é lido uma vez e cacheado). Qualquer
novo cadastro (Motorista, Rota, Emitente, SMP...) reaproveita isso — só
precisa registrar a URL em config/apisul_config.json -> servicos_soap.
"""
from __future__ import annotations

from typing import Any

import zeep
from zeep.helpers import serialize_object

from config.settings import ApisulConfig

_clientes: dict[str, zeep.Client] = {}


def obter_cliente(cfg: ApisulConfig, servico: str) -> zeep.Client:
    if servico not in _clientes:
        _clientes[servico] = zeep.Client(wsdl=cfg.wsdl_url(servico))
    return _clientes[servico]


def chamar_operacao(cfg: ApisulConfig, servico: str, operacao: str, **kwargs) -> dict[str, Any]:
    """Chama uma operação SOAP e devolve a resposta já convertida para dict puro."""
    cliente = obter_cliente(cfg, servico)
    metodo = getattr(cliente.service, operacao)
    resultado = metodo(**kwargs)
    return serialize_object(resultado, target_cls=dict)
