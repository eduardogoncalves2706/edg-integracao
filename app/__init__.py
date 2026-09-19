from flask import Flask

from app.extensions import db, login_manager
from config.settings import ApisulConfig, FlaskConfig


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(FlaskConfig())
    app.config["APISUL_CONFIG"] = ApisulConfig.load()

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import Usuario

    @login_manager.user_loader
    def carregar_usuario(user_id: str):
        return db.session.get(Usuario, int(user_id))

    from app.routes.auth import bp as auth_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.historico import bp as historico_bp
    from app.routes.lotes import bp as lotes_bp
    from app.routes.motorista import bp as motorista_bp
    from app.routes.ponto_geografico import bp as ponto_geografico_bp
    from app.routes.resultados import bp as resultados_bp
    from app.routes.usuarios import bp as usuarios_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(historico_bp)
    app.register_blueprint(lotes_bp)
    app.register_blueprint(motorista_bp)
    app.register_blueprint(ponto_geografico_bp)
    app.register_blueprint(resultados_bp)
    app.register_blueprint(usuarios_bp)

    from app.cli import registrar_comandos

    registrar_comandos(app)

    return app
