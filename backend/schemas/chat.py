"""Pydantic schemas for Chat endpoints."""
from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    session_id: Optional[str] = Field(None, description="Optional session identifier")


class ChatResponse(BaseModel):
    response: str
    tool_used: Optional[str] = None
    chart_config: Optional[dict] = None
    data: Optional[list] = None
