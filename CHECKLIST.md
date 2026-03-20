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
- [ ] Khởi tạo Next.js 14+ App Router project trong `frontend/`
- [ ] Cài đặt Tailwind CSS, Zustand, Recharts/Echarts, Shadcn UI
- [ ] Viết `frontend/app/page.tsx` - UI chia 2 cột (Chat & Canvas)
- [ ] Viết `frontend/app/api/chat/route.ts` - xử lý SSE Streaming
- [ ] Viết `frontend/components/agent/ChatInterface.tsx`
- [ ] Viết `frontend/components/visualizations/DynamicChart.tsx` - render JSON thành Echarts
- [ ] Viết `frontend/store/useAgentStore.ts` - Zustand state management
- [ ] Viết `frontend/hooks/useAgentStream.ts` - xử lý kết nối SSE

## Phase 4: AI & Services Integration
- [ ] Viết `backend/ml_models/time_series.py` - module dự đoán dùng Scikit-learn/Prophet
- [ ] Tích hợp Dify API workflow vào chat_router.py
- [ ] Cấu hình Zilliz Vector DB cho Semantic Layer (RAG)
- [ ] Tích hợp OpenAI GPT cho Text-to-SQL và insight generation
- [ ] Setup interface hooks cho Voice/Audio (Phase 2 - chưa implement core logic)

## System Testing & Build
- [ ] Test Backend FastAPI khởi động và kết nối Supabase thành công
- [ ] Test luồng Streaming SSE từ Backend lên Frontend
- [ ] Mock việc gọi Dify API để test sinh cấu hình JSON biểu đồ
- [ ] Frontend build thành công không lỗi
- [ ] Backend chạy không lỗi
