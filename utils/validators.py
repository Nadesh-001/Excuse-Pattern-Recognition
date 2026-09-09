import re

def validate_email(email):
    if not email: return False
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def validate_password(password):
    if not password: return False
    return len(password) >= 6
