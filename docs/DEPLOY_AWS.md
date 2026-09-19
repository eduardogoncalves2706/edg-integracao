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
| Security Group (app) | `edg-integracao-api-sg` | Porta 80/tcp, libera IP por IP (self-service via tela de Usuários, ou manual) |
| Route 53 Hosted Zone | `integrador.edgsolutions.com.br` (Z0720256KO9TOIXOZS3A) | Subdomínio delegado do domínio `edgsolutions.com.br` (registrado no registro.br) — só esse subdomínio, não mexe no resto do domínio. Registro A aponta pro IP público atual da task, TTL 60s |
| Security Group (db) | `edg-integracao-db-sg` | Porta 5432/tcp, libera o SG da app + IPs de admin pra rodar `flask` CLI direto |
| Secrets Manager | `edg-integracao/app` | JSON com `DB_PASSWORD` e `FLASK_SECRET_KEY` |
| IAM Role (execução) | `ecsTaskExecutionRole` | Compartilhada com outro projeto da conta (authcnpj) — só pull de ECR + logs. Tem uma policy inline extra (`edg-integracao-secrets-read`) pra ler o secret acima |
| IAM Role (task) | `edg-integracao-task-role` | Só desta app. Policy `liberar-ip-proprio-sg`: `ec2:AuthorizeSecurityGroupIngress`/`RevokeSecurityGroupIngress` restrita ao ARN do `edg-integracao-api-sg` — é o que permite a tela de Usuários liberar IP sozinha, sem dar acesso amplo à conta |

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

## DNS — atualizar depois de cada deploy

Sem ALB/NLB, `integrador.edgsolutions.com.br` é um registro A "manual":
depois de qualquer redeploy, atualizar pro IP novo (TTL 60s, propaga rápido):

```bash
IP_NOVO="<pegue com o comando acima>"
cat > /tmp/route53-change.json <<EOF
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "integrador.edgsolutions.com.br",
      "Type": "A",
      "TTL": 60,
      "ResourceRecords": [{"Value": "$IP_NOVO"}]
    }
  }]
}
EOF
aws route53 change-resource-record-sets --hosted-zone-id Z0720256KO9TOIXOZS3A \
  --change-batch file:///tmp/route53-change.json
```

Limitação conhecida: se a task cair sozinha (crash) fora de um deploy
planejado, o DNS fica apontando pro IP antigo até alguém notar e rodar isso
de novo — não é failover automático (isso só existe com ALB/NLB).

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
  usuários). Domínio próprio (`integrador.edgsolutions.com.br`, subdomínio
  delegado do `edgsolutions.com.br` no registro.br) resolve o "endereço
  fixo" por ~$0,50/mês (hosted zone) em vez de ~US$16-20/mês do ALB — o
  preço é precisar atualizar o registro A manualmente a cada deploy (ver
  seção "DNS" acima). Reavaliar ALB/NLB quando for pra uso real com mais
  gente, principalmente pelo failover automático em caso de crash.
- **Sem Alembic**: mudanças de schema hoje exigem `flask reset-db` (dropa
  tudo). Aceitável em fase de teste; configurar migrations de verdade antes
  de ter dados reais que importem.
- **Sem CI/CD**: build/push/deploy é manual, do Mac de quem está mexendo.
