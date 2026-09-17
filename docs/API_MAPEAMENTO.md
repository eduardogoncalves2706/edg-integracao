# Mapeamento da API ApisulLog Integração

Levantamento feito em 2026-09-17 a partir do ambiente de homologação:
- Swagger REST: https://hml-api-novoapisullog.apisul.com.br/swagger/ui/index
  (discovery real: `swagger/docs/v2` — o `swagger/docs/v1` não existe)
- Serviço SOAP PontoGeografico: https://hml-api-novoapisullog.apisul.com.br/ApisulLog.Integracao.PontoGeografico.svc

## Duas famílias de API, não uma só

O Swagger em `/swagger/ui/index` documenta a API **REST** do ApisulLog (app
motorista/ChatBot/Fretes/SMP/Rastreamento etc — 105 rotas, ver
`swagger_v2_apisullog.json`). **PontoGeografico não está nessa lista.**

Os cadastros de integração (`ApisulLog.Integracao.*`) são serviços **SOAP
(WCF)** separados, um `.svc` por entidade. Confirmado por sondagem HTTP:

| Serviço              | URL                                                              | Status |
|----------------------|-------------------------------------------------------------------|--------|
| PontoGeografico       | `/ApisulLog.Integracao.PontoGeografico.svc`                       | 200 (implementado) |
| Motorista             | `/ApisulLog.Integracao.Motorista.svc`                             | 200 (existe — próximo cadastro) |
| Rota                  | `/ApisulLog.Integracao.Rota.svc`                                  | 200 (existe) |
| Emitente              | `/ApisulLog.Integracao.Emitente.svc`                              | 200 (existe) |
| SMP                   | `/ApisulLog.Integracao.SMP.svc`                                   | 200 (existe) |
| Frete/Autenticacao/Usuario/Token | — | 404 (não existem com esse nome) |

Cada `.svc?singleWsdl` traz o contrato completo (operações, tipos, campos
obrigatórios). O app foi desenhado para ler esse WSDL e gerar o
Excel/validação automaticamente a partir dele (ver `app/services/soap_client.py`),
então adicionar Motorista/Rota/Emitente/SMP depois é replicar o padrão do
PontoGeografico, não reinventar.

## Autenticação (gera o `token` usado nas chamadas SOAP)

O token numérico exigido em todas as operações SOAP (`token: xs:int`) é obtido
via REST, que **está** no swagger v2:

```
POST /v1/Auth/Token
Body: { "Usuario": "string", "Senha": "string" }
Resposta: object (schema não detalhado no swagger — validar no primeiro teste
          real com credenciais de homologação; ver services/auth_token_client.py
          para o parsing defensivo já implementado)
```

Existe também `/v2/Login/GetLogin` (Usuario/Serial) e `/v2/Login/AutenticarLogin`,
mas parecem ser do fluxo do app motorista (ApisulMob), não do integrador — por
isso o app usa `/v1/Auth/Token`.

**Importante:** este token de integração é uma credencial de sistema (uma
conta de serviço fornecida pela Apisul para a integração), diferente do
login usuário/senha do próprio app de integração (esse é só controle de
acesso interno, gravado no Postgres). Configurar em `config/apisul_config.json`.

## Contrato SOAP — PontoGeografico

Porta: `IPontoGeografico` (BasicHttpBinding, doc/literal). Três operações:

### 1. InserePontoGeografico (cadastro/upsert)
Entrada: `token (int)` + `pontoModeloIntegracao`:

| Campo                      | Tipo       | Obrigatório* | Observação |
|----------------------------|------------|--------------|------------|
| Identificador              | string     | recomendado  | chave do ponto no seu sistema |
| IdentificadorCliente       | int        | opcional     | |
| Apelido                    | string     | recomendado  | nome amigável do ponto |
| CNPJ                       | string     | condicional  | |
| Endereco                   | string     | sim          | |
| Numero                     | string     | não          | |
| Bairro                     | string     | não          | |
| Cidade                     | string     | sim          | |
| CodigoIBGECidade           | int        | recomendado  | |
| Estado / UF                | string     | sim          | |
| Pais                       | string     | sim          | default "Brasil" |
| CEP                        | string     | recomendado  | |
| Telefone                   | string     | não          | |
| Coordenadas                | Coordenada[] (Latitude/Longitude double) | recomendado | array — v1 do app trata 1 par lat/long por linha |
| Raio                       | int        | não          | metros, geofence |
| IdTipoPonto                | byte       | sim          | domínio definido pela Apisul |
| IdTipoGeoGeoCodeIntegracao | int        | não          | |
| TipoGeorreferenciamento    | string     | não          | |
| JanelaInicial / JanelaFinal| dateTime   | não          | janela de atendimento |
| IdPontoGeografico          | int        | não (0 = novo) | usado pela Apisul para update |

(*) "Obrigatório" aqui é inferência de negócio — no XSD **todos os campos
estão `minOccurs="0"`**, ou seja, o WSDL não impõe nada; a API deve validar
em runtime. Ajustar a coluna "obrigatório" do Excel assim que o primeiro
teste real contra a homologação devolver mensagens de erro de validação.

Saída: `RetornoInserePontoGeografico` = `TransacaoOk (bool)` +
`MensagensErro[] (Codigo, Mensagem)` + `MensagensAviso[]` + `MensagensSucesso[]`
+ `PontoGeografico` (o objeto persistido, com `IdPontoGeografico` preenchido).

### 2. BuscaPontoGeografico / BuscaPontosGeograficos
Busca por `Apelido`, `CNPJ`, `Identificador` ou `IdentificadorCliente`.
Não usadas no fluxo de cadastro em lote (v1), ficam disponíveis em
`services/soap_client.py` para uma futura tela de consulta.

## Arquivo bruto
- `PontoGeografico.wsdl` — WSDL completo baixado (`?singleWsdl`)
- `swagger_v2_apisullog.json` — spec REST completo (`swagger/docs/v2`)
