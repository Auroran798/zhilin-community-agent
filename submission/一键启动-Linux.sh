#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="$ROOT/docker/docker-compose.submit.yml"
IMAGE_TAR="$ROOT/docker/zhilin-beijing-amd64.tar"
IMAGE="zhilin-beijing:2026.08.11-amd64"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-8501}"
export API_PORT WEB_PORT

command -v docker >/dev/null 2>&1 || { echo "启动失败：未检测到 Docker。" >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "启动失败：Docker 引擎未运行。" >&2; exit 1; }
[[ -f "$COMPOSE" ]] || { echo "启动失败：缺少 $COMPOSE" >&2; exit 1; }
[[ -f "$IMAGE_TAR" ]] || { echo "启动失败：缺少 $IMAGE_TAR" >&2; exit 1; }

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "正在导入离线镜像（通常需要 1—5 分钟）..."
  docker load --input "$IMAGE_TAR"
fi

echo "正在启动智邻管家；首次启动会创建演示数据库并导入受控知识库..."
docker compose -f "$COMPOSE" up -d --remove-orphans

deadline=$((SECONDS + 600))
until curl --fail --silent "http://127.0.0.1:${API_PORT}/ready" >/dev/null; do
  if (( SECONDS >= deadline )); then
    docker compose -f "$COMPOSE" logs --tail 120 api
    echo "启动失败：API 在 10 分钟内未就绪。" >&2
    exit 1
  fi
  sleep 3
done
web_deadline=$((SECONDS + 120))
until curl --fail --silent "http://127.0.0.1:${WEB_PORT}/_stcore/health" >/dev/null; do
  if (( SECONDS >= web_deadline )); then
    docker compose -f "$COMPOSE" logs --tail 80 web
    echo "启动失败：Web 页面在 2 分钟内未就绪。" >&2
    exit 1
  fi
  sleep 2
done

echo "启动成功："
echo "  智能体页面：http://127.0.0.1:${WEB_PORT}"
echo "  API 文档：  http://127.0.0.1:${API_PORT}/docs"
echo "  演示账户密码：DemoPass123!"
