# MySQL 数据库备份与恢复 SOP

## 1. 概述

本文档描述 MySQL 数据库的备份策略、操作步骤和恢复流程，确保数据安全性和业务连续性。

**备份策略**：
- 全量备份：每天凌晨 2:00
- 增量备份（binlog）：实时
- 备份保留：本地 7 天，远端（OSS/NFS）30 天

---

## 2. 备份工具选择

| 工具 | 适用场景 | 特点 |
|------|----------|------|
| mysqldump | 小型数据库（< 10GB）| 逻辑备份，兼容性好 |
| xtrabackup | 中大型数据库 | 物理热备，速度快 |
| mysqlpump | 并行逻辑备份 | MySQL 5.7+ 推荐 |
| binlog backup | 增量备份 | 配合全量使用 |

---

## 3. mysqldump 备份

### 3.1 全量备份

```bash
#!/bin/bash
# /opt/scripts/mysql_full_backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/data/backup/mysql"
MYSQL_USER="backup_user"
MYSQL_PASS="your_password"
MYSQL_HOST="127.0.0.1"

mkdir -p ${BACKUP_DIR}

# 全量备份所有数据库
mysqldump \
  -h${MYSQL_HOST} \
  -u${MYSQL_USER} \
  -p${MYSQL_PASS} \
  --all-databases \
  --single-transaction \
  --flush-logs \
  --master-data=2 \
  --routines \
  --triggers \
  --events \
  | gzip > ${BACKUP_DIR}/full_${DATE}.sql.gz

echo "Backup completed: full_${DATE}.sql.gz"

# 删除 7 天前的备份
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +7 -delete
```

### 3.2 单库备份

```bash
mysqldump -h127.0.0.1 -uroot -p \
  --single-transaction \
  --databases mydb \
  | gzip > /data/backup/mydb_$(date +%Y%m%d).sql.gz
```

### 3.3 备份验证

```bash
# 检查备份文件完整性
gzip -t /data/backup/mysql/full_20240101_020000.sql.gz
echo $?  # 0 表示正常

# 查看备份大小
ls -lh /data/backup/mysql/
```

---

## 4. XtraBackup 备份（推荐大型数据库）

### 4.1 安装

```bash
# CentOS/RHEL
yum install percona-xtrabackup-80

# Ubuntu/Debian
apt-get install percona-xtrabackup-80
```

### 4.2 全量备份

```bash
xtrabackup --backup \
  --user=backup_user \
  --password=your_password \
  --target-dir=/data/backup/xtrabackup/full \
  --parallel=4

# 准备备份（使日志一致）
xtrabackup --prepare --target-dir=/data/backup/xtrabackup/full
```

### 4.3 增量备份

```bash
# 基于全量的增量备份
xtrabackup --backup \
  --user=backup_user \
  --password=your_password \
  --target-dir=/data/backup/xtrabackup/inc1 \
  --incremental-basedir=/data/backup/xtrabackup/full
```

---

## 5. Binlog 备份配置

### 5.1 开启 Binlog

在 `/etc/mysql/mysql.conf.d/mysqld.cnf` 或 `/etc/my.cnf` 中：

```ini
[mysqld]
log_bin = /var/log/mysql/mysql-bin.log
binlog_format = ROW
expire_logs_days = 7
max_binlog_size = 500M
server_id = 1
```

重启 MySQL：
```bash
systemctl restart mysql
```

### 5.2 验证 Binlog 状态

```sql
SHOW VARIABLES LIKE 'log_bin';
SHOW BINARY LOGS;
SHOW MASTER STATUS;
```

---

## 6. 数据恢复

### 6.1 从 mysqldump 恢复

```bash
# 解压
gunzip -c /data/backup/mysql/full_20240101_020000.sql.gz > /tmp/full_backup.sql

# 恢复所有数据库（谨慎！会覆盖现有数据）
mysql -uroot -p < /tmp/full_backup.sql

# 恢复单个数据库
mysql -uroot -p mydb < /tmp/mydb_20240101.sql
```

### 6.2 从 XtraBackup 恢复

```bash
# 停止 MySQL
systemctl stop mysql

# 清空数据目录（谨慎！）
rm -rf /var/lib/mysql/*

# 恢复数据
xtrabackup --copy-back --target-dir=/data/backup/xtrabackup/full

# 修复权限
chown -R mysql:mysql /var/lib/mysql

# 启动 MySQL
systemctl start mysql
```

### 6.3 基于时间点恢复（PITR）

用于恢复到某个时间点，配合全量备份 + binlog：

```bash
# 1. 先恢复最近的全量备份
mysql -uroot -p < full_backup.sql

# 2. 找到误操作时间点
mysqlbinlog --start-datetime="2024-01-01 10:00:00" \
            --stop-datetime="2024-01-01 10:30:00" \
            /var/log/mysql/mysql-bin.000001 > /tmp/binlog_recovery.sql

# 3. 应用 binlog（跳过误操作的 SQL）
mysql -uroot -p < /tmp/binlog_recovery.sql
```

---

## 7. 自动化备份计划

### 7.1 配置 cron

```bash
crontab -e

# 每天凌晨 2:00 执行全量备份
0 2 * * * /opt/scripts/mysql_full_backup.sh >> /var/log/mysql_backup.log 2>&1

# 每小时备份 binlog
0 * * * * /opt/scripts/mysql_binlog_backup.sh >> /var/log/mysql_binlog_backup.log 2>&1
```

### 7.2 备份上传到对象存储

```bash
# 使用 ossutil（阿里云 OSS）
ossutil cp /data/backup/mysql/ oss://my-bucket/mysql-backup/ -r

# 使用 aws cli（AWS S3）
aws s3 sync /data/backup/mysql/ s3://my-bucket/mysql-backup/
```

---

## 8. 备份监控告警

**需要监控的指标**：
- 备份文件是否在预期时间内生成
- 备份文件大小是否异常（过小可能表示备份失败）
- 备份磁盘空间使用率

**告警脚本示例**：
```bash
#!/bin/bash
BACKUP_FILE="/data/backup/mysql/full_$(date +%Y%m%d)_*.sql.gz"
if ls ${BACKUP_FILE} 1>/dev/null 2>&1; then
    echo "Backup OK"
else
    # 发送告警（邮件/企微/钉钉）
    echo "ALERT: MySQL backup failed for $(date +%Y%m%d)" | mail -s "MySQL Backup Alert" ops@company.com
fi
```

---

## 9. 常见问题处理

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| Lock wait timeout | 备份时锁表超时 | 使用 `--single-transaction`，或在低峰期备份 |
| Disk full during backup | 磁盘空间不足 | 清理旧备份，或挂载更大的备份盘 |
| mysqldump: Got error: 1449 | 触发器引用了不存在的用户 | 先修复触发器定义，或加 `--skip-triggers` |
| Replication broken after restore | binlog position 不一致 | 恢复时使用 `--master-data=2` 记录 position |
