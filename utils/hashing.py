import bcrypt

class BcryptContext:
    def __init__(self, rounds=10):
        self.rounds = rounds

    def hash(self, secret):
        if not secret:
            return None
        # Truncate to 72 bytes as per bcrypt spec
        secret_bytes = secret[:72].encode('utf-8')
        salt = bcrypt.gensalt(rounds=self.rounds)
        return bcrypt.hashpw(secret_bytes, salt).decode('utf-8')

    def verify(self, secret, hashed):
        if not secret or not hashed:
            return False
        try:
            if isinstance(hashed, str):
                hashed = hashed.encode('utf-8')
            return bcrypt.checkpw(secret[:72].encode('utf-8'), hashed)
        except Exception:
            return False

    def needs_update(self, hashed):
        """Mock for compatibility with services using passlib's needs_update."""
        # For now, we assume if it's a valid bcrypt hash, it's fine.
        return False

# Compatibility object for CryptContext
pwd_context = BcryptContext(rounds=10)

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)
