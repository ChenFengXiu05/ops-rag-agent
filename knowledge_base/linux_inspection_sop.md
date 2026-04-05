# Linux 服务器日常巡检 SOP

## 1. 概述

本文档规定 Linux 服务器日常运维巡检的标准操作流程，频率建议：
- **每日巡检**：核心业务系统
- **每周巡检**：全量服务器
- **每月巡检**：深度性能分析

---

## 2. 系统基本信息检查

```bash
# 查看系统版本
cat /etc/os-release
uname -a

# 查看系统运行时间和负载
uptime

# 查看登录用户
w
last | head -20
```

---

## 3. CPU 检查

```bash
# 实时 CPU 使用率（q 退出）
top -b -n 1 | head -20

# 更直观的展示
htop

# CPU 详细信息
lscpu

# 历史 CPU 使用率（需安装 sysstat）
sar -u 1 10
```

**告警阈值**：
- CPU 使用率 > 80% 持续 5 分钟 → 警告
- CPU 使用率 > 95% 持续 1 分钟 → 紧急

**高 CPU 排查**：
```bash
# 找出 CPU 占用最高的进程
ps aux --sort=-%cpu | head -10

# 查看进程详情
top -p <pid>

# 查看进程调用栈（需要 gdb）
strace -p <pid> -c
```

---

## 4. 内存检查

```bash
# 查看内存使用情况
free -h

# 详细内存信息
cat /proc/meminfo

# 占用内存最高的进程
ps aux --sort=-%mem | head -10
```

**告警阈值**：
- 内存使用率 > 85% → 警告
- Swap 使用 > 50% → 关注
- OOM killer 触发 → 紧急

**排查 OOM**：
```bash
# 查看 OOM 日志
dmesg | grep -i "out of memory"
grep -i "oom" /var/log/messages
```

---

## 5. 磁盘检查

```bash
# 磁盘空间使用
df -h

# 查找大文件（超过 1GB）
find / -type f -size +1G 2>/dev/null

# 查找大目录
du -sh /* 2>/dev/null | sort -rh | head -10

# 磁盘 I/O 统计
iostat -x 1 5

# 查看磁盘 inode 使用率
df -i
```

**告警阈值**：
- 磁盘使用率 > 80% → 警告
- 磁盘使用率 > 90% → 紧急
- Inode 使用率 > 80% → 警告

**磁盘清理常用命令**：
```bash
# 清理旧日志
journalctl --vacuum-time=7d
find /var/log -name "*.gz" -mtime +30 -delete

# Docker 清理
docker system prune -f
docker volume prune -f
```

---

## 6. 网络检查

```bash
# 查看网络连接状态
ss -tunlp
netstat -tunlp  # 旧版系统

# 查看网络接口状态
ip link show
ip addr show

# 网络流量监控
iftop -i eth0
nload eth0

# 连接数统计
ss -s

# 查看 TIME_WAIT 连接数
ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn
```

**告警阈值**：
- 带宽使用率 > 80% → 警告
- TIME_WAIT 连接数 > 10000 → 关注
- 丢包率 > 0.1% → 警告

---

## 7. 系统日志检查

```bash
# 查看系统错误日志
journalctl -p err -n 50

# 查看最近的系统日志
journalctl -n 100 --no-pager

# 查看 kernel 日志
dmesg -T | tail -50

# 查看认证日志（SSH 暴力破解等）
tail -100 /var/log/auth.log   # Debian/Ubuntu
tail -100 /var/log/secure      # CentOS/RHEL
```

**重点关注**：
- `kernel: EXT4-fs error` → 文件系统错误
- `Out of memory: Kill process` → OOM 事件
- `Failed password` 频繁出现 → 可能被暴力破解
- `segfault` → 程序异常崩溃

---

## 8. 进程和服务检查

```bash
# 查看所有 systemd 服务状态
systemctl list-units --type=service --state=failed

# 查看特定服务
systemctl status nginx
systemctl status docker
systemctl status kubelet

# 查看僵尸进程
ps aux | awk '$8=="Z" {print $2, $11}'
```

---

## 9. 安全检查

```bash
# 查看最近登录记录
last -n 20
lastb -n 20  # 失败的登录

# 查看计划任务
crontab -l
ls -la /etc/cron*

# 检查 SUID/SGID 文件（安全审计）
find / -type f \( -perm -4000 -o -perm -2000 \) 2>/dev/null

# 查看监听端口（与上次巡检对比）
ss -tlnp | grep LISTEN
```

---

## 10. 巡检报告模板

```
巡检日期：YYYY-MM-DD
巡检人员：XXX
服务器：hostname / IP

CPU：使用率 __% （正常/警告/异常）
内存：使用率 __% （正常/警告/异常）
磁盘：/ __% /data __% （正常/警告/异常）
网络：带宽 __Mbps （正常/警告/异常）

异常事项：
1.
2.

处理措施：
1.
2.

遗留问题：
```

---

## 11. 常见告警及处理

| 告警 | 原因 | 处理步骤 |
|------|------|----------|
| NodeMemoryUsageHigh | 内存不足 | 1. 找出占用进程 2. 重启或扩容 |
| NodeDiskUsageHigh | 磁盘空间不足 | 1. 清理日志/临时文件 2. 扩容磁盘 |
| NodeCPUUsageHigh | CPU 过载 | 1. 找出高CPU进程 2. 限制或迁移 |
| SystemdServiceFailed | 服务崩溃 | 1. `journalctl -u <service>` 2. 重启服务 |
