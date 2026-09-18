import click
from flask import Flask

from app.extensions import db
from app.models import Usuario


def registrar_comandos(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas que ainda não existem. Não migra colunas novas em
        tabelas já existentes — use `reset-db` pra isso (apaga os dados)."""
        db.create_all()
        click.echo("Tabelas criadas/atualizadas com sucesso.")

    @app.cli.command("reset-db")
    @click.confirmation_option(prompt="Isso apaga TODOS os dados (usuários, lotes, chamadas). Continuar?")
    def reset_db():
        """Recria o schema do zero. Sem Alembic configurado ainda — usar só
        na fase de testes; uma vez em produção de verdade, trocar por
        migrations de verdade em vez de dropar tabela."""
        db.drop_all()
        db.create_all()
        click.echo("Schema recriado do zero.")

    @app.cli.command("criar-usuario")
    @click.option("--login", "login_", prompt=True)
    @click.option("--nome", prompt=True)
    @click.option("--senha", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--admin", is_flag=True, default=False)
    def criar_usuario(login_: str, nome: str, senha: str, admin: bool):
        """Cria (ou atualiza a senha de) um usuário do app de integração."""
        usuario = Usuario.query.filter_by(login=login_).first()
        if usuario is None:
            usuario = Usuario(login=login_, nome=nome)
            db.session.add(usuario)
        else:
            usuario.nome = nome
        usuario.set_senha(senha)
        usuario.ativo = True
        if admin:
            usuario.admin = True
        db.session.commit()
        click.echo(f"Usuário '{login_}' pronto para uso.")
