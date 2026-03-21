# Omni-Revenue Agent

**AI Web Agent for Enterprise Data Analysis** - Hệ thống phân tích dữ liệu doanh thu thông minh, kết hợp Generative UI, Agentic Workflow, và Zero Data Lake Architecture.

## Tổng quan

Omni-Revenue Agent cho phép người dùng **chat bằng ngôn ngữ tự nhiên** để truy vấn dữ liệu doanh thu, tự động sinh biểu đồ (Dashboard), nhận cảnh báo bất thường (Alarm), và dự đoán xu hướng (Predict).

### Kiến trúc hệ thống

| Layer | Công nghệ | Mô tả |
| ------- | --------- | ----- |
| **Frontend** | Next.js 14+, Tailwind CSS, Zustand, Recharts | Generative UI với SSE streaming |
| **Backend** | FastAPI, asyncpg, APScheduler | API Gateway, SQL Proxy, Cron Jobs |
| **Database** | Supabase (PostgreSQL) | Zero Data Lake Architecture |
| **AI Orchestration** | Dify, Zilliz, OpenAI GPT | Multi-Agent, Semantic Layer, Text-to-SQL |
| **Data Pipeline** | dbt, Python Scripts | In-database Transformation |
| **Market Intel** | TinyFish (AgentQL) | Web Scraping đối thủ cạnh tranh |
| **ML** | Scikit-learn | Time Series Prediction |

## Cấu trúc thư mục

```bash
omni-revenue-agent/
├── frontend/                    # Next.js App
│   ├── app/
│   │   ├── api/chat/route.ts    # SSE Streaming Proxy
│   │   ├── page.tsx             # UI 2 cột (Chat & Canvas)
│   │   ├── layout.tsx           # Root Layout
│   │   └── globals.css          # Tailwind + Custom CSS
│   ├── components/
│   │   ├── agent/
│   │   │   └── ChatInterface.tsx    # Giao diện chat
│   │   └── visualizations/
│   │       └── DynamicChart.tsx      # Render JSON → biểu đồ
│   ├── store/
│   │   └── useAgentStore.ts     # Zustand state management
│   └── hooks/
│       └── useAgentStream.ts    # SSE connection handler
│
├── backend/                     # FastAPI App
│   ├── main.py                  # App init, CORS, APScheduler
│   ├── api/routes/
│   │   ├── chat_router.py       # Chat endpoint + Dify integration
│   │   ├── sql_proxy.py         # Safe SQL execution (SELECT only)
│   │   ├── predict_router.py    # Predictive analytics endpoint
│   │   └── market_intel_router.py  # TinyFish Market Intelligence API
│   ├── services/
│   │   ├── db_executor.py       # Supabase connection (asyncpg)
│   │   ├── manus_visualizer.py  # Chart config generation
│   │   ├── alarm_monitor.py     # Proactive alarm logic (+ competitor enrichment)
│   │   ├── tinyfish_service.py  # TinyFish Market Intelligence service
│   │   ├── dify_service.py      # Dify API integration
│   │   └── zilliz_service.py    # Vector DB semantic layer
│   ├── ml_models/
│   │   └── time_series.py       # Revenue prediction (Scikit-learn)
│   └── hooks/
│       └── voice_interface.py   # Voice hooks (Phase 2)
│
├── data_pipeline/               # Data Engineering
│   ├── crawler_scripts/
│   │   ├── mock_data_loader.py  # Mock data → raw_staging
│   │   └── tinyfish_market_crawler.py  # TinyFish → Market Intel
│   └── dbt_transform/
│       ├── dbt_project.yml
│       ├── profiles.yml
│       └── models/              # SQL transform JSONB → analytics_mart
│           ├── stg_competitor_prices.sql  # Competitor prices from TinyFish
│
├── database/
│   └── supabase_schema.sql      # DDL cho Zero Data Lake
│
├── CHECKLIST.md                 # Tracking tiến độ
└── .gitignore
```

## 4 Core Tasks

### Task 1: On-Demand Query & Dashboard

User gõ câu hỏi → Dify Agent sinh SQL → SQL Proxy chạy trên Supabase → Visualizer sinh JSON config → DynamicChart render biểu đồ tương tác.

### Task 2: Automated Data Pipeline

Python scripts crawl data → INSERT vào JSONB `raw_staging` → dbt transform sang `analytics_mart` (fact_sales, dim_products, dim_customers).

### Task 3: Proactive Alarm

APScheduler chạy mỗi 60 phút → So sánh doanh thu với `hourly_snapshot` → Nếu giảm >15%: webhook Dify + email SendGrid + SSE notification.

### Task 4: Predictive Analytics

Query time series → Train Polynomial Regression in-memory → Kết hợp ngữ cảnh Zilliz → OpenAI sinh báo cáo insight chiến lược.

## Cài đặt & Chạy

### Yêu cầu

- Python 3.11+
- Node.js 18+
- Supabase account
- Dify account (optional)
- Zilliz Cloud account (optional)

### 1. Database Setup

```bash
# Chạy schema SQL trên Supabase SQL Editor
cat database/supabase_schema.sql
```

### 2. Backend

```bash
cd backend
cp .env.example .env
# Điền thông tin Supabase, Dify, OpenAI, Zilliz vào .env

pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### 3. Data Pipeline

```bash
# Đổ mock data
cd data_pipeline/crawler_scripts
python mock_data_loader.py

# Chạy dbt transform
cd ../dbt_transform
dbt run
```

### 4. Frontend

```bash
cd frontend
cp .env.example .env.local
# Điền NEXT_PUBLIC_BACKEND_URL

pnpm install
pnpm dev
```

Truy cập: `http://localhost:3000`

## API Endpoints

| Method | Endpoint | Mô tả |
| -------- | ---------- | ----- |
| GET | `/` | Service info |
| GET | `/health` | Health check |
| POST | `/api/chat/stream` | Chat SSE streaming |
| POST | `/api/sql/execute` | Execute SQL (SELECT only) |
| POST | `/api/predict/revenue` | Revenue prediction |
| GET | `/api/predict/health` | Prediction service health |
| GET | `/api/alarm/stream` | Alarm SSE stream |
| GET | `/api/market-intel/status` | TinyFish config status |
| POST | `/api/market-intel/crawl` | Trigger market crawl |
| GET | `/api/market-intel/summary` | Market intel summary |
| GET | `/api/market-intel/competitors` | Competitor prices data |
| GET | `/docs` | Swagger UI |

## Environment Variables

### Backend (.env)

| Variable | Mô tả |
| ---------- | ----- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (server-side only) |
| `SUPABASE_DATABASE_URL` | PostgreSQL connection string |
| `DIFY_API_URL` | Dify API base URL |
| `DIFY_API_KEY` | Dify API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ZILLIZ_CLOUD_URI` | Zilliz Cloud endpoint |
| `ZILLIZ_API_KEY` | Zilliz API key |
| `SENDGRID_API_KEY` | SendGrid email API key |
| `TINYFISH_API_KEY` | TinyFish (AgentQL) API key for market intelligence |
| `FRONTEND_URL` | Frontend URL for CORS |

Lưu ý: endpoint `/api/sql/execute` đang dùng asyncpg nên vẫn cần `SUPABASE_DATABASE_URL` (hoặc bộ `SUPABASE_DB_HOST/USER/PASSWORD/NAME`) để truy vấn SQL read-only trực tiếp.

### Frontend (.env.local)

| Variable | Mô tả |
| ---------- | ----- |
| `NEXT_PUBLIC_BACKEND_URL` | Backend API URL |

## Conventional Commits

Dự án tuân thủ [Conventional Commits](https://www.conventionalcommits.org/):

```bash
feat(backend): implement SQL proxy endpoint
feat(frontend): add DynamicChart component
fix(backend): resolve SSE connection timeout
docs: update README with API documentation
```

## Roadmap

- [x] Phase 1: Database & Pipeline
- [x] Phase 2: Backend Core (FastAPI)
- [x] Phase 3: Frontend Chat & Canvas (Next.js)
- [x] Phase 4: AI Integration (Dify, Zilliz, ML)
- [x] Phase 5: Market Intelligence (TinyFish/AgentQL)
- [ ] Phase 2 (Future): Voice-to-Text / Text-to-Speech integration
- [ ] Phase 2 (Future): Multi-tenant support
- [ ] Phase 2 (Future): Advanced ML models (Prophet, LSTM)

## License

Private - All rights reserved.
