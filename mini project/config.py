import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    APP_ENV = os.getenv("APP_ENV", "development").lower()
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'degreepath.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv(
        "SESSION_COOKIE_SECURE",
        "true" if os.getenv("APP_ENV", "development").lower() == "production" else "false",
    ).lower() == "true"
    REMEMBER_COOKIE_HTTPONLY = True
    WTF_CSRF_TIME_LIMIT = 3600