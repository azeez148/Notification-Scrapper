import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/psc_jobs")
PDF_STORAGE_PATH: str = os.getenv("PDF_STORAGE_PATH", "data/pdfs")

NOTIFICATIONS_URL: str = "https://www.keralapsc.gov.in/index.php/notifications"

REQUEST_TIMEOUT: int = 30
REQUEST_MAX_RETRIES: int = 3
REQUEST_RETRY_BACKOFF: float = 2.0


def _parse_max_notifications(raw_value: str | None) -> int | None:
	if raw_value is None:
		return None

	value = raw_value.strip().lower()
	if not value or value in {"all", "none", "*"}:
		return None

	parsed = int(value)
	if parsed <= 0:
		raise ValueError("MAX_NOTIFICATIONS must be greater than 0")
	return parsed


MAX_NOTIFICATIONS: int | None = _parse_max_notifications(os.getenv("MAX_NOTIFICATIONS", "10"))
