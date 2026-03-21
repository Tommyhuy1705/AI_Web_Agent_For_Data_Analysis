# ============================================================
# SIA Backend — Dockerfile
# Multi-stage build: builder + production image with Playwright
# ============================================================

# ── Stage 1: Builder ─────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Production ──────────────────────────────────────
# Use full Debian-based image (not slim) to support Playwright/Chromium
FROM python:3.11 AS production

WORKDIR /app

# Install runtime system dependencies + Playwright OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    git \
    # Chromium / Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libx11-6 \
    libxext6 \
    libxss1 \
    fonts-liberation \
    xdg-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Install Playwright and download Chromium browser
RUN pip install playwright && \
    playwright install --with-deps chromium

# Copy application source
COPY . /app/backend
COPY .env.example /app/backend/.env.example

# Set PYTHONPATH so `from backend.xxx import ...` works
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Tell Playwright to use the installed Chromium
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Create non-root user for security
# Note: Playwright browser must be accessible by appuser
RUN useradd -m -u 1001 appuser && \
    cp -r /root/.cache /home/appuser/.cache 2>/dev/null || true && \
    chown -R appuser:appuser /app /home/appuser/.cache 2>/dev/null || true
USER appuser

ENV PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Start FastAPI with uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
