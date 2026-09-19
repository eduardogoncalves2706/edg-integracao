"""Cliente REST genérico para os endpoints ApisulLog que não são SOAP (ex.:
InsereMotorista). Ao contrário do SOAP (token no corpo), essas rotas levam
o token no header `token`."""
from __future__ import annotations

from typing import Any

import requests

from config.settings import ApisulConfig


def post_json(cfg: ApisulConfig, caminho: str, token: int, corpo: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    url = f"{cfg.base_url}{caminho}"
    resposta = requests.post(
        url,
        json=corpo,
        headers={"token": str(token), "Content-Type": "application/json", "Accept": "application/json"},
        timeout=timeout,
    )
    corpo_resposta = resposta.json() if resposta.content else {}
    return {"status_http": resposta.status_code, "corpo": corpo_resposta}
