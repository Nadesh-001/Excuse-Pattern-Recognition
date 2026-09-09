"""
extensions.py
=============
Shared Flask extension instances created *before* the app factory runs.
Import these here (not from app.py) to avoid circular imports in blueprints.
"""
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager

csrf = CSRFProtect()
login_manager = LoginManager()
