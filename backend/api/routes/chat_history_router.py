"""
Chat History Router
API endpoints để quản lý chat sessions và messages.

Endpoints:
  POST   /api/chat/sessions              - Tạo session mới
  GET    /api/chat/sessions/{user_id}    - Lấy danh sách sessions của user
  GET    /api/chat/sessions/{session_id}/messages - Lấy messages của session
  DELETE /api/chat/sessions/{session_id} - Xóa session
  GET    /api/chat/sessions/{session_id}/context  - Lấy context cho LLM
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.chat_history_service import (
    create_session,
    get_session,
    list_sessions,
    get_messages,
    get_context_messages,
    delete_session,
    save_message,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat History"])


# ============================================================
# Request/Response Models
# ============================================================

class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="default_user", description="User identifier")
    title: Optional[str] = Field(None, description="Session title (auto-generated if empty)")


class SaveMessageRequest(BaseModel):
    session_id: str
    role: str = Field(..., description="'user' | 'assistant' | 'system'")
    content: str
    metadata: Optional[dict] = None


# ============================================================
# Session Endpoints
# ============================================================

@router.post("/sessions")
async def create_chat_session(request: CreateSessionRequest):
    """
    Tạo một chat session mới.
    Được gọi khi user nhấn nút "New Chat".
    """
    try:
        session = await create_session(
            user_id=request.user_id,
            title=request.title,
        )
        return {
            "success": True,
            "session": session,
        }
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_user_sessions(
    user_id: str = Query(default="default_user", description="User identifier"),
    limit: int = Query(default=20, ge=1, le=100),
):
    """
    Lấy danh sách chat sessions của user.
    Dùng để hiển thị sidebar lịch sử chat.
    """
    try:
        sessions = await list_sessions(user_id=user_id, limit=limit)
        return {
            "success": True,
            "user_id": user_id,
            "sessions": sessions,
            "count": len(sessions),
        }
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_chat_session(session_id: str):
    """Lấy thông tin chi tiết của một session."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"success": True, "session": session}


@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """
    Xóa một chat session (soft delete).
    Được gọi khi user xóa một cuộc hội thoại.
    """
    try:
        await delete_session(session_id)
        return {"success": True, "message": f"Session {session_id} deleted"}
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Message Endpoints
# ============================================================

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    Lấy danh sách messages của một session.
    Dùng để hiển thị lại lịch sử hội thoại khi user chọn session cũ.
    """
    try:
        messages = await get_messages(session_id=session_id, limit=limit)
        return {
            "success": True,
            "session_id": session_id,
            "messages": messages,
            "count": len(messages),
        }
    except Exception as e:
        logger.error(f"Failed to get messages for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/context")
async def get_session_context(session_id: str):
    """
    Lấy context messages của session theo định dạng LLM.
    Dùng nội bộ để inject vào LLM prompt.
    """
    try:
        context = await get_context_messages(session_id=session_id)
        return {
            "success": True,
            "session_id": session_id,
            "context": context,
            "count": len(context),
        }
    except Exception as e:
        logger.error(f"Failed to get context for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/messages")
async def add_message_to_session(session_id: str, request: SaveMessageRequest):
    """
    Lưu một tin nhắn vào session.
    Thường được gọi nội bộ từ chat_router, nhưng cũng expose ra ngoài để test.
    """
    try:
        if request.role not in ("user", "assistant", "system"):
            raise HTTPException(
                status_code=400,
                detail="role must be 'user', 'assistant', or 'system'"
            )
        message = await save_message(
            session_id=session_id,
            role=request.role,
            content=request.content,
            metadata=request.metadata,
        )
        return {"success": True, "message": message}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
