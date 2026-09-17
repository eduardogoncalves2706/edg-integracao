from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import Usuario

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.selecionar_cadastro"))

    if request.method == "POST":
        login_informado = request.form.get("login", "").strip()
        senha_informada = request.form.get("senha", "")

        usuario = Usuario.query.filter_by(login=login_informado).first()
        if usuario and usuario.ativo and usuario.checar_senha(senha_informada):
            usuario.ultimo_login_em = datetime.now(timezone.utc)
            db.session.commit()
            login_user(usuario)
            return redirect(url_for("dashboard.selecionar_cadastro"))

        flash("Usuário ou senha inválidos.", "danger")

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
