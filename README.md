# 运维智能化 RAG Agent 平台

> 面向运维场景的智能 RAG Agent，实现**感知 → 检索 → 分析 → 建议 → 可选执行**的全链路智能处置能力。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.2-orange.svg)](https://langchain.com)

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        服务层 (FastAPI)                          │
│   POST /ask  │  POST /alert  │  POST /agent/run  │  /metrics    │
└──────┬───────┴───────┬───────┴────────┬──────────┴─────────────┘
       │               │                │
┌──────▼──────┐  ┌─────▼──────┐  ┌─────▼──────────────────────┐
│  RAG Q&A    │  │  告警处置   │  │  LangGraph Agent           │
│  Chain      │  │  Handler   │  │  (kubectl/ES/Shell/PromQL) │
└──────┬──────┘  └─────┬──────┘  └─────┬──────────────────────┘
       │               │                │
┌──────▼───────────────▼────────────────▼────────────┐
│              检索层                                  │
│  Query Embedding → ChromaDB/Milvus → BGE Reranker  │
└──────────────────────┬─────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────┐
│              数据层                                  │
│  PDF/MD/TXT → Chunking → BGE Embedding → 向量库     │
└────────────────────────────────────────────────────┘
```

## 功能分阶段

| Phase | 功能 | 状态 |
|-------|------|------|
| Phase 1 | 基础 RAG 问答（PDF/MD/TXT 入库，三种切分策略，RAGAS 评估） | ✅ |
| Phase 2 | Prometheus Alertmanager Webhook，告警→检索→通知 | ✅ |
| Phase 3 | LangGraph Agent 工具调用（kubectl/ES/Shell），人工审批节点 | ✅ |
| Phase 4 | BGE Reranker，HyDE，LangSmith 全链路追踪，K8s Helm 部署 | ✅ |

## 快速启动

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少填写 ANTHROPIC_API_KEY 或 OPENAI_API_KEY
```

### 2. Docker Compose 一键启动

```bash
docker-compose up -d
```

服务地址：
- **API**: http://localhost:8000
- **Swagger 文档**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

### 3. 本地开发启动

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 核心接口

### 文档入库

```bash
curl -X POST http://localhost:8000/api/v1/documents/ingest \
  -F "file=@./knowledge_base/example_runbook.md" \
  -F "chunking_strategy=recursive" \
  -F "chunk_size=512"
```

### 知识库问答

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Pod CrashLoopBackOff 如何排查？", "top_k": 5}'
```

### Prometheus 告警接收

```bash
# 配置 Alertmanager Webhook 指向此接口
curl -X POST http://localhost:8000/api/v1/alert \
  -H "Content-Type: application/json" \
  -d @examples/alert_payload.json
```

### Agent 工具调用

```bash
curl -X POST http://localhost:8000/api/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"question": "查看 production 命名空间下所有 CrashLoopBackOff 的 Pod 并分析原因"}'
```

## 批量导入知识库

```bash
python scripts/ingest_docs.py --dir ./knowledge_base --strategy recursive
```

## RAGAS 评估

```bash
python scripts/evaluate.py \
  --dataset ./data/eval_dataset.json \
  --output ./data/ragas_report.json
```

## 运行测试

```bash
pytest tests/ -v --tb=short
```

## 技术栈

| 类别 | 技术 |
|------|------|
| 大模型 | Claude API (claude-opus-4-6) / OpenAI API |
| Agent 框架 | LangChain 0.2 · LangGraph |
| Embedding | BGE-large-zh-v1.5（本地） / text-embedding-ada-002 |
| 向量数据库 | ChromaDB（开发） → Milvus（生产） |
| Reranker | BGE-Reranker-v2-m3 |
| RAG 评估 | RAGAS |
| 可观测性 | LangSmith · Prometheus · Grafana |
| 监控接入 | Prometheus Alertmanager Webhook |
| 日志接入 | Elasticsearch |
| 服务封装 | FastAPI + uvicorn |
| 部署 | Docker · Kubernetes · Helm |
| 通知 | 钉钉 / 企业微信 Webhook |

## 项目结构

```
ops-rag-agent/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── core/                   # 配置、日志
│   ├── rag/                    # 文档加载、切分、Embedding、向量库、QA链
│   ├── agent/                  # LangGraph Agent、工具、审批节点
│   ├── alert/                  # Alertmanager 解析、处置、通知
│   ├── evaluation/             # RAGAS 评估
│   ├── models/                 # Pydantic 数据模型
│   └── api/routes/             # FastAPI 路由
├── tests/                      # 单元测试
├── scripts/                    # 批量入库、评估脚本
├── helm/                       # K8s Helm Chart（含 HPA）
├── config/                     # Prometheus、Grafana 配置
├── knowledge_base/             # 示例运维文档
├── Dockerfile
└── docker-compose.yml
```

## 简历描述参考

> 基于 LangChain + BGE + ChromaDB/Milvus 构建运维知识库 RAG 系统，对接 Prometheus Alertmanager Webhook 实现告警自动检索处置文档；集成 kubectl / Elasticsearch / Shell 工具调用能力，高危操作引入人工审批节点；用 RAGAS 框架评估 RAG 效果；整体服务基于 Docker + Kubernetes 部署，提供 Grafana 监控面板，Agent 决策链路通过 LangSmith 全程追踪。
