#!/bin/sh
set -eu

# Docker/Linux 环境始终从脚本所在的项目根目录启动。
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_ROOT"

# 镜像可以通过 PYTHON_BIN 覆盖解释器，默认使用 PATH 中的 python。
PYTHON_BIN=${PYTHON_BIN:-python}
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "[错误] 找不到 Python 解释器: $PYTHON_BIN" >&2
    exit 1
fi

# 传入参数时允许 Docker ENTRYPOINT 执行显式命令；无参数时启动服务。
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec "$PYTHON_BIN" main.py
