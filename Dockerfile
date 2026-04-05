FROM python:3.11-slim

WORKDIR /app

# ── 系统依赖 ──────────────────────────────────────────────────────────────────
# poppler-utils: PDF 解析  curl: 健康检查
# apt 使用阿里云镜像加速（国内服务器）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── kubectl 直接从宿主机挂载，不在镜像内安装 ────────────────────────────────
# 见 docker-compose.minimal.yml: /usr/bin/kubectl:/usr/local/bin/kubectl:ro

# ── pip 全局镜像 (阿里云) ───────────────────────────────────────────────────
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com \
    && pip config set global.timeout 120

# ── 第一步：安装 CPU 版 torch（必须先装，且用 pytorch.org whl index）────────
# --index-url 指向 pytorch.org CPU whl（确保拿到 CPU 版而不是 GPU 版）
# --extra-index-url 指向阿里云（torch 的依赖包 networkx/sympy 等从这里下载，避免超时）
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://mirrors.aliyun.com/pypi/simple/ \
    torch==2.6.0

# ── 第二步：安装其余依赖（走阿里云镜像）────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/data /app/models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
