-- ============================================================
-- Migration 001: Chat History & Dashboard Cache
-- Phase 7: Tối ưu hóa AI Agent
-- Created: 2026-03-21
-- ============================================================

-- ============================================================
-- TABLE: chat_sessions
-- Lưu trữ các phiên hội thoại của user
-- ============================================================
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     VARCHAR(255) NOT NULL DEFAULT 'default_user',
    title       VARCHAR(500) DEFAULT 'New Conversation',
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id
    ON public.chat_sessions (user_id);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at
    ON public.chat_sessions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_is_active
    ON public.chat_sessions (is_active)
    WHERE is_active = TRUE;

-- ============================================================
-- TABLE: chat_messages
-- Lưu trữ từng message trong phiên hội thoại
-- ============================================================
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id
    ON public.chat_messages (session_id);

CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
    ON public.chat_messages (created_at ASC);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
    ON public.chat_messages (session_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_chat_messages_metadata_gin
    ON public.chat_messages USING GIN (metadata);

-- ============================================================
-- TABLE: dashboard_cache
-- Cache kết quả dashboard theo các mốc thời gian
-- ============================================================
CREATE TABLE IF NOT EXISTS public.dashboard_cache (
    cache_key   VARCHAR(100) PRIMARY KEY,
    data        JSONB NOT NULL,
    cached_at   TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    cache_slot  VARCHAR(10) DEFAULT NULL  -- '07:00', '10:00', '13:00', '16:00'
);

CREATE INDEX IF NOT EXISTS idx_dashboard_cache_expires_at
    ON public.dashboard_cache (expires_at);

CREATE INDEX IF NOT EXISTS idx_dashboard_cache_cached_at
    ON public.dashboard_cache (cached_at DESC);

-- ============================================================
-- FUNCTION: update_updated_at_column
-- Tự động cập nhật updated_at khi có thay đổi
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger cho chat_sessions
DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON public.chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON public.chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- COMMENTS
-- ============================================================
COMMENT ON TABLE public.chat_sessions IS 'Phiên hội thoại của user với AI Agent';
COMMENT ON TABLE public.chat_messages IS 'Lịch sử từng message trong phiên hội thoại';
COMMENT ON TABLE public.dashboard_cache IS 'Cache dashboard data theo các mốc 07:00, 10:00, 13:00, 16:00';
COMMENT ON COLUMN public.chat_messages.metadata IS 'Metadata bổ sung: sql, chartConfig, rowCount, agentThoughts...';
COMMENT ON COLUMN public.dashboard_cache.cache_slot IS 'Mốc thời gian cache: 07:00, 10:00, 13:00, 16:00';
