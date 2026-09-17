# Integração ApisulLog

App interno (Flask + Postgres) para cadastrar entidades na API de integração
da ApisulLog a partir de planilhas Excel. V1 cobre **Ponto Geográfico**; o
mapeamento completo da API está em [`docs/API_MAPEAMENTO.md`](docs/API_MAPEAMENTO.md).

Fluxo: login → selecionar tipo de cadastro → baixar modelo de Excel →
preencher → enviar → o app valida cada linha, chama a API (SOAP) e grava o
payload enviado + a resposta de cada chamada no Postgres.

## Setup

1. **Dependências Python**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Banco Postgres do app** (guarda usuários e o histórico de chamadas —
   é um banco novo, separado dos bancos de leitura já usados em `db_config/`
   na raiz do workspace).
   ```bash
   cp config/db_config.template.json config/db_config.json
   # edite host/dbname/user
   cp .env.example .env
   # preencha INTEGRACAO_DB_PASSWORD no .env
   ```

3. **Credenciais de integração ApisulLog** (a conta de serviço usada para
   chamar a API, não confundir com o login do usuário do app):
   ```bash
   cp config/apisul_config.template.json config/apisul_config.json
   # edite "usuario"; a senha vai em APISUL_INTEGRACAO_SENHA no .env
   ```
   O `base_url` já vem apontando para homologação
   (`hml-api-novoapisullog.apisul.com.br`); trocar para produção quando for
   a hora.

4. **Criar as tabelas e o primeiro usuário do app**
   ```bash
   export FLASK_APP=run.py
   flask init-db
   flask criar-usuario
   ```

5. **Rodar**
   ```bash
   python run.py
   # http://localhost:5000
   ```

## Estrutura

```
app/
  models.py               Usuario, LoteImportacao, ChamadaApi (SQLAlchemy)
  routes/                 auth (login), dashboard (seleção), ponto_geografico
  services/
    auth_token_client.py  POST /v1/Auth/Token -> token de integração (cacheado)
    soap_client.py        cliente zeep genérico p/ qualquer *.svc da Apisul
    ponto_geografico_service.py   chama InserePontoGeografico e interpreta o retorno
    excel_ponto_geografico.py     gera o modelo .xlsx e valida a planilha enviada
config/
  settings.py              carrega db_config.json / apisul_config.json + .env
docs/
  API_MAPEAMENTO.md         o que foi descoberto na API (WSDL, auth, campos)
  PontoGeografico.wsdl       WSDL bruto baixado do ambiente de homologação
  swagger_v2_apisullog.json  spec REST completa (para referência)
```

## Adicionar um novo cadastro (ex.: Motorista)

Confirmado que existe `ApisulLog.Integracao.Motorista.svc` (e Rota, Emitente,
SMP) — mesmo padrão do PontoGeografico. Passos para replicar:

1. Baixar o WSDL: `.../ApisulLog.Integracao.Motorista.svc?singleWsdl` e
   documentar os campos em `docs/API_MAPEAMENTO.md`.
2. Adicionar a URL em `config/apisul_config.template.json` ->
   `servicos_soap.motorista`.
3. Criar `app/services/excel_motorista.py` (mesma forma de
   `excel_ponto_geografico.py`, trocando a lista `COLUNAS`).
4. Criar `app/services/motorista_service.py` (mesma forma de
   `ponto_geografico_service.py`).
5. Criar `app/routes/motorista.py` (copiar `ponto_geografico.py`) + templates.
6. Marcar `"disponivel": True` no card correspondente em
   `app/routes/dashboard.py`.

## Pendências para validar contra a API real

- Formato exato da resposta de `POST /v1/Auth/Token` (o swagger não
  documenta o schema — só foi possível confirmar `{Usuario, Senha}` na
  entrada). `auth_token_client._extrair_token` cobre os formatos mais
  comuns; ajustar no primeiro teste com credenciais de homologação.
- No XSD do WSDL todo campo de `PontoGeograficoModeloIntegracao` é opcional
  (`minOccurs="0"`) — a coluna "obrigatório" do Excel em
  `excel_ponto_geografico.py` é uma inferência de negócio. Ajustar assim que
  a API real devolver mensagens de validação.
