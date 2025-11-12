"""Application factory for the Flask app.

This module wires together:
- Flask: the web framework handling HTTP requests/responses in a WSGI server.
- Flask SQLAlchemy (`SQLAlchemy`): ORM layer mapping Python classes to table schemas.
- Flask-Migrate (`Migrate`): Alembic-powered migration tooling for schema changes.

Database terminology:
- ORM "model" class ≈ table schema definition; columns map to table fields.
- The database is typically a remote network service reached over TCP (e.g., PostgreSQL on port 5432).

Networking terminology:
- The app serves HTTP endpoints (routes) to clients (browsers/cURL) over TCP.
- A WSGI server (e.g., Werkzeug in development) listens on an IP/host and port.
- The database URI is a connection string (scheme://user:pass@host:port/db) used to establish a TCP connection; TLS may encrypt traffic if configured.

Migrations (schema change workflow):
- After changing a model (table schema), autogenerate a migration:
    flask db migrate -m "describe schema change"
- Apply the migration to the database over the network connection:
    flask db upgrade

Key concepts:
- App factory pattern (`create_app`) creates and configures a new Flask app instance.
- `db = SQLAlchemy()` creates a lazy extension object bound later via `db.init_app(app)`.
- `Migrate(app, db)` enables `flask db ...` commands based on model metadata.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()

def create_app():
    """Create and configure the Flask application instance.

    Steps:
    1. Instantiate Flask with `template_folder='templates'` so Jinja2 finds templates.
    2. Load configuration from `Config` (e.g., `SECRET_KEY`, DB URI).
    3. Bind SQLAlchemy to the app via `db.init_app(app)` so ORM sessions can connect to the DB over TCP.
    4. Register routes (HTTP endpoints) that use models (schemas) for data access.
    5. Initialize migration support with `Migrate(app, db)`.

    Returns:
        Flask: A fully configured Flask application.
    """
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(Config)

    db.init_app(app)

    from routes import register_routes
    register_routes(app, db)

    migrate = Migrate(app, db)

    return app