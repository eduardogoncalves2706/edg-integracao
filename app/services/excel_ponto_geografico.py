"""Geração do modelo de Excel e leitura/validação da planilha preenchida
para o cadastro de Ponto Geográfico.

A lista de colunas espelha `PontoGeograficoModeloIntegracao` do WSDL (ver
docs/API_MAPEAMENTO.md). `Latitude`/`Longitude` são colunas achatadas do
array `Coordenadas` — v1 assume um único par de coordenadas por ponto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

NOME_ABA_DADOS = "PontoGeografico"
NOME_ABA_INSTRUCOES = "Instrucoes"
MARCADOR_LINHA_EXEMPLO = "EXEMPLO-APAGAR-ESTA-LINHA"


@dataclass
class Coluna:
    campo: str
    titulo: str
    obrigatorio: bool
    tipo: str  # "texto" | "inteiro" | "decimal" | "data"
    exemplo: Any
    descricao: str


COLUNAS: list[Coluna] = [
    Coluna("Identificador", "Identificador", True, "texto", "PG-0001",
           "Chave única do ponto no seu sistema. Usada para localizar/atualizar depois."),
    Coluna("IdentificadorCliente", "Identificador Cliente", False, "inteiro", "",
           "Código interno do cliente dono do ponto, se aplicável."),
    Coluna("Apelido", "Apelido", True, "texto", "CD Guarulhos",
           "Nome amigável exibido nas telas da Apisul."),
    Coluna("CNPJ", "CNPJ", False, "texto", "12345678000199", "Somente números."),
    Coluna("Endereco", "Endereço", True, "texto", "Rod. Presidente Dutra, km 220", ""),
    Coluna("Numero", "Número", False, "texto", "1500", ""),
    Coluna("Bairro", "Bairro", False, "texto", "Cumbica", ""),
    Coluna("Cidade", "Cidade", True, "texto", "Guarulhos", ""),
    Coluna("CodigoIBGECidade", "Código IBGE Cidade", False, "inteiro", 3518800, ""),
    Coluna("UF", "UF", True, "texto", "SP", "Sigla com 2 letras."),
    Coluna("Estado", "Estado", False, "texto", "São Paulo", ""),
    Coluna("Pais", "País", False, "texto", "Brasil", "Padrão: Brasil, se deixado em branco."),
    Coluna("CEP", "CEP", False, "texto", "07034000", "Somente números."),
    Coluna("Telefone", "Telefone", False, "texto", "1123456789", ""),
    Coluna("Latitude", "Latitude", False, "decimal", -23.4356, ""),
    Coluna("Longitude", "Longitude", False, "decimal", -46.4731, ""),
    Coluna("Raio", "Raio (m)", False, "inteiro", 300, "Raio da geofence em metros."),
    Coluna("IdTipoPonto", "Id Tipo Ponto", True, "inteiro", 1,
           "Domínio de tipos de ponto definido pela Apisul (consultar tabela)."),
    Coluna("IdTipoGeoGeoCodeIntegracao", "Id Tipo Geocode", False, "inteiro", "", ""),
    Coluna("TipoGeorreferenciamento", "Tipo Georreferenciamento", False, "texto", "", ""),
    Coluna("JanelaInicial", "Janela Inicial", False, "data", "08:00", "Data/hora ou HH:MM."),
    Coluna("JanelaFinal", "Janela Final", False, "data", "18:00", "Data/hora ou HH:MM."),
    Coluna("IdPontoGeografico", "Id Ponto Geografico (update)", False, "inteiro", "",
           "Deixe em branco para novo cadastro. Preencha para atualizar um ponto existente."),
]


def gerar_modelo() -> BytesIO:
    wb = Workbook()
    aba: Worksheet = wb.active
    aba.title = NOME_ABA_DADOS

    cabecalho_font = Font(bold=True, color="FFFFFF")
    cabecalho_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    obrigatorio_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

    for col_idx, coluna in enumerate(COLUNAS, start=1):
        celula = aba.cell(row=1, column=col_idx, value=coluna.titulo + (" *" if coluna.obrigatorio else ""))
        celula.font = cabecalho_font
        celula.fill = cabecalho_fill
        celula.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if coluna.obrigatorio:
            aba.cell(row=2, column=col_idx).fill = obrigatorio_fill
        aba.column_dimensions[celula.column_letter].width = max(16, len(coluna.titulo) + 2)

    aba.cell(row=2, column=1, value=MARCADOR_LINHA_EXEMPLO)
    for col_idx, coluna in enumerate(COLUNAS, start=1):
        if col_idx == 1:
            continue
        aba.cell(row=2, column=col_idx, value=coluna.exemplo)
    for cel in aba[2]:
        cel.font = Font(italic=True, color="808080")

    aba.freeze_panes = "A3"

    instrucoes = wb.create_sheet(NOME_ABA_INSTRUCOES)
    instrucoes.append(["Campo", "Obrigatório", "Tipo", "Exemplo", "Descrição"])
    for cel in instrucoes[1]:
        cel.font = cabecalho_font
        cel.fill = cabecalho_fill
    for coluna in COLUNAS:
        instrucoes.append([
            coluna.titulo,
            "Sim" if coluna.obrigatorio else "Não",
            coluna.tipo,
            coluna.exemplo,
            coluna.descricao,
        ])
    for largura, col_letra in zip([26, 12, 10, 20, 60], ["A", "B", "C", "D", "E"]):
        instrucoes.column_dimensions[col_letra].width = largura
    instrucoes.append([])
    instrucoes.append(["Preencha a aba 'PontoGeografico'. A linha 2 é um exemplo — pode"
                        " apagar o conteúdo dela ou sobrescrever, mas não apague a linha 1"
                        " (cabeçalho)."])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


@dataclass
class LinhaValidada:
    numero_linha: int
    dados: dict[str, Any] = field(default_factory=dict)
    erros: list[str] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return not self.erros


def _converter(valor, tipo: str, obrigatorio: bool, titulo: str, erros: list[str]):
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obrigatorio:
            erros.append(f"'{titulo}' é obrigatório.")
        return None
    try:
        if tipo == "texto":
            return str(valor).strip()
        if tipo == "inteiro":
            return int(float(valor))
        if tipo == "decimal":
            return float(valor)
        if tipo == "data":
            if isinstance(valor, datetime):
                return valor
            texto = str(valor).strip()
            for formato in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%H:%M"):
                try:
                    return datetime.strptime(texto, formato)
                except ValueError:
                    continue
            erros.append(f"'{titulo}': data/hora '{valor}' em formato não reconhecido.")
            return None
    except (TypeError, ValueError):
        erros.append(f"'{titulo}': valor '{valor}' inválido para tipo {tipo}.")
        return None
    return valor


def ler_planilha(arquivo) -> list[LinhaValidada]:
    """Lê um arquivo .xlsx (file-like) e devolve uma linha validada por registro."""
    wb = load_workbook(arquivo, data_only=True)
    if NOME_ABA_DADOS not in wb.sheetnames:
        raise ValueError(
            f"A planilha enviada não tem a aba '{NOME_ABA_DADOS}'. Baixe o modelo atualizado."
        )
    aba = wb[NOME_ABA_DADOS]

    linhas: list[LinhaValidada] = []
    for numero_linha, linha_valores in enumerate(
        aba.iter_rows(min_row=2, values_only=True), start=2
    ):
        if not any(linha_valores):
            continue
        if linha_valores and str(linha_valores[0] or "").strip() == MARCADOR_LINHA_EXEMPLO:
            continue

        lv = LinhaValidada(numero_linha=numero_linha)
        for idx, coluna in enumerate(COLUNAS):
            valor_bruto = linha_valores[idx] if idx < len(linha_valores) else None
            lv.dados[coluna.campo] = _converter(
                valor_bruto, coluna.tipo, coluna.obrigatorio, coluna.titulo, lv.erros
            )
        linhas.append(lv)

    return linhas


def montar_payload_soap(dados: dict[str, Any]) -> dict[str, Any]:
    """Converte uma linha validada no formato esperado por
    PontoGeograficoModeloIntegracao (monta Coordenadas a partir de Lat/Long)."""
    latitude = dados.get("Latitude")
    longitude = dados.get("Longitude")
    coordenadas = None
    if latitude is not None and longitude is not None:
        coordenadas = {"Coordenada": [{"Latitude": latitude, "Longitude": longitude}]}

    payload = {
        "Identificador": dados.get("Identificador"),
        "IdentificadorCliente": dados.get("IdentificadorCliente"),
        "Apelido": dados.get("Apelido"),
        "CNPJ": dados.get("CNPJ"),
        "Endereco": dados.get("Endereco"),
        "Numero": dados.get("Numero"),
        "Bairro": dados.get("Bairro"),
        "Cidade": dados.get("Cidade"),
        "CodigoIBGECidade": dados.get("CodigoIBGECidade"),
        "UF": dados.get("UF"),
        "Estado": dados.get("Estado"),
        "Pais": dados.get("Pais") or "Brasil",
        "CEP": dados.get("CEP"),
        "Telefone": dados.get("Telefone"),
        "Coordenadas": coordenadas,
        "Raio": dados.get("Raio"),
        "IdTipoPonto": dados.get("IdTipoPonto"),
        "IdTipoGeoGeoCodeIntegracao": dados.get("IdTipoGeoGeoCodeIntegracao"),
        "TipoGeorreferenciamento": dados.get("TipoGeorreferenciamento"),
        "JanelaInicial": dados.get("JanelaInicial"),
        "JanelaFinal": dados.get("JanelaFinal"),
        "IdPontoGeografico": dados.get("IdPontoGeografico") or 0,
    }
    return {k: v for k, v in payload.items() if v is not None}
