#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
docker compose -f "$ROOT/docker/docker-compose.submit.yml" down
echo "服务已停止；演示数据卷保留。"
