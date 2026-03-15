from sqlalchemy import Column, ForeignKey, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from kerala_psc_scraper.models.job_notification import Base


notification_qualifications = Table(
    "notification_qualifications",
    Base.metadata,
    Column(
        "notification_id",
        String(64),
        ForeignKey("normalized_notifications.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "qualification_id",
        String(64),
        ForeignKey("qualifications.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Qualification(Base):
    __tablename__ = "qualifications"

    id = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)


class AgeLimit(Base):
    __tablename__ = "age_limits"

    id = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)


class MethodOfAppointment(Base):
    __tablename__ = "methods_of_appointment"

    id = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)


class RecruitmentType(Base):
    __tablename__ = "recruitment_types"

    id = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)


class Department(Base):
    __tablename__ = "departments"

    id = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)


class NormalizedNotification(Base):
    __tablename__ = "normalized_notifications"

    id = Column(String(64), primary_key=True)
    title = Column(Text, nullable=True)
    category_no = Column(String(50), nullable=False)
    post_name = Column(Text, nullable=True)
    scale_of_pay = Column(Text, nullable=True)
    vacancies = Column(Text, nullable=True)
    last_date = Column(String(50), nullable=True)
    pdf_url = Column(Text, nullable=True)
    source_url = Column(Text, nullable=True)
    created_at = Column(String(64), nullable=True)
    updated_at = Column(String(64), nullable=True)

    method_of_appointment_id = Column(
        String(64),
        ForeignKey("methods_of_appointment.id", ondelete="SET NULL"),
        nullable=True,
    )
    age_limit_id = Column(
        String(64),
        ForeignKey("age_limits.id", ondelete="SET NULL"),
        nullable=True,
    )
    recruitment_type_id = Column(
        String(64),
        ForeignKey("recruitment_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    department_id = Column(
        String(64),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )

    method_of_appointment = relationship("MethodOfAppointment")
    age_limit = relationship("AgeLimit")
    recruitment_type = relationship("RecruitmentType")
    department = relationship("Department")
    qualifications = relationship("Qualification", secondary=notification_qualifications)

    __table_args__ = (
        UniqueConstraint("category_no", name="uq_normalized_notifications_category_no"),
    )
