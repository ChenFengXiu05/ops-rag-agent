# 监控告警处理 SOP

## 1. 概述

本文档描述基于 Prometheus + Alertmanager + Grafana 的监控告警体系的日常运维操作，包括告警响应、故障处理和告警规则管理。

---

## 2. 告警级别定义

| 级别 | 颜色 | 响应时间 | 说明 |
|------|------|----------|------|
| P0（Critical） | 红色 | 立即（5分钟内） | 业务完全不可用，需要立即处理 |
| P1（High） | 橙色 | 15分钟内 | 核心功能受损，需要快速响应 |
| P2（Medium） | 黄色 | 1小时内 | 部分功能异常，需要关注 |
| P3（Low） | 蓝色 | 当天内 | 性能问题或预警，计划处理 |

---

## 3. 告警接收渠道

- **企业微信/钉钉**：P0/P1 告警实时推送
- **邮件**：所有告警汇总（每小时）
- **PagerDuty/OnCall**：P0 告警电话呼叫
- **Grafana Dashboard**：可视化大屏展示

---

## 4. 告警处理流程

```
告警触发
   ↓
值班人员接收告警（确认收到，回复"收到"）
   ↓
初步判断影响范围和严重程度
   ↓
登录相关系统进行排查
   ↓
确认根因
   ↓
执行修复操作
   ↓
验证业务恢复
   ↓
告警自动恢复 / 手动关闭
   ↓
编写故障复盘报告（P0/P1 必须）
```

---

## 5. Prometheus 常用查询

### 5.1 CPU 相关

```promql
# 节点 CPU 使用率
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# 进程 CPU 使用率
rate(process_cpu_seconds_total[5m]) * 100

# 容器 CPU 使用率
rate(container_cpu_usage_seconds_total{container!=""}[5m]) * 100
```

### 5.2 内存相关

```promql
# 节点内存使用率
(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100

# 容器内存使用
container_memory_working_set_bytes{container!=""}

# 容器内存使用率（相对于 limit）
container_memory_working_set_bytes / container_spec_memory_limit_bytes * 100
```

### 5.3 磁盘相关

```promql
# 磁盘使用率
(1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100

# 磁盘 IO 读写速率
rate(node_disk_read_bytes_total[5m])
rate(node_disk_written_bytes_total[5m])
```

### 5.4 网络相关

```promql
# 网络收发速率（字节/秒）
rate(node_network_receive_bytes_total{device!="lo"}[5m])
rate(node_network_transmit_bytes_total{device!="lo"}[5m])

# 网络错误包数
rate(node_network_receive_errs_total[5m])
```

### 5.5 Kubernetes 相关

```promql
# Pod 重启次数
increase(kube_pod_container_status_restarts_total[1h])

# 节点不可用数量
count(kube_node_status_condition{condition="Ready",status="true"} == 0)

# Deployment 不可用副本数
kube_deployment_status_replicas_unavailable > 0

# PVC 使用率
kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes * 100
```

---

## 6. 常见告警规则示例

```yaml
# prometheus/rules/node.yml
groups:
  - name: node.rules
    rules:
      - alert: NodeCPUUsageHigh
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Node CPU usage high"
          description: "Node {{ $labels.instance }} CPU usage is {{ $value }}%"

      - alert: NodeMemoryUsageHigh
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 > 85
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Node memory usage high"
          description: "Node {{ $labels.instance }} memory usage is {{ $value }}%"

      - alert: NodeDiskUsageHigh
        expr: (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Node disk usage high"
          description: "Node {{ $labels.instance }} disk usage is {{ $value }}%"

      - alert: NodeDown
        expr: up{job="node"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Node is down"
          description: "Node {{ $labels.instance }} has been down for more than 1 minute"
```

---

## 7. Alertmanager 配置

### 7.1 路由配置

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'namespace']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      repeat_interval: 1h
    - match:
        severity: warning
      receiver: 'warning-alerts'
      repeat_interval: 4h

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://ops-rag-agent:8000/api/v1/alert/webhook'

  - name: 'critical-alerts'
    webhook_configs:
      - url: 'http://ops-rag-agent:8000/api/v1/alert/webhook'
    wechat_configs:  # 企业微信
      - api_url: 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send'
        corp_id: 'your_corp_id'
        agent_id: 'your_agent_id'
        api_secret: 'your_api_secret'
```

---

## 8. 告警静默（Silence）操作

当进行计划内维护时，需要静默相关告警：

```bash
# 使用 amtool 创建静默
amtool silence add \
  --alertmanager.url http://alertmanager:9093 \
  alertname="NodeCPUUsageHigh" \
  instance="server01:9100" \
  --duration 2h \
  --comment "计划维护：升级内核，预计 2 小时"

# 查看所有静默
amtool silence query --alertmanager.url http://alertmanager:9093

# 删除静默
amtool silence expire <silence-id> --alertmanager.url http://alertmanager:9093
```

---

## 9. Grafana 使用

### 9.1 常用 Dashboard

| Dashboard | 用途 | ID |
|-----------|------|-----|
| Node Exporter Full | 服务器详情 | 1860 |
| Kubernetes Cluster | K8s 集群概览 | 7249 |
| MySQL Overview | MySQL 监控 | 7362 |
| Nginx | Nginx 状态 | 9614 |

### 9.2 告警联系人配置

```
Grafana → Alerting → Contact Points → Add Contact Point
选择类型：企业微信 Webhook / 钉钉 Webhook
输入 Webhook URL
测试发送
```

---

## 10. 告警处理记录模板

```
【告警信息】
告警名：
触发时间：
影响范围：
告警内容：

【初步判断】
可能原因：
影响评估：

【排查过程】
1.
2.

【根本原因】

【修复操作】
1.
2.

【恢复时间】

【总结与预防】
```

---

## 11. 常见告警处理速查

| 告警名 | 处理步骤 |
|--------|----------|
| NodeCPUUsageHigh | 1. `ps aux --sort=-%cpu` 找高CPU进程 2. 是否需要扩容/限速 |
| NodeMemoryUsageHigh | 1. `ps aux --sort=-%mem` 2. 检查内存泄漏 3. 考虑扩容 |
| NodeDiskUsageHigh | 1. `du -sh /* sort -rh` 2. 清理日志/临时文件 3. 扩容 |
| KubePodCrashLooping | 1. `kubectl logs --previous` 2. 检查 OOM 或配置错误 |
| KubeDeploymentNotAvailable | 1. `kubectl describe deployment` 2. 检查镜像/资源/依赖 |
| ProbeHTTPFailure | 1. 测试端口 `curl -v url` 2. 检查防火墙 3. 重启服务 |
| SSLCertExpiringSoon | 1. 联系证书管理员 2. `certbot renew` 3. 重载 Nginx |
