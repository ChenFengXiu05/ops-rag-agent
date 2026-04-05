# Nginx 故障排查 SOP

## 1. 概述

本文档描述 Nginx 常见故障的排查流程和解决方案，适用于 Web 服务器、反向代理、负载均衡等场景。

---

## 2. 快速诊断

```bash
# 检查 Nginx 进程状态
systemctl status nginx
ps aux | grep nginx

# 检查配置语法
nginx -t

# 查看 Nginx 版本和编译参数
nginx -V

# 查看监听端口
ss -tlnp | grep nginx
```

---

## 3. 日志分析

### 3.1 日志文件位置

```bash
# 默认日志路径
/var/log/nginx/access.log   # 访问日志
/var/log/nginx/error.log    # 错误日志

# 自定义路径查看
grep -r "access_log\|error_log" /etc/nginx/
```

### 3.2 实时查看日志

```bash
# 实时错误日志
tail -f /var/log/nginx/error.log

# 实时访问日志
tail -f /var/log/nginx/access.log

# 过滤 5xx 错误
tail -f /var/log/nginx/access.log | grep '" 5'
```

### 3.3 访问日志分析

```bash
# 统计 HTTP 状态码
awk '{print $9}' /var/log/nginx/access.log | sort | uniq -c | sort -rn

# TOP 10 访问 IP
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -rn | head -10

# TOP 10 慢请求（需要日志格式包含 $request_time）
awk '{print $NF, $7}' /var/log/nginx/access.log | sort -rn | head -10

# 统计每分钟请求数（流量分析）
awk '{print $4}' /var/log/nginx/access.log | cut -c 1-17 | sort | uniq -c
```

---

## 4. 常见故障排查

### 4.1 502 Bad Gateway

**原因**：后端服务不可达或响应超时

**排查步骤**：
```bash
# 1. 查看错误日志
tail -100 /var/log/nginx/error.log | grep "502\|connect() failed\|upstream"

# 2. 测试后端服务是否正常
curl -v http://127.0.0.1:8080/health   # 替换为实际后端地址

# 3. 检查上游配置
cat /etc/nginx/sites-enabled/*.conf | grep -A 5 "upstream\|proxy_pass"

# 4. 检查 upstream 服务器
nginx -T | grep "server " | grep -v "#"
```

**常见错误日志**：
```
connect() failed (111: Connection refused)   → 后端服务未启动
connect() failed (110: Connection timed out) → 防火墙或网络问题
upstream prematurely closed connection       → 后端服务崩溃
```

**解决方案**：
```bash
# 重启后端服务
systemctl restart app-service

# 增加超时时间（nginx.conf）
proxy_connect_timeout 60s;
proxy_send_timeout 60s;
proxy_read_timeout 60s;
```

### 4.2 504 Gateway Timeout

**原因**：后端响应时间超过 Nginx 等待时间

**排查**：
```bash
# 查看当前超时配置
nginx -T | grep "timeout"

# 测试后端响应时间
time curl http://127.0.0.1:8080/slow-endpoint
```

**解决方案**：
```nginx
# 增加超时时间
proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

### 4.3 403 Forbidden

**原因**：权限问题或访问被拒绝

**排查**：
```bash
# 查看错误日志
grep "403\|Permission denied\|access forbidden" /var/log/nginx/error.log

# 检查文件权限
ls -la /var/www/html/
namei -l /var/www/html/index.html

# 检查 nginx 进程用户
ps aux | grep "nginx: worker"
```

**常见原因及修复**：
```bash
# 文件权限不对
chmod 644 /var/www/html/index.html
chown www-data:www-data /var/www/html/ -R

# SELinux 问题（CentOS）
chcon -R -t httpd_sys_content_t /var/www/html/
# 或临时关闭 SELinux
setenforce 0
```

### 4.4 404 Not Found

**排查**：
```bash
# 检查 root 目录是否正确
nginx -T | grep -A 5 "server_name\|root"

# 验证文件是否存在
ls -la /var/www/html/missing-file.html

# 检查 try_files 配置
grep -r "try_files" /etc/nginx/
```

### 4.5 Nginx 无法启动

**排查**：
```bash
# 检查配置语法错误
nginx -t

# 查看启动错误日志
journalctl -u nginx -n 50
cat /var/log/nginx/error.log | head -20

# 检查端口占用
ss -tlnp | grep ':80\|:443'
fuser 80/tcp
fuser 443/tcp
```

**常见原因**：
```bash
# 端口已被占用
kill -9 $(fuser 80/tcp)
# 或找出占用的进程
lsof -i :80

# 配置文件语法错误
nginx -t 2>&1   # 查看具体错误位置
```

### 4.6 SSL/HTTPS 故障

```bash
# 测试 SSL 连接
openssl s_client -connect yourdomain.com:443

# 检查证书有效期
echo | openssl s_client -connect yourdomain.com:443 2>/dev/null | openssl x509 -noout -dates

# 检查证书链完整性
openssl verify -CAfile /path/to/ca.crt /path/to/server.crt

# 查看 Nginx SSL 配置
nginx -T | grep -A 10 "ssl_certificate"
```

---

## 5. 性能调优

### 5.1 连接数相关

```bash
# 查看当前连接状态（需要 stub_status 模块）
curl http://localhost/nginx_status

# 查看系统连接数
ss -s
```

**配置优化**：
```nginx
worker_processes auto;           # 与 CPU 核数一致
worker_connections 10240;        # 每个 worker 最大连接数

# keepalive
keepalive_timeout 65;
keepalive_requests 1000;

# 上游 keepalive
upstream backend {
    server 127.0.0.1:8080;
    keepalive 32;                # 保持长连接数
}
```

### 5.2 缓冲区调优

```nginx
proxy_buffer_size 4k;
proxy_buffers 8 4k;
proxy_busy_buffers_size 8k;

client_body_buffer_size 10K;
client_header_buffer_size 1k;
client_max_body_size 8m;
```

---

## 6. 常用操作命令

```bash
# 重新加载配置（不中断连接）
nginx -s reload
systemctl reload nginx

# 优雅关闭
nginx -s quit

# 强制关闭
nginx -s stop

# 重新打开日志文件（日志切割后需要）
nginx -s reopen
```

---

## 7. 告警处理参考

| 告警 | 含义 | 处理步骤 |
|------|------|----------|
| NginxHighErrorRate | 5xx 错误率高 | 1. 查看错误日志 2. 检查后端服务健康状态 |
| NginxHighLatency | 响应延迟高 | 1. 检查后端服务性能 2. 增加超时配置 |
| NginxDown | Nginx 进程不存在 | 1. `systemctl start nginx` 2. 查看启动失败原因 |
| NginxCertExpiringSoon | SSL 证书即将过期 | 1. 更新 SSL 证书 2. 执行 `certbot renew` |
