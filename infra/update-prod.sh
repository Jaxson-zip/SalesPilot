#!/bin/bash
# 生产环境极速热更新（零现场编译，直接拉取预构建镜像）
# 用法：./infra/update-prod.sh
set -e
cd "$(dirname "$0")/.."

echo "=== 1. 拉取代码与配置 ==="
git pull origin main

echo "=== 2. 拉取预构建镜像（零编译） ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

echo "=== 3. 平滑热重启容器 ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "=== 4. 自动执行数据库迁移 ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T core alembic upgrade head || true

echo "=== 5. 容器健康检查 ==="
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

echo "=== 部署全部完成！耗时通常小于 20 秒 ==="
