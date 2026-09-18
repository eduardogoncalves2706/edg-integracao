"""Autoatendimento de liberação de IP no security group da app na AWS.

Usa boto3 — dentro do ECS, as credenciais vêm automaticamente da IAM Task
Role anexada à task (ver docs/DEPLOY_AWS.md); localmente, do seu `aws
configure`. A IAM policy da task role é restrita a autorizar/revogar ingress
SÓ neste security group específico (não dá acesso amplo à conta).
"""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

PORTA_APP = 8000
DESCRICAO_PREFIXO = "auto-liberado-por-app:"


class IpInvalidoError(ValueError):
    pass


class SecurityGroupNaoConfiguradoError(RuntimeError):
    pass


@dataclass
class ResultadoLiberacao:
    ip: str
    ja_estava_liberado: bool


def _validar_ip(ip: str) -> str:
    ip = (ip or "").strip()
    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise IpInvalidoError(f"'{ip}' não é um endereço IPv4/IPv6 válido.") from exc
    return ip


def _client():
    regiao = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.client("ec2", region_name=regiao)


def _security_group_id() -> str:
    sg_id = os.environ.get("AWS_APP_SECURITY_GROUP_ID")
    if not sg_id:
        raise SecurityGroupNaoConfiguradoError(
            "AWS_APP_SECURITY_GROUP_ID não configurado — defina essa variável de "
            "ambiente com o id do security group da aplicação para habilitar a "
            "liberação automática de IP."
        )
    return sg_id


def liberar_ip(ip: str, identificacao: str) -> ResultadoLiberacao:
    """Abre a porta da app (8000/tcp) para `ip` no security group configurado.
    Idempotente: se a regra já existir, não é um erro."""
    ip_validado = _validar_ip(ip)
    cliente = _client()
    sg_id = _security_group_id()

    try:
        cliente.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                "IpProtocol": "tcp",
                "FromPort": PORTA_APP,
                "ToPort": PORTA_APP,
                "IpRanges": [{
                    "CidrIp": f"{ip_validado}/32",
                    "Description": f"{DESCRICAO_PREFIXO}{identificacao}"[:255],
                }],
            }],
        )
        return ResultadoLiberacao(ip=ip_validado, ja_estava_liberado=False)
    except ClientError as exc:
        codigo = exc.response.get("Error", {}).get("Code")
        if codigo == "InvalidPermission.Duplicate":
            return ResultadoLiberacao(ip=ip_validado, ja_estava_liberado=True)
        raise
