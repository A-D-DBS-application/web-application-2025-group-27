"""Authenticatie utilities - session management en decorators."""

import uuid
from functools import wraps
from typing import Optional

from flask import flash, g, redirect, request, session, url_for

from app import db
from models import User


def login_user(user: User) -> None:
    """Sla user ID op in session.
    
    Dit is de enige manier om een gebruiker "in te loggen" - er is geen
    password verificatie in deze MVP (email-only login).
    """
    session["user_id"] = str(user.id)


def _reset_context() -> None:
    """Reset Flask context - gebruik bij logout of invalid session.
    
    Verwijdert alle session data en zet g.current_user en g.current_company
    op None. Dit zorgt ervoor dat de gebruiker als "niet ingelogd" wordt gezien.
    """
    session.clear()
    g.current_user = None
    g.current_company = None


def get_current_user() -> Optional[User]:
    """Laad huidige gebruiker uit session en zet g.current_user/g.current_company.
    
    Deze functie wordt aangeroepen in app.py via before_request hook.
    Als er geen geldige session is, wordt de context gereset.
    """
    user_id = session.get("user_id")
    if not user_id:
        _reset_context()
        return None
    try:
        user_uuid = uuid.UUID(user_id)
    except (TypeError, ValueError):
        # Ongeldige UUID in session - reset context
        _reset_context()
        return None
    user = db.session.query(User).filter(User.id == user_uuid).first()
    if user and user.is_active:
        g.current_user = user
        g.current_company = user.company if user.company_id else None
        return user
    else:
        # Gebruiker niet gevonden of niet actief - reset context
        _reset_context()
        return None


def require_login(view_func):
    """Decorator om te vereisen dat gebruiker ingelogd is.
    
    Als gebruiker niet ingelogd is, redirect naar login pagina met
    "next" parameter zodat gebruiker na login terugkomt op dezelfde pagina.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not getattr(g, "current_user", None):
            flash("Please log in.", "error")
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapper
