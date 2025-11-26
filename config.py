"""Configuration for the Flask application."""

import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres.hwszjtatbzxyysezjdne:kuxpaDhohtuzpuwwy8@aws-1-eu-north-1.pooler.supabase.com:6543/postgres",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

