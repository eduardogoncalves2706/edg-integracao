from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import LoteImportacao

bp = Blueprint("historico", __name__, url_prefix="/historico")

POR_PAGINA = 20


@bp.route("/")
@login_required
def index():
    pagina = request.args.get("pagina", 1, type=int)
    paginacao = (
        LoteImportacao.query
        .order_by(LoteImportacao.criado_em.desc())
        .paginate(page=pagina, per_page=POR_PAGINA, error_out=False)
    )
    return render_template("historico.html", lotes=paginacao.items, paginacao=paginacao)
