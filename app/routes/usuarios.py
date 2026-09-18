from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Usuario
from app.services.aws_security_group import (
    IpInvalidoError,
    SecurityGroupNaoConfiguradoError,
    liberar_ip,
)

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


def _exigir_admin_ou_proprio(usuario_id: int) -> Usuario:
    usuario = Usuario.query.get_or_404(usuario_id)
    if not current_user.admin and current_user.id != usuario.id:
        abort(403)
    return usuario


@bp.route("/")
@login_required
def index():
    if not current_user.admin:
        return redirect(url_for("usuarios.editar", usuario_id=current_user.id))
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return render_template("usuarios/lista.html", usuarios=usuarios)


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    if not current_user.admin:
        abort(403)

    if request.method == "POST":
        login_ = request.form.get("login", "").strip()
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "")
        admin = bool(request.form.get("admin"))

        erro = None
        if not login_ or not nome or not senha:
            erro = "Preencha usuário, nome e senha."
        elif Usuario.query.filter_by(login=login_).first():
            erro = f"Já existe um usuário com o login '{login_}'."

        if erro:
            flash(erro, "danger")
            return render_template("usuarios/form.html", usuario=None, form=request.form)

        usuario = Usuario(login=login_, nome=nome, admin=admin, ativo=True)
        usuario.set_senha(senha)
        db.session.add(usuario)
        db.session.commit()
        flash(f"Usuário '{login_}' criado.", "success")
        return redirect(url_for("usuarios.index"))

    return render_template("usuarios/form.html", usuario=None, form=None)


@bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@login_required
def editar(usuario_id: int):
    usuario = _exigir_admin_ou_proprio(usuario_id)

    if request.method == "POST":
        usuario.nome = request.form.get("nome", usuario.nome).strip()
        nova_senha = request.form.get("senha", "").strip()
        if nova_senha:
            usuario.set_senha(nova_senha)

        if current_user.admin:
            usuario.ativo = bool(request.form.get("ativo"))
            # impede o admin de se autodesativar por engano, travando o próprio acesso
            if usuario.id == current_user.id:
                usuario.ativo = True
            usuario.admin = bool(request.form.get("admin")) if usuario.id != current_user.id else usuario.admin

        db.session.commit()
        flash("Dados atualizados.", "success")
        return redirect(url_for("usuarios.editar", usuario_id=usuario.id))

    return render_template("usuarios/form.html", usuario=usuario, form=None)


@bp.route("/<int:usuario_id>/liberar-ip", methods=["POST"])
@login_required
def liberar_ip_route(usuario_id: int):
    usuario = _exigir_admin_ou_proprio(usuario_id)

    usar_ip_atual = request.form.get("usar_ip_atual")
    ip = request.remote_addr if usar_ip_atual else request.form.get("ip", "").strip()

    try:
        resultado = liberar_ip(ip, identificacao=usuario.login)
    except IpInvalidoError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("usuarios.editar", usuario_id=usuario.id))
    except SecurityGroupNaoConfiguradoError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("usuarios.editar", usuario_id=usuario.id))
    except Exception as exc:  # noqa: BLE001 - erro de AWS, mostra pro usuário em vez de 500
        flash(f"Falha ao liberar IP na AWS: {exc}", "danger")
        return redirect(url_for("usuarios.editar", usuario_id=usuario.id))

    usuario.ip_registrado = resultado.ip
    usuario.ip_liberado_em = datetime.now(timezone.utc)
    db.session.commit()

    if resultado.ja_estava_liberado:
        flash(f"O IP {resultado.ip} já estava liberado.", "info")
    else:
        flash(f"IP {resultado.ip} liberado na AWS com sucesso.", "success")
    return redirect(url_for("usuarios.editar", usuario_id=usuario.id))
