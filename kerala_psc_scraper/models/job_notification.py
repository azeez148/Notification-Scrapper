import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class JobNotification(Base):
    __tablename__ = "job_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=True)
    category_no = Column(String(50), nullable=False)
    recruitment_type = Column(Text, nullable=True)
    department = Column(Text, nullable=True)
    post_name = Column(Text, nullable=True)
    scale_of_pay = Column(Text, nullable=True)
    vacancies = Column(Text, nullable=True)
    method_of_appointment = Column(Text, nullable=True)
    age_limit = Column(Text, nullable=True)
    qualifications = Column(Text, nullable=True)
    last_date = Column(String(50), nullable=True)
    pdf_url = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (UniqueConstraint("category_no", name="uq_job_notifications_category_no"),)

    def __repr__(self) -> str:
        return f"<JobNotification category_no={self.category_no!r} post_name={self.post_name!r}>"
