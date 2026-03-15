import csv
import json
from pathlib import Path

from loguru import logger

from kerala_psc_scraper.services.normalization_service import (
    NormalizedDatasetBuilder,
    NotificationRawRecord,
)


def _clean_csv_value(value: str) -> str:
    cleaned = (value or "").strip()
    if cleaned.upper() == "NULL":
        return ""
    return cleaned


def _read_csv(csv_path: Path) -> list[NotificationRawRecord]:
    records: list[NotificationRawRecord] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            records.append(
                NotificationRawRecord(
                    id=_clean_csv_value(row.get("id") or ""),
                    title=_clean_csv_value(row.get("title") or ""),
                    category_no=_clean_csv_value(row.get("category_no") or ""),
                    recruitment_type=_clean_csv_value(row.get("recruitment_type") or ""),
                    department=_clean_csv_value(row.get("department") or ""),
                    post_name=_clean_csv_value(row.get("post_name") or ""),
                    scale_of_pay=_clean_csv_value(row.get("scale_of_pay") or ""),
                    vacancies=_clean_csv_value(row.get("vacancies") or ""),
                    method_of_appointment=_clean_csv_value(row.get("method_of_appointment") or ""),
                    age_limit=_clean_csv_value(row.get("age_limit") or ""),
                    qualifications=_clean_csv_value(row.get("qualifications") or ""),
                    last_date=_clean_csv_value(row.get("last_date") or ""),
                    pdf_url=_clean_csv_value(row.get("pdf_url") or ""),
                    source_url=_clean_csv_value(row.get("source_url") or ""),
                    created_at=_clean_csv_value(row.get("created_at") or ""),
                    updated_at=_clean_csv_value(row.get("updated_at") or ""),
                )
            )
    return records


def export_normalized_json(
    csv_file: str = "job_notifications.csv",
    output_file: str = "normalized_notifications.json",
) -> Path:
    csv_path = Path(csv_file)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    logger.info(f"Reading source CSV: {csv_path}")
    rows = _read_csv(csv_path)
    logger.info(f"Loaded {len(rows)} rows from CSV")

    builder = NormalizedDatasetBuilder()
    for row in rows:
        builder.add_notification(row)

    dataset = builder.build()
    output_path = Path(output_file)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, indent=2, ensure_ascii=False)

    logger.info(
        "Normalized JSON exported: "
        f"notifications={len(dataset['notifications'])}, "
        f"qualifications={len(dataset['qualifications'])}, "
        f"age_limits={len(dataset['age_limits'])}, "
        f"methods={len(dataset['methods_of_appointment'])}, "
        f"recruitment_types={len(dataset['recruitment_types'])}, "
        f"departments={len(dataset['departments'])}"
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
    export_normalized_json()
