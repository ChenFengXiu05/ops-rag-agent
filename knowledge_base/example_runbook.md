# Pod CrashLoopBackOff 处置 Runbook

## 触发条件
Pod 状态持续显示 `CrashLoopBackOff`，表明容器启动后立即崩溃并反复重启。

## 排查步骤

### Step 1: 查看 Pod 状态
```bash
kubectl get pods -n <namespace>
kubectl describe pod <pod-name> -n <namespace>
```
重点关注 `Events` 部分，查看最后一次容器退出原因。

### Step 2: 查看容器日志
```bash
# 查看当前日志
kubectl logs <pod-name> -n <namespace>

# 查看上一次崩溃的日志（关键！）
kubectl logs <pod-name> -n <namespace> --previous
```

### Step 3: 常见原因及处理

| 原因 | 特征 | 处置 |
|------|------|------|
| OOMKilled | Exit Code 137 | 调高 memory limit |
| 配置错误 | Exit Code 1, ConfigMap/Secret 缺失 | 检查环境变量和挂载 |
| 探针失败 | Liveness probe failed | 调整 initialDelaySeconds |
| 镜像问题 | ImagePullBackOff → CrashLoop | 验证镜像和 tag |
| 权限问题 | Permission denied | 检查 SecurityContext / RBAC |

### Step 4: 修复并验证
```bash
# 修改 Deployment 配置后
kubectl rollout status deployment/<name> -n <namespace>
kubectl get pods -n <namespace> -w
```

## 预防措施
1. 配置合理的资源 limits（CPU/Memory）
2. 设置 `startupProbe` 给应用足够的启动时间
3. 使用 `readinessProbe` 避免流量打到未就绪 Pod

---

# Node NotReady 处置 SOP

## 触发条件
Prometheus 告警 `NodeNotReady`，或 `kubectl get nodes` 显示节点状态为 `NotReady`。

## 排查步骤

### Step 1: 确认节点状态
```bash
kubectl get nodes
kubectl describe node <node-name>
```

### Step 2: 检查 kubelet
```bash
# 在节点上执行
systemctl status kubelet
journalctl -u kubelet -n 100 --no-pager
```

### Step 3: 检查网络插件
```bash
kubectl get pods -n kube-system | grep -E "calico|flannel|cilium|weave"
kubectl logs -n kube-system <network-plugin-pod>
```

### Step 4: 检查节点资源
```bash
# 磁盘空间
df -h
# 内存
free -m
# inode 使用
df -i
```

### Step 5: 常见修复

| 问题 | 修复方法 |
|------|---------|
| kubelet 停止 | `systemctl restart kubelet` |
| 磁盘满 | 清理 /var/log, docker images |
| 时钟偏差 | `ntpdate -u pool.ntp.org` |
| 网络插件异常 | 重启网络插件 Pod |

### Step 6: 驱逐节点（必要时）
```bash
# 驱逐节点上的 Pod（需要人工审批）
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
# 修复后重新加入
kubectl uncordon <node-name>
```

## 告警规则参考
```yaml
- alert: NodeNotReady
  expr: kube_node_status_condition{condition="Ready",status="true"} == 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Node {{ $labels.node }} is not ready"
```
