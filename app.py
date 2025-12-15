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

# Import parse_signal_details at module level to avoid circular imports
# This will be imported lazily in the context processor
def _get_parse_signal_details():
    """Lazy import of parse_signal_details to avoid circular imports."""
    from services.signals import parse_signal_details
    return parse_signal_details


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

    Migrate(app, db)

    # Load current user before each request
    from utils.auth import get_current_user
    
    @app.before_request
    def load_user():
        """Load current user and company before each request."""
        if not hasattr(g, "current_user"):
            get_current_user()

    # Register parse_signal_details as a Jinja2 global (available in all templates, including macros)
    def _get_parse_func():
        """Get parse_signal_details function with fallback."""
        try:
            return _get_parse_signal_details()
        except Exception:
            # Fallback if import fails (e.g., circular import)
            def parse_signal_details_fallback(signal):
                if not signal or not signal.details:
                    return {"text": "", "related_news": []}
                try:
                    import json
                    parsed = json.loads(signal.details)
                    if isinstance(parsed, dict) and "related_news" in parsed:
                        return {
                            "text": parsed.get("text", ""),
                            "related_news": parsed.get("related_news", [])
                        }
                except (json.JSONDecodeError, TypeError):
                    pass
                return {"text": signal.details, "related_news": []}
            return parse_signal_details_fallback
    
    app.jinja_env.globals['parse_signal_details'] = _get_parse_func()
    
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
