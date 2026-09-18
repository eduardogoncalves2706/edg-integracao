"""Geração do modelo de Excel e leitura/validação da planilha preenchida
para o cadastro de Ponto Geográfico.

O bloco "básico" de colunas replica a planilha oficial de coleta de dados da
Apisul (`RQ IMP 002`, aba "Pontos") — mesmos títulos, mesma ordem e a mesma
regra de obrigatoriedade condicional documentada lá: "Caso colunas Latitude
e Longitude não forem preenchidas, os campos Endereço, Número, Cep e Bairro
serão de preenchimento obrigatório". O bloco "avançado" expõe campos que a
API SOAP aceita (`PontoGeograficoModeloIntegracao`, ver docs/API_MAPEAMENTO.md)
mas que não fazem parte do formulário padrão de coleta — ficam opcionais.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

NOME_ABA_DADOS = "PontoGeografico"
NOME_ABA_INSTRUCOES = "Instrucoes"
MARCADOR_LINHA_EXEMPLO = "EXEMPLO-APAGAR-ESTA-LINHA"

# Domínio oficial de "Tipo de Ponto" -> IdTipoPonto, confirmado pela Apisul
# em 2026-09-18. Alguns rótulos do dropdown da planilha RQ IMP 002 (Planta,
# Checkpoint, Cross Docking) não existem nessa tabela oficial — foram
# removidos do dropdown do modelo até a Apisul esclarecer o equivalente.
TIPOS_PONTO: dict[str, int] = {
    "Permitido": 1,
    "Proibido": 2,
    "CD": 3,
    "Filial": 4,
    "Matriz": 5,
    "Fábrica": 6,
    "Pátio": 7,
    "Oficina": 8,
    "Expedição": 9,
    "CDD": 10,
    "Ponto de Entrega": 11,
    "Área": 12,
}


@dataclass
class Coluna:
    campo: str
    titulo: str
    obrigatorio: bool
    tipo: str  # "texto" | "inteiro" | "decimal" | "data" | "tipo_ponto"
    exemplo: Any
    descricao: str
    avancado: bool = False


COLUNAS: list[Coluna] = [
    # --- bloco básico: espelha a planilha oficial RQ IMP 002 (aba "Pontos") ---
    Coluna("Identificador", "Identificador (Nome do ponto)", True, "texto", "Grupo Apisul", ""),
    Coluna("TipoPonto", "Tipo de Ponto", True, "tipo_ponto", "Matriz",
           "Selecione um dos valores da lista (CD, Filial, Matriz, Fábrica, CDD, "
           "Ponto de entrega, Planta, Checkpoint, Cross Docking)."),
    Coluna("Endereco", "Rua/Avenida/Estrada", False, "texto", "Rua Pereira Franco",
           "Obrigatório se Latitude/Longitude não forem preenchidas."),
    Coluna("Numero", "Número", False, "texto", "347",
           "Obrigatório se Latitude/Longitude não forem preenchidas."),
    Coluna("Bairro", "Bairro", False, "texto", "São João",
           "Obrigatório se Latitude/Longitude não forem preenchidas."),
    Coluna("CEP", "Cep", False, "texto", "90240-520",
           "Obrigatório se Latitude/Longitude não forem preenchidas."),
    Coluna("Cidade", "Cidade", True, "texto", "Porto Alegre", ""),
    Coluna("UF", "UF", True, "texto", "RS", "Sigla com 2 letras."),
    Coluna("Pais", "País", False, "texto", "Brasil", "Padrão: Brasil, se deixado em branco."),
    Coluna("CNPJ", "CNPJ", False, "texto", "64127812000185", ""),
    Coluna("Telefone", "Telefone", False, "texto", "(51) 2121-9005", ""),
    Coluna("Latitude", "Latitude", False, "decimal", -30.004108,
           "Se preenchida junto com Longitude, dispensa endereço completo."),
    Coluna("Longitude", "Longitude", False, "decimal", -51.191499, ""),
    # --- bloco avançado: aceito pela API, fora do formulário padrão de coleta ---
    Coluna("IdentificadorCliente", "[Avançado] Identificador Cliente", False, "inteiro", "",
           "Código interno do cliente dono do ponto, se aplicável.", avancado=True),
    Coluna("CodigoIBGECidade", "[Avançado] Código IBGE Cidade", False, "inteiro", "",
           "", avancado=True),
    Coluna("Raio", "[Avançado] Raio (m)", False, "inteiro", "",
           "Raio da geofence em metros.", avancado=True),
    Coluna("IdTipoGeoGeoCodeIntegracao", "[Avançado] Id Tipo Geocode", False, "inteiro", "",
           "", avancado=True),
    Coluna("TipoGeorreferenciamento", "[Avançado] Tipo Georreferenciamento", False, "texto", "",
           "", avancado=True),
    Coluna("JanelaInicial", "[Avançado] Janela Inicial", False, "data", "",
           "Data/hora ou HH:MM.", avancado=True),
    Coluna("JanelaFinal", "[Avançado] Janela Final", False, "data", "",
           "Data/hora ou HH:MM.", avancado=True),
    Coluna("IdPontoGeografico", "[Avançado] Id Ponto Geografico (update)", False, "inteiro", "",
           "Deixe em branco para novo cadastro. Preencha para atualizar um ponto existente.",
           avancado=True),
]

_COLUNAS_ENDERECO_CONDICIONAL = ("Endereco", "Numero", "Bairro", "CEP")


def gerar_modelo() -> BytesIO:
    wb = Workbook()
    aba: Worksheet = wb.active
    aba.title = NOME_ABA_DADOS

    cabecalho_font = Font(bold=True, color="FFFFFF")
    cabecalho_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    avancado_fill = PatternFill(start_color="5B7A99", end_color="5B7A99", fill_type="solid")
    obrigatorio_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

    for col_idx, coluna in enumerate(COLUNAS, start=1):
        celula = aba.cell(row=1, column=col_idx, value=coluna.titulo + (" *" if coluna.obrigatorio else ""))
        celula.font = cabecalho_font
        celula.fill = avancado_fill if coluna.avancado else cabecalho_fill
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

    # dropdown de Tipo de Ponto, igual à planilha oficial RQ IMP 002
    idx_tipo_ponto = next(i for i, c in enumerate(COLUNAS, start=1) if c.campo == "TipoPonto")
    coluna_letra = aba.cell(row=1, column=idx_tipo_ponto).column_letter
    dv = DataValidation(
        type="list",
        formula1='"' + ",".join(TIPOS_PONTO.keys()) + '"',
        allow_blank=True,
        showDropDown=False,
    )
    aba.add_data_validation(dv)
    dv.add(f"{coluna_letra}2:{coluna_letra}1048576")

    instrucoes = wb.create_sheet(NOME_ABA_INSTRUCOES)
    instrucoes.append([
        "Informe o endereço completo (Rua, Número, Bairro, Cep) OU Latitude/Longitude.",
    ])
    instrucoes.append([
        "Se Latitude e Longitude ficarem em branco, Rua/Número/Bairro/Cep passam a ser obrigatórios.",
    ])
    instrucoes.append([])
    instrucoes.append(["Campo", "Obrigatório", "Tipo", "Exemplo", "Descrição"])
    for cel in instrucoes[4]:
        cel.font = cabecalho_font
        cel.fill = cabecalho_fill
    for coluna in COLUNAS:
        instrucoes.append([
            coluna.titulo,
            "Sim" if coluna.obrigatorio else ("Condicional" if coluna.campo in _COLUNAS_ENDERECO_CONDICIONAL else "Não"),
            coluna.tipo,
            coluna.exemplo,
            coluna.descricao,
        ])
    for largura, col_letra in zip([32, 14, 12, 20, 60], ["A", "B", "C", "D", "E"]):
        instrucoes.column_dimensions[col_letra].width = largura

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


def _converter(valor, coluna: Coluna, erros: list[str]):
    vazio = valor is None or (isinstance(valor, str) and not valor.strip())

    if coluna.tipo == "tipo_ponto":
        if vazio:
            if coluna.obrigatorio:
                erros.append(f"'{coluna.titulo}' é obrigatório.")
            return None
        texto = str(valor).strip()
        if texto not in TIPOS_PONTO:
            erros.append(
                f"'{coluna.titulo}': valor '{texto}' não reconhecido. "
                f"Use um dos valores da lista: {', '.join(TIPOS_PONTO)}."
            )
            return None
        return texto

    if vazio:
        if coluna.obrigatorio:
            erros.append(f"'{coluna.titulo}' é obrigatório.")
        return None
    try:
        if coluna.tipo == "texto":
            return str(valor).strip()
        if coluna.tipo == "inteiro":
            return int(float(valor))
        if coluna.tipo == "decimal":
            return float(valor)
        if coluna.tipo == "data":
            if isinstance(valor, datetime):
                return valor
            texto = str(valor).strip()
            for formato in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%H:%M"):
                try:
                    return datetime.strptime(texto, formato)
                except ValueError:
                    continue
            erros.append(f"'{coluna.titulo}': data/hora '{valor}' em formato não reconhecido.")
            return None
    except (TypeError, ValueError):
        erros.append(f"'{coluna.titulo}': valor '{valor}' inválido para tipo {coluna.tipo}.")
        return None
    return valor


def _validar_regra_endereco_ou_coordenada(dados: dict[str, Any], erros: list[str]) -> None:
    """Replica a regra da planilha oficial: sem Lat/Long, o endereço completo
    (Rua, Número, Bairro, Cep) vira obrigatório."""
    tem_coordenada = dados.get("Latitude") is not None and dados.get("Longitude") is not None
    if tem_coordenada:
        return
    faltando = [
        COLUNAS_POR_CAMPO[campo].titulo
        for campo in _COLUNAS_ENDERECO_CONDICIONAL
        if not dados.get(campo)
    ]
    if faltando:
        erros.append(
            "Sem Latitude/Longitude, é obrigatório informar: " + ", ".join(faltando) + "."
        )


COLUNAS_POR_CAMPO = {c.campo: c for c in COLUNAS}


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
            lv.dados[coluna.campo] = _converter(valor_bruto, coluna, lv.erros)

        _validar_regra_endereco_ou_coordenada(lv.dados, lv.erros)
        linhas.append(lv)

    return linhas


def montar_payload_soap(dados: dict[str, Any]) -> dict[str, Any]:
    """Converte uma linha validada no formato esperado por
    PontoGeograficoModeloIntegracao (monta Coordenadas a partir de Lat/Long,
    converte o rótulo de Tipo de Ponto para o código numérico IdTipoPonto)."""
    latitude = dados.get("Latitude")
    longitude = dados.get("Longitude")
    coordenadas = None
    if latitude is not None and longitude is not None:
        coordenadas = {"Coordenada": [{"Latitude": latitude, "Longitude": longitude}]}

    tipo_ponto = dados.get("TipoPonto")
    id_tipo_ponto = TIPOS_PONTO.get(tipo_ponto) if tipo_ponto else None

    payload = {
        "Identificador": dados.get("Identificador"),
        "IdentificadorCliente": dados.get("IdentificadorCliente"),
        "Apelido": dados.get("Identificador"),
        "CNPJ": dados.get("CNPJ"),
        "Endereco": dados.get("Endereco"),
        "Numero": dados.get("Numero"),
        "Bairro": dados.get("Bairro"),
        "Cidade": dados.get("Cidade"),
        "CodigoIBGECidade": dados.get("CodigoIBGECidade"),
        "UF": dados.get("UF"),
        "Pais": dados.get("Pais") or "Brasil",
        "CEP": dados.get("CEP"),
        "Telefone": dados.get("Telefone"),
        "Coordenadas": coordenadas,
        "Raio": dados.get("Raio"),
        "IdTipoPonto": id_tipo_ponto,
        "IdTipoGeoGeoCodeIntegracao": dados.get("IdTipoGeoGeoCodeIntegracao"),
        "TipoGeorreferenciamento": dados.get("TipoGeorreferenciamento"),
        "JanelaInicial": dados.get("JanelaInicial"),
        "JanelaFinal": dados.get("JanelaFinal"),
        "IdPontoGeografico": dados.get("IdPontoGeografico") or 0,
    }
    return {k: v for k, v in payload.items() if v is not None}
