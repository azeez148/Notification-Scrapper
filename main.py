import sys

from loguru import logger

from kerala_psc_scraper.database.db import get_session, init_db
from kerala_psc_scraper.services.notification_service import process_all_notifications


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    logger.info("Initialising database schema")
    init_db()

    logger.info("Starting Kerala PSC Notification Scraper")
    session = get_session()
    try:
        process_all_notifications(session)
    finally:
        session.close()

    logger.info("Done")


if __name__ == "__main__":
    main()
