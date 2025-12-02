"""Configuration for the Flask application."""

import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")
    SQLALCHEMY_DATABASE_URI = db_url
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

