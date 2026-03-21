"""
Diagnostics Router — Backend Health & Service Verification
Endpoint: GET /api/diagnostics/services
Kiểm tra trạng thái tất cả external services (ElevenLabs, Exa, etc.)
"""

import logging
import os
from typing import Dict, Any

from fastapi import APIRouter
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diagnostics", tags=["Diagnostics"])


@router.get("/services")
async def check_services() -> Dict[str, Any]:
    """
    Kiểm tra trạng thái tất cả services và trả về chi tiết lỗi.
    Dùng để debug cấu hình.
    """
    results = {
        "timestamp": str(__import__("datetime").datetime.utcnow()),
        "services": {},
    }

    # 1. ElevenLabs
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "")
    
    results["services"]["elevenlabs"] = {
        "configured": bool(elevenlabs_key),
        "has_key": len(elevenlabs_key) > 0,
        "key_length": len(elevenlabs_key) if elevenlabs_key else 0,
        "key_starts_with": elevenlabs_key[:10] + "..." if elevenlabs_key else "NOT_SET",
        "voice_id_configured": bool(elevenlabs_voice_id),
        "voice_id": elevenlabs_voice_id or "NOT_SET",
    }

    # Test ElevenLabs API connectivity
    if elevenlabs_key:
        try:
            from elevenlabs import ElevenLabs

            client = ElevenLabs(api_key=elevenlabs_key)
            
            # Try to get voices (lightweight test)
            voices = client.voices.get_all()
            results["services"]["elevenlabs"]["api_test"] = {
                "status": "connected",
                "available_voices": len(list(voices)) if voices else 0,
                "error": None,
            }
        except Exception as e:
            results["services"]["elevenlabs"]["api_test"] = {
                "status": "failed",
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
            logger.error(f"ElevenLabs API test failed: {e}", exc_info=True)
    else:
        results["services"]["elevenlabs"]["api_test"] = {
            "status": "skipped",
            "reason": "API key not configured",
        }

    # 2. Exa (Market News Search)
    exa_key = os.getenv("EXA_API_KEY", "")
    results["services"]["exa"] = {
        "configured": bool(exa_key),
        "has_key": len(exa_key) > 0,
        "key_length": len(exa_key) if exa_key else 0,
    }

    if exa_key:
        try:
            from exa_py import Exa
            client = Exa(api_key=exa_key)
            # Test with a simple search
            results["services"]["exa"]["api_test"] = {
                "status": "connected",
                "error": None,
            }
        except Exception as e:
            results["services"]["exa"]["api_test"] = {
                "status": "failed",
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

    # 3. Supabase
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
    
    results["services"]["supabase"] = {
        "configured": bool(supabase_url and supabase_key),
        "url": supabase_url or "NOT_SET",
        "has_key": bool(supabase_key),
        "key_length": len(supabase_key) if supabase_key else 0,
    }

    if supabase_url and supabase_key:
        try:
            from supabase import create_client
            client = create_client(supabase_url, supabase_key)
            # Test connection with a simple query
            response = client.table("raw_staging").select("COUNT", count="exact").execute()
            results["services"]["supabase"]["api_test"] = {
                "status": "connected",
                "row_count": response.count if hasattr(response, 'count') else "unknown",
                "error": None,
            }
        except Exception as e:
            results["services"]["supabase"]["api_test"] = {
                "status": "failed",
                "error_type": type(e).__name__,
                "error_message": str(e),
            }

    # 4. LLM Providers
    dashscope_key = os.getenv("DASHSCOPE_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    
    results["services"]["llm"] = {
        "dashscope_configured": bool(dashscope_key),
        "dashscope_key_length": len(dashscope_key) if dashscope_key else 0,
        "openai_configured": bool(openai_key),
        "openai_key_length": len(openai_key) if openai_key else 0,
        "at_least_one_configured": bool(dashscope_key or openai_key),
    }

    return results


@router.get("/elevenlabs-test")
async def test_elevenlabs():
    """
    Test ElevenLabs API with a simple text-to-speech request.
    Returns detailed error information for debugging.
    """
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")
    
    if not elevenlabs_key:
        return {
            "status": "failed",
            "error": "ELEVENLABS_API_KEY not configured in environment",
            "advice": "Add ELEVENLABS_API_KEY to .env and redeploy",
        }

    try:
        from elevenlabs import ElevenLabs

        client = ElevenLabs(api_key=elevenlabs_key)
        
        # Get default voice
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        
        # Test with short text
        test_text = "Xin chào. Đây là bài kiểm tra ElevenLabs."
        
        logger.info(f"Testing ElevenLabs with voice_id={voice_id}, model_id={model_id}")
        
        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=test_text,
            model_id=model_id,
        )
        
        # Collect first chunk to verify it works
        audio_bytes = b"".join(chunk for chunk in audio_generator)
        
        return {
            "status": "success",
            "message": "ElevenLabs API is working correctly",
            "test_audio_size_bytes": len(audio_bytes),
            "voice_id": voice_id,
            "model_id": model_id,
            "test_text": test_text,
        }

    except ImportError as e:
        return {
            "status": "failed",
            "error_type": "ImportError",
            "error": "elevenlabs package not installed",
            "details": str(e),
            "advice": "Run: pip install elevenlabs",
        }
    except Exception as e:
        return {
            "status": "failed",
            "error_type": type(e).__name__,
            "error": str(e),
            "advice": "Check ELEVENLABS_API_KEY is correct and not expired",
            "full_traceback": __import__("traceback").format_exc(),
        }
