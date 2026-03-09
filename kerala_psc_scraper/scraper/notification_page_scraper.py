import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from kerala_psc_scraper.config.settings import (
    REQUEST_MAX_RETRIES,
    REQUEST_RETRY_BACKOFF,
    REQUEST_TIMEOUT,
)
from kerala_psc_scraper.scraper import NotificationJob


def _get_html(url: str) -> Optional[str]:
    for attempt in range(1, REQUEST_MAX_RETRIES + 1):
        try:
            logger.info(f"Fetching notification detail page: {url} (attempt {attempt})")
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            logger.warning(f"Attempt {attempt} failed for {url}: {exc}")
            if attempt < REQUEST_MAX_RETRIES:
                time.sleep(REQUEST_RETRY_BACKOFF * attempt)
    logger.error(f"All {REQUEST_MAX_RETRIES} attempts failed for {url}")
    return None


def scrape_notification_page(page_url: str, fallback_last_date: str = "") -> List[NotificationJob]:
    html = _get_html(page_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    jobs: List[NotificationJob] = []

    # Locate the main content area (Joomla article body)
    content = (
        soup.find("div", class_="item-page")
        or soup.find("div", class_="article-content")
        or soup.find("div", id=lambda i: i and "content" in i.lower())
        or soup.find("article")
        or soup.find("body")
    )

    if content is None:
        logger.warning(f"Could not find content area on {page_url}")
        return []

    full_text = content.get_text("\n", strip=True)

    # Find all PDF links on the page
    pdf_links = []
    for anchor in content.find_all("a", href=True):
        href = anchor["href"]
        if href.lower().endswith(".pdf"):
            if not href.startswith("http"):
                href = "https://www.keralapsc.gov.in" + href
            pdf_links.append((anchor.get_text(strip=True), href))

    # If there are no PDF links, try site-wide
    if not pdf_links:
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if href.lower().endswith(".pdf"):
                if not href.startswith("http"):
                    href = "https://www.keralapsc.gov.in" + href
                pdf_links.append((anchor.get_text(strip=True), href))

    # Find all category+job title blocks in the text
    # Pattern: job title followed by CAT.NO.XX/YYYY on same or adjacent line
    cat_pattern = re.compile(r"CAT\.?\s*NO\.?\s*([\d]+/\d{4})", re.IGNORECASE)
    cat_matches = list(cat_pattern.finditer(full_text))

    if not cat_matches:
        logger.warning(f"No category numbers found on {page_url}")
        return []

    lines = full_text.splitlines()

    for match in cat_matches:
        category_no = match.group(1).strip()

        # Find job title: look at lines near the CAT.NO match
        match_pos = match.start()
        text_before = full_text[:match_pos].strip()
        preceding_lines = [l.strip() for l in text_before.splitlines() if l.strip()]
        job_title = preceding_lines[-1] if preceding_lines else ""

        # Try to find a PDF link associated with this category
        pdf_url: Optional[str] = None
        for anchor_text, href in pdf_links:
            # If only one PDF, assign it; otherwise try to match by category
            if len(pdf_links) == 1:
                pdf_url = href
                break
            normalized_cat = category_no.replace("/", "_").replace(" ", "")
            if normalized_cat in href or category_no in anchor_text:
                pdf_url = href
                break

        # Fallback: first PDF link
        if pdf_url is None and pdf_links:
            pdf_url = pdf_links[0][1]

        jobs.append(
            NotificationJob(
                title=job_title,
                category_no=category_no,
                pdf_url=pdf_url,
                source_url=page_url,
                last_date=fallback_last_date,
            )
        )

    logger.info(f"Found {len(jobs)} job entries on {page_url}")
    return jobs
