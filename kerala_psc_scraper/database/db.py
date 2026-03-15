from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from kerala_psc_scraper.config.settings import DATABASE_URL
from kerala_psc_scraper.models.job_notification import Base
from kerala_psc_scraper.models import normalized_notification  # noqa: F401

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
