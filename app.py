"""app.py — CineLog Flask application factory"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()


def create_app(config=None):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///cinelog.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    if config:
        app.config.update(config)

    db.init_app(app)

    from routes.films import films_bp
    from routes.collection import collection_bp
    from routes.watchlist.watchlist import watchlist_bp

    app.register_blueprint(films_bp, url_prefix="/films")
    app.register_blueprint(collection_bp, url_prefix="/collection")
    app.register_blueprint(watchlist_bp, url_prefix="/watchlist")

    with app.app_context():
        db.create_all()

    return app


# Module-level WSGI entrypoint. Deployment servers (gunicorn, etc.) and tools
# that look for a top-level "app" import this; the factory stays available for
# tests, which build isolated app instances via create_app(config=...).
app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
