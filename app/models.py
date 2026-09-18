from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


def _now():
    return datetime.now(timezone.utc)


STATUS_PENDENTE = "pendente"
STATUS_PROCESSANDO = "processando"
STATUS_SUCESSO = "sucesso"
STATUS_ERRO = "erro"


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    login = db.Column(db.String(80), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    admin = db.Column(db.Boolean, nullable=False, default=False)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    ultimo_login_em = db.Column(db.DateTime(timezone=True), nullable=True)

    # Autoatendimento de liberação de IP na AWS (ver app/services/aws_security_group.py).
    ip_registrado = db.Column(db.String(45), nullable=True)
    ip_liberado_em = db.Column(db.DateTime(timezone=True), nullable=True)

    def set_senha(self, senha_texto_plano: str) -> None:
        self.senha_hash = generate_password_hash(senha_texto_plano)

    def checar_senha(self, senha_texto_plano: str) -> bool:
        return check_password_hash(self.senha_hash, senha_texto_plano)

    @property
    def is_active(self) -> bool:  # sobrescreve UserMixin.is_active
        return self.ativo


class LoteImportacao(db.Model):
    __tablename__ = "lotes_importacao"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    tipo_cadastro = db.Column(db.String(60), nullable=False)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    total_linhas = db.Column(db.Integer, nullable=False, default=0)
    linhas_sucesso = db.Column(db.Integer, nullable=False, default=0)
    linhas_erro = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PROCESSANDO)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    concluido_em = db.Column(db.DateTime(timezone=True), nullable=True)

    usuario = db.relationship("Usuario")
    chamadas = db.relationship("ChamadaApi", backref="lote", order_by="ChamadaApi.linha_excel")

    @property
    def linhas_pendentes(self) -> int:
        return self.total_linhas - self.linhas_sucesso - self.linhas_erro


class ChamadaApi(db.Model):
    __tablename__ = "chamadas_api"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    lote_id = db.Column(db.Integer, db.ForeignKey("lotes_importacao.id"), nullable=True)

    tipo_cadastro = db.Column(db.String(60), nullable=False)
    operacao = db.Column(db.String(120), nullable=False)
    linha_excel = db.Column(db.Integer, nullable=True)
    identificador_registro = db.Column(db.String(120), nullable=True)

    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDENTE)
    payload_enviado = db.Column(db.JSON, nullable=True)
    resposta_recebida = db.Column(db.JSON, nullable=True)
    mensagem_erro = db.Column(db.Text, nullable=True)
    duracao_ms = db.Column(db.Integer, nullable=True)

    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=_now)
    processado_em = db.Column(db.DateTime(timezone=True), nullable=True)

    usuario = db.relationship("Usuario")

    @property
    def sucesso(self) -> bool:
        return self.status == STATUS_SUCESSO
