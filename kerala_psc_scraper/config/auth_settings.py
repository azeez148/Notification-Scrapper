import os

JWT_ACCESS_SECRET = os.getenv("JWT_ACCESS_SECRET", "change-me-access-secret-at-least-32-characters")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "change-me-refresh-secret-at-least-32-characters")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ISSUER = os.getenv("JWT_ISSUER", "notification-scrapper")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "notification-scrapper-users")
JWT_ACCESS_TTL_SECONDS = int(os.getenv("JWT_ACCESS_TTL_SECONDS", "900"))
JWT_REFRESH_TTL_SECONDS = int(os.getenv("JWT_REFRESH_TTL_SECONDS", "2592000"))
PASSWORD_RESET_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TTL_MINUTES", "30"))
LOGIN_RATE_LIMIT_PER_MINUTE = int(os.getenv("LOGIN_RATE_LIMIT_PER_MINUTE", "5"))
FORGOT_RATE_LIMIT_PER_HOUR = int(os.getenv("FORGOT_RATE_LIMIT_PER_HOUR", "5"))
