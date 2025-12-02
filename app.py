"""Application factory for the Flask app - simplified for MVP."""

import traceback

# Load environment variables BEFORE importing Config
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(Config)
    db.init_app(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.main import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    migrate = Migrate(app, db)

    # Load current user before each request
    from utils.auth import get_current_user
    
    @app.before_request
    def load_user():
        """Load current user and company before each request."""
        if not hasattr(g, "current_user"):
            get_current_user()

    @app.context_processor
    def add_to_templates():
        """Add variables to template context."""
        return {
            "current_company": getattr(g, "current_company", None),
            "current_user": getattr(g, "current_user", None),
        }
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all exceptions."""
        db.session.rollback()
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

    return app
