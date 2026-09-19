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
| PontoGeografico       | `/ApisulLog.Integracao.PontoGeografico.svc`                       | 200 (implementado, cadastro via SOAP) |
| Motorista             | `/ApisulLog.Integracao.Motorista.svc`                             | 200 (existe, mas só tem `BuscaPontuacao` — ver abaixo) |
| Rota                  | `/ApisulLog.Integracao.Rota.svc`                                  | 200 (existe) |
| Emitente              | `/ApisulLog.Integracao.Emitente.svc`                              | 200 (existe) |
| SMP                   | `/ApisulLog.Integracao.SMP.svc`                                   | 200 (existe) |
| Frete/Autenticacao/Usuario/Token | — | 404 (não existem com esse nome) |

Cada `.svc?singleWsdl` traz o contrato completo (operações, tipos, campos
obrigatórios). O app foi desenhado para ler esse WSDL e gerar o
Excel/validação automaticamente a partir dele (ver `app/services/soap_client.py`).

**Correção importante (2026-09-18):** nem todo cadastro é SOAP. O
`.svc` de Motorista só expõe `BuscaPontuacao` — o **cadastro** de motorista
(`InsereMotorista`) é uma rota **REST** do mesmo Swagger que documenta o
token (`POST /insereMotorista`, tag `Motorista`, operação
`Motorista_PostAsync`). Ou seja: antes de implementar um cadastro novo,
**checar os dois lugares** (o `.svc?singleWsdl` E o swagger REST) em vez de
assumir que segue o padrão SOAP do PontoGeografico. Ver `app/services/rest_client.py`
pro cliente REST genérico, usado pelo Motorista.

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

## Planilha oficial de coleta (RQ IMP 002, aba "Pontos")

Em `docs/1.1. Planilha de coleta de dados - RQ IMP 002...xlsx` está o
formulário padrão que a Apisul já usa para coletar pontos
geográficos dos clientes. É uma fonte melhor que o WSDL pra decidir o que
realmente é obrigatório no dia a dia — o modelo de Excel do app
(`app/services/excel_ponto_geografico.py`) foi realinhado com ela:

- **Colunas e ordem** iguais à aba "Pontos": Identificador (Nome do ponto),
  Tipo de Ponto, Rua/Avenida/Estrada, Número, Bairro, Cep, Cidade, UF, País,
  CNPJ, Telefone, Latitude, Longitude. Campos extras que só a API aceita
  (IdentificadorCliente, Raio, JanelaInicial/Final etc.) viraram um bloco
  "[Avançado]" opcional no fim da planilha, fora do formulário padrão.
- **Regra de obrigatoriedade condicional**, copiada literalmente da
  instrução da planilha: *"Caso colunas Latitude e Longitude não forem
  preenchidas, os campos Endereço, Número, Cep e Bairro serão de
  preenchimento obrigatório."* Implementada em
  `_validar_regra_endereco_ou_coordenada`.
- **"Tipo de Ponto" é uma lista suspensa** (data validation da própria
  planilha) com os valores: `CD, Filial, Matriz, Fábrica, CDD, Ponto de
  entrega, Planta, Checkpoint, Cross Docking`. O modelo gerado pelo app
  reproduz esse dropdown.

### Código numérico de IdTipoPonto (confirmado)

Tabela oficial De→Para confirmada em 2026-09-18 (`TIPOS_PONTO` em
`excel_ponto_geografico.py`):

| Rótulo           | IdTipoPonto |
|-------------------|:-----------:|
| Permitido         | 1 |
| Proibido          | 2 |
| CD                | 3 |
| Filial            | 4 |
| Matriz            | 5 |
| Fábrica           | 6 |
| Pátio             | 7 |
| Oficina           | 8 |
| Expedição         | 9 |
| CDD               | 10 |
| Ponto de Entrega  | 11 |
| Área              | 12 |

Os rótulos "Planta", "Checkpoint" e "Cross Docking" que apareciam no
dropdown da planilha RQ IMP 002 não têm equivalente nessa tabela — foram
removidos do dropdown do modelo de Excel até a Apisul esclarecer o
equivalente correto.

## Ambientes

| Ambiente | Base URL |
|----------|----------|
| Homologação | `https://hml-api-novoapisullog.apisul.com.br` |
| Produção | `https://api-novoapisullog.apisul.com.br` (mesma estrutura, sem o prefixo `hml-`) |

## Primeiro cadastro real (2026-09-18) — funcionou

Testado `InserePontoGeografico` em **produção**, com token de uma conta de
teste (`379981910`), só endereço (sem Lat/Long), `IdTipoPonto=3` (CD):

```json
{"Identificador": "TESTE-CLAUDE-001", "Apelido": "TESTE-CLAUDE-001",
 "Endereco": "Rua Pereira Franco", "Numero": "347", "Bairro": "Sao Joao",
 "Cidade": "Porto Alegre", "UF": "RS", "Pais": "Brasil", "CEP": "90240520",
 "IdTipoPonto": 3, "IdPontoGeografico": 0}
```

`TransacaoOk: true`. Retornou `IdPontoGeografico = 10220474` — **esse ponto
ficou de verdade cadastrado na conta**, é o "TESTE-CLAUDE-001" que aparece
no painel da Apisul; apagar/renomear lá se não for pra manter.

Descobertas importantes desse teste:
- **A API geocodifica sozinha** o endereço informado (sem precisar mandar
  Lat/Long): devolveu `Coordenadas` como um polígono de 5 pontos (a área do
  endereço), `CodigoIBGECidade`, `Estado` por extenso e
  `TipoGeorreferenciamento: "Endereço"` preenchidos automaticamente.
- **Raio tem default de 500m** quando não informado — vem como aviso, não
  erro: `MensagensAviso: [{"Codigo": 5022, "Mensagem": "Como o Raio não foi
  informado, será considerado o valor padrão de 500 m"}]`.
- **Chamada é lenta**: ~37s de ponta a ponta (client SOAP + geocodificação
  do lado da Apisul). Para lotes grandes de planilha, isso significa que um
  upload de N linhas leva N × ~30-40s de forma síncrona — vale considerar
  processamento assíncrono/fila se os lotes crescerem além de umas poucas
  dezenas de linhas.
- Confirma que os nomes de campo do payload (`Endereco`, `Numero`, `Bairro`,
  `Cidade`, `UF`, `Pais`, `CEP`, `Identificador`, `Apelido`, `IdTipoPonto`,
  `IdPontoGeografico`) e o código `IdTipoPonto=3` (CD) estão corretos.

Pendência: confirmar com a Apisul se essa conta de teste tem algum
isolamento (sandbox dentro de produção) ou se os pontos cadastrados entram
nos dados reais/operacionais da empresa.

## Lat/Long vs endereço: quem ganha (testado em 2026-09-18)

Enviamos um ponto com endereço de Porto Alegre/RS **e** coordenadas de São
Paulo/SP (bem diferentes de propósito) na mesma chamada. Resultado:
**as coordenadas ganham** — a API ignorou completamente o endereço texto
enviado e reverse-geocodificou a partir do Lat/Long, devolvendo "Praça da
Sé, 347, SÃO PAULO SP" (aproveitou o Número enviado, mas trocou rua/cidade/
UF pelo que corresponde às coordenadas). Ou seja: se as duas informações
forem enviadas e não baterem, o endereço nunca é usado — só serve como
fallback de fato quando Lat/Long ficam em branco.

## Suporte à planilha oficial de coleta (não só o modelo do app)

`ler_planilha` agora aceita dois formatos, testado com o arquivo real:

1. O modelo gerado pelo próprio app (aba "PontoGeografico", cabeçalho na
   linha 1).
2. A planilha oficial de coleta da Apisul, sem nenhuma adaptação — aba
   "Pontos", cabeçalho fixo na linha 6, dados a partir da linha 7, coluna A
   ignorada (é só numeração sequencial). Testado com o arquivo real do
   projeto: reconheceu as 3 linhas preenchidas (Matriz, Filial SPO, Filial
   BLM), ignorou a linha "Exemplo" e todas as linhas vazias até a 507.

---

# Cadastro de Motorista (REST)

`POST {base_url}/insereMotorista`, tag `Motorista` / operação
`Motorista_PostAsync` no swagger. Diferente do PontoGeografico:

- **Token vai no header** (`token: <valor>`), não no corpo da mensagem.
- Corpo é JSON puro (`MotoristaModeloIntegracao`), não SOAP/XML.
- Resposta (`BaseRetornoRestModelo`) **não tem `TransacaoOk`** — sucesso se
  inferece pela ausência de `MensagensErro` (ou presença de
  `MensagensSucesso`). HTTP 400 devolve direto um array de
  `RetornoMensagem`, fora do envelope padrão.

## Campos (`MotoristaModeloIntegracao`)

| Campo | Tipo | Observação |
|---|---|---|
| NomeCompleto | string | |
| Documento | string | CPF/DNI/RUT/CI conforme `TipoDocumento` |
| TipoDocumento | int | domínio abaixo |
| TipoMotorista | int | domínio abaixo |
| DDD | string | separado do número — a planilha de coleta traz telefone junto, o app extrai o DDD |
| NumeroTelefonePrincipal | string | sem DDD |
| TipoTelefone | int | enum `[1,2,3,4,5,6,7]` no swagger — **pendente**, só vimos "Celular" nos dados reais e não temos a tabela De→Para. Assumindo Celular = 1 até confirmar |
| Ativo | bool | |
| UF | string | |
| Cidade | string | |
| PlacaVeiculoPadrao | string | opcional |
| CPFGestorFrota | string | opcional |
| LocalizadorApisulMob | string | opcional |
| Contatos | array de `{DDD, Telefone, TipoTelefone, Nome, Observacao}` | opcional, fora do modelo básico do Excel |
| DataAdmissao | datetime | opcional |
| CodContratante | string | opcional |
| CodFuncionario | string | opcional |

### Domínios confirmados pela Apisul (2026-09-18)

**IdTipoMotorista**: 1-Autônomo, 2-Agregado, 3-Frota
(planilha de coleta usa só "Frota" nos exemplos, mas dropdown real da
aba "Relação de motoristas" tem as 3 opções).

**IdTipoDocumento**: 1-CPF, 2-DNI, 3-RUT, 4-CI (documento de identidade
por país — DNI=Argentina, RUT=Chile, CI=Bolívia/Paraguai/Uruguai). Modelo
básico do Excel assume CPF (Brasil); os outros ficam disponíveis pra quem
cadastrar motorista de outro país.

**IdGeoPais** (referência geral de país, não é campo direto do Motorista,
mas é o mesmo domínio usado em outros cadastros): 1-Argentina, 2-Bolívia,
3-Brasil, 4-Chile, 9-Paraguai, 11-Uruguai, 12-Venezuela. Note os números
não são sequenciais (5-8 e 10 não informados) — não inferir os que faltam.

**Pendência**: código de `TipoTelefone` não confirmado.

## Planilha oficial de coleta (aba "Relação de motoristas")

Mesmo arquivo do PontoGeografico. Cabeçalho na linha 6, dados da linha 7,
coluna A é número sequencial: `Nome, CPF, Tipo Motorista, Cidade, Estado,
País, Tipo Telefone, Número Telefone`. Dropdown de "Tipo Motorista" em
`$K$10:$K$12` = Frota/Autonomo/Agregado. Só uma coluna de telefone
(combina DDD+número, ex. "63 8114-5893") — o app separa DDD dos primeiros
dígitos.

## Arquivo bruto
- `PontoGeografico.wsdl` — WSDL completo baixado (`?singleWsdl`)
- `swagger_v2_apisullog.json` — spec REST completo (`swagger/docs/v2`)
