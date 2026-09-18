from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import STATUS_ERRO, STATUS_PENDENTE, ChamadaApi, LoteImportacao
from app.services import excel_ponto_geografico as excel_service
from app.services.processamento_lote import iniciar_processamento_async
from app.utils import json_safe

bp = Blueprint("ponto_geografico", __name__, url_prefix="/cadastros/ponto-geografico")

TIPO_CADASTRO = "ponto_geografico"


@bp.route("/")
@login_required
def index():
    return render_template("ponto_geografico.html")


@bp.route("/modelo")
@login_required
def baixar_modelo():
    buffer = excel_service.gerar_modelo()
    return send_file(
        buffer,
        as_attachment=True,
        download_name="modelo_ponto_geografico.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/enviar", methods=["POST"])
@login_required
def enviar():
    token_texto = request.form.get("token", "").strip()
    if not token_texto:
        flash("Informe o token de integração da Apisul.", "warning")
        return redirect(url_for("ponto_geografico.index"))
    try:
        token = int(token_texto)
    except ValueError:
        flash("Token inválido: deve ser um número inteiro.", "danger")
        return redirect(url_for("ponto_geografico.index"))

    arquivo = request.files.get("planilha")
    if not arquivo or not arquivo.filename:
        flash("Selecione um arquivo .xlsx preenchido a partir do modelo.", "warning")
        return redirect(url_for("ponto_geografico.index"))

    try:
        linhas = excel_service.ler_planilha(arquivo)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("ponto_geografico.index"))

    if not linhas:
        flash("Nenhuma linha de dados encontrada na planilha.", "warning")
        return redirect(url_for("ponto_geografico.index"))

    cfg = current_app.config["APISUL_CONFIG"]

    lote = LoteImportacao(
        usuario_id=current_user.id,
        tipo_cadastro=TIPO_CADASTRO,
        nome_arquivo=arquivo.filename,
        total_linhas=len(linhas),
    )
    db.session.add(lote)
    db.session.flush()  # garante lote.id antes de vincular as chamadas

    for linha in linhas:
        if not linha.valida:
            lote.linhas_erro += 1
            chamada = ChamadaApi(
                usuario_id=current_user.id,
                lote_id=lote.id,
                tipo_cadastro=TIPO_CADASTRO,
                operacao="ValidacaoPlanilha",
                linha_excel=linha.numero_linha,
                identificador_registro=linha.dados.get("Identificador"),
                status=STATUS_ERRO,
                payload_enviado=json_safe(linha.dados),
                mensagem_erro="; ".join(linha.erros),
            )
        else:
            payload = excel_service.montar_payload_soap(linha.dados)
            chamada = ChamadaApi(
                usuario_id=current_user.id,
                lote_id=lote.id,
                tipo_cadastro=TIPO_CADASTRO,
                operacao="InserePontoGeografico",
                linha_excel=linha.numero_linha,
                identificador_registro=linha.dados.get("Identificador"),
                status=STATUS_PENDENTE,
                payload_enviado=json_safe(payload),
            )
        db.session.add(chamada)

    db.session.commit()

    # Se todas as linhas já falharam na validação, não há nada pra processar.
    if lote.linhas_erro < lote.total_linhas:
        iniciar_processamento_async(current_app._get_current_object(), lote.id, cfg, token)
    else:
        lote.status = "concluido"
        db.session.commit()

    return redirect(url_for("lotes.detalhe", lote_id=lote.id))
