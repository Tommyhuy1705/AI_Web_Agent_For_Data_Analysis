# Omni-Revenue Agent

**AI Web Agent for Enterprise Data Analysis** - An intelligent revenue analytics platform that combines Generative UI, Agentic Workflow, and a Zero Data Lake Architecture.

## Overview

Omni-Revenue Agent allows users to **chat in natural language** to query revenue data, automatically generate visual dashboards, receive anomaly alerts, and run predictive analytics.

### System Architecture (Technology Snapshot 2026)

| Layer | Technologies | Description |
| ------- | --------- | ----- |
| **Frontend** | Next.js 14 (App Router), React 18, TypeScript 5, Tailwind CSS 3, Zustand, Zod, ECharts + Recharts | Generative UI, SSE streaming, dynamic dashboard and static dashboard pages |
| **Backend** | FastAPI, Uvicorn, Pydantic v2, HTTPX, APScheduler | API gateway, chat streaming orchestration, scheduled jobs, integrations |
| **Database** | Supabase PostgreSQL, PostgREST/RPC, JSONB | Zero Data Lake model (raw JSONB + analytics mart) |
| **AI Orchestration** | Dify, OpenAI SDK (AsyncOpenAI), DashScope (Qwen 3.5), Zilliz | Text-to-SQL, insight generation, semantic context enrichment |
| **Data Pipeline** | dbt Core + dbt-postgres, Python ETL scripts | In-database transformation from `raw_staging` to `analytics_mart` |
| **Market Intelligence** | TinyFish (AgentQL) | Competitor crawling and alert enrichment |
| **ML** | Scikit-learn, Pandas, NumPy | Time-series forecasting and revenue analytics |
| **DevOps** | Docker (multi-stage), Docker Compose, GitHub Actions, AWS ECR + EC2 | Automated CI/CD build, push, and deploy |

## Core Technologies in Use

- **Runtime and Frameworks:** Python 3.11, Node.js 20 (Docker), FastAPI, Next.js 14, React 18.
- **Frontend Engineering:** TypeScript 5, Tailwind CSS, Zustand state management, Zod validation, React Markdown + remark-gfm.
- **Visualization:** ECharts (`echarts-for-react`) for advanced charts and Recharts for flexible chart components.
- **Streaming and Real-time:** End-to-end SSE flow (FastAPI `StreamingResponse` -> Next.js API route -> browser EventSource).
- **LLM Layer (multi-provider):** DashScope/Qwen (`qwen3.5-122b-a10b`) as primary provider, OpenAI (`gpt-4.1-mini`) as fallback via OpenAI-compatible SDK.
- **Data Access Pattern:** Read-only SQL guardrail with a 3-layer execution strategy: asyncpg (direct), Supabase RPC (`exec_sql`), and PostgREST parser fallback.
- **Data Engineering:** Dedicated dbt project in `data_pipeline/dbt_transform`, materializing analytics tables in `analytics_mart`.
- **Automation and Jobs:** APScheduler for smart alarm, dashboard cache refresh, dbt run/test, monthly strategy report, and periodic TinyFish crawling.
- **Quality and CI:** pytest + pytest-asyncio + httpx (ASGITransport), Ruff linting (backend), TypeScript + ESLint (frontend) via GitHub Actions.
- **Deployment:** Multi-stage Dockerfiles for backend/frontend, dev and prod Compose files, ECR image deployment to EC2 via SSH action.

## Detailed Architecture Report

### 1. System Objectives

The system is designed to transform natural-language business questions into controlled analytics actions with the following goals:

- Reduce time-to-insight from business question to chart and recommendation.
- Standardize revenue data through a mart model for dashboarding, alerting, and forecasting.
- Enforce safe read-only query behavior in AI-generated SQL workflows.
- Automate data operations and reporting through scheduled processes.

### 2. Architecture Principles

- **API-first:** Frontend communicates with backend strictly through REST and SSE.
- **Read-only analytics guardrail:** Text-to-SQL paths allow `SELECT` queries only.
- **Graceful fallback:** If external integrations fail (Dify/Zilliz), fallback paths keep core workflows available.
- **In-database transformation:** dbt is used to keep transformation logic close to data.
- **Operational automation:** Scheduled jobs handle alarms, cache refresh, dbt execution, and monthly reporting.

### 3. Layered Logical Architecture

1. **Presentation Layer (Next.js Frontend):**
Renders chat workspace, static dashboard, chart canvas, and real-time stream status.

2. **Application Layer (FastAPI):**
Handles intent routing (query/dashboard/predict), calls LLM and external services, executes safe SQL, and emits SSE events.

3. **Data Access Layer:**
`db_executor` implements a 3-tier strategy: asyncpg direct -> Supabase RPC -> PostgREST parser fallback.

4. **Data Platform Layer:**
Supabase PostgreSQL stores raw data, mart data, system metrics, chat history, and dashboard cache.

5. **AI and Intelligence Layer:**
Multi-provider LLM client (DashScope/OpenAI), Dify workflow integration, TinyFish market crawl, and Zilliz semantic context.

### 4. Critical End-to-End Flows

#### 4.1 Streaming Chat Query and Chart

1. User submits a question from the frontend.
2. Frontend calls the Next.js API route, which forwards to backend `/api/chat/stream`.
3. Backend classifies intent:
- Predict request -> forecast branch.
- Dashboard request -> multi-panel dashboard branch.
- General query -> Dify branch (if configured), with direct-LLM fallback.
4. SQL is generated with read-only constraints and executed against data.
5. Backend emits SSE lifecycle events: `start -> status -> sql_generated -> data_ready -> chart -> insight -> complete -> done`.
6. Frontend updates UI in real time and persists session context.

#### 4.2 Dashboard Aggregate API

1. Frontend dashboard calls `/api/dashboard/data`.
2. Backend executes multiple dataset queries in parallel (revenue, products, segments, channels, competitors).
3. A unified payload is returned for dashboard grid rendering in a single request.

#### 4.3 Predictive Analytics

1. Historical revenue is retrieved from monthly views.
2. In-memory polynomial regression is trained using scikit-learn.
3. Forecasts are generated for N future periods.
4. Zilliz context retrieval is optionally applied to enrich interpretation.
5. LLM generates strategic insight text.

#### 4.4 Alarm and Notification

1. Alarm job runs daily at 08:00 ICT.
2. Overnight revenue windows are compared against baseline data.
3. If threshold is breached, the system emits SSE alarms, triggers Dify webhook, sends SendGrid email, and enriches context with competitor signals when available.

### 5. Key Backend Components

- **Routing:** `chat_router`, `predict_router`, `dashboard_router`, `sql_proxy`, `market_intel_router`, `chat_history_router`.
- **Core services:** `db_executor`, `manus_visualizer`, `alarm_monitor`, `dashboard_cache_service`, `dbt_runner`, `monthly_report`.
- **AI services:** `llm_client` (provider abstraction), `dify_service`, `zilliz_service`.
- **Stateful modules:** chat session/message history and DB-backed dashboard cache.

### 6. Data Architecture and Pipeline

- **Raw ingestion:** crawler scripts write data into raw tables (JSONB and structured formats).
- **Transformation:** dbt models standardize data into `analytics_mart` (facts, dimensions, analytical views).
- **Serving:** application APIs query views/tables directly for chat and dashboard workloads.
- **Caching:** dashboard snapshots are stored by time slot to reduce peak-time query pressure.

### 7. Scheduler Matrix (APScheduler)

| Job | Schedule | Purpose |
| --- | --- | --- |
| Smart Alarm Morning | 08:00 Asia/Ho_Chi_Minh | Detect overnight revenue anomalies |
| Dashboard Cache Refresh | 07:00, 10:00, 13:00, 16:00 Asia/Ho_Chi_Minh | Pre-build dashboard datasets |
| dbt Run/Test | Currently every 2 minutes (test mode) | Transform and validate data models automatically |
| Monthly Strategy Report | 01:00 UTC on day 1 monthly | Generate strategic report and send email |
| TinyFish Crawl | Every 6 hours (when key is configured) | Collect market intelligence data |

### 8. Security and Data Controls

- Blocks SQL statements that can modify or delete schema/data.
- Recommends read-only DB credentials for AI query pathways.
- Separates secrets by environment (local/dev/prod) via env files.
- Uses fallback behavior when external AI providers are unavailable.

### 9. Deployment and Operations

- Multi-stage Docker images reduce runtime footprint and improve security (non-root runtime).
- `docker-compose.yml` is used for local/dev, `docker-compose.prod.yml` for EC2 deployment.
- GitHub Actions CI runs backend lint/tests and frontend typecheck/lint.
- GitHub Actions CD builds/pushes images to ECR and deploys to EC2 over SSH.

### 10. Documentation Readiness

The README is now suitable as a foundation for full project documentation:

- System context and architecture decision records.
- API and SSE event contracts.
- Data contracts (schema/view/cache).
- Operations runbook (scheduler, deployment, fallback).
- Security checklist and incident response guidance.

## Project Structure

```bash
omni-revenue-agent/
├── frontend/                    # Next.js app
│   ├── app/
│   │   ├── api/chat/route.ts    # SSE streaming proxy
│   │   ├── page.tsx             # Two-column UI (Chat & Canvas)
│   │   ├── layout.tsx           # Root layout
│   │   └── globals.css          # Tailwind + custom CSS
│   ├── components/
│   │   ├── agent/
│   │   │   └── ChatInterface.tsx    # Chat UI
│   │   └── visualizations/
│   │       └── DynamicChart.tsx      # Render JSON into chart
│   ├── store/
│   │   └── useAgentStore.ts     # Zustand state management
│   └── hooks/
│       └── useAgentStream.ts    # SSE connection handler
│
├── backend/                     # FastAPI app
│   ├── main.py                  # App init, CORS, APScheduler
│   ├── api/routes/
│   │   ├── chat_router.py       # Chat endpoint + Dify integration
│   │   ├── sql_proxy.py         # Safe SQL execution (SELECT only)
│   │   ├── predict_router.py    # Predictive analytics endpoint
│   │   └── market_intel_router.py  # TinyFish market intelligence API
│   ├── services/
│   │   ├── db_executor.py       # Supabase access (asyncpg/RPC/PostgREST)
│   │   ├── manus_visualizer.py  # Chart config generation
│   │   ├── alarm_monitor.py     # Alarm logic (+ competitor enrichment)
│   │   ├── tinyfish_service.py  # TinyFish market intelligence service
│   │   ├── dify_service.py      # Dify API integration
│   │   └── zilliz_service.py    # Vector DB semantic layer
│   ├── ml_models/
│   │   └── time_series.py       # Revenue prediction (Scikit-learn)
│   └── hooks/
│       └── voice_interface.py   # Voice hooks (Phase 2)
│
├── data_pipeline/               # Data engineering
│   ├── crawler_scripts/
│   │   ├── mock_data_loader.py  # Mock data -> raw_staging
│   │   └── tinyfish_market_crawler.py  # TinyFish -> market intel
│   └── dbt_transform/
│       ├── dbt_project.yml
│       ├── profiles.yml
│       └── models/              # SQL transform JSONB -> analytics_mart
│           ├── stg_competitor_prices.sql  # Competitor prices from TinyFish
│
├── database/
│   └── supabase_schema.sql      # Zero Data Lake DDL
│
├── CHECKLIST.md                 # Progress tracking
└── .gitignore
```

## 4 Core Tasks

### Task 1: On-Demand Query and Dashboard

User asks a question -> Dify agent generates SQL -> SQL Proxy executes on Supabase -> Visualizer builds JSON chart config -> DynamicChart renders interactive chart.

### Task 2: Automated Data Pipeline

Python scripts crawl data -> insert into JSONB `raw_staging` -> dbt transforms into `analytics_mart` (fact_sales, dim_products, dim_customers).

### Task 3: Proactive Alarm

APScheduler runs at 08:00 (Asia/Ho_Chi_Minh) -> compares overnight revenue window against baseline -> if threshold is exceeded: Dify webhook + SendGrid email + SSE notification.

### Task 4: Predictive Analytics

Query time series -> train in-memory polynomial regression -> optionally enrich with Zilliz context -> LLM (DashScope/OpenAI) generates strategic insight report.

## Setup and Run

### Requirements

- Python 3.11+
- Node.js 20+ (recommended to match production Docker image)
- Supabase account
- Dify account (optional)
- OpenAI or DashScope API key (at least one)
- Zilliz Cloud account (optional)
- TinyFish API key (optional, for market intelligence)

### 1. Database Setup

```bash
# Run schema SQL in Supabase SQL Editor
cat database/supabase_schema.sql
```

### 2. Backend

```bash
cd backend
cp .env.example .env
# Fill Supabase, Dify, OpenAI/DashScope, and Zilliz values in .env

pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### 3. Data Pipeline

```bash
# Load mock data
cd data_pipeline/crawler_scripts
python mock_data_loader.py

# Run dbt transform
cd ../dbt_transform
dbt run
```

### 4. Frontend

```bash
cd frontend
cp .env.example .env.local
# Set NEXT_PUBLIC_BACKEND_URL

pnpm install
pnpm dev
```

Access: `http://localhost:3000`

## API Endpoints

| Method | Endpoint | Description |
| -------- | ---------- | ----- |
| GET | `/` | Service info |
| GET | `/health` | Health check |
| POST | `/api/chat/stream` | Chat SSE streaming |
| POST | `/api/chat/query` | Chat non-streaming (testing/debug) |
| POST | `/api/chat/sessions` | Create chat session |
| GET | `/api/chat/sessions` | List sessions by user |
| GET | `/api/chat/sessions/{session_id}` | Session details |
| DELETE | `/api/chat/sessions/{session_id}` | Soft-delete session |
| GET | `/api/chat/sessions/{session_id}/messages` | Session message history |
| GET | `/api/chat/sessions/{session_id}/context` | LLM-formatted context |
| POST | `/api/chat/sessions/{session_id}/messages` | Save message manually/test |
| GET | `/api/dashboard/data` | Full dashboard dataset |
| POST | `/api/sql/execute` | Execute SQL (SELECT only) |
| GET | `/api/sql/health` | SQL proxy health |
| GET | `/api/sql/schemas` | List schemas |
| GET | `/api/sql/tables` | List tables |
| GET | `/api/sql/tables/{schema_name}` | Tables by schema |
| GET | `/api/sql/columns/{table_name}` | List columns |
| POST | `/api/predict/revenue` | Revenue prediction |
| GET | `/api/predict/health` | Prediction service health |
| GET | `/api/alarm/stream` | Alarm SSE stream |
| GET | `/api/market-intel/status` | TinyFish config status |
| POST | `/api/market-intel/crawl` | Trigger market crawl |
| GET | `/api/market-intel/summary` | Market intel summary |
| GET | `/api/market-intel/competitors` | Competitor prices data |
| GET | `/api/market-intel/competitor-context` | Competitor context for alarm/insight |
| GET | `/docs` | Swagger UI |

## Environment Variables

### Backend (.env)

| Variable | Description |
| ---------- | ----- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (server-side only) |
| `SUPABASE_DATABASE_URL` | PostgreSQL connection string |
| `DIFY_API_URL` | Dify API base URL |
| `DIFY_API_KEY` | Dify API key |
| `OPENAI_API_KEY` | OpenAI API key (fallback LLM provider) |
| `DASHSCOPE_API_KEY` | DashScope API key (Qwen primary provider) |
| `DASHSCOPE_MODEL` | Qwen model name (default: `qwen3.5-122b-a10b`) |
| `ZILLIZ_CLOUD_URI` | Zilliz Cloud endpoint |
| `ZILLIZ_API_KEY` | Zilliz API key |
| `SENDGRID_API_KEY` | SendGrid email API key |
| `TINYFISH_API_KEY` | TinyFish (AgentQL) API key for market intelligence |
| `FRONTEND_URL` | Frontend URL for CORS |

Note: `/api/sql/execute` may use asyncpg direct mode, so `SUPABASE_DATABASE_URL` (or `SUPABASE_DB_HOST/USER/PASSWORD/NAME`) is still required for direct read-only SQL execution.

### Frontend (.env.local)

| Variable | Description |
| ---------- | ----- |
| `NEXT_PUBLIC_BACKEND_URL` | Backend API URL |

## Conventional Commits

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```bash
feat(backend): implement SQL proxy endpoint
feat(frontend): add DynamicChart component
fix(backend): resolve SSE connection timeout
docs: update README with API documentation
```

## Roadmap

- [x] Phase 1: Database and Pipeline
- [x] Phase 2: Backend Core (FastAPI)
- [x] Phase 3: Frontend Chat and Canvas (Next.js)
- [x] Phase 4: AI Integration (Dify, Zilliz, ML)
- [x] Phase 5: Market Intelligence (TinyFish/AgentQL)
- [ ] Future: Voice-to-Text / Text-to-Speech integration
- [ ] Future: Multi-tenant support
- [ ] Future: Advanced ML models (Prophet, LSTM)

## License

Private - All rights reserved.
