import re
from io import BytesIO
from typing import Optional

import pdfplumber
import requests
from loguru import logger

from kerala_psc_scraper.config.settings import (
    REQUEST_MAX_RETRIES,
    REQUEST_RETRY_BACKOFF,
    REQUEST_TIMEOUT,
)


def _extract_section(text: str, start_pattern: str, end_patterns: list) -> str:
    start_match = re.search(start_pattern, text, re.IGNORECASE)
    if not start_match:
        return ""

    start_pos = start_match.end()
    end_pos = len(text)

    for end_pat in end_patterns:
        end_match = re.search(end_pat, text[start_pos:], re.IGNORECASE)
        if end_match:
            candidate = start_pos + end_match.start()
            if candidate < end_pos:
                end_pos = candidate

    return text[start_pos:end_pos].strip()


def _empty_result() -> dict:
    return {
        "recruitment_type": None,
        "category_no": None,
        "department": None,
        "post_name": None,
        "scale_of_pay": None,
        "vacancies": None,
        "method_of_appointment": None,
        "age_limit": None,
        "qualifications": None,
        "last_date": None,
    }


def _extract_full_text_from_bytes(pdf_bytes: bytes) -> str:
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parse_pdf(pdf_path: str) -> dict:
    logger.info(f"Parsing PDF: {pdf_path}")
    result: dict = _empty_result()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
    except Exception as exc:
        logger.error(f"Failed to open/read PDF {pdf_path}: {exc}")
        return result

    if not full_text.strip():
        logger.warning(f"No text extracted from PDF: {pdf_path}")
        return result

    # Recruitment type (e.g. "GENERAL RECRUITMENT – STATEWIDE")
    recruit_match = re.search(
        r"((?:GENERAL|SPECIAL|DIRECT)\s+RECRUITMENT[^\n]*)",
        full_text,
        re.IGNORECASE,
    )
    if recruit_match:
        result["recruitment_type"] = recruit_match.group(1).strip()

    # Category number
    cat_match = re.search(
        r"CATEGORY\s+NO[:\.]?\s*([\d]+/\d{4})",
        full_text,
        re.IGNORECASE,
    )
    if cat_match:
        result["category_no"] = cat_match.group(1).strip()

    # Department
    dept_match = re.search(
        r"Department\s*[:\-]\s*(.+)",
        full_text,
        re.IGNORECASE,
    )
    if dept_match:
        result["department"] = dept_match.group(1).strip()

    # Post name (Name of Post)
    post_match = re.search(
        r"(?:Name\s+of\s+Post|Post\s+Name)\s*[:\-]\s*(.+)",
        full_text,
        re.IGNORECASE,
    )
    if post_match:
        result["post_name"] = post_match.group(1).strip()

    # Scale of pay
    pay_match = re.search(
        r"Scale\s+of\s+Pay\s*[:\-]?\s*([\u20B9\u20A8₹Rs\.]+[\s\d,\-–]+(?:[\d,]+)?)",
        full_text,
        re.IGNORECASE,
    )
    if pay_match:
        result["scale_of_pay"] = pay_match.group(1).strip()
    else:
        # Broader fallback
        pay_match2 = re.search(
            r"([\u20B9₹]\s*[\d,]+\s*[–\-]\s*[\d,]+)",
            full_text,
        )
        if pay_match2:
            result["scale_of_pay"] = pay_match2.group(1).strip()

    # Vacancies / Number of vacancies
    vac_match = re.search(
        r"(?:Number\s+of\s+Vacanc(?:y|ies)|Vacancies?)\s*[:\-]?\s*(.+)",
        full_text,
        re.IGNORECASE,
    )
    if vac_match:
        result["vacancies"] = vac_match.group(1).strip().splitlines()[0].strip()

    # Method of appointment
    result["method_of_appointment"] = _extract_section(
        full_text,
        r"Method\s+of\s+Appointment\s*[:\-]?",
        [
            r"(?:^|\n)\s*\d+[\.\)]\s",
            r"Age\s+Limit",
            r"Qualifications?",
            r"Scale\s+of\s+Pay",
        ],
    )

    # Age limit
    result["age_limit"] = _extract_section(
        full_text,
        r"Age\s+Limit\s*[:\-]?",
        [
            r"Qualifications?",
            r"Method\s+of\s+Appointment",
            r"Scale\s+of\s+Pay",
            r"Last\s+date",
        ],
    )

    # Qualifications
    result["qualifications"] = _extract_section(
        full_text,
        r"Qualifications?\s*[:\-]?",
        [
            r"Age\s+Limit",
            r"Method\s+of\s+Appointment",
            r"Scale\s+of\s+Pay",
            r"Last\s+date",
            r"How\s+to\s+Apply",
        ],
    )

    # Last date
    last_date_match = re.search(
        r"Last\s+date\s+(?:for\s+submission\s+of\s+application\s*)?[:\-]?\s*(\d{2}-\d{2}-\d{4})",
        full_text,
        re.IGNORECASE,
    )
    if last_date_match:
        result["last_date"] = last_date_match.group(1).strip()

    logger.info(f"PDF parsed: category_no={result['category_no']}, post={result['post_name']}")
    return result


def parse_pdf_from_url(pdf_url: str) -> dict:
    logger.info(f"Parsing PDF from URL (in-memory): {pdf_url}")
    result: dict = _empty_result()

    pdf_bytes: Optional[bytes] = None
    for attempt in range(1, REQUEST_MAX_RETRIES + 1):
        try:
            response = requests.get(pdf_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            pdf_bytes = response.content
            break
        except requests.RequestException as exc:
            logger.warning(f"Attempt {attempt} failed for PDF URL {pdf_url}: {exc}")
            if attempt < REQUEST_MAX_RETRIES:
                # Keep retry behavior consistent with scraper/download components.
                import time

                time.sleep(REQUEST_RETRY_BACKOFF * attempt)

    if not pdf_bytes:
        logger.error(f"Failed to fetch PDF bytes from URL: {pdf_url}")
        return result

    try:
        full_text = _extract_full_text_from_bytes(pdf_bytes)
    except Exception as exc:
        logger.error(f"Failed to parse PDF bytes from URL {pdf_url}: {exc}")
        return result

    if not full_text.strip():
        logger.warning(f"No text extracted from PDF URL: {pdf_url}")
        return result

    # Recruitment type (e.g. "GENERAL RECRUITMENT – STATEWIDE")
    recruit_match = re.search(
        r"((?:GENERAL|SPECIAL|DIRECT)\s+RECRUITMENT[^\n]*)",
        full_text,
        re.IGNORECASE,
    )
    if recruit_match:
        result["recruitment_type"] = recruit_match.group(1).strip()

    # Category number
    cat_match = re.search(
        r"CATEGORY\s+NO[:\.]?\s*([\d]+/\d{4})",
        full_text,
        re.IGNORECASE,
    )
    if cat_match:
        result["category_no"] = cat_match.group(1).strip()

    # Department
    dept_match = re.search(
        r"Department\s*[:\-]\s*(.+)",
        full_text,
        re.IGNORECASE,
    )
    if dept_match:
        result["department"] = dept_match.group(1).strip()

    # Post name (Name of Post)
    post_match = re.search(
        r"(?:Name\s+of\s+Post|Post\s+Name)\s*[:\-]\s*(.+)",
        full_text,
        re.IGNORECASE,
    )
    if post_match:
        result["post_name"] = post_match.group(1).strip()

    # Scale of pay
    pay_match = re.search(
        r"Scale\s+of\s+Pay\s*[:\-]?\s*([\u20B9\u20A8₹Rs\.]+[\s\d,\-–]+(?:[\d,]+)?)",
        full_text,
        re.IGNORECASE,
    )
    if pay_match:
        result["scale_of_pay"] = pay_match.group(1).strip()
    else:
        pay_match2 = re.search(
            r"([\u20B9₹]\s*[\d,]+\s*[–\-]\s*[\d,]+)",
            full_text,
        )
        if pay_match2:
            result["scale_of_pay"] = pay_match2.group(1).strip()

    # Vacancies / Number of vacancies
    vac_match = re.search(
        r"(?:Number\s+of\s+Vacanc(?:y|ies)|Vacancies?)\s*[:\-]?\s*(.+)",
        full_text,
        re.IGNORECASE,
    )
    if vac_match:
        result["vacancies"] = vac_match.group(1).strip().splitlines()[0].strip()

    # Method of appointment
    result["method_of_appointment"] = _extract_section(
        full_text,
        r"Method\s+of\s+Appointment\s*[:\-]?",
        [
            r"(?:^|\n)\s*\d+[\.\)]\s",
            r"Age\s+Limit",
            r"Qualifications?",
            r"Scale\s+of\s+Pay",
        ],
    )

    # Age limit
    result["age_limit"] = _extract_section(
        full_text,
        r"Age\s+Limit\s*[:\-]?",
        [
            r"Qualifications?",
            r"Method\s+of\s+Appointment",
            r"Scale\s+of\s+Pay",
            r"Last\s+date",
        ],
    )

    # Qualifications
    result["qualifications"] = _extract_section(
        full_text,
        r"Qualifications?\s*[:\-]?",
        [
            r"Age\s+Limit",
            r"Method\s+of\s+Appointment",
            r"Scale\s+of\s+Pay",
            r"Last\s+date",
            r"How\s+to\s+Apply",
        ],
    )

    # Last date
    last_date_match = re.search(
        r"Last\s+date\s+(?:for\s+submission\s+of\s+application\s*)?[:\-]?\s*(\d{2}-\d{2}-\d{4})",
        full_text,
        re.IGNORECASE,
    )
    if last_date_match:
        result["last_date"] = last_date_match.group(1).strip()

    logger.info(f"PDF parsed from URL: category_no={result['category_no']}, post={result['post_name']}")
    return result
