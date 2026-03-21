"""
Chat History Service
Lưu trữ và truy xuất lịch sử hội thoại theo session.
Cung cấp context memory cho LLM khi trả lời câu hỏi tiếp theo.

Tables:
  - public.chat_sessions: metadata của mỗi phiên chat (PK: id uuid)
  - public.chat_messages: từng tin nhắn trong session (PK: id uuid, FK: session_id -> chat_sessions.id)
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import os

from backend.services.db_executor import fetch_one, execute_safe_query

logger = logging.getLogger(__name__)

# Số lượng message tối đa đưa vào context (tránh vượt token limit)
MAX_CONTEXT_MESSAGES = 10

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ============================================================
# Session Management
# ============================================================

async def create_session(user_id: str, title: Optional[str] = None) -> Dict[str, Any]:
    """
    Tạo mới một chat session.
    Returns session dict với id (session_id).
    """
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    session_data = {
        "id": session_id,
        "user_id": user_id,
        "title": title or "New Chat",
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/chat_sessions",
                json=session_data,
                headers=_headers(),
            )
            if resp.status_code in (200, 201):
                result = resp.json()
                created = result[0] if isinstance(result, list) else result
                # Normalize: expose session_id as alias for id
                created["session_id"] = created.get("id", session_id)
                created["message_count"] = 0
                logger.info(f"[ChatHistory] Session created: {session_id} for user {user_id}")
                return created
    except Exception as e:
        logger.error(f"[ChatHistory] Failed to create session: {e}")

    # Fallback
    session_data["session_id"] = session_id
    session_data["message_count"] = 0
    return session_data


async def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Lấy thông tin session theo id."""
    try:
        result = await fetch_one(
            f"SELECT id, user_id, title, is_active, created_at, updated_at "
            f"FROM chat_sessions WHERE id = '{session_id}'"
        )
        if result:
            result["session_id"] = result.get("id", session_id)
        return result
    except Exception as e:
        logger.error(f"[ChatHistory] Failed to get session {session_id}: {e}")
        return None


async def list_sessions(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Lấy danh sách sessions của user, sắp xếp theo thời gian mới nhất."""
    try:
        results = await execute_safe_query(
            f"SELECT id, user_id, title, created_at, updated_at "
            f"FROM chat_sessions "
            f"WHERE user_id = '{user_id}' AND is_active = true "
            f"ORDER BY updated_at DESC "
            f"LIMIT {limit}"
        )
        if results:
            for r in results:
                r["session_id"] = r.get("id", "")
                # Count messages
                count_result = await fetch_one(
                    f"SELECT COUNT(*) as cnt FROM chat_messages WHERE session_id = '{r['id']}'"
                )
                r["message_count"] = int(count_result["cnt"]) if count_result else 0
        return results or []
    except Exception as e:
        logger.error(f"[ChatHistory] Failed to list sessions for {user_id}: {e}")
        return []


async def update_session_title(session_id: str, title: str):
    """Cập nhật tiêu đề session."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.patch(
                f"{SUPABASE_URL}/rest/v1/chat_sessions?id=eq.{session_id}",
                json={"title": title[:100], "updated_at": datetime.now(timezone.utc).isoformat()},
                headers={**_headers(), "Prefer": "return=minimal"},
            )
    except Exception as e:
        logger.warning(f"[ChatHistory] Failed to update session title: {e}")


async def delete_session(session_id: str):
    """Soft delete session (đặt is_active = false)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.patch(
                f"{SUPABASE_URL}/rest/v1/chat_sessions?id=eq.{session_id}",
                json={"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()},
                headers={**_headers(), "Prefer": "return=minimal"},
            )
        logger.info(f"[ChatHistory] Session deleted (soft): {session_id}")
    except Exception as e:
        logger.error(f"[ChatHistory] Failed to delete session {session_id}: {e}")


# ============================================================
# Message Management
# ============================================================

async def save_message(
    session_id: str,
    role: str,  # "user" | "assistant" | "system"
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Lưu một tin nhắn vào chat_messages.
    Tự động cập nhật updated_at của session.
    """
    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    message_data = {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "created_at": now,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/chat_messages",
                json=message_data,
                headers=_headers(),
            )
            if resp.status_code in (200, 201):
                result = resp.json()
                saved = result[0] if isinstance(result, list) else result
                # Cập nhật session updated_at
                await _touch_session(session_id, now)
                return saved
    except Exception as e:
        logger.error(f"[ChatHistory] Failed to save message: {e}")

    return message_data


async def get_messages(
    session_id: str,
    limit: int = MAX_CONTEXT_MESSAGES,
) -> List[Dict[str, Any]]:
    """
    Lấy danh sách messages của session, sắp xếp theo thứ tự thời gian.
    """
    try:
        results = await execute_safe_query(
            f"SELECT id, session_id, role, content, metadata, created_at "
            f"FROM chat_messages "
            f"WHERE session_id = '{session_id}' "
            f"ORDER BY created_at ASC "
            f"LIMIT {limit}"
        )
        return results or []
    except Exception as e:
        logger.error(f"[ChatHistory] Failed to get messages for session {session_id}: {e}")
        return []


async def get_context_messages(session_id: str) -> List[Dict[str, str]]:
    """
    Trả về danh sách messages theo định dạng LLM context:
    [{"role": "user"|"assistant", "content": "..."}]
    Lấy MAX_CONTEXT_MESSAGES messages gần nhất.
    """
    try:
        results = await execute_safe_query(
            f"SELECT role, content FROM chat_messages "
            f"WHERE session_id = '{session_id}' "
            f"ORDER BY created_at DESC "
            f"LIMIT {MAX_CONTEXT_MESSAGES}"
        )
        if not results:
            return []
        # Đảo ngược để đúng thứ tự chronological
        messages = list(reversed(results))
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
            if msg.get("role") in ("user", "assistant")
        ]
    except Exception as e:
        logger.error(f"[ChatHistory] Failed to get context for session {session_id}: {e}")
        return []


# ============================================================
# Auto-title generation
# ============================================================

async def auto_generate_title(session_id: str, first_message: str):
    """
    Tự động tạo tiêu đề session từ message đầu tiên.
    Dùng LLM để tóm tắt ngắn gọn (tối đa 50 ký tự).
    """
    try:
        from backend.services.llm_client import chat_completion, is_configured
        if not is_configured():
            title = first_message[:50].strip()
            if len(first_message) > 50:
                title += "..."
            await update_session_title(session_id, title)
            return

        title = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "Tóm tắt câu hỏi sau thành tiêu đề ngắn gọn (tối đa 50 ký tự, không dùng dấu ngoặc kép). Chỉ trả về tiêu đề, không giải thích.",
                },
                {"role": "user", "content": first_message},
            ],
            temperature=0.3,
            max_tokens=30,
        )
        title = title.strip().strip('"').strip("'")[:100]
        await update_session_title(session_id, title)
        logger.info(f"[ChatHistory] Auto-title generated: '{title}' for session {session_id}")
    except Exception as e:
        logger.warning(f"[ChatHistory] Auto-title generation failed: {e}")
        await update_session_title(session_id, first_message[:50])


# ============================================================
# Private helpers
# ============================================================

async def _touch_session(session_id: str, updated_at: str):
    """Cập nhật updated_at của session sau khi có message mới."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.patch(
                f"{SUPABASE_URL}/rest/v1/chat_sessions?id=eq.{session_id}",
                json={"updated_at": updated_at},
                headers={**_headers(), "Prefer": "return=minimal"},
            )
    except Exception:
        pass  # Non-critical
