FROM python:3.11-slim

WORKDIR /app

# ── 系统依赖 ──────────────────────────────────────────────────────────────────
# poppler-utils: PDF 解析; curl: 健康检查; kubectl: Agent 执行 k8s 命令
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    curl \
    ca-certificates \
    apt-transport-https \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# ── 安装 kubectl ──────────────────────────────────────────────────────────────
ARG KUBECTL_VERSION=v1.29.3
RUN curl -LO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/kubectl \
    && kubectl version --client

# ── 第一步：单独安装 CPU 版 torch（体积小 ~700MB vs GPU版 2GB+）──────────────
# 必须在其他依赖之前装，否则 pip 会自动拉 GPU 版
RUN pip install --no-cache-dir \
    torch==2.3.0 \
    --index-url https://download.pytorch.org/whl/cpu

# ── 第二步：安装其余依赖 ──────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/data /app/models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
