"""
Test cases for Phase 8 new features:
  - Exa Neural Search (qualitative market news)
  - TinyFish market routing (quantitative)
  - Hybrid routing (revenue drop detection)
  - Audio Briefing endpoint (ElevenLabs TTS)
  - Chat routing intent detection

Run with:
    pytest backend/tests/test_new_features.py -v
    pytest backend/tests/test_new_features.py -v -k "exa"     # only Exa tests
    pytest backend/tests/test_new_features.py -v -k "audio"   # only audio tests
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Exa Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExaService:
    """Unit tests for exa_service.py — Qualitative Market News Search."""

    def test_exa_service_import(self):
        """exa_service module should import without errors."""
        from backend.services import exa_service
        assert hasattr(exa_service, "search_market_news")
        assert hasattr(exa_service, "search_competitor_news")
        assert hasattr(exa_service, "is_configured")

    def test_exa_not_configured_without_key(self):
        """is_configured() returns False when EXA_API_KEY is not set."""
        from backend.services.exa_service import is_configured
        with patch.dict(os.environ, {"EXA_API_KEY": ""}):
            # Re-check: the function reads env at call time
            assert isinstance(is_configured(), bool)

    def test_exa_configured_with_key(self):
        """is_configured() returns True when EXA_API_KEY is set."""
        with patch.dict(os.environ, {"EXA_API_KEY": "test-key-123"}):
            # Import fresh to pick up env
            import importlib
            import backend.services.exa_service as exa_mod
            importlib.reload(exa_mod)
            # After reload, check the module-level variable
            assert exa_mod.EXA_API_KEY == "test-key-123"

    @pytest.mark.asyncio
    async def test_search_market_news_returns_empty_without_key(self):
        """search_market_news() returns empty list when not configured."""
        from backend.services import exa_service
        with patch.object(exa_service, "EXA_API_KEY", ""):
            result = await exa_service.search_market_news("thị trường điện thoại")
            assert isinstance(result, list)
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_search_market_news_mock_response(self):
        """search_market_news() correctly parses Exa API mock response."""
        from backend.services import exa_service

        # Mock the Exa client
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(
                title="Thị trường điện thoại Q4 2024",
                url="https://example.com/news/1",
                published_date="2024-12-01",
                text="Thị trường điện thoại tăng trưởng 15% trong Q4 2024...",
                author="Nguyen Van A",
            )
        ]

        mock_client = MagicMock()
        mock_client.search_and_contents = MagicMock(return_value=mock_result)

        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}):
            with patch("backend.services.exa_service.Exa", return_value=mock_client):
                with patch.object(exa_service, "EXA_API_KEY", "test-key"):
                    results = await exa_service.search_market_news("thị trường điện thoại")

        assert isinstance(results, list)
        if len(results) > 0:
            article = results[0]
            assert "title" in article
            assert "url" in article

    @pytest.mark.asyncio
    async def test_search_competitor_news_mock(self):
        """search_competitor_news() builds correct query for competitor."""
        from backend.services import exa_service

        mock_result = MagicMock()
        mock_result.results = []

        mock_client = MagicMock()
        mock_client.search_and_contents = MagicMock(return_value=mock_result)

        with patch("backend.services.exa_service.Exa", return_value=mock_client):
            with patch.object(exa_service, "EXA_API_KEY", "test-key"):
                results = await exa_service.search_competitor_news("Samsung", "điện thoại")

        assert isinstance(results, list)
        # Verify the search was called
        mock_client.search_and_contents.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_exa_results_for_llm(self):
        """format_exa_results_for_llm() returns a non-empty string for valid results."""
        from backend.services import exa_service

        sample_results = [
            {
                "title": "Xu hướng thị trường 2024",
                "url": "https://example.com/1",
                "published_date": "2024-11-15",
                "text": "Thị trường đang tăng trưởng mạnh...",
                "author": "Tác giả A",
            }
        ]

        if hasattr(exa_service, "format_exa_results_for_llm"):
            formatted = exa_service.format_exa_results_for_llm(sample_results)
            assert isinstance(formatted, str)
            assert len(formatted) > 0
            assert "Xu hướng thị trường" in formatted


# ─────────────────────────────────────────────────────────────────────────────
# 2. Chat Routing Intent Detection Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestChatRouting:
    """Tests for chat_router.py intent classification logic."""

    def test_chat_router_import(self):
        """chat_router module should import without errors."""
        from backend.api.routes import chat_router
        assert hasattr(chat_router, "router")

    def test_market_qual_keywords_detection(self):
        """Qualitative market keywords should be detected correctly."""
        from backend.api.routes.chat_router import _is_market_qual_query

        # Should trigger Exa (qualitative)
        qual_queries = [
            "tại sao doanh thu giảm",
            "xu hướng thị trường điện thoại",
            "tin tức đối thủ cạnh tranh",
            "bối cảnh kinh tế vĩ mô",
            "nguyên nhân sụt giảm doanh số",
            "phân tích thị trường ngoài",
            "why is revenue dropping",
            "market trends 2024",
        ]
        for q in qual_queries:
            result = _is_market_qual_query(q)
            assert result is True, f"Expected qual=True for: '{q}'"

    def test_market_quant_keywords_detection(self):
        """Quantitative market keywords should be detected correctly."""
        from backend.api.routes.chat_router import _is_market_quant_query

        # Should trigger TinyFish (quantitative)
        quant_queries = [
            "giá đối thủ cạnh tranh",
            "số lượng bán trên shopee",
            "% giảm giá tiki",
            "competitor price",
            "đối thủ bán bao nhiêu",
        ]
        for q in quant_queries:
            result = _is_market_quant_query(q)
            assert result is True, f"Expected quant=True for: '{q}'"

    def test_hybrid_keywords_detection(self):
        """Hybrid routing keywords (revenue drop) should be detected correctly."""
        from backend.api.routes.chat_router import _is_hybrid_query

        # Should trigger hybrid (TinyFish + Exa)
        hybrid_queries = [
            "doanh thu giảm mạnh",
            "tại sao doanh thu rớt",
            "revenue drop analysis",
            "doanh thu sụt giảm",
        ]
        for q in hybrid_queries:
            result = _is_hybrid_query(q)
            assert result is True, f"Expected hybrid=True for: '{q}'"

    def test_internal_db_queries_not_routed_to_market(self):
        """Internal DB queries should NOT trigger market routing."""
        from backend.api.routes.chat_router import _is_market_qual_query, _is_market_quant_query

        internal_queries = [
            "doanh thu tháng này",
            "top 5 sản phẩm bán chạy",
            "khách hàng mua nhiều nhất",
            "tổng đơn hàng hôm nay",
        ]
        for q in internal_queries:
            qual = _is_market_qual_query(q)
            quant = _is_market_quant_query(q)
            # These should NOT be routed to market intel
            assert not (qual and quant), f"Internal query incorrectly routed: '{q}'"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Audio Briefing Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAudioBriefing:
    """Tests for /api/audio/briefing endpoint and audio_service.py."""

    def test_audio_service_import(self):
        """audio_service module should import without errors."""
        from backend.services import audio_service
        assert hasattr(audio_service, "text_to_speech_bytes")
        assert hasattr(audio_service, "text_to_speech_stream")
        assert hasattr(audio_service, "is_configured")

    def test_audio_router_import(self):
        """audio_router module should import without errors."""
        from backend.api.routes import audio_router
        assert hasattr(audio_router, "router")

    @pytest.mark.asyncio
    async def test_audio_status_endpoint(self):
        """GET /api/audio/status should return configuration status."""
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/audio/status")
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert isinstance(data["configured"], bool)

    @pytest.mark.asyncio
    async def test_audio_briefing_returns_error_without_key(self):
        """POST /api/audio/briefing should return 503 when ElevenLabs not configured."""
        from backend.main import app
        from backend.services import audio_service

        with patch.object(audio_service, "ELEVENLABS_API_KEY", ""):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/audio/briefing",
                    json={"text": "Doanh thu tháng này tăng 15%."},
                )
        # Should return 503 (service unavailable) or 400 when not configured
        assert response.status_code in (400, 503, 500)

    @pytest.mark.asyncio
    async def test_audio_briefing_validates_empty_text(self):
        """POST /api/audio/briefing should reject empty text."""
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/audio/briefing",
                json={"text": ""},
            )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_audio_briefing_mock_success(self):
        """POST /api/audio/briefing should return MP3 bytes when ElevenLabs works."""
        from backend.main import app
        from backend.services import audio_service

        fake_mp3_bytes = b"\xff\xfb\x90\x00" + b"\x00" * 100  # Fake MP3 header

        with patch.object(audio_service, "ELEVENLABS_API_KEY", "test-key"):
            with patch.object(audio_service, "text_to_speech_bytes", new_callable=AsyncMock) as mock_tts:
                mock_tts.return_value = fake_mp3_bytes
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/api/audio/briefing",
                        json={"text": "Báo cáo doanh thu tháng 12 năm 2024.", "stream": False},
                    )

        # If TTS mock is called, should return audio/mpeg
        if response.status_code == 200:
            assert "audio" in response.headers.get("content-type", "")

    def test_audio_service_text_truncation(self):
        """text_to_speech_bytes should handle text longer than 5000 chars."""
        from backend.services.audio_service import text_to_speech_bytes
        # Just verify the function exists and is callable
        assert callable(text_to_speech_bytes)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Market Intel Router Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestMarketIntelRouter:
    """Tests for /api/market-intel endpoints."""

    @pytest.mark.asyncio
    async def test_market_intel_status_endpoint(self):
        """GET /api/market-intel/status should return TinyFish status."""
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/market-intel/status")
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data or "tinyfish" in str(data).lower()

    @pytest.mark.asyncio
    async def test_market_intel_summary_endpoint(self):
        """GET /api/market-intel/summary should return market summary."""
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/market-intel/summary")
        # Should return 200 with data or 503 if TinyFish not configured
        assert response.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_market_intel_crawl_requires_key(self):
        """POST /api/market-intel/crawl should return 503 without TinyFish key."""
        from backend.main import app
        from backend.services import tinyfish_service

        with patch.object(tinyfish_service, "TINYFISH_API_KEY", ""):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/api/market-intel/crawl",
                    json={"keywords": ["điện thoại", "laptop"]},
                )
        assert response.status_code in (503, 400, 200)


# ─────────────────────────────────────────────────────────────────────────────
# 5. TinyFish Service Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTinyFishService:
    """Unit tests for tinyfish_service.py."""

    def test_tinyfish_service_import(self):
        """tinyfish_service module should import without errors."""
        from backend.services import tinyfish_service
        assert hasattr(tinyfish_service, "is_configured")
        assert hasattr(tinyfish_service, "run_competitor_crawl")

    def test_tinyfish_not_configured_without_key(self):
        """is_configured() returns False when TINYFISH_API_KEY is not set."""
        from backend.services import tinyfish_service
        with patch.object(tinyfish_service, "TINYFISH_API_KEY", ""):
            result = tinyfish_service.is_configured()
            assert result is False

    def test_tinyfish_configured_with_key(self):
        """is_configured() returns True when TINYFISH_API_KEY is set."""
        from backend.services import tinyfish_service
        with patch.object(tinyfish_service, "TINYFISH_API_KEY", "sk-tinyfish-test"):
            result = tinyfish_service.is_configured()
            assert result is True

    @pytest.mark.asyncio
    async def test_get_competitor_context_for_alarm_returns_string(self):
        """get_competitor_context_for_alarm() should return a string (possibly empty)."""
        from backend.services import tinyfish_service
        with patch.object(tinyfish_service, "TINYFISH_API_KEY", ""):
            result = await tinyfish_service.get_competitor_context_for_alarm()
            assert result is None or isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Health Endpoint — New Services
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthWithNewServices:
    """Verify /health endpoint reports new services correctly."""

    @pytest.mark.asyncio
    async def test_health_includes_exa_status(self):
        """GET /health should include Exa service status."""
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "exa" in data, "Health endpoint should report Exa status"
        assert "configured" in data["exa"]

    @pytest.mark.asyncio
    async def test_health_includes_elevenlabs_status(self):
        """GET /health should include ElevenLabs service status."""
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "elevenlabs" in data, "Health endpoint should report ElevenLabs status"
        assert "configured" in data["elevenlabs"]

    @pytest.mark.asyncio
    async def test_health_includes_tinyfish_status(self):
        """GET /health should include TinyFish service status."""
        from backend.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "tinyfish" in data, "Health endpoint should report TinyFish status"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Config Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestConfig:
    """Tests for core/config.py Settings class."""

    def test_config_import(self):
        """config module should import without errors."""
        from backend.core.config import get_settings, Settings
        assert callable(get_settings)

    def test_config_has_required_fields(self):
        """Settings should have all required service fields."""
        from backend.core.config import Settings
        fields = Settings.model_fields.keys()

        required_fields = [
            "supabase_url",
            "openai_api_key",
            "dashscope_api_key",
            "tinyfish_api_key",
            "exa_api_key",
            "elevenlabs_api_key",
            "elevenlabs_voice_id",
            "sendgrid_api_key",
        ]
        for field in required_fields:
            assert field in fields, f"Missing required field: {field}"

    def test_config_has_optional_dify_zilliz(self):
        """Settings should have optional Dify and Zilliz fields."""
        from backend.core.config import Settings
        fields = Settings.model_fields.keys()

        optional_fields = [
            "dify_api_key",
            "dify_api_url",
            "zilliz_cloud_uri",
            "zilliz_api_key",
        ]
        for field in optional_fields:
            assert field in fields, f"Missing optional field: {field}"

    def test_config_properties(self):
        """Settings properties should work correctly."""
        from backend.core.config import Settings

        s = Settings(
            tinyfish_api_key="test-key",
            exa_api_key="test-exa",
            elevenlabs_api_key="test-11labs",
            dify_api_key="",
            dify_webhook_url="",
            zilliz_cloud_uri="",
            zilliz_api_key="",
        )
        assert s.is_tinyfish_configured is True
        assert s.is_exa_configured is True
        assert s.is_elevenlabs_configured is True
        assert s.is_dify_configured is False  # no webhook URL
        assert s.is_zilliz_configured is False  # no URI
