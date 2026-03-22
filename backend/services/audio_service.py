"""
Audio Service — ElevenLabs Text-to-Speech
Chuyển đổi văn bản insight/báo cáo thành file âm thanh MP3.

Endpoint: POST /api/audio/briefing
Input: {"text": "Nội dung cần đọc..."}
Output: Stream MP3 audio
"""

import logging
import os
from typing import AsyncGenerator, Optional, Tuple

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
# Default voice: Rachel (multilingual) — có thể thay bằng voice ID tiếng Việt
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

# Try to import elevenlabs
try:
    from elevenlabs import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"elevenlabs not available: {e}")
    ELEVENLABS_AVAILABLE = False


class AudioServiceError(Exception):
    """Custom exception for audio service errors."""
    pass


def is_configured() -> bool:
    """Check if ElevenLabs API key is configured."""
    return bool(ELEVENLABS_API_KEY) and ELEVENLABS_AVAILABLE


def _validate_api_key() -> Tuple[bool, str]:
    """
    Validate ElevenLabs API key format and configuration.
    
    Returns:
        (is_valid: bool, error_message: str)
    """
    if not ELEVENLABS_AVAILABLE:
        return False, "elevenlabs package not properly installed. Windows long path issue. Try enabling long paths or using Docker."
    
    if not ELEVENLABS_API_KEY:
        return False, "ELEVENLABS_API_KEY is not set in environment variables"
    
    if len(ELEVENLABS_API_KEY.strip()) < 10:
        return False, f"ELEVENLABS_API_KEY appears to be invalid (too short: {len(ELEVENLABS_API_KEY)} chars)"
    
    return True, ""


async def text_to_speech_bytes(
    text: str,
    voice_id: Optional[str] = None,
    model_id: Optional[str] = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    use_speaker_boost: bool = True,
) -> Tuple[Optional[bytes], Optional[str]]:
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
        Tuple[MP3 bytes hoặc None, error message nếu thất bại]
    """
    # Validate configuration
    is_valid, error_msg = _validate_api_key()
    if not is_valid:
        logger.warning(f"ElevenLabs configuration error: {error_msg}")
        return None, error_msg

    _voice_id = voice_id or ELEVENLABS_VOICE_ID
    _model_id = model_id or ELEVENLABS_MODEL_ID

    # Giới hạn text để tránh timeout và chi phí cao
    max_chars = 5000
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
        logger.info(f"Text truncated to {max_chars} characters for TTS")

    try:
        # Check if elevenlabs package is installed
        try:
            from elevenlabs import ElevenLabs
        except ImportError:
            error = "elevenlabs package not installed. Run: pip install elevenlabs"
            logger.error(error)
            return None, error

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

        if not audio_bytes:
            error = "ElevenLabs returned empty audio stream"
            logger.error(error)
            return None, error

        logger.info(
            f"ElevenLabs TTS completed: {len(text)} chars → {len(audio_bytes)} bytes"
        )
        return audio_bytes, None

    except Exception as e:
        error_type = type(e).__name__
        error_str = str(e)
        
        # Detect specific error types
        if "authentication" in error_str.lower() or "unauthorized" in error_str.lower() or "401" in error_str:
            error_msg = f"ElevenLabs authentication failed: Invalid or expired API key (Detail: {error_str})"
        elif "rate_limit" in error_str.lower() or "429" in error_str:
            error_msg = f"ElevenLabs rate limit exceeded. Please try again later (Detail: {error_str})"
        elif "invalid_voice_id" in error_str.lower() or "voice_id" in error_str.lower():
            error_msg = f"Invalid voice ID '{_voice_id}' (Detail: {error_str})"
        elif "connection" in error_str.lower() or "timeout" in error_str.lower():
            error_msg = f"Connection error with ElevenLabs API (Detail: {error_str})"
        else:
            error_msg = f"ElevenLabs API error ({error_type}): {error_str}"
        
        logger.error(f"ElevenLabs TTS error: {error_msg}", exc_info=True)
        return None, error_msg


async def text_to_speech_stream(
    text: str,
    voice_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Tuple[Optional[AsyncGenerator[bytes, None]], Optional[str]]:
    """
    Stream MP3 audio từ ElevenLabs (chunk by chunk).
    Dùng cho streaming response trong FastAPI.

    Returns:
        Tuple[generator for MP3 chunks (bytes) or None, error message if failed]
    """
    # Validate configuration
    is_valid, error_msg = _validate_api_key()
    if not is_valid:
        logger.warning(f"ElevenLabs configuration error: {error_msg}")
        return None, error_msg

    _voice_id = voice_id or ELEVENLABS_VOICE_ID
    _model_id = model_id or ELEVENLABS_MODEL_ID

    # Giới hạn text
    max_chars = 5000
    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    async def _stream_generator():
        try:
            try:
                from elevenlabs import ElevenLabs
            except ImportError:
                logger.error("elevenlabs package not installed")
                return

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

        except Exception as e:
            logger.error(f"ElevenLabs stream error: {e}")

    try:
        # Pre-validate before starting stream
        try:
            from elevenlabs import ElevenLabs
        except ImportError:
            error = "elevenlabs package not installed. Run: pip install elevenlabs"
            return None, error
        
        return _stream_generator(), None
    except Exception as e:
        return None, f"Stream initialization error: {str(e)}"


def get_available_voices() -> Tuple[list, Optional[str]]:
    """
    Lấy danh sách giọng đọc có sẵn từ ElevenLabs.
    Dùng để hiển thị trong UI cho người dùng chọn.
    
    Returns:
        Tuple[list of voices, error message if failed]
    """
    # Validate configuration
    is_valid, error_msg = _validate_api_key()
    if not is_valid:
        return [], error_msg

    try:
        try:
            from elevenlabs import ElevenLabs
        except ImportError:
            error = "elevenlabs package not installed"
            logger.error(error)
            return [], error

        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        response = client.voices.get_all()
        voices = [
            {
                "voice_id": v.voice_id,
                "name": v.name,
                "category": getattr(v, "category", ""),
                "labels": getattr(v, "labels", {}),
            }
            for v in response.voices
        ]
        return voices, None
    except Exception as e:
        error_msg = f"Failed to get ElevenLabs voices: {str(e)}"
        logger.error(error_msg)
        return [], error_msg
