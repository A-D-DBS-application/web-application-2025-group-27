"""Application factory for de Flask-app - vereenvoudigd voor MVP."""

import traceback

# Laad environment variabelen VOOR het importeren van Config
# Dit is nodig omdat Config DATABASE_URL uit environment variabelen leest
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optioneel - app werkt ook zonder als environment variabelen al gezet zijn
    pass

from flask import Flask, g
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()

def _get_parse_signal_details():
    """Lazy import van parse_signal_details om circulaire imports te vermijden.
    
    Deze functie wordt alleen aangeroepen wanneer nodig, niet bij module load.
    Dit voorkomt circulaire dependencies tussen app.py en services.signals.
    """
    from services.signals import parse_signal_details
    return parse_signal_details


def create_app():
    """Maak en configureer de Flask-applicatie.
    
    Initialiseert alle componenten: database, blueprints, context processors,
    en error handlers. Dit is de application factory pattern voor Flask.
    """
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(Config)
    db.init_app(app)

    # Registreer blueprints voor routes
    from routes.auth import auth_bp
    from routes.main import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    Migrate(app, db)

    # Laad huidige gebruiker voor elke request
    # Dit zorgt ervoor dat g.current_user en g.current_company beschikbaar zijn
    from utils.auth import get_current_user
    
    @app.before_request
    def load_user():
        """Laad huidige gebruiker en company voor elke request.
        
        Dit voorkomt dat we in elke route opnieuw moeten checken of de gebruiker
        ingelogd is. De gebruiker wordt geladen op basis van session data.
        """
        if not hasattr(g, "current_user"):
            get_current_user()

    # Registreer parse_signal_details als Jinja2 global (beschikbaar in alle templates, inclusief macros)
    # Dit is nodig omdat signal macros deze functie nodig hebben om related_news te parsen
    def _get_parse_func():
        """Haal parse_signal_details functie op met fallback.
        
        Als de import faalt (bijv. circulaire import), gebruiken we een fallback
        die de signal details handmatig parse. Dit voorkomt dat templates crashen.
        """
        try:
            return _get_parse_signal_details()
        except Exception:
            # Fallback als import faalt (bijv. circulaire import tijdens development)
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
        """Voeg variabelen toe aan template context.
        
        Deze variabelen zijn automatisch beschikbaar in alle templates,
        zodat we niet in elke render_template() call hoeven te passen.
        """
        return {
            "current_company": getattr(g, "current_company", None),
            "current_user": getattr(g, "current_user", None),
        }
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Behandel alle exceptions.
        
        Voor MVP: toon traceback voor debugging. In productie zou dit
        een generieke error pagina moeten zijn zonder stack trace.
        """
        db.session.rollback()
        return f"Error: {str(e)}<br><pre>{traceback.format_exc()}</pre>", 500

    return app
