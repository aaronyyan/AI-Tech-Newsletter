#!/usr/bin/env bash
# Cron wrapper: 先跑完整版，失败则降级精选版
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[wrapper] 尝试完整版..."
if python3 "$DIR/daily.py" 2>&1; then
    echo "[wrapper] 完整版成功"
    exit 0
fi

echo "[wrapper] 完整版失败，降级精选版..."
python3 "$DIR/daily.py" --essential 2>&1
