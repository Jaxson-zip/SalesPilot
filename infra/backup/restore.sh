#!/usr/bin/env sh
# 从备份恢复（会覆盖当前数据库和附件，先停 core / web，恢复完再启动）：
#   CONFIRM=yes infra/backup/restore.sh backups/db-20261030-033000.dump [backups/uploads-20261030-033000.tar.gz]
# 环境变量 COMPOSE 同 backup.sh
set -eu
export MSYS_NO_PATHCONV=1  # Windows Git Bash 下不要把容器内路径（/data）改写成本机路径
cd "$(dirname "$0")/../.."
DUMP=${1:?用法：CONFIRM=yes infra/backup/restore.sh <db-*.dump> [uploads-*.tar.gz]}
UPLOADS=${2:-}
COMPOSE=${COMPOSE:-docker compose -f docker-compose.yml -f docker-compose.prod.yml}
if [ "${CONFIRM:-}" != "yes" ]; then
  echo "将用 $DUMP 覆盖当前数据库${UPLOADS:+，用 $UPLOADS 覆盖附件}。确认无误后加 CONFIRM=yes 再运行。"
  exit 1
fi

$COMPOSE stop core web
$COMPOSE exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < "$DUMP"
if [ -n "$UPLOADS" ]; then
  $COMPOSE run --rm --no-deps -T core sh -c 'rm -rf /data/uploads/* && tar xzf - -C /data' < "$UPLOADS"
fi
$COMPOSE start core web
echo "恢复完成：$DUMP${UPLOADS:+、$UPLOADS}"
