# OMNI-REVENUE AGENT - PROJECT CHECKLIST

## Phase 1: Database & Pipeline Setup
- [x] Tạo file `database/supabase_schema.sql` với 3 schema: raw_staging, analytics_mart, system_metrics
- [x] Tạo bảng `raw_staging.raw_sales` (JSONB)
- [x] Tạo bảng `analytics_mart.fact_sales`, `analytics_mart.dim_products`, `analytics_mart.dim_customers`
- [x] Tạo bảng `system_metrics.hourly_snapshot`
- [x] Tạo script `data_pipeline/crawler_scripts/mock_data_loader.py` để đổ mock data vào raw_staging
- [x] Tạo dbt project `data_pipeline/dbt_transform/` với các model SQL transform JSONB sang analytics_mart

## Phase 2: Backend Core (FastAPI)
- [x] Khởi tạo FastAPI app trong `backend/main.py` với SSE config và APScheduler
- [x] Viết `backend/services/db_executor.py` - kết nối Supabase qua asyncpg
- [x] Viết `backend/api/routes/sql_proxy.py` - endpoint chạy SQL an toàn (chỉ SELECT)
- [x] Viết `backend/api/routes/chat_router.py` - nhận text, gọi Dify API, stream SSE
- [x] Viết `backend/services/alarm_monitor.py` - logic so sánh snapshot 1h
- [x] Viết `backend/services/manus_visualizer.py` - sinh cấu hình JSON biểu đồ
- [x] Cài đặt APScheduler cron job cho Proactive Alarm (mỗi 60 phút)
- [x] Tạo file `backend/requirements.txt`

## Phase 3: Frontend Chat & Canvas (Next.js)
- [x] Khởi tạo Next.js 14+ App Router project trong `frontend/`
- [x] Cài đặt Tailwind CSS, Zustand, Recharts/Echarts, Shadcn UI
- [x] Viết `frontend/app/page.tsx` - UI chia 2 cột (Chat & Canvas)
- [x] Viết `frontend/app/api/chat/route.ts` - xử lý SSE Streaming
- [x] Viết `frontend/components/agent/ChatInterface.tsx`
- [x] Viết `frontend/components/visualizations/DynamicChart.tsx` - render JSON thành Echarts
- [x] Viết `frontend/store/useAgentStore.ts` - Zustand state management
- [x] Viết `frontend/hooks/useAgentStream.ts` - xử lý kết nối SSE

## Phase 4: AI & Services Integration
- [x] Viết `backend/ml_models/time_series.py` - module dự đoán dùng Scikit-learn/Prophet
- [x] Tích hợp Dify API workflow vào chat_router.py
- [x] Cấu hình Zilliz Vector DB cho Semantic Layer (RAG)
- [x] Tích hợp OpenAI GPT cho Text-to-SQL và insight generation
- [x] Setup interface hooks cho Voice/Audio (Phase 2 - chưa implement core logic)

## System Testing & Build
- [x] Test Backend FastAPI khởi động và kết nối Supabase thành công
- [x] Test luồng Streaming SSE từ Backend lên Frontend
- [x] Mock việc gọi Dify API để test sinh cấu hình JSON biểu đồ
- [x] Frontend build thành công không lỗi
- [x] Backend chạy không lỗi

## Comprehensive System Test (2026-03-21)

### Backend API Tests (15/15 PASS)
- [x] GET / - Service info endpoint
- [x] GET /health - Database healthy (REST API mode), Scheduler running
- [x] GET /docs - Swagger UI accessible
- [x] POST /api/sql/execute - SQL queries (fact_sales, all views)
- [x] SQL Injection prevention - DROP/DELETE/UPDATE blocked
- [x] POST /api/predict/revenue - Revenue predictions (3 months)
- [x] POST /api/predict/revenue (with insight) - Vietnamese AI insight generation
- [x] GET /api/predict/health - Predict service healthy
- [x] POST /api/chat/stream - SSE streaming (start->status->sql->data->chart->insight->done)
- [x] POST /api/chat/query - Non-streaming chat query
- [x] GET /api/alarm/stream - SSE alarm stream connection
- [x] v_monthly_revenue view - 13 months data
- [x] v_product_performance view - Products ranked by revenue
- [x] v_customer_segment_revenue view - Segments by region
- [x] v_daily_revenue view - Daily revenue data

### Frontend UI Tests (10/10 PASS)
- [x] Page load - 2-column layout (Chat + Canvas)
- [x] Header - Branding, alarm bell, version indicator
- [x] Quick suggestion buttons - Fill input on click
- [x] Chat send - Message sent with typing indicator
- [x] SSE streaming - Real-time response with status updates
- [x] Chart rendering - Bar/Line charts render correctly (Recharts)
- [x] Chart history - Bottom tabs show previous charts, clickable
- [x] Multiple queries - Consecutive queries all work
- [x] Clear chat - Resets to welcome screen (+ chart history cleared)
- [x] Connection status - Green dot shows connected

### Bug Fixes Applied
- [x] Fixed: clearMessages() now also resets chartHistory[] (was persisting after clear)
