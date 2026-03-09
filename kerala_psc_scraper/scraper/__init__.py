from dataclasses import dataclass
from typing import Optional


@dataclass
class NotificationListItem:
    title: str
    notification_page_url: str
    category_number_range: str
    last_date: str


@dataclass
class NotificationJob:
    title: str
    category_no: str
    pdf_url: Optional[str] = None
    source_url: Optional[str] = None
    last_date: Optional[str] = None
