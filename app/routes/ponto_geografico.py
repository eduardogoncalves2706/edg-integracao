from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import ChamadaApi, LoteImportacao
from app.services import excel_ponto_geografico as excel_service
from app.services.ponto_geografico_service import inserir_ponto_geografico
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

    resultados_para_tela = []

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
                payload_enviado=json_safe(linha.dados),
                resposta_recebida=None,
                sucesso=False,
                mensagem_erro="; ".join(linha.erros),
            )
            db.session.add(chamada)
            resultados_para_tela.append({
                "linha": linha.numero_linha,
                "identificador": linha.dados.get("Identificador") or "-",
                "sucesso": False,
                "mensagem": "; ".join(linha.erros),
            })
            continue

        payload = excel_service.montar_payload_soap(linha.dados)
        resultado = inserir_ponto_geografico(cfg, token, payload)

        if resultado.sucesso:
            lote.linhas_sucesso += 1
        else:
            lote.linhas_erro += 1

        chamada = ChamadaApi(
            usuario_id=current_user.id,
            lote_id=lote.id,
            tipo_cadastro=TIPO_CADASTRO,
            operacao="InserePontoGeografico",
            linha_excel=linha.numero_linha,
            identificador_registro=linha.dados.get("Identificador"),
            payload_enviado=json_safe(resultado.payload_enviado),
            resposta_recebida=json_safe(resultado.resposta),
            sucesso=resultado.sucesso,
            mensagem_erro=resultado.mensagem_erro,
            duracao_ms=resultado.duracao_ms,
        )
        db.session.add(chamada)
        resultados_para_tela.append({
            "linha": linha.numero_linha,
            "identificador": linha.dados.get("Identificador") or "-",
            "sucesso": resultado.sucesso,
            "mensagem": resultado.mensagem_erro or "Cadastrado com sucesso.",
        })

    db.session.commit()

    return render_template("resultado.html", lote=lote, resultados=resultados_para_tela)
