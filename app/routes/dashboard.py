from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import STATUS_ERRO, STATUS_SUCESSO, ChamadaApi, LoteImportacao

bp = Blueprint("dashboard", __name__)

# Cadastro fica "disponivel=False" até ter uma rota/serviço implementado -
# assim a tela de seleção já mostra o roadmap sem precisar mexer no template.
CADASTROS = [
    {
        "chave": "ponto_geografico",
        "titulo": "Ponto Geográfico",
        "descricao": "Cadastro/atualização de pontos geográficos (endereço, coordenadas, geofence).",
        "disponivel": True,
        "url_endpoint": "ponto_geografico.index",
    },
    {
        "chave": "motorista",
        "titulo": "Motorista",
        "descricao": "Cadastro de motoristas (frota, agregado ou autônomo).",
        "disponivel": True,
        "url_endpoint": "motorista.index",
    },
    {
        "chave": "rota",
        "titulo": "Rota",
        "descricao": "Cadastro de rotas.",
        "disponivel": False,
        "url_endpoint": None,
    },
    {
        "chave": "emitente",
        "titulo": "Emitente",
        "descricao": "Cadastro de emitentes.",
        "disponivel": False,
        "url_endpoint": None,
    },
]


@bp.route("/cadastros")
@login_required
def selecionar_cadastro():
    return render_template("dashboard.html", cadastros=CADASTROS)


@bp.route("/")
@login_required
def visao_geral():
    agora = datetime.now(timezone.utc)
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inicio_mes_anterior = (inicio_mes - timedelta(days=1)).replace(day=1)

    def contar(status=None, desde=None, ate=None):
        q = ChamadaApi.query
        if status:
            q = q.filter(ChamadaApi.status == status)
        if desde:
            q = q.filter(ChamadaApi.criado_em >= desde)
        if ate:
            q = q.filter(ChamadaApi.criado_em < ate)
        return q.count()

    total_mes = contar(desde=inicio_mes)
    total_mes_anterior = contar(desde=inicio_mes_anterior, ate=inicio_mes)
    sucesso_mes = contar(status=STATUS_SUCESSO, desde=inicio_mes)
    erro_mes = contar(status=STATUS_ERRO, desde=inicio_mes)
    erro_mes_anterior = contar(status=STATUS_ERRO, desde=inicio_mes_anterior, ate=inicio_mes)

    taxa_sucesso = (sucesso_mes / total_mes * 100) if total_mes else None

    duracao_media = (
        db.session.query(func.avg(ChamadaApi.duracao_ms))
        .filter(ChamadaApi.duracao_ms.isnot(None), ChamadaApi.criado_em >= inicio_mes)
        .scalar()
    )

    composicao = {
        row[0]: row[1]
        for row in (
            db.session.query(ChamadaApi.status, func.count(ChamadaApi.id))
            .filter(ChamadaApi.criado_em >= inicio_mes)
            .group_by(ChamadaApi.status)
            .all()
        )
    }

    ultimas = (
        ChamadaApi.query
        .order_by(ChamadaApi.criado_em.desc())
        .limit(8)
        .all()
    )

    dias = []
    for i in range(6, -1, -1):
        dia = (agora - timedelta(days=i)).date()
        inicio_dia = datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc)
        fim_dia = inicio_dia + timedelta(days=1)
        qtd = contar(desde=inicio_dia, ate=fim_dia)
        dias.append({"label": dia.strftime("%d/%m"), "valor": qtd})

    lotes_recentes = (
        LoteImportacao.query
        .order_by(LoteImportacao.criado_em.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "visao_geral.html",
        total_mes=total_mes,
        variacao_total=_variacao(total_mes, total_mes_anterior),
        taxa_sucesso=taxa_sucesso,
        erro_mes=erro_mes,
        variacao_erro=_variacao(erro_mes, erro_mes_anterior),
        duracao_media=duracao_media,
        composicao=composicao,
        ultimas=ultimas,
        dias=dias,
        lotes_recentes=lotes_recentes,
    )


def _variacao(atual: int, anterior: int):
    if not anterior:
        return None
    return (atual - anterior) / anterior * 100
