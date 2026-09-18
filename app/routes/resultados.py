from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.models import ChamadaApi, LoteImportacao

bp = Blueprint("resultados", __name__, url_prefix="/resultados")

POR_PAGINA = 25


@bp.route("/")
@login_required
def index():
    status = request.args.get("status") or None
    tipo_cadastro = request.args.get("tipo_cadastro") or None
    busca = request.args.get("busca") or None
    pagina = request.args.get("pagina", 1, type=int)

    query = ChamadaApi.query.order_by(ChamadaApi.criado_em.desc())
    if status:
        query = query.filter(ChamadaApi.status == status)
    if tipo_cadastro:
        query = query.filter(ChamadaApi.tipo_cadastro == tipo_cadastro)
    if busca:
        query = query.filter(ChamadaApi.identificador_registro.ilike(f"%{busca}%"))

    paginacao = query.paginate(page=pagina, per_page=POR_PAGINA, error_out=False)

    tipos_disponiveis = [
        row[0] for row in
        ChamadaApi.query.with_entities(ChamadaApi.tipo_cadastro).distinct().all()
    ]

    return render_template(
        "resultados.html",
        chamadas=paginacao.items,
        paginacao=paginacao,
        filtros={"status": status, "tipo_cadastro": tipo_cadastro, "busca": busca},
        tipos_disponiveis=tipos_disponiveis,
    )


@bp.route("/<int:chamada_id>/detalhe.json")
@login_required
def detalhe_json(chamada_id: int):
    chamada = ChamadaApi.query.get_or_404(chamada_id)
    lote = LoteImportacao.query.get(chamada.lote_id) if chamada.lote_id else None
    return jsonify({
        "id": chamada.id,
        "linha": chamada.linha_excel,
        "identificador": chamada.identificador_registro,
        "tipo_cadastro": chamada.tipo_cadastro,
        "operacao": chamada.operacao,
        "status": chamada.status,
        "mensagem_erro": chamada.mensagem_erro,
        "duracao_ms": chamada.duracao_ms,
        "criado_em": chamada.criado_em.isoformat() if chamada.criado_em else None,
        "processado_em": chamada.processado_em.isoformat() if chamada.processado_em else None,
        "payload_enviado": chamada.payload_enviado,
        "resposta_recebida": chamada.resposta_recebida,
        "planilha": lote.nome_arquivo if lote else None,
        "usuario": chamada.usuario.nome if chamada.usuario else None,
    })
