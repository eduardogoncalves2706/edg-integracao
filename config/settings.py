"""Carrega configuração da aplicação a partir de arquivos JSON + variáveis de ambiente.

Segue o mesmo padrão já usado em ``db_config/*.json`` no restante do
workspace: o arquivo real (git-ignorado) traz host/usuário, e a senha vem de
uma variável de ambiente indicada por ``*_env`` — nunca fica em texto puro no
arquivo versionado.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent


def _load_json(filename: str, template: str) -> dict:
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Configuração '{filename}' não encontrada. Copie {template} para "
            f"{filename} e preencha com os valores do seu ambiente."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_password(cfg: dict, direct_key: str, env_key: str) -> str | None:
    if cfg.get(direct_key):
        return cfg[direct_key]
    env_name = cfg.get(env_key)
    if env_name:
        return os.environ.get(env_name)
    return None


@dataclass
class DbConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str | None
    sslmode: str | None = None

    @property
    def sqlalchemy_uri(self) -> str:
        auth = self.user
        if self.password:
            auth = f"{self.user}:{self.password}"
        uri = f"postgresql+psycopg://{auth}@{self.host}:{self.port}/{self.dbname}"
        if self.sslmode:
            uri += f"?sslmode={self.sslmode}"
        return uri

    @classmethod
    def load(cls) -> "DbConfig":
        # Em contêiner (ECS) a config vem só de variáveis de ambiente — não
        # há config/db_config.json dentro da imagem. Localmente, sem DB_HOST
        # setado, cai no arquivo JSON de sempre.
        if os.environ.get("DB_HOST"):
            return cls(
                host=os.environ["DB_HOST"],
                port=int(os.environ.get("DB_PORT", 5432)),
                dbname=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD"),
                sslmode=os.environ.get("DB_SSLMODE"),
            )
        cfg = _load_json("db_config.json", "db_config.template.json")
        return cls(
            host=cfg["host"],
            port=cfg.get("port", 5432),
            dbname=cfg["dbname"],
            user=cfg["user"],
            password=_resolve_password(cfg, "password", "password_env"),
            sslmode=cfg.get("sslmode"),
        )


@dataclass
class ApisulConfig:
    """Configuração de conexão com a API Apisul (URLs dos serviços SOAP).

    O token de integração é digitado pelo usuário na tela a cada envio (ver
    app/routes/ponto_geografico.py) — não é lido daqui. `usuario`/`senha`
    ficam disponíveis apenas para um eventual modo automático futuro
    (app/services/auth_token_client.py), hoje não usado no fluxo principal.
    """

    ambiente: str
    base_url: str
    auth_token_path: str
    usuario: str | None
    senha: str | None
    token_ttl_minutos: int
    servicos_soap: dict

    def wsdl_url(self, servico: str) -> str:
        caminho = self.servicos_soap[servico]
        return f"{self.base_url}{caminho}?singleWsdl"

    def servico_url(self, servico: str) -> str:
        caminho = self.servicos_soap[servico]
        return f"{self.base_url}{caminho}"

    @classmethod
    def load(cls) -> "ApisulConfig":
        if os.environ.get("APISUL_BASE_URL"):
            return cls(
                ambiente=os.environ.get("APISUL_AMBIENTE", "homologacao"),
                base_url=os.environ["APISUL_BASE_URL"].rstrip("/"),
                auth_token_path=os.environ.get("APISUL_AUTH_TOKEN_PATH", "/v1/Auth/Token"),
                usuario=os.environ.get("APISUL_USUARIO"),
                senha=os.environ.get("APISUL_SENHA"),
                token_ttl_minutos=int(os.environ.get("APISUL_TOKEN_TTL_MINUTOS", 15)),
                servicos_soap={
                    "ponto_geografico": os.environ.get(
                        "APISUL_SVC_PONTO_GEOGRAFICO", "/ApisulLog.Integracao.PontoGeografico.svc"
                    ),
                },
            )
        cfg = _load_json("apisul_config.json", "apisul_config.template.json")
        return cls(
            ambiente=cfg.get("ambiente", "homologacao"),
            base_url=cfg["base_url"].rstrip("/"),
            auth_token_path=cfg.get("auth_token_path", "/v1/Auth/Token"),
            usuario=cfg.get("usuario"),
            senha=_resolve_password(cfg, "senha", "senha_env"),
            token_ttl_minutos=cfg.get("token_ttl_minutos", 15),
            servicos_soap=cfg.get("servicos_soap", {}),
        )


class FlaskConfig:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "troque-esta-chave-em-producao")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB, suficiente para os modelos de excel

    def __init__(self):
        self.SQLALCHEMY_DATABASE_URI = DbConfig.load().sqlalchemy_uri
