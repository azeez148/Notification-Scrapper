import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from kerala_psc_scraper.config.settings import (
    NOTIFICATIONS_URL,
    REQUEST_MAX_RETRIES,
    REQUEST_RETRY_BACKOFF,
    REQUEST_TIMEOUT,
)
from kerala_psc_scraper.scraper import NotificationListItem


def _get_html(url: str) -> Optional[str]:
    for attempt in range(1, REQUEST_MAX_RETRIES + 1):
        try:
            logger.info(f"Fetching notification list page: {url} (attempt {attempt})")
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            logger.warning(f"Attempt {attempt} failed for {url}: {exc}")
            if attempt < REQUEST_MAX_RETRIES:
                time.sleep(REQUEST_RETRY_BACKOFF * attempt)
    logger.error(f"All {REQUEST_MAX_RETRIES} attempts failed for {url}")
    return None


def scrape_notification_list(url: str = NOTIFICATIONS_URL) -> List[NotificationListItem]:
    html = _get_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results: List[NotificationListItem] = []

    # The notifications page has a table with notification rows
    table = soup.find("table")
    if table is None:
        # Fallback: try to find rows by common class patterns
        logger.warning("No table found on notifications page; trying article/div search")
        return _scrape_from_divs(soup, url)

    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # Try to extract title and link from anchor tags
        anchor = row.find("a", href=True)
        if anchor is None:
            continue

        title_text = anchor.get_text(strip=True)
        notification_url = anchor["href"]
        if not notification_url.startswith("http"):
            notification_url = "https://www.keralapsc.gov.in" + notification_url

        # Category number range is typically in one of the cells
        category_range = ""
        last_date = ""
        for cell in cells:
            text = cell.get_text(strip=True)
            if "CAT" in text.upper():
                category_range = text
            date_match = re.search(r"\d{1,2}-\d{1,2}-\d{4}", text)
            if date_match:
                last_date = date_match.group(0)

        results.append(
            NotificationListItem(
                title=title_text,
                notification_page_url=notification_url,
                category_number_range=category_range,
                last_date=last_date,
            )
        )

    logger.info(f"Found {len(results)} notification items on list page")
    return results


def _scrape_from_divs(soup: BeautifulSoup, base_url: str) -> List[NotificationListItem]:
    results: List[NotificationListItem] = []

    # Try finding rows in common CMS patterns (Joomla-based site)
    items = soup.find_all("div", class_=lambda c: c and "item" in c.lower())
    if not items:
        items = soup.find_all("article")

    for item in items:
        anchor = item.find("a", href=True)
        if anchor is None:
            continue

        title_text = anchor.get_text(strip=True)
        notification_url = anchor["href"]
        if not notification_url.startswith("http"):
            notification_url = "https://www.keralapsc.gov.in" + notification_url

        text_content = item.get_text(" ", strip=True)
        category_range = ""
        last_date = ""

        cat_match = re.search(r"CAT\.?\s*NO\s*[:\.]?\s*[\d/]+(?:\s+TO\s+CAT\.?\s*NO\s*[:\.]?\s*[\d/]+)?", text_content, re.IGNORECASE)
        if cat_match:
            category_range = cat_match.group(0).strip()

        date_match = re.search(r"\d{2}-\d{2}-\d{4}", text_content)
        if date_match:
            last_date = date_match.group(0)

        results.append(
            NotificationListItem(
                title=title_text,
                notification_page_url=notification_url,
                category_number_range=category_range,
                last_date=last_date,
            )
        )

    logger.info(f"Found {len(results)} notification items via div/article search")
    return results
