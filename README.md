# Integração ApisulLog

App interno (Flask + Postgres) para cadastrar entidades na API de integração
da ApisulLog a partir de planilhas Excel. V1 cobre **Ponto Geográfico**; o
mapeamento completo da API está em [`docs/API_MAPEAMENTO.md`](docs/API_MAPEAMENTO.md).

Fluxo: login → selecionar tipo de cadastro → baixar modelo de Excel →
preencher → informar o **token de integração** (gerado pela Apisul,
`POST /v1/Auth/Token`) → enviar → o app valida cada linha, chama a API (SOAP)
usando esse token e grava o payload enviado + a resposta de cada chamada no
Postgres.

O token é digitado na própria tela a cada envio (não fica salvo em
configuração nem no banco) — isso deixa o app "plugável" em qualquer token
válido para testar, sem precisar reconfigurar nada.

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

3. **URL da API Apisul** (só a URL do ambiente — o token de cada chamada é
   digitado na tela, não fica configurado aqui):
   ```bash
   cp config/apisul_config.template.json config/apisul_config.json
   ```
   O `base_url` já vem apontando para homologação
   (`hml-api-novoapisullog.apisul.com.br`); trocar para produção quando for
   a hora. Os campos `usuario`/`senha` do arquivo só importam se um dia
   ligarmos a geração automática de token (`app/services/auth_token_client.py`,
   hoje não usada no fluxo principal).

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
    auth_token_client.py  POST /v1/Auth/Token -> token (não usado no fluxo atual, ver Pendências)
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

- V1 usa **token manual**: o usuário cola na tela um token já gerado (por
  exemplo via Postman, chamando `POST /v1/Auth/Token` com Usuario/Senha).
  `app/services/auth_token_client.py` já implementa essa chamada e um cache
  de token, para quando quisermos automatizar isso dentro do próprio app —
  falta então plugá-lo na rota e decidir onde guardar a credencial de
  serviço com segurança (Secrets Manager, por exemplo).
- No XSD do WSDL todo campo de `PontoGeograficoModeloIntegracao` é opcional
  (`minOccurs="0"`) — a coluna "obrigatório" do Excel em
  `excel_ponto_geografico.py` é uma inferência de negócio. Ajustar assim que
  a API real devolver mensagens de validação.
