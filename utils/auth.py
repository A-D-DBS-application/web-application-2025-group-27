"""Authentication utilities - session management and decorators."""

import uuid
from functools import wraps
from typing import Optional

from flask import flash, g, redirect, request, session, url_for

from app import db
from models import User


def login_user(user: User) -> None:
    """Store user ID in session."""
    session["user_id"] = str(user.id)


def get_current_user() -> Optional[User]:
    """Load current user from session and set g.current_user/g.current_company."""
    user_id = session.get("user_id")
    
    if not user_id:
        g.current_user = None
        g.current_company = None
        return None
    
    try:
        user_uuid = uuid.UUID(user_id)
    except (TypeError, ValueError):
        session.clear()
        g.current_user = None
        g.current_company = None
        return None
    
    user = db.session.query(User).filter(User.id == user_uuid).first()
    
    if user and user.is_active:
        g.current_user = user
        g.current_company = user.company if user.company_id else None
    else:
        session.clear()
        g.current_user = None
        g.current_company = None
    
    return None


def require_login(view_func):
    """Decorator to require authenticated user."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not getattr(g, "current_user", None):
            flash("Please log in.", "error")
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapper
