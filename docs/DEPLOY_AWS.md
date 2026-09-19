# Infraestrutura AWS — conta 255530396736 (us-east-1)

Sem Terraform/CloudFormation ainda — tudo foi provisionado via AWS CLI.
Este documento existe pra não depender de memória de quem mexeu por último.
`deploy/task-definition.template.json` é o "source of truth" da task
definition (com `__DB_HOST__` como placeholder).

## Recursos

| Recurso | Nome/Id | Observação |
|---|---|---|
| RDS Postgres | `edg-integracao-db` (db.t4g.micro) | Privado (`--no-publicly-accessible`), banco `integracao_apisullog`, subnet group `default-vpc-07255c28f7c777f07` |
| ECR | `edg-integracao-api` | Imagem `:latest`, arquitetura ARM64 (build nativo em Mac Apple Silicon) |
| ECS Cluster | `edg-integracao-cluster` | Fargate |
| ECS Service | `edg-integracao-api-service` | 1 task, `assignPublicIp=ENABLED` (sem ALB — IP público muda a cada redeploy) |
| ECS Task Definition | `edg-integracao-api` | Ver `deploy/task-definition.template.json` |
| Security Group (app) | `edg-integracao-api-sg` | Porta 80/tcp, libera IP por IP (self-service via tela de Usuários, ou manual) + o prefix list gerenciado `com.amazonaws.global.cloudfront.origin-facing` (pra CloudFront alcançar a origem) |
| Security Group (db) | `edg-integracao-db-sg` | Porta 5432/tcp, libera o SG da app + IPs de admin pra rodar `flask` CLI direto |
| Secrets Manager | `edg-integracao/app` | JSON com `DB_PASSWORD` e `FLASK_SECRET_KEY` |
| IAM Role (execução) | `ecsTaskExecutionRole` | Compartilhada com outro projeto da conta (authcnpj) — só pull de ECR + logs. Tem uma policy inline extra (`edg-integracao-secrets-read`) pra ler o secret acima |
| IAM Role (task) | `edg-integracao-task-role` | Só desta app. Policy `liberar-ip-proprio-sg`: `ec2:AuthorizeSecurityGroupIngress`/`RevokeSecurityGroupIngress` restrita ao ARN do `edg-integracao-api-sg` — é o que permite a tela de Usuários liberar IP sozinha, sem dar acesso amplo à conta |
| CloudFront + ACM | ver seção "CloudFront + certificado (HTTPS)" abaixo | Front TLS na frente do app, DNS gerenciado direto no registro.br (não usa Route 53) |

## Fluxo de deploy (manual, sem CI/CD ainda)

```bash
# 1. build (Mac Apple Silicon já gera ARM64 nativo, compatível com o Fargate)
docker build -t edg-integracao-api:local .

# 2. push
aws ecr get-login-password --region us-east-1 | docker login --username AWS \
  --password-stdin 255530396736.dkr.ecr.us-east-1.amazonaws.com
docker tag edg-integracao-api:local 255530396736.dkr.ecr.us-east-1.amazonaws.com/edg-integracao-api:latest
docker push 255530396736.dkr.ecr.us-east-1.amazonaws.com/edg-integracao-api:latest

# 3. redeploy (mesma task definition, só troca a imagem por trás da tag :latest)
aws ecs update-service --region us-east-1 --cluster edg-integracao-cluster \
  --service edg-integracao-api-service --force-new-deployment

# se mudou algo na task definition (env var, IAM role, etc.), registrar uma
# revisão nova a partir do template antes:
#   sed "s#__DB_HOST__#$(seu host aqui)#" deploy/task-definition.template.json > /tmp/task-def.json
#   aws ecs register-task-definition --cli-input-json file:///tmp/task-def.json
#   aws ecs update-service ... --task-definition edg-integracao-api  (pega a ultima revisao ACTIVE)
```

## Descobrir o IP público atual da task

Sem ALB, o IP muda a cada deploy — é assim que se descobre:

```bash
TASK_ARN=$(aws ecs list-tasks --region us-east-1 --cluster edg-integracao-cluster \
  --service-name edg-integracao-api-service --query "taskArns[0]" --output text)
ENI=$(aws ecs describe-tasks --region us-east-1 --cluster edg-integracao-cluster \
  --tasks "$TASK_ARN" --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text)
aws ec2 describe-network-interfaces --region us-east-1 --network-interface-ids "$ENI" \
  --query "NetworkInterfaces[0].Association.PublicIp" --output text
```

## Rodar comandos `flask` (init-db, criar-usuario) contra o RDS

O RDS não é publicamente acessível — rodar como task avulsa dentro da VPC:

```bash
aws ecs run-task --region us-east-1 --cluster edg-integracao-cluster \
  --task-definition edg-integracao-api --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[...6 subnets do default VPC...],securityGroups=[sg-0c6cb27ec7a3a3e81],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides":[{"name":"edg-integracao-api","command":["flask","init-db"]}]}'
```

Ver logs em CloudWatch, log group `/ecs/edg-integracao-api` (um stream por task).

## Pendências / próximos passos de infra

- **Sem ALB**: decidido propositalmente por custo (fase de teste, poucos
  usuários). CloudFront + domínio próprio (ver seção abaixo) resolve TLS e
  endereço fixo por centavos/mês em vez de ~US$16-20/mês do ALB — o preço é
  precisar atualizar manualmente o registro `origin-integrador` (A) a cada
  deploy, e não ter failover automático se a task cair sozinha fora de um
  deploy planejado. Reavaliar ALB/NLB quando for pra uso real com mais gente.
- **Sem Alembic**: mudanças de schema hoje exigem `flask reset-db` (dropa
  tudo). Aceitável em fase de teste; configurar migrations de verdade antes
  de ter dados reais que importem.
- **Sem CI/CD**: build/push/deploy é manual, do Mac de quem está mexendo.

## CloudFront + certificado (HTTPS)

Adicionado em 2026-09-19 pra resolver o aviso de "não seguro" (login/senha
trafegando em HTTP puro). Sem ALB (custo), usamos CloudFront como front TLS:

| Recurso | Valor |
|---|---|
| Certificado ACM | `arn:aws:acm:us-east-1:255530396736:certificate/0c8dd1d8-fecc-4309-8253-05d1db4e187d` (us-east-1, validado por DNS) |
| Distribuição CloudFront | `EQW0UB12TQTRX` — `d5ypltdmwtvtk.cloudfront.net` |
| Origem da distribuição | `origin-integrador.edgsolutions.com.br` (A record, **atualizar a cada redeploy** — CloudFront não aceita IP direto como origem, exige um nome) |
| DNS público | `integrador.edgsolutions.com.br` CNAME → `d5ypltdmwtvtk.cloudfront.net` (fixo, não muda) |

Registro.br não tem API pública — todos os registros DNS (origem, validação
do certificado, CNAME final) foram adicionados manualmente pelo usuário no
"Editar Zona" (modo avançado, powered by DNSSHIM) do painel. **O único que
precisa ser atualizado a cada deploy é o `origin-integrador` (tipo A)** —
avisar o usuário do IP novo pra ele trocar no painel.

Fluxo depois de cada deploy:
1. Pegar o IP novo da task (comando na seção acima).
2. Avisar o usuário pra atualizar `origin-integrador.edgsolutions.com.br`
   (A) pro IP novo no painel do registro.br.
3. CloudFront resolve `origin-integrador` de novo automaticamente (sem TTL
   de cache do lado da CloudFront pra esse tipo de resolução — ela consulta
   DNS a cada nova conexão de origem, não fixa o IP).
