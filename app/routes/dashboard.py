from flask import Blueprint, render_template
from flask_login import login_required

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
        "descricao": "Cadastro de motoristas.",
        "disponivel": False,
        "url_endpoint": None,
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


@bp.route("/")
@login_required
def selecionar_cadastro():
    return render_template("dashboard.html", cadastros=CADASTROS)
