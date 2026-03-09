import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/psc_jobs")
PDF_STORAGE_PATH: str = os.getenv("PDF_STORAGE_PATH", "data/pdfs")

NOTIFICATIONS_URL: str = "https://www.keralapsc.gov.in/index.php/notifications"

REQUEST_TIMEOUT: int = 30
REQUEST_MAX_RETRIES: int = 3
REQUEST_RETRY_BACKOFF: float = 2.0
