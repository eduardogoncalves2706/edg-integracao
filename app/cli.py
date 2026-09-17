import click
from flask import Flask

from app.extensions import db
from app.models import Usuario


def registrar_comandos(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas no Postgres configurado em config/db_config.json."""
        db.create_all()
        click.echo("Tabelas criadas/atualizadas com sucesso.")

    @app.cli.command("criar-usuario")
    @click.option("--login", "login_", prompt=True)
    @click.option("--nome", prompt=True)
    @click.option("--senha", prompt=True, hide_input=True, confirmation_prompt=True)
    def criar_usuario(login_: str, nome: str, senha: str):
        """Cria (ou atualiza a senha de) um usuário do app de integração."""
        usuario = Usuario.query.filter_by(login=login_).first()
        if usuario is None:
            usuario = Usuario(login=login_, nome=nome)
            db.session.add(usuario)
        else:
            usuario.nome = nome
        usuario.set_senha(senha)
        usuario.ativo = True
        db.session.commit()
        click.echo(f"Usuário '{login_}' pronto para uso.")
