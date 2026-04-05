# Kubernetes Pod 故障排查 SOP

## 1. 概述

本文档描述 Kubernetes Pod 常见故障的标准排查流程，适用于运维团队日常使用。

---

## 2. Pod 状态说明

| 状态 | 含义 |
|------|------|
| Pending | Pod 已创建但尚未调度到节点，或正在拉取镜像 |
| Running | Pod 已调度并成功启动 |
| CrashLoopBackOff | 容器反复崩溃重启 |
| OOMKilled | 容器因内存超限被系统杀死 |
| ImagePullBackOff | 镜像拉取失败 |
| Evicted | Pod 因资源压力被驱逐 |
| Terminating | Pod 正在终止，长时间停留表示有 finalizer 未清除 |

---

## 3. 排查步骤

### 3.1 查看 Pod 状态

```bash
kubectl get pods -n <namespace>
kubectl get pods -n <namespace> -o wide   # 显示节点信息
```

### 3.2 查看 Pod 详情（Events）

```bash
kubectl describe pod <pod-name> -n <namespace>
```

重点关注：
- `Events` 部分，查看调度失败、镜像拉取失败等原因
- `Conditions` 中 Ready/ContainersReady 是否为 True

### 3.3 查看容器日志

```bash
# 查看当前日志
kubectl logs <pod-name> -n <namespace>

# 查看上一次崩溃的日志
kubectl logs <pod-name> -n <namespace> --previous

# 实时跟踪日志
kubectl logs -f <pod-name> -n <namespace>

# 多容器 Pod 指定容器
kubectl logs <pod-name> -c <container-name> -n <namespace>
```

### 3.4 进入容器排查

```bash
kubectl exec -it <pod-name> -n <namespace> -- /bin/bash
# 若没有 bash
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh
```

---

## 4. 常见故障处理

### 4.1 CrashLoopBackOff

**原因**：应用启动失败、配置错误、依赖服务不可达

**排查**：
```bash
kubectl logs <pod-name> -n <namespace> --previous
kubectl describe pod <pod-name> -n <namespace>
```

**处理**：
1. 查看退出码（Exit Code）：
   - `1`：应用程序错误
   - `137`：OOM 或被 kill -9
   - `143`：收到 SIGTERM 后超时
2. 检查 ConfigMap/Secret 是否正确挂载
3. 检查依赖服务（数据库、缓存）是否可达

### 4.2 ImagePullBackOff

**原因**：镜像不存在、仓库认证失败、网络问题

**排查**：
```bash
kubectl describe pod <pod-name> -n <namespace>
# 查看 Events 中的 Failed to pull image
```

**处理**：
1. 检查镜像名称和 tag 是否正确
2. 检查 imagePullSecrets 是否配置：
```bash
kubectl get secret -n <namespace>
kubectl get pod <pod-name> -n <namespace> -o yaml | grep imagePullSecrets
```
3. 手动在节点上测试拉取：`docker pull <image-name>`

### 4.3 OOMKilled

**原因**：容器内存使用超过 limit 限制

**排查**：
```bash
kubectl describe pod <pod-name> -n <namespace>
# 查看 Last State: OOMKilled
kubectl top pod <pod-name> -n <namespace>
```

**处理**：
1. 适当调大内存 limit：
```yaml
resources:
  limits:
    memory: "1Gi"  # 调整为合适的值
  requests:
    memory: "512Mi"
```
2. 分析应用内存泄漏问题
3. 考虑使用 VPA（Vertical Pod Autoscaler）

### 4.4 Pending（调度失败）

**原因**：资源不足、节点选择器不匹配、污点/容忍配置错误

**排查**：
```bash
kubectl describe pod <pod-name> -n <namespace>
# 查看 Events: 0/3 nodes are available
```

**处理**：
```bash
# 查看节点资源
kubectl describe nodes | grep -A 5 "Allocated resources"

# 查看节点标签
kubectl get nodes --show-labels

# 检查是否有 taints
kubectl describe node <node-name> | grep Taint
```

### 4.5 Terminating 卡住

**原因**：Pod 有 finalizer 未清除，或 preStop hook 超时

**处理**：
```bash
# 强制删除（谨慎使用）
kubectl delete pod <pod-name> -n <namespace> --force --grace-period=0

# 清除 finalizer
kubectl patch pod <pod-name> -n <namespace> -p '{"metadata":{"finalizers":null}}'
```

---

## 5. 节点问题排查

```bash
# 查看节点状态
kubectl get nodes

# 查看节点详情
kubectl describe node <node-name>

# 查看节点上的所有 Pod
kubectl get pods --all-namespaces -o wide --field-selector spec.nodeName=<node-name>
```

---

## 6. 告警处理参考

| 告警名 | 处理步骤 |
|--------|----------|
| KubePodCrashLooping | 1. `kubectl logs --previous` 2. 检查配置 3. 重启 Pod |
| KubePodNotReady | 1. `kubectl describe pod` 2. 检查 readinessProbe 配置 |
| KubeNodeNotReady | 1. SSH 登录节点 2. 检查 kubelet 状态 3. 重启 kubelet |
| KubeMemoryOvercommit | 1. 降低 Pod memory request 2. 扩容节点 |

---

## 7. 快速命令速查

```bash
# 重启 Deployment
kubectl rollout restart deployment/<deploy-name> -n <namespace>

# 查看回滚历史
kubectl rollout history deployment/<deploy-name> -n <namespace>

# 回滚到上一版本
kubectl rollout undo deployment/<deploy-name> -n <namespace>

# 扩缩容
kubectl scale deployment/<deploy-name> --replicas=3 -n <namespace>
```
