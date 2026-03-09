import time
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

from kerala_psc_scraper.config.settings import (
    PDF_STORAGE_PATH,
    REQUEST_MAX_RETRIES,
    REQUEST_RETRY_BACKOFF,
    REQUEST_TIMEOUT,
)


def _safe_filename(category_no: str) -> str:
    return category_no.replace("/", "_").replace(" ", "_") + ".pdf"


def download_pdf(pdf_url: str, category_no: str, storage_path: str = PDF_STORAGE_PATH) -> Optional[str]:
    dest_dir = Path(storage_path)
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = _safe_filename(category_no)
    dest_path = dest_dir / filename

    if dest_path.exists():
        logger.info(f"PDF already exists, skipping download: {dest_path}")
        return str(dest_path)

    for attempt in range(1, REQUEST_MAX_RETRIES + 1):
        try:
            logger.info(f"Downloading PDF: {pdf_url} -> {dest_path} (attempt {attempt})")
            response = requests.get(pdf_url, timeout=REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()

            with open(dest_path, "wb") as fh:
                for chunk in response.iter_content(chunk_size=8192):
                    fh.write(chunk)

            logger.info(f"PDF downloaded successfully: {dest_path}")
            return str(dest_path)
        except requests.RequestException as exc:
            logger.warning(f"Attempt {attempt} failed for PDF {pdf_url}: {exc}")
            if dest_path.exists():
                dest_path.unlink()
            if attempt < REQUEST_MAX_RETRIES:
                time.sleep(REQUEST_RETRY_BACKOFF * attempt)

    logger.error(f"All {REQUEST_MAX_RETRIES} attempts failed for PDF {pdf_url}")
    return None
