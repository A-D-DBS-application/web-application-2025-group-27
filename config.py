"""Configuratie voor de Flask-applicatie."""

import os


class Config:
    """Flask configuratie klasse.
    
    Leest configuratie uit environment variabelen. DATABASE_URL is verplicht
    en moet gezet zijn voordat de app start.
    """
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # DATABASE_URL is verplicht - app kan niet starten zonder database connectie
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")
    SQLALCHEMY_DATABASE_URI = db_url
    
    # SQLAlchemy optimalisaties
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Niet nodig voor MVP, bespaart resources
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}  # Herstelt stale database connections

