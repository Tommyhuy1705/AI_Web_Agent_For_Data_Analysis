"""
Dify Service - Integration with Dify AI Platform
Điều phối luồng đa tác tử (Multi-Agent) qua Dify API.

Dify Agent Flow:
1. Nhận text query từ user
2. LLM quét Zilliz để hiểu cấu trúc bảng analytics_mart
3. Sinh SQL query
4. Gọi /api/sql/execute endpoint
5. Trả về kết quả
"""

import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Dify Configuration
DIFY_API_URL = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")


class DifyService:
    """Service class cho Dify API integration."""

    def __init__(self):
        self.api_url = DIFY_API_URL
        self.api_key = DIFY_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @property
    def is_configured(self) -> bool:
        """Kiểm tra Dify đã được cấu hình chưa."""
        return bool(self.api_key and self.api_key != "app-your_dify_api_key")

    async def send_chat_message(
        self,
        query: str,
        user_id: str = "default_user",
        conversation_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Gửi chat message sang Dify và stream response.

        Args:
            query: Câu hỏi của user
            user_id: ID user
            conversation_id: ID conversation (nếu tiếp tục)
            inputs: Biến đầu vào bổ sung

        Yields:
            Dict chứa event type và data
        """
        if not self.is_configured:
            yield {
                "event": "error",
                "data": {"message": "Dify API key not configured"},
            }
            return

        payload = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "streaming",
            "conversation_id": conversation_id or "",
            "user": user_id,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self.api_url}/chat-messages",
                    json=payload,
                    headers=self.headers,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield {
                            "event": "error",
                            "data": {
                                "message": f"Dify API error {response.status_code}: {error_text.decode()}"
                            },
                        }
                        return

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        try:
                            data = json.loads(line[6:])
                            event_type = data.get("event", "")

                            if event_type == "message":
                                yield {
                                    "event": "message",
                                    "data": {
                                        "chunk": data.get("answer", ""),
                                        "conversation_id": data.get("conversation_id", ""),
                                        "message_id": data.get("message_id", ""),
                                    },
                                }

                            elif event_type == "message_end":
                                yield {
                                    "event": "message_end",
                                    "data": {
                                        "conversation_id": data.get("conversation_id", ""),
                                        "metadata": data.get("metadata", {}),
                                    },
                                }

                            elif event_type == "agent_thought":
                                yield {
                                    "event": "agent_thought",
                                    "data": {
                                        "thought": data.get("thought", ""),
                                        "tool": data.get("tool", ""),
                                        "tool_input": data.get("tool_input", ""),
                                        "observation": data.get("observation", ""),
                                    },
                                }

                            elif event_type == "agent_message":
                                yield {
                                    "event": "agent_message",
                                    "data": {
                                        "answer": data.get("answer", ""),
                                    },
                                }

                            elif event_type == "error":
                                yield {
                                    "event": "error",
                                    "data": {
                                        "message": data.get("message", "Unknown Dify error"),
                                        "code": data.get("code", ""),
                                    },
                                }

                        except json.JSONDecodeError:
                            continue

        except httpx.TimeoutException:
            yield {
                "event": "error",
                "data": {"message": "Dify API request timeout (120s)"},
            }
        except Exception as e:
            logger.error(f"Dify service error: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": {"message": f"Dify service error: {str(e)}"},
            }

    async def run_workflow(
        self,
        inputs: Dict[str, Any],
        user_id: str = "system",
    ) -> Optional[Dict[str, Any]]:
        """
        Chạy Dify workflow (blocking mode).
        Dùng cho alarm webhook và các tác vụ nền.

        Args:
            inputs: Biến đầu vào cho workflow
            user_id: ID user

        Returns:
            Dict chứa kết quả workflow hoặc None nếu lỗi
        """
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.api_url}/workflows/run",
                    json={
                        "inputs": inputs,
                        "response_mode": "blocking",
                        "user": user_id,
                    },
                    headers=self.headers,
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Dify workflow error: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Dify workflow error: {e}")
            return None

    async def get_conversations(
        self,
        user_id: str = "default_user",
        limit: int = 20,
    ) -> list:
        """Lấy danh sách conversations."""
        if not self.is_configured:
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.api_url}/conversations",
                    params={"user": user_id, "limit": limit},
                    headers=self.headers,
                )
                if response.status_code == 200:
                    return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Get conversations error: {e}")

        return []


# Singleton instance
dify_service = DifyService()
