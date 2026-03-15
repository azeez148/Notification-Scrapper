import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


def _normalize_whitespace(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if cleaned.upper() == "NULL":
        return ""
    return cleaned


def _clean_description(text: str) -> str:
    if not text:
        return ""

    cleaned = _normalize_whitespace(text)
    # Drop trailing section markers that commonly leak from PDF chunks (for example "7" or "7.").
    cleaned = re.sub(r"\s+\d+\.?$", "", cleaned).strip()
    return cleaned


def clean_title(title: Optional[str]) -> str:
    cleaned = _normalize_whitespace(title)
    if not cleaned:
        return ""

    # The source often leaves dangling '(' at the end of title text.
    cleaned = re.sub(r"\s*\(\s*$", "", cleaned)
    return cleaned.strip(" -")


def _split_value_and_description(
    text: Optional[str],
    value_extractor,
) -> Tuple[str, str]:
    raw = _normalize_whitespace(text)
    if not raw:
        return "", ""

    value = _normalize_whitespace(value_extractor(raw))
    if not value:
        return "", raw

    description = raw.replace(value, "", 1).strip(" .:-")
    return value, _clean_description(description)


def _extract_age_value(raw: str) -> str:
    lowered = raw.lower()
    if "not applicable" in lowered:
        return "Not applicable"
    if "upper age limit is not applicable" in lowered:
        return "Upper age limit is not applicable"

    match = re.search(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b", raw)
    if match:
        return f"{match.group(1)}-{match.group(2)}"

    return ""


def extract_age_limit_parts(text: Optional[str]) -> Tuple[str, str]:
    return _split_value_and_description(text, _extract_age_value)


def _extract_method_value(raw: str) -> str:
    lowered = raw.lower()
    if "by transfer" in lowered:
        return "By Transfer"
    if "direct recruitment" in lowered:
        return "Direct Recruitment"
    if "general recruitment" in lowered:
        return "General Recruitment"

    first_sentence = re.split(r"[\.;]\s+", raw, maxsplit=1)[0]
    return first_sentence[:100].strip()


def extract_method_of_appointment_parts(text: Optional[str]) -> Tuple[str, str]:
    return _split_value_and_description(text, _extract_method_value)


def _split_qualification_description(raw: str) -> Tuple[str, str]:
    marker_match = re.search(
        r"\b(EQUIVALENT\s*/\s*HIGHER\s*QUALIFICATION|EXEMPTION|NOTE|SPECIAL\s+CONCESSIONS|MODE\s+OF\s+SUBMITTING)\b",
        raw,
        re.IGNORECASE,
    )
    if not marker_match:
        return raw, ""

    split_at = marker_match.start()
    return raw[:split_at].strip(), _clean_description(raw[split_at:].strip())


def extract_qualification_items_and_description(text: Optional[str]) -> Tuple[List[str], str]:
    raw = _normalize_whitespace(text)
    if not raw:
        return [], ""

    primary, description = _split_qualification_description(raw)

    # Split on enumerations and OR/AND connectors while preserving meaningful phrases.
    primary = re.sub(r"\b\d+\s*[\.)]\s*", "|", primary)
    # Split only on uppercase connectors from notification formatting,
    # so phrases like "Tailoring and Garment Making" stay intact.
    primary = re.sub(r"\b(?:AND|OR)\b", "|", primary)
    chunks = [chunk.strip(" .:-") for chunk in primary.split("|")]

    items: List[str] = []
    seen = set()
    for chunk in chunks:
        item = _normalize_whitespace(chunk)
        if not item or len(item) < 8:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(item)

    return items, description


def _make_entity_key(value: str, description: str) -> str:
    return f"{value.lower()}|{description.lower()}"


def _make_next_id(prefix: str, number: int) -> str:
    return f"{prefix}_{number:04d}"


@dataclass
class NotificationRawRecord:
    id: str
    title: str
    category_no: str
    recruitment_type: str
    department: str
    post_name: str
    scale_of_pay: str
    vacancies: str
    method_of_appointment: str
    age_limit: str
    qualifications: str
    last_date: str
    pdf_url: str
    source_url: str
    created_at: str
    updated_at: str


class NormalizedDatasetBuilder:
    def __init__(self) -> None:
        self._qualification_map: Dict[str, str] = {}
        self._age_limit_map: Dict[str, str] = {}
        self._method_map: Dict[str, str] = {}
        self._recruitment_type_map: Dict[str, str] = {}
        self._department_map: Dict[str, str] = {}

        self.qualifications: List[dict] = []
        self.age_limits: List[dict] = []
        self.methods_of_appointment: List[dict] = []
        self.recruitment_types: List[dict] = []
        self.departments: List[dict] = []
        self.notifications: List[dict] = []

    def _get_or_create_qualification(self, value: str, description: str) -> str:
        key = _make_entity_key(value, description)
        existing_id = self._qualification_map.get(key)
        if existing_id:
            return existing_id

        next_id = _make_next_id("qual", len(self.qualifications) + 1)
        self._qualification_map[key] = next_id
        self.qualifications.append(
            {
                "id": next_id,
                "value": value,
                "description": description,
            }
        )
        return next_id

    def _get_or_create_age_limit(self, value: str, description: str) -> Optional[str]:
        if not value and not description:
            return None
        key = _make_entity_key(value, description)
        existing_id = self._age_limit_map.get(key)
        if existing_id:
            return existing_id

        next_id = _make_next_id("age", len(self.age_limits) + 1)
        self._age_limit_map[key] = next_id
        self.age_limits.append(
            {
                "id": next_id,
                "value": value,
                "description": description,
            }
        )
        return next_id

    def _get_or_create_method(self, value: str, description: str) -> Optional[str]:
        if not value and not description:
            return None
        key = _make_entity_key(value, description)
        existing_id = self._method_map.get(key)
        if existing_id:
            return existing_id

        next_id = _make_next_id("method", len(self.methods_of_appointment) + 1)
        self._method_map[key] = next_id
        self.methods_of_appointment.append(
            {
                "id": next_id,
                "value": value,
                "description": description,
            }
        )
        return next_id

    def _get_or_create_recruitment_type(self, value: str) -> Optional[str]:
        normalized_value = _normalize_whitespace(value)
        if not normalized_value:
            return None

        key = normalized_value.lower()
        existing_id = self._recruitment_type_map.get(key)
        if existing_id:
            return existing_id

        next_id = _make_next_id("recruitment", len(self.recruitment_types) + 1)
        self._recruitment_type_map[key] = next_id
        self.recruitment_types.append(
            {
                "id": next_id,
                "value": normalized_value,
            }
        )
        return next_id

    def _get_or_create_department(self, value: str) -> Optional[str]:
        normalized_value = _normalize_whitespace(value)
        if not normalized_value:
            return None

        key = normalized_value.lower()
        existing_id = self._department_map.get(key)
        if existing_id:
            return existing_id

        next_id = _make_next_id("department", len(self.departments) + 1)
        self._department_map[key] = next_id
        self.departments.append(
            {
                "id": next_id,
                "value": normalized_value,
            }
        )
        return next_id

    def add_notification(self, record: NotificationRawRecord) -> None:
        age_value, age_description = extract_age_limit_parts(record.age_limit)
        method_value, method_description = extract_method_of_appointment_parts(
            record.method_of_appointment
        )
        qualification_values, qualification_description = (
            extract_qualification_items_and_description(record.qualifications)
        )

        age_limit_id = self._get_or_create_age_limit(age_value, age_description)
        method_id = self._get_or_create_method(method_value, method_description)
        recruitment_type_id = self._get_or_create_recruitment_type(
            record.recruitment_type
        )
        department_id = self._get_or_create_department(record.department)

        qualification_ids: List[str] = []
        for value in qualification_values:
            qualification_id = self._get_or_create_qualification(
                value,
                qualification_description,
            )
            qualification_ids.append(qualification_id)

        self.notifications.append(
            {
                "id": record.id,
                "title": clean_title(record.title),
                "category_no": record.category_no,
                "post_name": record.post_name,
                "scale_of_pay": record.scale_of_pay,
                "vacancies": record.vacancies,
                "last_date": record.last_date,
                "pdf_url": record.pdf_url,
                "source_url": record.source_url,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "method_of_appointment_id": method_id,
                "age_limit_id": age_limit_id,
                "recruitment_type_id": recruitment_type_id,
                "department_id": department_id,
                "qualification_ids": qualification_ids,
            }
        )

    def build(self) -> dict:
        return {
            "notifications": self.notifications,
            "qualifications": self.qualifications,
            "age_limits": self.age_limits,
            "methods_of_appointment": self.methods_of_appointment,
            "recruitment_types": self.recruitment_types,
            "departments": self.departments,
        }
