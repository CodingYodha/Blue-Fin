# ============================================================================
# Intelli-Credit — Single-container HuggingFace Spaces deployment
# All four services (frontend, backend, go-service, ai-service) run inside
# one container, orchestrated by supervisord, behind an nginx reverse proxy
# on port 7860 (the only port HF Spaces exposes).
# ============================================================================

# ---------- Stage 1: Build Go binary ----------
FROM golang:1.24-bookworm AS go-builder
WORKDIR /build
COPY go-service/ .
RUN go build -o /go-service .

# ---------- Stage 2: Build React frontend ----------
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
# The backend is reverse-proxied on the same domain, so API calls go to /api/*
ENV VITE_API_URL=""
RUN npm run build

# ---------- Stage 3: Final runtime image ----------
FROM python:3.11-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system deps: Node.js 20, nginx, supervisor, and libs for EasyOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    nginx \
    supervisor \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Go service binary ────────────────────────────────────────────────────
COPY --from=go-builder /go-service /app/go-service/go-service

# ── Frontend static build ────────────────────────────────────────────────
COPY --from=frontend-builder /build/dist /app/frontend/dist

# ── Node.js backend ──────────────────────────────────────────────────────
WORKDIR /app/backend
COPY backend/package.json backend/package-lock.json* ./
RUN npm install --production
COPY backend/ .

# ── Python AI service ────────────────────────────────────────────────────
WORKDIR /app/ai-service
COPY ai-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ai-service/ .

# ── ML model artifacts (LightGBM .pkl files) ────────────────────────────
# These are bundled in ml_core/models/ — no extra step needed.

# ── Shared tmp directory ─────────────────────────────────────────────────
RUN mkdir -p /tmp/intelli-credit

# ── Config files ─────────────────────────────────────────────────────────
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

WORKDIR /app
EXPOSE 7860

CMD ["/app/start.sh"]
