"""Pydantic schemas for Alarm events."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AlarmEvent(BaseModel):
    metric_name: str
    current_value: float
    previous_value: float
    change_pct: float
    severity: str  # "warning" | "critical"
    message: str
    triggered_at: datetime
    email_sent: bool = False
    email_recipients: Optional[list[str]] = None
