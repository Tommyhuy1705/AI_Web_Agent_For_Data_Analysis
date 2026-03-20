"""
Voice Interface Hooks (Phase 2 - Interface Only)
Setup sẵn interface cho Voice-to-Text và Text-to-Speech.
Sử dụng ElevenLabs API (chưa implement core logic).

Lưu ý: Đây là Phase 2 feature. Chỉ setup interface hooks,
chưa implement core logic.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ElevenLabs Configuration (Phase 2)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")


class VoiceInterface:
    """
    Interface cho Voice features.
    Phase 2: Chỉ setup hooks, chưa implement.
    """

    def __init__(self):
        self.api_key = ELEVENLABS_API_KEY
        self.voice_id = ELEVENLABS_VOICE_ID
        self._initialized = False

    @property
    def is_configured(self) -> bool:
        """Kiểm tra ElevenLabs đã được cấu hình chưa."""
        return bool(self.api_key)

    async def speech_to_text(self, audio_data: bytes) -> Optional[str]:
        """
        [Phase 2] Convert speech audio to text.

        Args:
            audio_data: Raw audio bytes

        Returns:
            Transcribed text hoặc None
        """
        # TODO: Implement in Phase 2
        logger.info("Voice-to-Text: Not implemented yet (Phase 2)")
        raise NotImplementedError("Voice-to-Text will be implemented in Phase 2")

    async def text_to_speech(self, text: str) -> Optional[bytes]:
        """
        [Phase 2] Convert text to speech audio.

        Args:
            text: Text to convert

        Returns:
            Audio bytes hoặc None
        """
        # TODO: Implement in Phase 2
        logger.info("Text-to-Speech: Not implemented yet (Phase 2)")
        raise NotImplementedError("Text-to-Speech will be implemented in Phase 2")

    async def health_check(self) -> Dict[str, Any]:
        """Health check cho voice service."""
        return {
            "status": "not_implemented",
            "phase": 2,
            "configured": self.is_configured,
            "message": "Voice features will be available in Phase 2",
        }


# Singleton instance
voice_interface = VoiceInterface()
