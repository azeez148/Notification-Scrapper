import os

MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "12"))
MAX_PASSWORD_LENGTH = int(os.getenv("MAX_PASSWORD_LENGTH", "128"))


def _required_secret(name: str) -> str:
    value = os.getenv(name)
    if not value or len(value) < 32:
        raise RuntimeError(f"{name} must be set and at least 32 characters long")
    return value


JWT_ACCESS_SECRET = _required_secret("JWT_ACCESS_SECRET")
JWT_REFRESH_SECRET = _required_secret("JWT_REFRESH_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("JWT_ISSUER", "notification-scraper")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "notification-scraper-users")
JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "900"))
JWT_REFRESH_TTL_SECONDS = int(os.getenv("JWT_REFRESH_TTL_SECONDS", "2592000"))
PASSWORD_RESET_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "30"))
LOGIN_RATE_LIMIT_PER_MINUTE = int(os.getenv("LOGIN_RATE_LIMIT_PER_MINUTE", "5"))
FORGOT_RATE_LIMIT_PER_HOUR = int(os.getenv("FORGOT_RATE_LIMIT_PER_HOUR", "5"))
ACCOUNT_LOCK_THRESHOLD = int(os.getenv("ACCOUNT_LOCK_THRESHOLD", "5"))
ACCOUNT_LOCK_DURATION_MINUTES = int(os.getenv("ACCOUNT_LOCK_DURATION_MINUTES", "15"))
