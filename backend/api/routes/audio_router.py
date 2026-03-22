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
from backend.services.llm_client import chat_completion, is_configured as is_llm_configured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audio", tags=["Audio"])


class BriefingRequest(BaseModel):
    """Request body cho audio briefing."""
    text: str = Field(..., description="Văn bản cần chuyển thành giọng nói", min_length=1, max_length=5000)
    voice_id: Optional[str] = Field(None, description="ElevenLabs Voice ID (tùy chọn)")
    model_id: Optional[str] = Field(None, description="ElevenLabs Model ID (tùy chọn)")
    stream: bool = Field(False, description="Trả về stream thay vì toàn bộ file")
    summarize: bool = Field(True, description="Tự động tóm tắt trước khi đọc")
    summary_words: int = Field(200, ge=120, le=300, description="Số từ mục tiêu cho bản tóm tắt")


def _trim_to_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


async def _build_english_audio_script(text: str, target_words: int) -> str:
    """Create a concise English script for TTS, targeting around target_words."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""

    if not is_llm_configured():
        # Fallback when LLM is unavailable: truncate to a manageable English-sized length.
        return _trim_to_words(cleaned, target_words)

    try:
        summarized = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an executive briefing writer. Convert the input into natural, spoken English "
                        "for text-to-speech. Keep it concise, factual, and easy to listen to. "
                        "Target 180-220 words unless the input is too short. "
                        "Return plain text only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Rewrite and summarize this content into spoken English around {target_words} words:\n\n"
                        f"{cleaned}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=420,
        )
        return _trim_to_words(" ".join(summarized.split()), 240)
    except Exception as e:
        logger.warning(f"Failed to summarize audio script with LLM: {e}")
        return _trim_to_words(cleaned, target_words)


@router.get("/status")
async def audio_status():
    """Kiểm tra trạng thái ElevenLabs configuration."""
    from backend.services.audio_service import _validate_api_key
    
    is_valid, error_msg = _validate_api_key()
    return {
        "configured": is_valid,
        "service": "ElevenLabs TTS",
        "purpose": "Convert AI insights to MP3 audio briefings",
        "status": "ready" if is_valid else "error",
        "error": error_msg if not is_valid else None,
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
        error_msg = "ElevenLabs chưa được cấu hình. Vui lòng thêm ELEVENLABS_API_KEY vào .env"
        logger.error(error_msg)
        raise HTTPException(
            status_code=503,
            detail=error_msg,
        )

    logger.info(
        f"Audio briefing request: {len(request.text)} chars, stream={request.stream}, "
        f"summarize={request.summarize}, summary_words={request.summary_words}"
    )

    script_text = request.text
    if request.summarize:
        script_text = await _build_english_audio_script(request.text, request.summary_words)

    if not script_text.strip():
        raise HTTPException(status_code=400, detail="Audio text is empty after preprocessing")

    if request.stream:
        # Streaming response (chunk by chunk)
        audio_stream, stream_error = await text_to_speech_stream(
            text=script_text,
            voice_id=request.voice_id,
            model_id=request.model_id,
        )
        
        if stream_error:
            logger.error(f"Audio stream initialization failed: {stream_error}")
            raise HTTPException(
                status_code=500,
                detail=f"Không thể tạo audio. {stream_error}",
            )
        
        if audio_stream is None:
            logger.error("Audio stream generator is None")
            raise HTTPException(
                status_code=500,
                detail="Không thể tạo audio stream. Vui lòng kiểm tra cấu hình ElevenLabs.",
            )
        
        async def audio_stream_generator():
            async for chunk in audio_stream:
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
        audio_bytes, audio_error = await text_to_speech_bytes(
            text=script_text,
            voice_id=request.voice_id,
            model_id=request.model_id,
        )

        if audio_error:
            logger.error(f"Audio generation failed: {audio_error}")
            error_lower = audio_error.lower()
            status_code = 500
            if "quota exceeded" in error_lower or "quota_exceeded" in error_lower or "insufficient credits" in error_lower:
                status_code = 402
            elif "rate limit" in error_lower:
                status_code = 429

            raise HTTPException(
                status_code=status_code,
                detail=f"Không thể tạo audio. {audio_error}",
            )

        if not audio_bytes:
            logger.error(f"Audio generation returned empty bytes for text: {request.text[:100]}")
            raise HTTPException(
                status_code=500,
                detail="Không thể tạo audio. ElevenLabs API trả về dữ liệu trống.",
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

    voices, error_msg = get_available_voices()
    
    if error_msg:
        logger.error(f"Failed to fetch voices: {error_msg}")
        raise HTTPException(
            status_code=500,
            detail=f"Không thể lấy danh sách giọng đọc. {error_msg}",
        )
    
    return {
        "voices": voices,
        "count": len(voices),
    }
