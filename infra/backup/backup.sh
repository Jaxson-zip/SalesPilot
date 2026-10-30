#!/usr/bin/env sh
# 备份数据库和上传的附件（票据、样例图片）。在仓库根目录或任意位置运行均可：
#   infra/backup/backup.sh [备份目录，默认 ./backups]
# 环境变量：KEEP_DAYS 保留天数（默认 14）；COMPOSE 编排命令（默认按正式部署叠加 docker-compose.prod.yml）
# 定时：crontab -e 加一行  30 3 * * * cd /srv/salespilot && infra/backup/backup.sh >> backups/backup.log 2>&1
# 备份文件只在本机，硬盘坏了会一起丢：请再同步一份到对象存储或另一台机器（见 docs/上线部署指南.md）
set -eu
export MSYS_NO_PATHCONV=1  # Windows Git Bash 下不要把容器内路径（/data）改写成本机路径
cd "$(dirname "$0")/../.."
DIR=${1:-backups}
KEEP_DAYS=${KEEP_DAYS:-14}
COMPOSE=${COMPOSE:-docker compose -f docker-compose.yml -f docker-compose.prod.yml}
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$DIR"

# 先写 .part，成功后再改名：中途失败不会留下看起来完整的坏备份
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DIR/db-$STAMP.dump.part"
mv "$DIR/db-$STAMP.dump.part" "$DIR/db-$STAMP.dump"
$COMPOSE exec -T core tar czf - -C /data uploads > "$DIR/uploads-$STAMP.tar.gz.part"
mv "$DIR/uploads-$STAMP.tar.gz.part" "$DIR/uploads-$STAMP.tar.gz"

find "$DIR" -maxdepth 1 \( -name 'db-*.dump' -o -name 'uploads-*.tar.gz' \) -mtime +"$KEEP_DAYS" -delete
echo "$(date '+%F %T') 备份完成：$DIR/db-$STAMP.dump、$DIR/uploads-$STAMP.tar.gz"
