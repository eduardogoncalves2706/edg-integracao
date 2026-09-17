from datetime import datetime
from typing import Any


def json_safe(valor: Any) -> Any:
    """Converte recursivamente datetimes (e afins) em algo serializável em
    JSON, para gravar payload/resposta em colunas JSON do Postgres."""
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: json_safe(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [json_safe(v) for v in valor]
    return valor
