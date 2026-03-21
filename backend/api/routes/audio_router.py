"""
Audio Router — Text-to-Speech Briefing
Endpoint: POST /api/audio/briefing
Nhận vào đoạn text insight và trả về stream file âm thanh MP3.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from backend.services.audio_service import (
    is_configured,
    text_to_speech_bytes,
    text_to_speech_stream,
    get_available_voices,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audio", tags=["Audio"])


class BriefingRequest(BaseModel):
    """Request body cho audio briefing."""
    text: str = Field(..., description="Văn bản cần chuyển thành giọng nói", min_length=1, max_length=5000)
    voice_id: Optional[str] = Field(None, description="ElevenLabs Voice ID (tùy chọn)")
    model_id: Optional[str] = Field(None, description="ElevenLabs Model ID (tùy chọn)")
    stream: bool = Field(False, description="Trả về stream thay vì toàn bộ file")


@router.get("/status")
async def audio_status():
    """Kiểm tra trạng thái ElevenLabs configuration."""
    return {
        "configured": is_configured(),
        "service": "ElevenLabs TTS",
        "purpose": "Convert AI insights to MP3 audio briefings",
    }


@router.post("/briefing")
async def create_audio_briefing(request: BriefingRequest):
    """
    Chuyển đổi text insight thành file âm thanh MP3.

    - Nhận vào đoạn text tóm tắt (Insight)
    - Gọi ElevenLabs API để tạo audio
    - Trả về stream file âm thanh .mp3

    Frontend dùng thẻ <audio> ẩn để play() ngay lập tức.
    """
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="ElevenLabs chưa được cấu hình. Vui lòng thêm ELEVENLABS_API_KEY vào .env.",
        )

    logger.info(f"Audio briefing request: {len(request.text)} chars, stream={request.stream}")

    if request.stream:
        # Streaming response (chunk by chunk)
        async def audio_stream_generator():
            async for chunk in text_to_speech_stream(
                text=request.text,
                voice_id=request.voice_id,
                model_id=request.model_id,
            ):
                yield chunk

        return StreamingResponse(
            audio_stream_generator(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=briefing.mp3",
                "Cache-Control": "no-cache",
            },
        )
    else:
        # Full response (toàn bộ file MP3)
        audio_bytes = await text_to_speech_bytes(
            text=request.text,
            voice_id=request.voice_id,
            model_id=request.model_id,
        )

        if not audio_bytes:
            logger.error(f"Failed to generate audio bytes for text: {request.text[:100]}")
            raise HTTPException(
                status_code=500,
                detail="Không thể tạo audio. ElevenLabs API có thể bị lỗi hoặc API key không hợp lệ. Kiểm tra logs backend để biết chi tiết.",
            )

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=briefing.mp3",
                "Content-Length": str(len(audio_bytes)),
                "Cache-Control": "no-cache",
            },
        )


@router.get("/voices")
async def list_voices():
    """Lấy danh sách giọng đọc có sẵn từ ElevenLabs."""
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="ElevenLabs chưa được cấu hình.",
        )

    voices = get_available_voices()
    return {
        "voices": voices,
        "count": len(voices),
    }
