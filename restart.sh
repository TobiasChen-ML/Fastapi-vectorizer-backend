#!/usr/bin/env bash
# restart.sh : 杀掉老 gunicorn → 清 Redis → 启动新 gunicorn

set -euo pipefail

echo "1. 查找并杀掉旧 gunicorn 进程 ..."
# 过滤掉 grep 自身，避免误杀
old_pids=$(ps -ef | awk '/gunicorn/ && !/awk/{print $2}')
if [[ -n "$old_pids" ]]; then
  echo "   将杀掉 PID: $old_pids"
  kill -9 $old_pids
  sleep 1
fi

echo "2. 清空 Redis ..."
# 如果 Redis 设了密码，改成  redis-cli -a YOURPASSWORD FLUSHALL
redis-cli FLUSHALL

echo "3. 启动新 gunicorn ..."
# 这里用 exec 让 gunicorn 成为 1 号进程，方便 Docker 或 systemd 管理
exec gunicorn main:app -c gunicorn.py