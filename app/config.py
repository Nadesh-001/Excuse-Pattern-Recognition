import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Neural_Protocol Configuration — AWS RDS PostgreSQL."""
    # Flask
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "a3f9c8e2f6b1d4e0c9a7e0cbdcb2e77f3b9a1e4d7a5f2c6e8b4a9d0c1f7e3a")

    # Database (AWS RDS)
    DB_HOST = os.getenv("DB_HOST", "excuseai-db.clyi8oi4e0xr.ap-south-1.rds.amazonaws.com")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "Aswin2026")
    DB_NAME = os.getenv("DB_NAME", "postgres")

    # AI Logic
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_API_KEY_SECONDARY = os.getenv("GROQ_API_KEY_SECONDARY") or GROQ_API_KEY
    GROQ_API_KEY_TERTIARY = os.getenv("GROQ_API_KEY_TERTIARY") or GROQ_API_KEY
    GROQ_API_KEY_QUATERNARY = os.getenv("GROQ_API_KEY_QUATERNARY") or GROQ_API_KEY
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or GROQ_API_KEY
    AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
    AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", 0.6))
    AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", 2048))

    # Files
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_FILE_SIZE_MB", 50)) * 1024 * 1024

    # Session
    SESSION_COOKIE_HTTPONLY = True
    # Session Security
    # Set to True once HTTPS is enabled
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV", "development").lower() == "production"
    SESSION_COOKIE_SAMESITE = "Lax"
