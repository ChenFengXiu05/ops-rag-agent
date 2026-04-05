#!/bin/bash
# =============================================================================
# ops-rag-agent 部署脚本 — Rocky Linux 9.5 / Docker Compose
# 使用方式：chmod +x scripts/deploy.sh && bash scripts/deploy.sh
# =============================================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="${APP_DIR}/docker-compose.minimal.yml"
IMAGE_NAME="ops-rag-agent"

# 颜色输出
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

info "============================================"
info "  ops-rag-agent 部署脚本"
info "  目录: ${APP_DIR}"
info "============================================"

# 1. 检查 .env 文件
if [ ! -f "${APP_DIR}/.env" ]; then
    warn ".env 不存在，从 .env.example 复制..."
    cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
    error "请先编辑 .env 文件（填写 VLLM_BASE_URL 等配置），然后重新运行此脚本"
fi

# 2. 检查 kubeconfig
KUBECONFIG_PATH="${KUBECONFIG_PATH:-$HOME/.kube/config}"
if [ ! -f "${KUBECONFIG_PATH}" ]; then
    warn "kubeconfig 不存在: ${KUBECONFIG_PATH}"
    warn "kubectl 工具将不可用，RAG 问答功能不受影响"
    warn "如需接入 K8s，请先配置 kubeconfig 后重新部署"
    # 创建空 kubeconfig 避免挂载失败
    mkdir -p "$(dirname ${KUBECONFIG_PATH})"
    echo '{}' > "${KUBECONFIG_PATH}"
else
    info "kubeconfig 已找到: ${KUBECONFIG_PATH}"
    kubectl get nodes 2>/dev/null && info "K8s 集群连接正常" || warn "kubectl 连接失败，请检查 kubeconfig"
fi

# 3. 创建 models 目录（BGE 模型缓存）
mkdir -p "${APP_DIR}/models"
info "模型缓存目录: ${APP_DIR}/models"

# 4. 检查 Docker 和 Docker Compose
command -v docker &>/dev/null || error "Docker 未安装"
docker compose version &>/dev/null || docker-compose version &>/dev/null || error "Docker Compose 未安装"
info "Docker 版本: $(docker --version)"

# 5. 构建镜像
info "开始构建镜像（首次约需 5-10 分钟）..."
cd "${APP_DIR}"
docker compose -f "${COMPOSE_FILE}" build --no-cache
info "镜像构建完成"

# 6. 启动服务
info "启动服务..."
docker compose -f "${COMPOSE_FILE}" up -d
info "服务已启动"

# 7. 等待健康检查
info "等待服务就绪（BGE 模型首次加载约需 2-3 分钟）..."
MAX_WAIT=180
ELAPSED=0
until curl -sf http://localhost:8000/health &>/dev/null; do
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        error "服务启动超时，请查看日志: docker compose -f ${COMPOSE_FILE} logs -f app"
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    echo -n "."
done
echo ""
info "服务已就绪！"

# 8. 导入知识库文档
if ls "${APP_DIR}/knowledge_base/"*.md &>/dev/null; then
    info "导入知识库文档..."
    docker compose -f "${COMPOSE_FILE}" exec app \
        python scripts/ingest_docs.py --dir ./knowledge_base --collection ops_knowledge
    info "知识库导入完成"
else
    warn "knowledge_base/ 目录下没有文档，跳过导入"
fi

# 9. 完成
echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "  Chat UI:    http://$(hostname -I | awk '{print $1}'):8000/ui"
echo "  API 文档:   http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "  健康检查:   http://$(hostname -I | awk '{print $1}'):8000/health"
echo ""
echo "  查看日志:   docker compose -f ${COMPOSE_FILE} logs -f app"
echo "  停止服务:   docker compose -f ${COMPOSE_FILE} down"
echo "  重启服务:   docker compose -f ${COMPOSE_FILE} restart app"
echo ""
