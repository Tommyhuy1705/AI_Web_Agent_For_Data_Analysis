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

---

## Phase 5: System Upgrade (2026-03-21)

### Task 1: Static Dashboard Page (/dashboard) ✅
- [x] Tạo `backend/api/routes/dashboard_router.py` - API endpoint tổng hợp dashboard data
- [x] Tạo `frontend/app/dashboard/page.tsx` - Trang Dashboard tĩnh với grid biểu đồ
- [x] Dashboard API trả về 6 datasets: revenue_summary, monthly_revenue, top_products, customer_segments, daily_revenue, channel_distribution
- [x] Fix revenue_summary: Compute aggregates in Python (PostgREST không hỗ trợ aggregate functions)
- [x] Fix customer_segments & channel_distribution: Dùng views có sẵn thay vì GROUP BY
- [x] Thêm link Dashboard vào header trang chính
- [x] Cập nhật `next.config.mjs` với rewrites cho backend API proxy
- [x] **Test: 6/6 dashboard datasets PASS** (500 orders, 22.5B VND, 13 months, 10 products, 3 segments, 30 days, 4 channels)

### Task 2: Predict Tool Integration in Chat ✅
- [x] Thêm keyword detection: "dự đoán", "dự báo", "forecast", "predict", "xu hướng tương lai"...
- [x] Tạo `_process_predict()` - Xử lý predict queries trong SSE streaming flow
- [x] Tạo `_handle_predict_query()` - Xử lý predict queries trong non-streaming mode
- [x] Auto-detect số periods và period_type từ user message (regex parsing)
- [x] Chart type: `composed` (bar actual + line predicted)
- [x] Fix PostgREST alias issue: Bỏ column aliases, rename trong Python
- [x] **Test: Predict via chat/query PASS** (tool_used: predict_revenue, 3 predictions)
- [x] **Test: Predict via chat/stream PASS** (SSE events: start→status→sql_generated→data_ready→chart→insight→complete→done)
- [x] **Test: Keyword detection PASS** (6/6 test cases correct routing)

### Task 3: dbt Run Cron Job (Daily at Midnight) ✅
- [x] Tạo `backend/services/dbt_runner.py` - Service chạy dbt commands bất đồng bộ
- [x] Thêm APScheduler CronTrigger: `CronTrigger(hour=0, minute=0)` - Mỗi ngày lúc 00:00 UTC
- [x] Flow: `dbt run` → (nếu thành công) `dbt test`
- [x] Error handling: Timeout, FileNotFoundError (dbt chưa cài), generic exceptions
- [x] **Test: Health check shows 2 jobs PASS** (hourly_alarm + daily_dbt)
- [x] **Test: dbt_runner graceful error PASS** (returns "dbt not found" when dbt not installed)

### Task 4: Monthly Strategy Report Cron Job ✅
- [x] Tạo `backend/services/monthly_report.py` - Service sinh báo cáo chiến lược hàng tháng
- [x] Thêm APScheduler CronTrigger: `CronTrigger(day=1, hour=1, minute=0)` - Ngày 1 mỗi tháng lúc 01:00 UTC
- [x] Flow: Collect data → Run predictions → OpenAI sinh báo cáo → Lưu DB (monthly_insights) → Email
- [x] Báo cáo gồm 5 phần: Tổng quan tháng, Phân tích sản phẩm, Phân tích khách hàng, Dự báo & xu hướng, Đề xuất chiến lược
- [x] Tích hợp SendGrid email gửi báo cáo tự động
- [x] **Test: Health check shows 3 jobs PASS** (hourly_alarm + daily_dbt + monthly_report)

### Task 5: Enhanced SendGrid Email in Alarm Monitor ✅
- [x] Thêm retry logic: Tối đa 3 lần retry với exponential delay (2s, 4s, 6s)
- [x] Thêm AI-generated insight: Phân tích nguyên nhân giảm doanh thu bằng OpenAI
- [x] Nâng cấp HTML email template: KPI cards, severity colors, detail table
- [x] Thêm CTA button: Link tới /dashboard để xem chi tiết
- [x] Thêm FRONTEND_URL config cho email links
- [x] **Test: Alarm SSE stream PASS** (keep-alive ping working)
- [x] **Test: Backend healthy with 3 scheduler jobs PASS**

### Commits Pushed (Phase 5)
| Commit | Message |
|--------|---------|
| `0a7ab1e` | feat: add Dashboard page with grid charts and dashboard API endpoint |
| `b200372` | feat: integrate predict tool into chat flow with auto-detection |
| `c7e4067` | feat: add dbt run cron job (daily at midnight) via APScheduler |
| `7a35220` | feat: add monthly strategy report cron job (1st of month) |
| `7fb238c` | feat: upgrade alarm_monitor with enhanced SendGrid email, retry logic, AI insight |

---

## Phase 6: TinyFish Integration & System Testing with New Data (2026-03-21)

### Task 1: Data Import & Reset ✅
- [x] Xóa toàn bộ dữ liệu cũ trong `fact_sales`, `dim_products`, `dim_customers` (bypass FK constraints)
- [x] Import lại `dim_customers.csv` (1,000 records)
- [x] Import lại `dim_products.csv` (1,681 records)
- [x] Import lại `fact_sales.csv` (1,000 records)
- [x] Pull commit mới nhất từ GitHub (`8e87f91` — TinyFish integration)
- [x] Load mock data vào `raw_staging.raw_sales` (500 records)

### Task 2: Dashboard Refresh Test ✅
- [x] Thêm 50 bản ghi `fact_sales` giả (sale_id 1001–1050) với `created_at = NOW()`
- [x] Xác nhận tổng đơn hàng tăng lên 1,053 records
- [x] dbt scheduler chạy tự động sau 2 phút (TEST MODE)
- [x] Dashboard API phản ánh đúng doanh thu ~2.4 tỷ VND sau khi dbt transform
- [x] **Test PASS: Dashboard refresh hoạt động đúng với data mới**

### Task 3: Alarm System Test ✅
- [x] Set `hourly_snapshot.value = 7,197,793,530 VND` (3x doanh thu thực tế)
- [x] Chạy `check_hourly_revenue_alarm()` — phát hiện thay đổi **-66.67%**
- [x] Alarm kích hoạt thành công (`ALARM TRIGGERED! Revenue dropped 66.67%`)
- [x] Email cảnh báo gửi thành công qua SendGrid (HTTP 202 Accepted)
- [x] Người nhận: nqkhanh2925@gmail.com, giahuytranviet.work@gmail.com, thaiitruong220805@gmail.com
- [x] Snapshot được upsert với giá trị mới (2,399,264,510 VND)
- [x] **Test PASS: Alarm system gửi email thành công**

### Task 4: TinyFish Crawler Test ✅
- [x] Cấu hình `TINYFISH_API_KEY=sk-tinyfish-jn6qp8boM-...` vào `backend/.env`
- [x] Xác định đúng endpoint SSE: `https://agent.tinyfish.ai/v1/automation/run-sse`
- [x] Crawl Tiki.vn keyword "máy lọc nước" — thu thập 5 sản phẩm competitor
- [x] Lưu raw data vào `raw_market_intel` (1 record, crawl_type=competitor_price)
- [x] Lưu chi tiết vào `competitor_prices` (5 records với price, rating, seller)
- [x] Backend restart nhận diện `tinyfish_configured: true`
- [x] TinyFish scheduler đăng ký thành công (mỗi 6 giờ)
- [x] **Test PASS: TinyFish crawl Tiki.vn thành công, dữ liệu lưu vào Supabase**

### Task 5: Bug Fixes ✅
- [x] Fix: `upsert_via_rest()` lỗi 409 conflict với `hourly_snapshot` — dùng PATCH thay POST
- [x] Fix: `TINYFISH_API_KEY` không được load bởi backend — thêm key vào `backend/.env`
- [x] Fix: TinyFish sync endpoint `/run` bị timeout/disconnect — chuyển sang SSE endpoint `/run-sse`

### Dữ liệu Crawl từ TinyFish (Tiki.vn — Máy lọc nước)
| Sản phẩm | Giá (VND) | Rating |
|---|---|---|
| Combo 8 lõi lọc nước Karofi KSI80 | 990,000 | ★5 |
| Máy lọc nước UF Lõi Lọc PVDF 3000L/h | 2,350,000 | ★0 |
| Máy Lọc Nước AQUAPHOR CRYSTAL ECO NANO | 8,900,000 | ★5 |
| Máy lọc nước để bàn RO Philips ADD6910 | 12,960,000 | ★5 |
| Máy Lọc Nước AQUAPHOR MORION DWM-101S RO | 16,900,000 | ★5 |

### Commits (Phase 6)
| Commit | Message |
|--------|----------|
| `43087a6` | `docs: add CHECKLIST.md phase 6 - TinyFish integration and system testing` |
| `e7c2a43` | `test(data): reimport CSV data (dim_customers 1000, dim_products 1681, fact_sales 1000) and load 500 mock staging records` |
| `298562f` | `test(dashboard): add 50 fake sales records script for dashboard refresh test after 2-min dbt scheduler` |
| `05b5995` | `test(alarm): validate alarm trigger at -66.67% revenue drop, SendGrid email HTTP 202 confirmed` |
| `ba29977` | `feat(tinyfish): configure TINYFISH_API_KEY and test SSE crawler on Tiki.vn - 5 competitor products crawled` |
| `5826ea1` | `fix(upsert): document upsert_via_rest 409 conflict bug - use PATCH for hourly_snapshot update to avoid unique constraint violation` |
