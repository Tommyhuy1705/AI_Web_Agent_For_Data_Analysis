"""
Audio Service — ElevenLabs Text-to-Speech
Chuyển đổi văn bản insight/báo cáo thành file âm thanh MP3.

Endpoint: POST /api/audio/briefing
Input: {"text": "Nội dung cần đọc..."}
Output: Stream MP3 audio
"""

import logging
import os
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
# Default voice: Rachel (multilingual) — có thể thay bằng voice ID tiếng Việt
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")


def is_configured() -> bool:
    """Check if ElevenLabs API key is configured."""
    return bool(ELEVENLABS_API_KEY)


async def text_to_speech_bytes(
    text: str,
    voice_id: Optional[str] = None,
    model_id: Optional[str] = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    use_speaker_boost: bool = True,
) -> Optional[bytes]:
    """
    Gọi ElevenLabs API để chuyển text thành MP3 bytes.

    Args:
        text: Văn bản cần đọc (tối đa ~5000 ký tự)
        voice_id: ID giọng đọc (mặc định: Rachel)
        model_id: Model TTS (mặc định: eleven_multilingual_v2)
        stability: Độ ổn định giọng (0.0-1.0)
        similarity_boost: Độ rõ ràng (0.0-1.0)
        style: Phong cách đọc (0.0-1.0)
        use_speaker_boost: Tăng cường chất lượng giọng

    Returns:
        MP3 bytes hoặc None nếu thất bại
    """
    if not is_configured():
        logger.warning("ElevenLabs API key not configured — ELEVENLABS_API_KEY is missing")
        return None

    _voice_id = voice_id or ELEVENLABS_VOICE_ID
    _model_id = model_id or ELEVENLABS_MODEL_ID

    # Giới hạn text để tránh timeout và chi phí cao
    max_chars = 5000
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
        logger.info(f"Text truncated to {max_chars} characters for TTS")

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

        # Gọi ElevenLabs TTS API
        audio_generator = client.text_to_speech.convert(
            voice_id=_voice_id,
            text=text,
            model_id=_model_id,
            voice_settings={
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": use_speaker_boost,
            },
        )

        # Thu thập tất cả chunks thành bytes
        audio_bytes = b"".join(chunk for chunk in audio_generator)

        logger.info(
            f"ElevenLabs TTS completed: {len(text)} chars → {len(audio_bytes)} bytes"
        )
        return audio_bytes

    except ImportError:
        logger.error("elevenlabs not installed. Run: pip install elevenlabs")
        return None
    except Exception as e:
        logger.error(f"ElevenLabs TTS error: {e}")
        return None


async def text_to_speech_stream(
    text: str,
    voice_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> AsyncGenerator[bytes, None]:
    """
    Stream MP3 audio từ ElevenLabs (chunk by chunk).
    Dùng cho streaming response trong FastAPI.

    Yields:
        MP3 audio chunks (bytes)
    """
    if not is_configured():
        logger.warning("ElevenLabs API key not configured")
        return

    _voice_id = voice_id or ELEVENLABS_VOICE_ID
    _model_id = model_id or ELEVENLABS_MODEL_ID

    # Giới hạn text
    max_chars = 5000
    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

        audio_generator = client.text_to_speech.convert(
            voice_id=_voice_id,
            text=text,
            model_id=_model_id,
            voice_settings={
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        )

        for chunk in audio_generator:
            if chunk:
                yield chunk

    except ImportError:
        logger.error("elevenlabs not installed")
    except Exception as e:
        logger.error(f"ElevenLabs stream error: {e}")


def get_available_voices() -> list:
    """
    Lấy danh sách giọng đọc có sẵn từ ElevenLabs.
    Dùng để hiển thị trong UI cho người dùng chọn.
    """
    if not is_configured():
        return []

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        response = client.voices.get_all()
        return [
            {
                "voice_id": v.voice_id,
                "name": v.name,
                "category": getattr(v, "category", ""),
                "labels": getattr(v, "labels", {}),
            }
            for v in response.voices
        ]
    except Exception as e:
        logger.error(f"Failed to get ElevenLabs voices: {e}")
        return []
