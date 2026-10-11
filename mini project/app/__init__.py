from pathlib import Path
import secrets

from flask import Flask, render_template
from flask_login import current_user
from dotenv import load_dotenv

from .extensions import csrf, db, login_manager, migrate


def create_app(test_config=None):
    load_dotenv()
    from config import Config

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        if app.config.get("APP_ENV") == "production":
            raise RuntimeError("SECRET_KEY must be set when APP_ENV=production.")
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning("Using an ephemeral development secret; sessions will reset on restart.")
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Sign in to continue."
    login_manager.login_message_category = "info"

    from . import models
    from .admin import bp as admin_bp
    from .academics import bp as academics_bp
    from .auth import bp as auth_bp
    from .career import bp as career_bp
    from .commands import register_commands
    from .planner import bp as planner_bp
    from .student import bp as student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(academics_bp)
    app.register_blueprint(planner_bp)
    app.register_blueprint(career_bp)
    app.register_blueprint(admin_bp)
    register_commands(app)

    @app.context_processor
    def inject_user():
        return {"current_user": current_user}

    @app.get("/")
    def landing():
        return render_template("landing.html")

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        app.logger.exception("Unhandled application error")
        return render_template("errors/500.html"), 500

    return app


@login_manager.user_loader
def load_user(user_id):
    from .models import User
    return db.session.get(User, int(user_id))