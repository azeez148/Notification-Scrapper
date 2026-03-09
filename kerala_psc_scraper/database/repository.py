from typing import Optional

from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kerala_psc_scraper.models.job_notification import JobNotification


class JobNotificationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def exists(self, category_no: str) -> bool:
        return (
            self.session.query(JobNotification)
            .filter(JobNotification.category_no == category_no)
            .first()
            is not None
        )

    def save(self, notification: JobNotification) -> Optional[JobNotification]:
        try:
            self.session.add(notification)
            self.session.commit()
            self.session.refresh(notification)
            logger.info(f"Saved notification: category_no={notification.category_no}")
            return notification
        except IntegrityError:
            self.session.rollback()
            logger.warning(
                f"Duplicate entry skipped: category_no={notification.category_no}"
            )
            return None
        except Exception as exc:
            self.session.rollback()
            logger.error(f"Error saving notification {notification.category_no}: {exc}")
            raise
