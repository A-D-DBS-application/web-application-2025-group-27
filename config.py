"""Configuration for the Flask application.

This module defines a `Config` class whose attributes are read by Flask and extensions.

Notes:
- `SECRET_KEY`: used by Flask to sign session cookies and CSRF tokens.
- `SQLALCHEMY_DATABASE_URI`: SQLAlchemy database connection URI
  (e.g., "postgresql://user:password@host:port/database").
  - Networking: `host` and `port` identify the DB server over TCP; use TLS if required.
- `SQLALCHEMY_TRACK_MODIFICATIONS`: keep False to avoid event-system overhead.

Database terminology:
- ORM model classes define the table schema; altering a model alters the schema.

Migrations (schema change workflow):
- Generate a migration when models (schemas) change:
    flask db migrate -m "describe schema change"
- Apply the migration to the database (over the configured network connection):
    flask db upgrade

Production tip:
- Load secrets/URIs from environment variables rather than hardcoding.
"""

class Config: 
    """Base configuration loaded via `app.config.from_object(Config)`.

    Attributes:
        SECRET_KEY (str): Secret for signing session data and CSRF tokens.
        SQLALCHEMY_DATABASE_URI (str): SQLAlchemy DSN used to open a TCP connection to the DB.
        SQLALCHEMY_TRACK_MODIFICATIONS (bool): Disables event system overhead when False.
    """
    SECRET_KEY = 'your_secret_key'
    SQLALCHEMY_DATABASE_URI = "postgresql://postgres.hwszjtatbzxyysezjdne:kuxpaDhohtuzpuwwy8@aws-1-eu-north-1.pooler.supabase.com:6543/postgres"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

