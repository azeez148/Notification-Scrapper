import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from kerala_psc_scraper.parser.pdf_parser import parse_pdf_from_url
from kerala_psc_scraper.scraper.notification_list_scraper import scrape_notification_list
from kerala_psc_scraper.scraper.notification_page_scraper import scrape_notification_page
from kerala_psc_scraper.services.normalization_service import (
    NormalizedDatasetBuilder,
    NotificationRawRecord,
)


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")


def export_normalized_json_from_web(
    output_file: str = "normalized_notifications.json",
    max_notifications: Optional[int] = None,
) -> Path:
    if max_notifications is not None and max_notifications <= 0:
        raise ValueError("max_notifications must be greater than 0")

    logger.info("Scraping notification list from web")
    list_items = scrape_notification_list()
    if not list_items:
        raise RuntimeError("No notification list items found from web source")

    builder = NormalizedDatasetBuilder()
    processed_categories: set[str] = set()

    for list_item in list_items:
        if max_notifications is not None and len(builder.notifications) >= max_notifications:
            logger.info(f"Reached max_notifications={max_notifications}, stopping scrape")
            break

        logger.info(f"Processing detail page: {list_item.notification_page_url}")
        jobs = scrape_notification_page(
            list_item.notification_page_url,
            fallback_last_date=list_item.last_date,
        )

        for job in jobs:
            if max_notifications is not None and len(builder.notifications) >= max_notifications:
                break

            category_no = (job.category_no or "").strip()
            if not category_no:
                continue

            if category_no in processed_categories:
                logger.info(f"Skipping duplicate category: {category_no}")
                continue

            parsed: dict = {}
            if job.pdf_url:
                parsed = parse_pdf_from_url(job.pdf_url)
            else:
                logger.warning(f"No PDF URL for category_no={category_no}")

            now_text = _now_text()
            record = NotificationRawRecord(
                id=str(uuid.uuid4()),
                title=job.title or (parsed.get("post_name") or ""),
                category_no=parsed.get("category_no") or category_no,
                recruitment_type=parsed.get("recruitment_type") or "",
                department=parsed.get("department") or "",
                post_name=parsed.get("post_name") or job.title or "",
                scale_of_pay=parsed.get("scale_of_pay") or "",
                vacancies=parsed.get("vacancies") or "",
                method_of_appointment=parsed.get("method_of_appointment") or "",
                age_limit=parsed.get("age_limit") or "",
                qualifications=parsed.get("qualifications") or "",
                last_date=parsed.get("last_date") or job.last_date or "",
                pdf_url=job.pdf_url or "",
                source_url=job.source_url or list_item.notification_page_url,
                created_at=now_text,
                updated_at=now_text,
            )

            builder.add_notification(record)
            processed_categories.add(record.category_no)

    dataset = builder.build()
    output_path = Path(output_file)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, indent=2, ensure_ascii=False)

    logger.info(
        "Web normalized JSON exported: "
        f"notifications={len(dataset['notifications'])}, "
        f"qualifications={len(dataset['qualifications'])}, "
        f"age_limits={len(dataset['age_limits'])}, "
        f"methods={len(dataset['methods_of_appointment'])}, "
        f"recruitment_types={len(dataset['recruitment_types'])}, "
        f"departments={len(dataset['departments'])}, "
        f"limit={'all' if max_notifications is None else max_notifications}"
    )
    logger.info(f"Output file: {output_path.resolve()}")
    return output_path


if __name__ == "__main__":
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    export_normalized_json_from_web()
