from typing import List

from loguru import logger
from sqlalchemy.orm import Session

from kerala_psc_scraper.database.repository import JobNotificationRepository
from kerala_psc_scraper.models.job_notification import JobNotification
from kerala_psc_scraper.parser.pdf_parser import parse_pdf_from_url
from kerala_psc_scraper.scraper import NotificationJob
from kerala_psc_scraper.scraper.notification_list_scraper import scrape_notification_list
from kerala_psc_scraper.scraper.notification_page_scraper import scrape_notification_page


def process_all_notifications(session: Session) -> None:
    logger.info("Starting notification scraping pipeline")
    repo = JobNotificationRepository(session)

    # Step 1: Scrape the notification list page
    list_items = scrape_notification_list()
    if not list_items:
        logger.warning("No notification list items found")
        return

    for list_item in list_items:
        logger.info(f"Processing notification: {list_item.title}")

        # Step 2: Scrape the notification detail page
        jobs: List[NotificationJob] = scrape_notification_page(
            list_item.notification_page_url,
            fallback_last_date=list_item.last_date,
        )

        for job in jobs:
            _process_job(job, repo)

    logger.info("Notification scraping pipeline complete")


def _process_job(job: NotificationJob, repo: JobNotificationRepository) -> None:
    if repo.exists(job.category_no):
        logger.info(f"Skipping existing record: category_no={job.category_no}")
        return

    parsed: dict = {}

    # Step 3: Parse PDF directly from URL in memory (no local file write)
    if job.pdf_url:
        parsed = parse_pdf_from_url(job.pdf_url)
    else:
        logger.warning(f"No PDF URL for category_no={job.category_no}")

    # Step 4: Build and save the record
    notification = JobNotification(
        title=job.title or parsed.get("post_name"),
        category_no=parsed.get("category_no") or job.category_no,
        recruitment_type=parsed.get("recruitment_type"),
        department=parsed.get("department"),
        post_name=parsed.get("post_name") or job.title,
        scale_of_pay=parsed.get("scale_of_pay"),
        vacancies=parsed.get("vacancies"),
        method_of_appointment=parsed.get("method_of_appointment"),
        age_limit=parsed.get("age_limit"),
        qualifications=parsed.get("qualifications"),
        last_date=parsed.get("last_date") or job.last_date,
        pdf_url=job.pdf_url,
        source_url=job.source_url,
    )

    logger.info(f"Saving notification: category_no={notification.category_no}")
    repo.save(notification)
