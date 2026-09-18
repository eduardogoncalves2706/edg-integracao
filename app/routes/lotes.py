from flask import Blueprint, jsonify, render_template
from flask_login import login_required

from app.models import ChamadaApi, LoteImportacao

bp = Blueprint("lotes", __name__, url_prefix="/lotes")


@bp.route("/<int:lote_id>")
@login_required
def detalhe(lote_id: int):
    lote = LoteImportacao.query.get_or_404(lote_id)
    return render_template("lote_detalhe.html", lote=lote)


@bp.route("/<int:lote_id>/status.json")
@login_required
def status_json(lote_id: int):
    lote = LoteImportacao.query.get_or_404(lote_id)
    chamadas = (
        ChamadaApi.query
        .filter_by(lote_id=lote.id)
        .order_by(ChamadaApi.linha_excel)
        .all()
    )
    return jsonify({
        "id": lote.id,
        "status": lote.status,
        "total_linhas": lote.total_linhas,
        "linhas_sucesso": lote.linhas_sucesso,
        "linhas_erro": lote.linhas_erro,
        "linhas_pendentes": lote.linhas_pendentes,
        "chamadas": [
            {
                "id": c.id,
                "linha": c.linha_excel,
                "identificador": c.identificador_registro or "-",
                "status": c.status,
                "mensagem": c.mensagem_erro,
                "duracao_ms": c.duracao_ms,
            }
            for c in chamadas
        ],
    })
