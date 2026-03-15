import sys

from loguru import logger

from export_normalized_json_from_web import export_normalized_json_from_web
from kerala_psc_scraper.config.settings import MAX_NOTIFICATIONS
from load_normalized_data import load_normalized_data


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    logger.info("Starting web-to-normalized pipeline")
    logger.info(
        f"Notification count mode: {'all' if MAX_NOTIFICATIONS is None else MAX_NOTIFICATIONS}"
    )

    normalized_json_path = export_normalized_json_from_web(
        output_file="normalized_notifications.json",
        max_notifications=MAX_NOTIFICATIONS,
    )
    logger.info(f"Test JSON ready: {normalized_json_path}")

    load_normalized_data(str(normalized_json_path))

    logger.info("Done: web data fetched, normalized JSON generated, and DB loaded")


if __name__ == "__main__":
    main()
