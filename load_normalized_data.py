import json
from pathlib import Path
from typing import Any

from loguru import logger

from kerala_psc_scraper.database.db import engine, get_session, init_db
from kerala_psc_scraper.models.normalized_notification import (
    AgeLimit,
    Department,
    MethodOfAppointment,
    NormalizedNotification,
    Qualification,
    RecruitmentType,
    notification_qualifications,
)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_normalized_data(input_file: str = "normalized_notifications.json") -> None:
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Normalized JSON file not found: {input_path}")

    dataset = _read_json(input_path)
    notifications = dataset.get("notifications", [])
    qualifications = dataset.get("qualifications", [])
    age_limits = dataset.get("age_limits", [])
    methods = dataset.get("methods_of_appointment", [])
    recruitment_types = dataset.get("recruitment_types", [])
    departments = dataset.get("departments", [])

    logger.info("Rebuilding normalized schema")
    notification_qualifications.drop(bind=engine, checkfirst=True)
    NormalizedNotification.__table__.drop(bind=engine, checkfirst=True)
    Qualification.__table__.drop(bind=engine, checkfirst=True)
    AgeLimit.__table__.drop(bind=engine, checkfirst=True)
    MethodOfAppointment.__table__.drop(bind=engine, checkfirst=True)
    RecruitmentType.__table__.drop(bind=engine, checkfirst=True)
    Department.__table__.drop(bind=engine, checkfirst=True)

    logger.info("Initialising database schema")
    init_db()

    session = get_session()
    try:
        logger.info("Clearing previous normalized data")
        session.execute(notification_qualifications.delete())
        session.query(NormalizedNotification).delete()
        session.query(Qualification).delete()
        session.query(AgeLimit).delete()
        session.query(MethodOfAppointment).delete()
        session.query(RecruitmentType).delete()
        session.query(Department).delete()
        session.commit()

        logger.info("Inserting recruitment_type records")
        for item in recruitment_types:
            session.add(
                RecruitmentType(
                    id=item["id"],
                    value=item.get("value") or "",
                )
            )

        logger.info("Inserting department records")
        for item in departments:
            session.add(
                Department(
                    id=item["id"],
                    value=item.get("value") or "",
                )
            )

        logger.info("Inserting method_of_appointment records")
        for item in methods:
            session.add(
                MethodOfAppointment(
                    id=item["id"],
                    value=item.get("value"),
                    description=item.get("description"),
                )
            )

        logger.info("Inserting age_limit records")
        for item in age_limits:
            session.add(
                AgeLimit(
                    id=item["id"],
                    value=item.get("value"),
                    description=item.get("description"),
                )
            )

        logger.info("Inserting qualification records")
        for item in qualifications:
            session.add(
                Qualification(
                    id=item["id"],
                    value=item.get("value") or "",
                    description=item.get("description"),
                )
            )

        session.flush()

        logger.info("Inserting normalized notification records")
        for item in notifications:
            session.add(
                NormalizedNotification(
                    id=item["id"],
                    title=item.get("title"),
                    category_no=item.get("category_no") or "",
                    post_name=item.get("post_name"),
                    scale_of_pay=item.get("scale_of_pay"),
                    vacancies=item.get("vacancies"),
                    last_date=item.get("last_date"),
                    pdf_url=item.get("pdf_url"),
                    source_url=item.get("source_url"),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                    method_of_appointment_id=item.get("method_of_appointment_id"),
                    age_limit_id=item.get("age_limit_id"),
                    recruitment_type_id=item.get("recruitment_type_id"),
                    department_id=item.get("department_id"),
                )
            )

        session.flush()

        logger.info("Inserting notification_qualification mappings")
        mapping_rows: list[dict[str, str]] = []
        for item in notifications:
            notification_id = item["id"]
            for qualification_id in item.get("qualification_ids", []):
                mapping_rows.append(
                    {
                        "notification_id": notification_id,
                        "qualification_id": qualification_id,
                    }
                )

        if mapping_rows:
            session.execute(notification_qualifications.insert(), mapping_rows)

        session.commit()
        logger.info(
            "Normalized DB load complete: "
            f"notifications={len(notifications)}, "
            f"qualifications={len(qualifications)}, "
            f"age_limits={len(age_limits)}, "
            f"methods={len(methods)}, "
            f"recruitment_types={len(recruitment_types)}, "
            f"departments={len(departments)}, "
            f"mappings={len(mapping_rows)}"
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    load_normalized_data()
